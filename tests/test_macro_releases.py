from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO

import httpx
import pytest
from openpyxl import Workbook

from research.data_catalog import DATA_REQUIREMENTS
from research.macro_releases import (
    BEA_GDP_PAGE,
    BEA_VINTAGE_WORKBOOK,
    CENSUS_MARTS_INDEX,
    XLSX_CONTENT_TYPE,
    BEAGDPReleaseProvider,
    CensusMARTSReleaseProvider,
)
from research.models import RawArtifact
from research.official_data import (
    _store_release_workbook_observations,
    publish_official_dashboards,
)
from research.providers import ProviderResult
from research.services import record_provider_result, store_series_observations


def _workbook_bytes(workbook: Workbook) -> bytes:
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def _bea_vintage_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Vintage History"
    sheet.append(["Last Updated June 25, 2026"])
    sheet.append(["2026Q1"])
    sheet.append([None, "Vintage", "GDP", "GDI", "Real GDP", "Real GDI", "Release Date"])
    sheet.append([None, "Third", "31,865.7", "31,574.2", "2.1", "1.2", "Jun 25, 2026"])
    sheet.append([None, "Second", "31,819.5", "31,539.4", "1.6", "0.9", "May 28, 2026"])
    sheet.append(["2025Q4"])
    sheet.append([None, "Vintage", "GDP", "GDI", "Real GDP", "Real GDI", "Release Date"])
    sheet.append(
        [
            None,
            "Revised",
            "31,422.5",
            "31,199.9",
            "0.5",
            "1.6",
            "May 28, 2026 GDP not open for revision",
        ]
    )
    return _workbook_bytes(workbook)


def _bea_comparison_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "GDPhistQ"
    sheet["A1"] = "June 25, 2026"
    sheet["A2"] = (
        "2026Q1 (Third Estimate) Comparisons -- Percent Change from Preceding Period "
        "in Real Gross Domestic Product and Related Measures"
    )
    rows = [
        ("Gross domestic product (GDP)", 2.1, "2025Q4", 0.5),
        ("Personal consumption expenditures", 0.5, "2025Q4", 1.9),
        ("Goods", 0.5, "2025Q4", 0.3),
        ("Services", 0.5, "2025Q4", 2.7),
        ("Gross private domestic investment", 7.9, "2025Q4", 2.3),
        ("Fixed investment", 6.5, "2025Q4", 1.5),
        ("Exports", 5.4, "2025Q4", -3.1),
        ("Imports", 1.8, "2025Q4", -1.2),
        ("Government consumption expenditures and gross investment", 1.2, "2025Q4", 0.4),
    ]
    for row_number, (label, current, previous_period, previous) in enumerate(rows, start=6):
        sheet.cell(row_number, 1, label)
        sheet.cell(row_number, 2, current)
        sheet.cell(row_number, 5, previous_period)
        sheet.cell(row_number, 6, previous)
    sheet.cell(
        20,
        1,
        "2026Q1 (Third Estimate) Comparisons -- Contributions to Percent Change "
        "in Real Gross Domestic Product",
    )
    contribution_rows = [
        ("Personal consumption expenditures", 0.37, "2025Q4", 1.30),
        ("Gross private domestic investment", 1.35, "2025Q4", 0.40),
        ("Net exports of goods and services", -0.37, "2025Q4", 0.46),
        ("Government consumption expenditures and gross investment", 0.74, "2025Q4", -0.99),
    ]
    for row_number, (label, current, previous_period, previous) in enumerate(
        contribution_rows, start=24
    ):
        sheet.cell(row_number, 1, label)
        sheet.cell(row_number, 2, current)
        sheet.cell(row_number, 5, previous_period)
        sheet.cell(row_number, 6, previous)
    return _workbook_bytes(workbook)


def _census_workbook() -> bytes:
    workbook = Workbook()
    sales = workbook.active
    sales.title = "Table 1."
    sales.cell(6, 10, "Adjusted2")
    sales.cell(7, 10, 2026)
    sales.cell(7, 13, 2025)
    for column, label in enumerate(("Apr.3", "Mar.", "Feb.", "Apr.", "Mar."), start=10):
        sales.cell(8, column, label)
    for column, status in enumerate(("(a)", "(p)", "(r)", "(r)", "(r)"), start=10):
        sales.cell(9, column, status)
    sales.cell(11, 2, "Retail & food services, ")
    sales.cell(12, 2, "  total")
    for column, value in enumerate((757085, 753370, 741278, 721903, 723339), start=10):
        sales.cell(12, column, value)

    changes = workbook.create_sheet("Table 2.")
    changes.cell(8, 3, "Apr. 2026 Advance")
    changes.cell(8, 5, "Mar. 2026 Preliminary")
    changes.cell(11, 3, "Mar. 2026")
    changes.cell(11, 4, "Apr. 2025")
    changes.cell(11, 5, "Feb. 2026")
    changes.cell(11, 6, "Mar. 2025")
    changes.cell(14, 2, "Retail & food services, ")
    changes.cell(15, 2, "  total")
    changes.cell(15, 3, 0.5)
    changes.cell(15, 4, 4.9)
    changes.cell(15, 5, 1.6)
    changes.cell(15, 6, 4.2)
    return _workbook_bytes(workbook)


def _bea_client(vintage: bytes, comparisons: bytes) -> httpx.Client:
    comparison_url = "https://www.bea.gov/sites/default/files/2026-06/hist1q26-3rd.xlsx"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == BEA_GDP_PAGE:
            return httpx.Response(
                200,
                text=(
                    '<html><a href="/sites/default/files/2026-06/hist1q26-3rd.xlsx">'
                    "Historical Comparisons</a></html>"
                ),
                headers={"content-type": "text/html"},
            )
        if url == BEA_VINTAGE_WORKBOOK:
            return httpx.Response(
                200,
                content=vintage,
                headers={"content-type": XLSX_CONTENT_TYPE, "last-modified": "June 25, 2026"},
            )
        if url == comparison_url:
            return httpx.Response(
                200,
                content=comparisons,
                headers={"content-type": XLSX_CONTENT_TYPE, "last-modified": "June 25, 2026"},
            )
        raise AssertionError(f"unexpected URL: {url}")

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _census_client(workbook: bytes) -> httpx.Client:
    latest = f"{CENSUS_MARTS_INDEX}rs2604.xlsx"

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == CENSUS_MARTS_INDEX:
            return httpx.Response(
                200,
                text=(
                    '<html><a href="rs9912.xlsx">old</a>'
                    '<a href="rs2603.xlsx">prior</a>'
                    '<a href="rs2604.xlsx">latest</a></html>'
                ),
                headers={"content-type": "text/html"},
            )
        if url == latest:
            return httpx.Response(
                200,
                content=workbook,
                headers={"content-type": XLSX_CONTENT_TYPE, "last-modified": "May 15, 2026"},
            )
        raise AssertionError(f"unexpected URL: {url}")

    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def test_bea_release_provider_preserves_vintages_components_and_artifact_hashes():
    vintage = _bea_vintage_workbook()
    comparisons = _bea_comparison_workbook()
    result = BEAGDPReleaseProvider(client=_bea_client(vintage, comparisons)).gdp_pce()

    assert result.ok
    assert result.metadata["quarter_count"] == 2
    assert result.metadata["comparison_quarter"] == "2026Q1"
    assert result.metadata["comparison_release_date"] == "2026-06-25"
    assert result.metadata["comparison_estimate_round"] == "Third"
    assert len(result.metadata["artifacts"]) == 3
    assert result.metadata["artifacts"][1]["sha256"] == hashlib.sha256(vintage).hexdigest()

    by_series_and_date = {
        (item["series_id"], item["date"]): item for item in result.records
    }
    latest_gdp = by_series_and_date[("BEA-A191RL", "2026-01-01")]
    assert latest_gdp["value"] == Decimal("2.1")
    assert latest_gdp["metadata"]["vintage_label"] == "Third"
    assert latest_gdp["metadata"]["estimate_round"] == "Third"
    assert latest_gdp["metadata"]["source_revision_date"] == "2026-06-25"
    assert by_series_and_date[("BEA-DPCERL", "2026-01-01")]["value"] == Decimal("0.5")
    assert by_series_and_date[("BEA-DPCERL", "2025-10-01")]["value"] == Decimal("1.9")
    assert by_series_and_date[("BEA-GPDI-GROWTH", "2026-01-01")]["value"] == Decimal("7.9")
    assert by_series_and_date[("BEA-PCE-CONTRIBUTION", "2026-01-01")][
        "value"
    ] == Decimal("0.37")
    assert by_series_and_date[("BEA-NET-EXPORTS-CONTRIBUTION", "2026-01-01")][
        "metadata"
    ]["unit"] == "percentage points contribution to real GDP growth"


def test_census_release_provider_selects_latest_calendar_file_and_preserves_status():
    workbook = _census_workbook()
    result = CensusMARTSReleaseProvider(client=_census_client(workbook)).monthly_retail_sales()

    assert result.ok
    assert result.metadata["workbook_url"].endswith("rs2604.xlsx")
    assert result.metadata["latest_value_date"] == "2026-04-01"
    assert result.metadata["artifacts"][1]["sha256"] == hashlib.sha256(workbook).hexdigest()
    by_series_and_date = {
        (item["series_id"], item["date"]): item for item in result.records
    }
    latest = by_series_and_date[("CENSUS-MRTS-44X72-SM-SA", "2026-04-01")]
    assert latest["value"] == 757085
    assert latest["metadata"]["estimate_status"] == "(a)"
    assert by_series_and_date[("CENSUS-MRTS-44X72-SM-SA-MOM", "2026-04-01")][
        "value"
    ] == Decimal("0.5")
    assert by_series_and_date[("CENSUS-MRTS-44X72-SM-SA-YOY", "2026-03-01")][
        "value"
    ] == Decimal("4.2")
    assert by_series_and_date[("CENSUS-MRTS-44X72-SM-SA-MOM", "2026-04-01")][
        "metadata"
    ]["estimate_status"] == "(a)"


@pytest.mark.django_db
def test_release_workbooks_persist_lineage_and_publish_gdp_and_consumer_pages():
    bea = BEAGDPReleaseProvider(
        client=_bea_client(_bea_vintage_workbook(), _bea_comparison_workbook())
    ).gdp_pce()
    census = CensusMARTSReleaseProvider(
        client=_census_client(_census_workbook())
    ).monthly_retail_sales()
    bea_run = record_provider_result(bea, persist=_store_release_workbook_observations)
    census_run = record_provider_result(census, persist=_store_release_workbook_observations)

    dashboards = {
        item.key: item
        for item in publish_official_dashboards(keys={"gdp", "consumer"})
    }

    assert bea_run.status == "success"
    assert census_run.status == "success"
    assert RawArtifact.objects.filter(run=bea_run).count() == 3
    assert RawArtifact.objects.filter(run=census_run).count() == 2
    assert set(dashboards) == {"gdp", "consumer"}
    gdp = {item["key"]: item for item in dashboards["gdp"].data["metrics"]}
    consumer = {
        item["key"]: item for item in dashboards["consumer"].data["metrics"]
    }
    assert gdp["bea-a191rl"]["display_value"] == "2.10%"
    assert gdp["bea-dpcerl"]["display_value"] == "0.50%"
    assert gdp["bea-pce-contribution"]["display_value"] == "0.37pp"
    assert consumer["census-mrts-44x72-sm-sa"]["display_value"] == "757,085 USD mn"
    assert consumer["census-mrts-44x72-sm-sa-mom"]["display_value"] == "0.50%"


@pytest.mark.django_db
def test_dashboard_deduplicates_same_date_across_provider_sources():
    older_fetch = datetime(2026, 6, 25, tzinfo=UTC)
    newer_fetch = older_fetch + timedelta(days=1)
    record_provider_result(
        ProviderResult(
            provider="bea",
            dataset="api-fixture",
            fetched_at=older_fetch,
            records=[
                {"series_id": "BEA-A191RL", "date": "2026-01-01", "value": "9.9"},
                {"series_id": "BEA-A191RL", "date": "2025-10-01", "value": "1.0"},
            ],
        ),
        persist=store_series_observations,
    )
    record_provider_result(
        ProviderResult(
            provider="bea-release",
            dataset="release-fixture",
            fetched_at=newer_fetch,
            records=[
                {"series_id": "BEA-A191RL", "date": "2026-01-01", "value": "2.1"},
                {"series_id": "BEA-A191RL", "date": "2025-10-01", "value": "0.5"},
            ],
        ),
        persist=store_series_observations,
    )

    dashboard = publish_official_dashboards(keys={"gdp"})[0]
    metric = next(item for item in dashboard.data["metrics"] if item["key"] == "bea-a191rl")
    chart = dashboard.data["chart_data"]

    assert metric["display_value"] == "2.10%"
    assert metric["change"] == 1.6
    assert [row["date"] for row in chart] == ["2025-10-01", "2026-01-01"]


def test_economy_catalog_separates_live_release_data_from_remaining_gaps():
    requirements = {item["key"]: item for item in DATA_REQUIREMENTS}

    assert requirements["bea-gdp-pce"]["status"] == "live"
    assert requirements["census-retail"]["status"] == "live"
    assert requirements["bea-gdp-contributions"]["status"] == "live"
    assert requirements["bea-gdp-vintage-trail"]["status"] == "needs_source"
    assert requirements["bea-personal-income-outlays"]["status"] == "needs_source"
    assert requirements["consumer-confidence"]["status"] == "purchase_required"
