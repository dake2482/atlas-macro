from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from research.models import Observation, SeriesDefinition, Source, SourceLicense
from research.official_data import publish_official_dashboards
from research.providers import (
    BLSProvider,
    CFTCProvider,
    NYFedMarketsProvider,
    TreasuryRatesProvider,
)


def _client(handler):
    return httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))


def test_ny_fed_provider_normalizes_reference_rate_metadata():
    def handler(request):
        assert request.url.path.endswith("/api/rates/secured/sofr/last/2.json")
        return httpx.Response(
            200,
            json={
                "refRates": [
                    {
                        "effectiveDate": "2026-07-09",
                        "type": "SOFR",
                        "percentRate": 3.53,
                        "percentPercentile99": 3.65,
                        "volumeInBillions": 3126,
                    }
                ]
            },
        )

    provider = NYFedMarketsProvider(client=_client(handler))
    result = provider.sofr(limit=2)

    assert result.ok
    assert result.records[0]["series_id"] == "SOFR"
    assert result.records[0]["value"] == Decimal("3.53")
    assert result.records[0]["metadata"]["percentPercentile99"] == 3.65


def test_treasury_provider_normalizes_nominal_curve_xml():
    payload = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
      xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content><m:properties>
        <d:NEW_DATE>2026-07-10T00:00:00</d:NEW_DATE>
        <d:BC_2YEAR>4.21</d:BC_2YEAR><d:BC_10YEAR>4.56</d:BC_10YEAR>
      </m:properties></content></entry>
    </feed>"""

    provider = TreasuryRatesProvider(
        client=_client(lambda _: httpx.Response(200, text=payload))
    )
    result = provider.yield_curve(year=2026)

    assert result.ok
    assert {(item["series_id"], item["value"]) for item in result.records} == {
        ("UST-2Y", Decimal("4.21")),
        ("UST-10Y", Decimal("4.56")),
    }


def test_bls_provider_normalizes_monthly_series():
    def handler(request):
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": "LNS14000000",
                            "data": [
                                {
                                    "year": "2026",
                                    "period": "M06",
                                    "periodName": "June",
                                    "value": "4.2",
                                    "footnotes": [],
                                }
                            ],
                        }
                    ]
                },
            },
        )

    provider = BLSProvider(client=_client(handler))
    result = provider.series(["LNS14000000"], start_year=2026, end_year=2026)

    assert result.ok
    assert result.records[0]["date"] == "2026-06-01"
    assert result.records[0]["value"] == Decimal("4.2")


def test_cftc_provider_expands_trader_groups_and_keeps_tuesday_date():
    payload = [
        {
            "report_date_as_yyyy_mm_dd": "2026-07-07T00:00:00.000",
            "contract_market_name": "E-MINI S&P 500",
            "cftc_contract_market_code": "13874A",
            "open_interest_all": "1000",
            "asset_mgr_positions_long": "600",
            "asset_mgr_positions_short": "200",
            "lev_money_positions_long": "100",
            "lev_money_positions_short": "300",
        }
    ]
    provider = CFTCProvider(client=_client(lambda _: httpx.Response(200, json=payload)))
    result = provider.positions(start_date="2024-01-01")

    assert result.ok
    assert result.row_count == 2
    assert {item["trader_group"] for item in result.records} == {
        "asset-manager",
        "leveraged-money",
    }
    assert {item["report_date"] for item in result.records} == {"2026-07-07"}


@pytest.mark.django_db
def test_demo_seed_is_not_rendered_on_public_pages(client, seeded_platform):
    home = client.get("/").content.decode()
    rates = client.get("/rates/yield-curve/").content.decode()
    news = client.get("/news/").content.decode()

    assert "演示日报" not in home
    assert "4.51%" not in rates
    assert "Atlas Demo Wire" not in news
    assert "没有真实数据时显示空缺" in rates


@pytest.mark.django_db
def test_public_dashboard_publisher_requires_approved_source_licence():
    source = Source.objects.create(
        key="test-approved-official",
        name="Approved Official Fixture",
        license_status=Source.LicenseStatus.OPEN,
        redistribution_allowed=True,
    )
    SourceLicense.objects.create(
        source=source,
        status=Source.LicenseStatus.OPEN,
        scope="Fixture public display",
        public_display_allowed=True,
        derived_display_allowed=True,
        historical_storage_allowed=True,
        redistribution_allowed=True,
    )
    for key, values in {"sofr": (3.58, 3.53), "effr": (3.62, 3.62)}.items():
        series = SeriesDefinition.objects.create(
            key=key,
            name=key.upper(),
            unit="%",
            source=source,
        )
        for day, value in enumerate(values, start=8):
            value_date = datetime(2026, 7, day, tzinfo=UTC)
            Observation.objects.create(
                series=series,
                value=Decimal(str(value)),
                value_date=value_date,
                as_of=value_date,
                fetched_at=value_date,
                batch_id=uuid.uuid4(),
                source=source,
            )

    dashboards = publish_official_dashboards()
    fed_funds = next(item for item in dashboards if item.key == "fed-funds")

    assert fed_funds.data["demo"] is False
    assert {item["label"] for item in fed_funds.data["metrics"]} >= {"SOFR", "EFFR"}
    assert all("Approved Official Fixture" in item["source"] for item in fed_funds.data["metrics"][:2])
