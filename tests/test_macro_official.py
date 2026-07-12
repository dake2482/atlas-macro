from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest

from research.macro_official import BEANIPAProvider, CensusMRTSProvider
from research.official_data import publish_official_dashboards
from research.providers import ProviderResult
from research.services import record_provider_result, store_series_observations


def _client(handler):
    return httpx.Client(base_url="https://example.test", transport=httpx.MockTransport(handler))


def test_bea_missing_key_skips_without_network(monkeypatch):
    monkeypatch.delenv("BEA_API_KEY", raising=False)

    def handler(_request):
        pytest.fail("missing BEA_API_KEY must not make an HTTP request")

    result = BEANIPAProvider(client=_client(handler)).gdp_pce(years=2026)

    assert result.skipped
    assert not result.ok
    assert result.metadata["reason"] == "BEA_API_KEY is not configured"


def test_bea_nipa_gdp_pce_uses_documented_parameters_and_preserves_revision_and_units():
    def handler(request):
        assert request.url.path == "/api/data"
        assert request.url.params["UserID"] == "bea-test-key"
        assert request.url.params["method"] == "GetData"
        assert request.url.params["DataSetName"] == "NIPA"
        assert request.url.params["TableName"] == "T10101"
        assert request.url.params["Frequency"] == "Q"
        assert request.url.params["Year"] == "2025,2026"
        assert request.url.params["ResultFormat"] == "JSON"
        return httpx.Response(
            200,
            json={
                "BEAAPI": {
                    "Results": {
                        "Statistic": "NIPA Table",
                        "UTCProductionTime": "2026-06-25T12:35:00.000",
                        "Data": [
                            {
                                "TableName": "T10101",
                                "SeriesCode": "A191RL",
                                "LineNumber": "1",
                                "LineDescription": "Gross domestic product",
                                "TimePeriod": "2026Q1",
                                "METRIC_NAME": "Percent Change From Preceding Period",
                                "CL_UNIT": "Percent change",
                                "UNIT_MULT": "0",
                                "DataValue": "2.1",
                                "NoteRef": "T10101",
                            },
                            {
                                "TableName": "T10101",
                                "SeriesCode": "DPCERL",
                                "LineNumber": "2",
                                "LineDescription": "Personal consumption expenditures",
                                "TimePeriod": "2026Q1",
                                "METRIC_NAME": "Percent Change From Preceding Period",
                                "CL_UNIT": "Percent change",
                                "UNIT_MULT": "0",
                                "DataValue": "0.5",
                                "NoteRef": "T10101",
                            },
                            {
                                "TableName": "T10101",
                                "SeriesCode": "A006RL",
                                "LineNumber": "3",
                                "LineDescription": "Goods",
                                "TimePeriod": "2026Q1",
                                "METRIC_NAME": "Percent Change From Preceding Period",
                                "CL_UNIT": "Percent change",
                                "UNIT_MULT": "0",
                                "DataValue": "-1.0",
                                "NoteRef": "T10101",
                            },
                        ],
                        "Notes": [
                            {
                                "NoteRef": "T10101",
                                "NoteText": (
                                    "Table 1.1.1. Percent Change From Preceding Period in "
                                    "Real Gross Domestic Product - LastRevised: June 25, 2026"
                                ),
                            }
                        ],
                    }
                }
            },
        )

    result = BEANIPAProvider(api_key="bea-test-key", client=_client(handler)).gdp_pce(
        years=(2025, 2026)
    )

    assert result.ok
    assert result.dataset == "nipa:gdp-pce-growth:Q"
    assert result.row_count == 2
    assert result.records[0]["series_id"] == "BEA-A191RL"
    assert result.records[0]["date"] == "2026-01-01"
    assert result.records[0]["value"] == Decimal("2.1")
    assert result.records[0]["metadata"]["calculation_type"] == "Percent change"
    assert result.records[0]["metadata"]["unit_multiplier"] == "0"
    assert result.records[0]["metadata"]["source_revision_date"] == "2026-06-25"
    assert result.metadata["api_production_time"] == "2026-06-25T12:35:00.000"
    assert result.metadata["vintage_policy"] == "latest-vintage-only"
    assert "not endorsed or certified" in result.metadata["attribution_notice"]


def test_bea_api_error_becomes_provider_failure():
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "BEAAPI": {
                    "Results": {
                        "Error": {
                            "APIErrorCode": "4",
                            "APIErrorDescription": "Invalid Request - Invalid Parameter",
                        }
                    }
                }
            },
        )

    result = BEANIPAProvider(api_key="bad-key", client=_client(handler)).nipa_table(
        "T10101", frequency="Q", years=2026
    )

    assert not result.ok
    assert not result.skipped
    assert "Invalid Parameter" in result.error


def test_census_missing_key_skips_without_network(monkeypatch):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)

    def handler(_request):
        pytest.fail("missing CENSUS_API_KEY must not make an HTTP request")

    result = CensusMRTSProvider(client=_client(handler)).monthly_retail_sales(time="2026-05")

    assert result.skipped
    assert not result.ok
    assert result.metadata["reason"] == "CENSUS_API_KEY is not configured"


def test_census_mrts_uses_current_required_key_and_preserves_source_precision():
    def handler(request):
        assert request.url.path == "/data/timeseries/eits/mrts"
        assert request.url.params["key"] == "census-test-key"
        assert request.url.params["category_code"] == "44X72"
        assert request.url.params["seasonally_adj"] == "yes"
        assert request.url.params["data_type_code"] == "SM"
        assert request.url.params["time"] == "2026-05"
        assert "cell_value" in request.url.params["get"]
        return httpx.Response(
            200,
            json=[
                [
                    "program_code",
                    "cell_value",
                    "time_slot_id",
                    "time_slot_date",
                    "time_slot_name",
                    "error_data",
                    "seasonally_adj",
                    "category_code",
                    "data_type_code",
                    "time",
                ],
                [
                    "MRTS",
                    "763700.0",
                    "M05",
                    "2026-05",
                    "May 2026",
                    "no",
                    "yes",
                    "44X72",
                    "SM",
                    "2026-05",
                ],
            ],
        )

    result = CensusMRTSProvider(
        api_key="census-test-key", client=_client(handler)
    ).monthly_retail_sales(time="2026-05")

    assert result.ok
    assert result.row_count == 1
    assert result.records[0]["series_id"] == "CENSUS-MRTS-44X72-SM-SA"
    assert result.records[0]["date"] == "2026-05-01"
    assert result.records[0]["value"] == Decimal("763700.0")
    assert result.records[0]["metadata"]["unit"] == "USD millions"
    assert result.records[0]["metadata"]["source_revision_date"] is None
    assert result.metadata["vintage_policy"] == "latest-vintage-only"
    assert result.metadata["source_revision_date"] is None
    assert "not a source vintage" in result.metadata["revision_note"]
    assert result.metadata["license"].startswith("CC0-1.0")
    assert "not endorsed or certified" in result.metadata["attribution_notice"]


def test_census_mrts_derives_month_from_slot_when_response_uses_year_predicate():
    def handler(_request):
        return httpx.Response(
            200,
            json=[
                [
                    "cell_value",
                    "time_slot_id",
                    "seasonally_adj",
                    "category_code",
                    "data_type_code",
                    "time",
                ],
                ["100", "M02", "no", "44X72", "SM", "2025"],
            ],
        )

    result = CensusMRTSProvider(
        api_key="census-test-key", client=_client(handler)
    ).monthly_retail_sales(time="2025", seasonally_adjusted=False)

    assert result.ok
    assert result.records[0]["date"] == "2025-02-01"
    assert result.records[0]["series_id"].endswith("-NSA")


@pytest.mark.django_db
def test_bea_and_census_observations_publish_gdp_and_consumer_pages():
    fetched_at = datetime(2026, 7, 12, tzinfo=UTC)
    bea = ProviderResult(
        provider="bea",
        dataset="bea-fixture",
        fetched_at=fetched_at,
        records=[
            {"series_id": "BEA-A191RL", "date": "2026-04-01", "value": "2.1"},
            {"series_id": "BEA-DPCERL", "date": "2026-04-01", "value": "1.7"},
            {"series_id": "BEA-REAL-PCE-MOM", "date": "2026-06-01", "value": "0.3"},
            {"series_id": "BEA-REAL-DPI-MOM", "date": "2026-06-01", "value": "0.2"},
            {
                "series_id": "BEA-PERSONAL-SAVING-RATE",
                "date": "2026-06-01",
                "value": "3.1",
            },
        ],
    )
    census = ProviderResult(
        provider="census",
        dataset="census-fixture",
        fetched_at=fetched_at,
        records=[
            {
                "series_id": "CENSUS-MRTS-44X72-SM-SA",
                "date": "2026-06-01",
                "value": "763700.0",
            },
            {
                "series_id": "CENSUS-MRTS-44X72-SM-SA-MOM",
                "date": "2026-06-01",
                "value": "0.4",
            },
            {
                "series_id": "CENSUS-MRTS-44X72-SM-SA-YOY",
                "date": "2026-06-01",
                "value": "3.9",
            },
        ],
    )
    record_provider_result(bea, persist=store_series_observations)
    record_provider_result(census, persist=store_series_observations)

    dashboards = {item.key: item for item in publish_official_dashboards()}

    assert {"gdp", "consumer"} <= dashboards.keys()
    gdp_metrics = {item["key"]: item for item in dashboards["gdp"].data["metrics"]}
    assert gdp_metrics["bea-a191rl"]["display_value"] == "2.10%"
    consumer_metrics = {
        item["key"]: item for item in dashboards["consumer"].data["metrics"]
    }
    assert consumer_metrics["census-mrts-44x72-sm-sa"]["display_value"] == (
        "763,700 USD mn"
    )
