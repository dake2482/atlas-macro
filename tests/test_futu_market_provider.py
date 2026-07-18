"""Deterministic tests for the Futu OpenD market-data provider and persistence.

The Futu SDK transport is mocked so these tests never depend on a running
OpenD gateway or network.  They cover the broker-private provenance contract:
every observation is marked ``estimated``, carries the Futu attribution and a
``broker_private`` flag, and the source row is licensed but non-redistributable.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
import pytest

from research.models import Instrument, Observation, Source
from research.providers import FutuProvider, ProviderResult
from research.services import store_futu_snapshots


def _snapshot_frame(rows: list[dict]) -> pd.DataFrame:
    columns = [
        "code",
        "name",
        "update_time",
        "last_price",
        "prev_close_price",
        "open_price",
        "high_price",
        "low_price",
        "volume",
        "turnover",
        "pe_ratio",
        "pb_ratio",
        "total_market_val",
    ]
    return pd.DataFrame([{col: row.get(col) for col in columns} for row in rows])


def test_futu_provider_returns_normalized_snapshots_with_provenance():
    provider = FutuProvider(host="127.0.0.1", port=11111)
    frame = _snapshot_frame(
        [
            {
                "code": "US.SPY",
                "name": "标普500ETF-SPDR",
                "update_time": "2026-07-17 20:01:12.982",
                "last_price": 743.29,
                "prev_close_price": 750.72,
                "open_price": 742.08,
                "high_price": 747.29,
                "low_price": 740.8,
                "volume": 62650961.0,
                "turnover": 46653108204.0,
                "pe_ratio": None,
                "pb_ratio": None,
                "total_market_val": None,
            }
        ]
    )
    with patch.object(provider, "_open_context") as mock_open:
        mock_open.return_value.get_market_snapshot.return_value = (0, frame)
        result = provider.market_snapshots(["US.SPY"])
    provider.close()

    assert result.ok
    assert len(result.records) == 1
    record = result.records[0]
    assert record["symbol"] == "US.SPY"
    assert record["name"] == "标普500ETF-SPDR"
    assert record["last_price"] == "743.29"
    assert record["prev_close"] == Decimal("750.72")
    assert result.metadata["attribution"] == "Futu OpenD"
    assert "券商私有行情" in result.metadata["license_scope"]
    assert result.metadata["opend_host"] == "127.0.0.1"
    assert result.metadata["opend_port"] == 11111


def test_futu_provider_skips_rows_with_missing_price():
    provider = FutuProvider()
    frame = _snapshot_frame(
        [
            {
                "code": "US.SPY",
                "name": "SPY",
                "update_time": "2026-07-17 20:01:12",
                "last_price": 743.29,
            },
            {"code": "US.BAD", "name": "Bad", "update_time": "", "last_price": None},
            {"code": "", "name": "Empty", "update_time": "", "last_price": 10},
        ]
    )
    with patch.object(provider, "_open_context") as mock_open:
        mock_open.return_value.get_market_snapshot.return_value = (0, frame)
        result = provider.market_snapshots(["US.SPY", "US.BAD"])
    provider.close()

    assert result.ok
    assert [r["symbol"] for r in result.records] == ["US.SPY"]


def test_futu_provider_failure_when_opend_returns_error():
    provider = FutuProvider()
    with patch.object(provider, "_open_context") as mock_open:
        mock_open.return_value.get_market_snapshot.return_value = (-1, "connection refused")
        result = provider.market_snapshots(["US.SPY"])
    provider.close()

    assert not result.ok
    assert "error" in result.error.lower()


def test_futu_provider_failure_on_sdk_exception():
    provider = FutuProvider()
    with patch.object(
        provider,
        "_open_context",
        side_effect=ConnectionError("OpenD not reachable"),
    ):
        result = provider.market_snapshots(["US.SPY"])
    provider.close()

    assert not result.ok
    assert "ConnectionError" in result.error


def test_futu_provider_failure_when_no_usable_rows():
    provider = FutuProvider()
    frame = _snapshot_frame([{"code": "US.X", "last_price": None}])
    with patch.object(provider, "_open_context") as mock_open:
        mock_open.return_value.get_market_snapshot.return_value = (0, frame)
        result = provider.market_snapshots(["US.X"])
    provider.close()

    assert not result.ok
    assert "no usable snapshots" in result.error


@pytest.mark.django_db
def test_store_futu_snapshots_creates_estimated_instrument_observations():
    source = Source.objects.create(key="futu", name="Futu OpenD 行情")
    result = ProviderResult(
        provider="futu",
        dataset="market-snapshots:US.SPY,US.AAPL",
        records=[
            {
                "symbol": "US.SPY",
                "name": "标普500ETF-SPDR",
                "last_price": "743.29",
                "prev_close": Decimal("750.72"),
                "open": Decimal("742.08"),
                "high": Decimal("747.29"),
                "low": Decimal("740.80"),
                "volume": Decimal("62650961"),
                "pe_ratio": None,
                "pb_ratio": None,
                "market_cap": None,
                "update_time": "2026-07-17 20:01:12",
            },
            {
                "symbol": "US.AAPL",
                "name": "苹果",
                "last_price": "333.74",
                "prev_close": Decimal("330.00"),
                "open": None,
                "high": None,
                "low": None,
                "volume": None,
                "pe_ratio": Decimal("35.2"),
                "pb_ratio": None,
                "market_cap": None,
                "update_time": "2026-07-17 20:01:11",
            },
        ],
        metadata={
            "attribution": "Futu OpenD",
            "license_scope": "券商私有行情，经 Futu OpenD 个人订阅获取；仅供参考，不可再分发",
        },
    )

    class FakeRun:
        batch_id = uuid.uuid4()

    count = store_futu_snapshots(result, source, FakeRun())  # type: ignore[arg-type]
    assert count == 2

    spy = Instrument.objects.get(symbol="US.SPY")
    assert spy.asset_class == "etf"  # SPY is in the ETF allowlist
    spy_obs = Observation.objects.get(instrument=spy, source=source)
    assert spy_obs.value == Decimal("743.29")
    assert spy_obs.quality_status == Observation.Quality.ESTIMATED
    assert spy_obs.metadata["broker_private"] is True
    assert spy_obs.metadata["source"] == "Futu OpenD"
    assert "券商私有" in spy_obs.metadata["license_scope"]

    aapl = Instrument.objects.get(symbol="US.AAPL")
    assert aapl.asset_class == "equity"  # not in the ETF allowlist
    aapl_obs = Observation.objects.get(instrument=aapl, source=source)
    assert aapl_obs.value == Decimal("333.74")
    assert aapl_obs.quality_status == Observation.Quality.ESTIMATED
    assert aapl_obs.metadata["pe_ratio"] == "35.2"


@pytest.mark.django_db
def test_store_futu_snapshots_is_idempotent_on_rerun():
    source = Source.objects.create(key="futu", name="Futu OpenD 行情")
    record = {
        "symbol": "US.SPY",
        "name": "SPY",
        "last_price": "743.29",
        "prev_close": Decimal("750.72"),
        "open": None,
        "high": None,
        "low": None,
        "volume": None,
        "pe_ratio": None,
        "pb_ratio": None,
        "market_cap": None,
        "update_time": "2026-07-17 20:01:12",
    }
    result = ProviderResult(
        provider="futu",
        dataset="market-snapshots:US.SPY",
        records=[record],
        metadata={"attribution": "Futu OpenD", "license_scope": "broker"},
    )

    class FakeRun:
        batch_id = uuid.uuid4()

    store_futu_snapshots(result, source, FakeRun())  # type: ignore[arg-type]
    record["last_price"] = "745.00"
    store_futu_snapshots(result, source, FakeRun())  # type: ignore[arg-type]

    spy = Instrument.objects.get(symbol="US.SPY")
    observations = Observation.objects.filter(instrument=spy, source=source)
    assert observations.count() == 1  # upsert, not append
    assert observations.first().value == Decimal("745.00")


def test_futu_license_scope_is_non_redistributable():
    provider = FutuProvider()
    assert "不可再分发" in provider.FUTU_LICENSE_SCOPE
    assert provider.ATTRIBUTION == "Futu OpenD"
    provider.close()


def test_futu_provider_close_is_safe_without_open_context():
    provider = FutuProvider()
    # close() must not raise when no context was ever opened
    provider.close()
    provider.close()  # idempotent
