from __future__ import annotations

import html
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from research.data_catalog import DATA_REQUIREMENTS
from research.models import (
    DashboardSnapshot,
    IngestionRun,
    MetricSnapshot,
    Observation,
    SeriesDefinition,
)
from research.official_data import (
    BLS_SERIES,
    INFLATION_PUBLICATION_GROUPS,
    MACRO_REQUIRED_SERIES,
    _inflation_page_is_buildable,
    _keys_with_current_required_batches,
    _mark_latest_dashboards_stale,
    _publishable_keys_for_source_groups,
    publish_official_dashboards,
    refresh_official_data,
)
from research.providers import ProviderResult
from research.services import record_provider_result, store_series_observations

INFLATION_SERIES = (
    "CUSR0000SA0",
    "CUUR0000SA0",
    "CUSR0000SA0L1E",
    "CUUR0000SA0L1E",
    "WPSFD4",
    "WPUFD4",
)
LATEST_PERIOD = date(2026, 5, 1)


def _month(start: date, offset: int) -> date:
    month_index = start.year * 12 + start.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def _inflation_records(
    *,
    omit: set[tuple[str, date]] | None = None,
    overrides: dict[tuple[str, date], Decimal] | None = None,
) -> list[dict]:
    omit = omit or set()
    overrides = overrides or {}
    start = date(2021, 5, 1)
    periods = [_month(start, index) for index in range(61)]
    records = []
    anchor_values = {
        ("CUSR0000SA0", LATEST_PERIOD): Decimal("121"),
        ("CUSR0000SA0", date(2026, 4, 1)): Decimal("110"),
        ("CUSR0000SA0", date(2026, 3, 1)): Decimal("105"),
        ("CUSR0000SA0", date(2026, 2, 1)): Decimal("100"),
        ("CUSR0000SA0", date(2026, 1, 1)): Decimal("100"),
        ("CUSR0000SA0", date(2025, 12, 1)): Decimal("100"),
        ("CUSR0000SA0", date(2025, 11, 1)): Decimal("100"),
        ("CUUR0000SA0", LATEST_PERIOD): Decimal("120"),
        ("CUUR0000SA0", date(2025, 5, 1)): Decimal("100"),
    }
    anchor_values.update(overrides)
    base_values = {
        "CUSR0000SA0": Decimal("100"),
        "CUUR0000SA0": Decimal("101"),
        "CUSR0000SA0L1E": Decimal("200"),
        "CUUR0000SA0L1E": Decimal("201"),
        "WPSFD4": Decimal("150"),
        "WPUFD4": Decimal("151"),
    }
    for series_id in INFLATION_SERIES:
        for index, period in enumerate(periods):
            if (series_id, period) in omit:
                continue
            preliminary = series_id in {"WPSFD4", "WPUFD4"} and index >= 57
            records.append(
                {
                    "series_id": series_id,
                    "date": period.isoformat(),
                    "value": anchor_values.get(
                        (series_id, period),
                        base_values[series_id] + Decimal(index) / Decimal("2"),
                    ),
                    "quality_status": "estimated" if preliminary else "fresh",
                    "metadata": {
                        "preliminary": preliminary,
                        "footnotes": (
                            [{"code": "P", "text": "preliminary"}]
                            if preliminary
                            else []
                        ),
                    },
                }
            )
    return records


def _inflation_run(
    *,
    omit: set[tuple[str, date]] | None = None,
    overrides: dict[tuple[str, date], Decimal] | None = None,
):
    return record_provider_result(
        ProviderResult(
            provider="bls",
            dataset="inflation-fixture",
            fetched_at=datetime(2026, 6, 10, 12, 35, tzinfo=UTC),
            records=_inflation_records(omit=omit, overrides=overrides),
            metadata={
                "requested_series": list(INFLATION_SERIES),
                "missing_series": [],
                "quality_status": "complete",
            },
        ),
        persist=store_series_observations,
    )


def _pce_inflation_records() -> list[dict]:
    start = date(2021, 5, 1)
    periods = [_month(start, index) for index in range(61)]
    anchors = {
        ("BEA-PCE-PRICE-INDEX", LATEST_PERIOD): Decimal("130"),
        ("BEA-PCE-PRICE-INDEX", date(2026, 4, 1)): Decimal("129"),
        ("BEA-PCE-PRICE-INDEX", date(2026, 2, 1)): Decimal("125"),
        ("BEA-PCE-PRICE-INDEX", date(2025, 11, 1)): Decimal("124"),
        ("BEA-PCE-PRICE-INDEX", date(2025, 5, 1)): Decimal("120"),
        ("BEA-CORE-PCE-PRICE-INDEX", LATEST_PERIOD): Decimal("260"),
        ("BEA-CORE-PCE-PRICE-INDEX", date(2026, 4, 1)): Decimal("259"),
        ("BEA-CORE-PCE-PRICE-INDEX", date(2026, 2, 1)): Decimal("255"),
        ("BEA-CORE-PCE-PRICE-INDEX", date(2025, 11, 1)): Decimal("254"),
        ("BEA-CORE-PCE-PRICE-INDEX", date(2025, 5, 1)): Decimal("250"),
    }
    records = []
    for series_id, base in (
        ("BEA-PCE-PRICE-INDEX", Decimal("100")),
        ("BEA-CORE-PCE-PRICE-INDEX", Decimal("200")),
    ):
        for index, period in enumerate(periods):
            records.append(
                {
                    "series_id": series_id,
                    "date": period.isoformat(),
                    "value": anchors.get(
                        (series_id, period),
                        base + Decimal(index) / Decimal("10"),
                    ),
                    "metadata": {
                        "official_series_code": (
                            "DPCERG"
                            if series_id == "BEA-PCE-PRICE-INDEX"
                            else "DPCCRG"
                        ),
                        "release_freshness_days": 45,
                    },
                }
            )
    return records


def _pce_inflation_run():
    return record_provider_result(
        ProviderResult(
            provider="bea-pio-release",
            dataset="personal-income-outlays-release",
            fetched_at=datetime(2026, 6, 25, 12, 35, tzinfo=UTC),
            records=_pce_inflation_records(),
            metadata={
                "latest_value_date": LATEST_PERIOD.isoformat(),
                "source_revision_date": "2026-06-25",
            },
        ),
        persist=store_series_observations,
    )


@pytest.mark.django_db
def test_inflation_contract_uses_six_monthly_bls_series():
    expected = set(INFLATION_SERIES)
    assert set(MACRO_REQUIRED_SERIES["inflation"]["bls"]) == expected
    assert expected <= set(BLS_SERIES)
    assert len(BLS_SERIES) <= 25

    _inflation_run()
    definitions = {
        item.key: item
        for item in SeriesDefinition.objects.filter(
            key__in={item.lower() for item in expected}
        )
    }
    assert set(definitions) == {item.lower() for item in expected}
    assert {item.unit for item in definitions.values()} == {"index"}
    assert {item.frequency for item in definitions.values()} == {"monthly"}

    assert MACRO_REQUIRED_SERIES["inflation"]["bea-pio-release"] == frozenset(
        {"BEA-PCE-PRICE-INDEX", "BEA-CORE-PCE-PRICE-INDEX"}
    )


@pytest.mark.django_db
def test_inflation_publication_uses_sa_momentum_nsa_yoy_and_full_lineage():
    run = _inflation_run()
    pce_run = _pce_inflation_run()
    assert _inflation_page_is_buildable(
        batch_id=run.batch_id, bea_pio_batch_id=pce_run.batch_id
    )

    dashboards = publish_official_dashboards(
        keys={"inflation"},
        source_batches={
            "bls": run.batch_id,
            "bea-pio-release": pce_run.batch_id,
        },
    )
    assert [item.key for item in dashboards] == ["inflation"]
    snapshot = dashboards[0]
    metrics = {item["key"]: item for item in snapshot.data["metrics"]}

    assert metrics["headline-cpi-mom"]["value"] == pytest.approx(10.0)
    assert metrics["headline-cpi-yoy"]["value"] == pytest.approx(20.0)
    assert metrics["headline-cpi-3m-annualized"]["value"] == pytest.approx(
        114.358881
    )
    assert metrics["headline-cpi-6m-annualized"]["value"] == pytest.approx(
        46.41
    )
    assert metrics["pce-price-index-mom"]["value"] == pytest.approx(0.7751938)
    assert metrics["pce-price-index-yoy"]["value"] == pytest.approx(8.3333333)
    assert metrics["core-pce-price-index-yoy"]["value"] == pytest.approx(4.0)
    assert metrics["headline-cpi-mom"]["metadata"]["seasonal_basis"] == (
        "seasonally_adjusted"
    )
    assert metrics["headline-cpi-yoy"]["metadata"]["seasonal_basis"] == (
        "not_seasonally_adjusted"
    )
    assert metrics["headline-cpi-mom"]["metadata"]["input_series"] == [
        "cusr0000sa0"
    ]
    assert metrics["headline-cpi-yoy"]["metadata"]["input_series"] == [
        "cuur0000sa0"
    ]
    assert all(item["unit"] == "%" for item in metrics.values())
    assert not any("index level" in item["label"].lower() for item in metrics.values())

    for metric in metrics.values():
        expected_batch = (
            str(pce_run.batch_id)
            if metric["metadata"]["source_keys"] == ["bea-pio-release"]
            else str(run.batch_id)
        )
        assert metric["metadata"]["input_batch_ids"] == [expected_batch]
        assert metric["metadata"]["input_lineage"]
        for lineage in metric["metadata"]["input_lineage"]:
            assert lineage["source_key"] in {"bls", "bea-pio-release"}
            assert lineage["license_scope"]
            assert lineage["batch_id"] == expected_batch
            assert lineage["value_date"]
            assert lineage["fetched_at"]
            assert lineage["quality_status"] in {"fresh", "estimated"}
            assert lineage["fallback_source"] is None

    ppi_metric = metrics["final-demand-ppi-6m-annualized"]
    assert ppi_metric["quality_status"] == "estimated"
    assert ppi_metric["metadata"]["preliminary"] is True
    chart_keys = {item["key"] for item in snapshot.data["charts"]}
    assert chart_keys == {
        "headline-cpi-rates",
        "core-cpi-rates",
        "final-demand-ppi-rates",
        "pce-price-rates",
        "core-pce-price-rates",
    }
    for chart in snapshot.data["charts"]:
        assert chart["time_axis"] == "date"
        for row in chart["data"]:
            assert not {"CPI", "核心 CPI", "PPI"} & set(row)
    latest_ppi = snapshot.data["charts"][2]["data"][-1]
    assert latest_ppi["_lineage"]["最终需求 PPI 同比"]["preliminary"] is True
    pce_chart = next(item for item in snapshot.data["charts"] if item["key"] == "pce-price-rates")
    latest_pce = pce_chart["data"][-1]
    assert latest_pce["PCE 价格指数 同比"] == pytest.approx(8.3333333)
    assert latest_pce["_lineage"]["PCE 价格指数 同比"]["source_keys"] == [
        "bea-pio-release"
    ]

    stored = MetricSnapshot.objects.get(
        key="inflation-headline-cpi-yoy", batch_id=snapshot.batch_id
    )
    assert stored.metadata["input_batch_ids"] == [str(run.batch_id)]
    assert stored.metadata["input_lineage"][0]["license_scope"]
    assert stored.metadata["seasonal_basis"] == "not_seasonally_adjusted"


@pytest.mark.parametrize(
    ("omit", "overrides"),
    [
        ({("CUSR0000SA0", date(2026, 4, 1))}, {}),
        ({("CUSR0000SA0", date(2026, 2, 1))}, {}),
        ({("CUSR0000SA0", date(2025, 11, 1))}, {}),
        ({("CUUR0000SA0", date(2025, 5, 1))}, {}),
        ({("CUUR0000SA0", LATEST_PERIOD)}, {}),
        ({}, {("CUSR0000SA0", date(2026, 4, 1)): Decimal("0")}),
        ({}, {("CUSR0000SA0", date(2026, 2, 1)): Decimal("-1")}),
        ({}, {("CUUR0000SA0", date(2025, 5, 1)): Decimal("0")}),
    ],
)
@pytest.mark.django_db
def test_inflation_refuses_missing_or_nonpositive_exact_inputs(omit, overrides):
    run = _inflation_run(omit=omit, overrides=overrides)
    pce_run = _pce_inflation_run()

    assert not _inflation_page_is_buildable(
        batch_id=run.batch_id, bea_pio_batch_id=pce_run.batch_id
    )
    assert (
        publish_official_dashboards(
            keys={"inflation"}, source_batches={"bls": run.batch_id}
        )
        == []
    )


@pytest.mark.django_db
def test_inflation_october_gap_never_uses_nearest_month():
    run = _inflation_run(omit={("CUSR0000SA0", date(2025, 10, 1))})
    pce_run = _pce_inflation_run()
    assert _inflation_page_is_buildable(
        batch_id=run.batch_id, bea_pio_batch_id=pce_run.batch_id
    )
    snapshot = publish_official_dashboards(
        keys={"inflation"},
        source_batches={
            "bls": run.batch_id,
            "bea-pio-release": pce_run.batch_id,
        },
    )[0]
    headline = next(
        item
        for item in snapshot.data["charts"]
        if item["key"] == "headline-cpi-rates"
    )
    rows = {item["date"]: item for item in headline["data"]}

    assert "CPI 环比" not in rows["2025-11-01"]
    assert "CPI 3M 年化" not in rows["2026-01-01"]
    assert "CPI 6M 年化" not in rows["2026-04-01"]
    assert {
        "CPI 环比",
        "CPI 同比",
        "CPI 3M 年化",
        "CPI 6M 年化",
    } <= set(rows["2026-05-01"])


@pytest.mark.django_db
def test_inflation_gate_is_isolated_and_rejects_mixed_current_batch():
    run = _inflation_run()
    pce_run = _pce_inflation_run()
    unrelated_failure = record_provider_result(
        ProviderResult.failure("dol-eta-ui", "claims", "fixture failure")
    )

    assert INFLATION_PUBLICATION_GROUPS == {
        "inflation": frozenset({"bls", "bea-pio-release"})
    }
    assert _publishable_keys_for_source_groups(
        [run, pce_run, unrelated_failure], INFLATION_PUBLICATION_GROUPS
    ) == {"inflation"}
    assert _keys_with_current_required_batches({"inflation"}, [run, pce_run]) == {
        "inflation"
    }

    Observation.objects.filter(
        series__key="cuur0000sa0", value_date__date=LATEST_PERIOD
    ).update(batch_id=uuid.uuid4())
    assert _keys_with_current_required_batches({"inflation"}, [run, pce_run]) == set()
    assert not _inflation_page_is_buildable(
        batch_id=run.batch_id, bea_pio_batch_id=pce_run.batch_id
    )


@pytest.mark.django_db
def test_inflation_failed_bls_keeps_snapshot_stale_and_same_values_recover():
    first_run = _inflation_run()
    first_pce_run = _pce_inflation_run()
    published = publish_official_dashboards(
        keys={"inflation"},
        source_batches={
            "bls": first_run.batch_id,
            "bea-pio-release": first_pce_run.batch_id,
        },
    )[0]
    failed = record_provider_result(
        ProviderResult.failure("bls", "inflation-fixture", "upstream timeout")
    )

    _mark_latest_dashboards_stale(
        {"inflation"}, [failed], groups=INFLATION_PUBLICATION_GROUPS
    )
    published.refresh_from_db()
    assert published.quality_status == "stale"
    failure_sources = {
        item["source"]: item for item in published.data["refresh_failure"]["sources"]
    }
    assert failure_sources["bls"] == {
        "source": "bls",
        "status": "failed",
        "row_count": 0,
        "error": "upstream timeout",
    }
    assert failure_sources["bea-pio-release"]["status"] == "missing"
    assert DashboardSnapshot.objects.filter(key="inflation").count() == 1

    recovered_run = _inflation_run()
    recovered_pce_run = _pce_inflation_run()
    assert (
        publish_official_dashboards(
            keys={"inflation"},
            source_batches={
                "bls": recovered_run.batch_id,
                "bea-pio-release": recovered_pce_run.batch_id,
            },
        )
        == []
    )
    latest = DashboardSnapshot.objects.filter(key="inflation").latest("created_at")
    assert "refresh_failure" not in latest.data


@pytest.mark.django_db
def test_inflation_get_controls_slice_group_and_sanitize(client):
    run = _inflation_run()
    pce_run = _pce_inflation_run()
    publish_official_dashboards(
        keys={"inflation"},
        source_batches={
            "bls": run.batch_id,
            "bea-pio-release": pce_run.batch_id,
        },
    )

    response = client.get(
        "/economy/inflation/", {"period": "1y", "tab": "producer"}
    )
    assert response.status_code == 200
    assert response.context["selected_period"] == "1y"
    assert response.context["selected_tab"] == "producer"
    assert [item["key"] for item in response.context["charts"]] == [
        "final-demand-ppi-rates"
    ]
    assert len(response.context["charts"][0]["data"]) <= 13
    body = html.unescape(response.content.decode())
    assert "U.S. Bureau of Labor Statistics" in body
    assert "period=3y&tab=producer" in body or "tab=producer&period=3y" in body
    assert "period=1y&tab=core" in body or "tab=core&period=1y" in body

    default = client.get("/economy/inflation/")
    assert default.context["selected_period"] == "3y"
    assert default.context["selected_tab"] == "overview"
    assert len(default.context["charts"]) == 5

    pce = client.get("/economy/inflation/", {"tab": "pce"})
    assert pce.status_code == 200
    assert [item["key"] for item in pce.context["charts"]] == [
        "pce-price-rates",
        "core-pce-price-rates",
    ]

    invalid = client.get(
        "/economy/inflation/",
        {"period": "<script>alert(1)</script>", "tab": "missing"},
    )
    assert invalid.context["selected_period"] == "3y"
    assert invalid.context["selected_tab"] == "overview"
    assert "<script>alert(1)</script>" not in invalid.content.decode()
    assert "alert%281%29" not in invalid.content.decode()


def test_inflation_catalog_marks_official_inputs_and_missing_layers():
    requirements = {
        item["key"]: item
        for item in DATA_REQUIREMENTS
        if item["page_key"] == "inflation"
    }
    assert requirements["bls-inflation-official"]["status"] == "live"
    assert requirements["bea-pce-inflation"]["status"] == "live"
    assert requirements["bls-inflation-components"]["status"] == "needs_source"
    assert requirements["inflation-market-expectations"]["status"] == (
        "needs_source"
    )
    assert requirements["inflation-vintage-trail"]["status"] == "needs_source"
    assert all(item["page_key"] == "inflation" for item in requirements.values())


@pytest.mark.django_db
def test_refresh_official_data_wires_independent_inflation_gate(monkeypatch):
    class FailingProvider:
        def __init__(self, source_key: str):
            self.source_key = source_key

        def __getattr__(self, method_name):
            def failed_call(**_kwargs):
                return ProviderResult.failure(
                    self.source_key,
                    method_name,
                    "unrelated fixture failure",
                )

            return failed_call

        def close(self):
            return None

    class FakeBLSProvider:
        fail = False

        def series(self, *_args, **_kwargs):
            if self.fail:
                return ProviderResult.failure(
                    "bls", "series:fixture", "BLS fixture failure"
                )
            return ProviderResult(
                provider="bls",
                dataset="series:fixture",
                fetched_at=datetime(2026, 6, 10, 12, 35, tzinfo=UTC),
                records=_inflation_records(),
                metadata={
                    "requested_series": list(INFLATION_SERIES),
                    "missing_series": [],
                    "quality_status": "complete",
                },
            )

        def close(self):
            return None

    class FakeBEAPIOReleaseProvider:
        fail = False

        def personal_income_outlays(self, **_kwargs):
            if self.fail:
                return ProviderResult.failure(
                    "bea-pio-release", "personal-income-outlays-release", "BEA PIO failure"
                )
            return ProviderResult(
                provider="bea-pio-release",
                dataset="personal-income-outlays-release",
                fetched_at=datetime(2026, 6, 25, 12, 35, tzinfo=UTC),
                records=_pce_inflation_records(),
                metadata={
                    "latest_value_date": LATEST_PERIOD.isoformat(),
                    "source_revision_date": "2026-06-25",
                },
            )

        def close(self):
            return None

    monkeypatch.setattr(
        "research.official_data.NYFedMarketsProvider",
        lambda: FailingProvider("ny-fed-markets"),
    )
    monkeypatch.setattr(
        "research.official_data.TreasuryRatesProvider",
        lambda: FailingProvider("us-treasury-rates"),
    )
    monkeypatch.setattr(
        "research.official_data.FiscalDataProvider",
        lambda: FailingProvider("treasury-fiscal-data"),
    )
    monkeypatch.setattr(
        "research.official_data.DOLWeeklyClaimsProvider",
        lambda: FailingProvider("dol-eta-ui"),
    )
    monkeypatch.setattr(
        "research.official_data.FederalReserveRSSProvider",
        lambda: FailingProvider("federal-reserve"),
    )
    monkeypatch.setattr(
        "research.official_data.BLSProvider", FakeBLSProvider
    )
    monkeypatch.setattr(
        "research.official_data.BEAPIOReleaseProvider", FakeBEAPIOReleaseProvider
    )

    first = refresh_official_data(current_year=2026)
    assert first["dashboard_keys"] == ["inflation"]
    assert first["stale_dashboard_keys"] == ["economy", "employment"]
    snapshot = DashboardSnapshot.objects.get(key="inflation")
    bls_run = IngestionRun.objects.filter(
        source__key="bls", status="success"
    ).latest("id")
    bea_run = IngestionRun.objects.filter(
        source__key="bea-pio-release", status="success"
    ).latest("id")
    assert set(snapshot.data["component_batches"]) == {
        str(bea_run.batch_id),
        str(bls_run.batch_id),
    }

    FakeBLSProvider.fail = True
    second = refresh_official_data(current_year=2026)
    assert "inflation" not in second["dashboard_keys"]
    assert second["stale_dashboard_keys"] == [
        "economy",
        "employment",
        "inflation",
    ]
    snapshot.refresh_from_db()
    assert snapshot.quality_status == "stale"
    failure_sources = {
        item["source"]: item for item in snapshot.data["refresh_failure"]["sources"]
    }
    assert failure_sources["bls"] == {
        "source": "bls",
        "status": "failed",
        "row_count": 0,
        "error": "BLS fixture failure",
    }
    assert failure_sources["bea-pio-release"]["status"] == "success"
