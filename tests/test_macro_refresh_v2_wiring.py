from __future__ import annotations

from types import SimpleNamespace

from django.db import transaction

from research import official_data
from research.providers import ProviderResult


class _Provider:
    def __init__(self, source: str, dataset: str, method_name: str):
        self.source = source
        self.dataset = dataset
        self.method_name = method_name

    def __getattr__(self, name):
        if name != self.method_name:
            raise AttributeError(name)

        def fetch(**_kwargs):
            return ProviderResult(
                provider=self.source,
                dataset=self.dataset,
                records=[
                    {
                        "series_id": f"{self.source}-fixture",
                        "date": "2026-06-01",
                        "value": "1",
                    }
                ],
            )

        return fetch

    def close(self):
        return None


def _factory(source: str, dataset: str, method_name: str):
    return lambda: _Provider(source, dataset, method_name)


def _spy(calls: list[tuple[str, str]]):
    def persist(result, source, run):
        assert source.key == result.provider == run.source.key
        assert run.dataset == result.dataset
        calls.append((source.key, run.dataset))
        return len(result.records)

    return persist


def test_macro_refresh_uses_every_v2_persistence_callback(monkeypatch, db):
    monkeypatch.setattr(
        official_data,
        "BEAGDPReleaseProvider",
        _factory("bea-release", "gdp-release-workbooks", "gdp_pce"),
    )
    monkeypatch.setattr(
        official_data,
        "CensusMARTSProvider",
        _factory("census", "marts:44X72:SM:yes", "monthly_retail_sales"),
    )
    monkeypatch.setattr(
        official_data,
        "CensusMARTSReleaseProvider",
        _factory(
            "census-release",
            "marts:retail-food-services",
            "monthly_retail_sales",
        ),
    )
    monkeypatch.setattr(
        official_data,
        "BEAPIOReleaseProvider",
        _factory(
            "bea-pio-release",
            "personal-income-outlays-release",
            "personal_income_outlays",
        ),
    )
    monkeypatch.setattr(
        official_data,
        "FederalReserveG19Provider",
        _factory("federal-reserve-g19", "consumer-credit", "consumer_credit"),
    )
    monkeypatch.setattr(
        official_data,
        "NYFedHouseholdDebtProvider",
        _factory(
            "ny-fed-household-credit",
            "household-debt-credit",
            "household_debt",
        ),
    )

    bea_calls: list[tuple[str, str]] = []
    census_calls: list[tuple[str, str]] = []
    consumer_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        official_data,
        "_store_bea_release_observations_v2",
        _spy(bea_calls),
    )
    monkeypatch.setattr(
        official_data,
        "_store_census_marts_observations_v2",
        _spy(census_calls),
    )
    monkeypatch.setattr(
        official_data,
        "_store_consumer_credit_observations_v2",
        _spy(consumer_calls),
    )
    monkeypatch.setattr(
        official_data,
        "_publishable_keys_for_source_groups",
        lambda runs, groups: set(),
    )
    monkeypatch.setattr(
        official_data,
        "_keys_with_current_required_batches",
        lambda keys, runs: set(),
    )
    monkeypatch.setattr(
        official_data,
        "_mark_latest_dashboards_stale",
        lambda *args, **kwargs: None,
    )
    gdp_coordinates = []

    def coordinate_gdp(runs):
        assert transaction.get_connection().in_atomic_block
        assert [(run.source.key, run.dataset, run.status) for run in runs] == [
            (
                "bea-release",
                "gdp-release-workbooks",
                "success",
            )
        ]
        assert bea_calls == [("bea-release", "gdp-release-workbooks")]
        assert census_calls == []
        assert consumer_calls == []
        gdp_coordinates.append(runs[0].pk)
        return [], set()

    monkeypatch.setattr(
        official_data,
        "coordinate_gdp_dashboard",
        coordinate_gdp,
    )
    coordination_order = []

    def coordinate_consumer(runs):
        assert transaction.get_connection().in_atomic_block
        coordination_order.append("consumer")
        return [], set()

    def coordinate_economy(*_args):
        assert transaction.get_connection().in_atomic_block
        coordination_order.append("economy")
        assert coordination_order == ["consumer", "economy"]
        return [], set()

    monkeypatch.setattr(
        official_data,
        "coordinate_consumer_dashboard",
        coordinate_consumer,
    )
    monkeypatch.setattr(
        official_data,
        "_coordinate_economy_dashboard",
        coordinate_economy,
    )
    inflation_coordinates = []

    def coordinate_inflation(runs):
        pio_runs = [
            run
            for run in runs
            if run.source.key == "bea-pio-release"
            and run.dataset == "personal-income-outlays-release"
        ]
        assert len(pio_runs) == 1
        assert pio_runs[0].status == "success"
        assert bea_calls[-1] == (
            "bea-pio-release",
            "personal-income-outlays-release",
        )
        inflation_coordinates.append(pio_runs[0].pk)
        return [], {"inflation"}

    monkeypatch.setattr(
        official_data,
        "coordinate_inflation_dashboard",
        coordinate_inflation,
    )

    result = official_data.refresh_macro_official_data(current_year=2026)

    assert result["dashboard_keys"] == []
    assert len(gdp_coordinates) == 1
    assert len(inflation_coordinates) == 1
    assert coordination_order == ["consumer", "economy"]
    assert bea_calls == [
        ("bea-release", "gdp-release-workbooks"),
        ("bea-pio-release", "personal-income-outlays-release"),
    ]
    assert census_calls == [
        ("census", "marts:44X72:SM:yes"),
        ("census-release", "marts:retail-food-services"),
    ]
    assert consumer_calls == [
        ("federal-reserve-g19", "consumer-credit"),
        ("ny-fed-household-credit", "household-debt-credit"),
    ]


def test_broad_refresh_coordinates_consumer_before_economy(monkeypatch, db):
    class BroadProvider:
        def __getattr__(self, method_name):
            def fetch(**_kwargs):
                return ProviderResult(
                    provider=f"fixture-{method_name.replace('_', '-')}",
                    dataset=f"fixture:{method_name}",
                    records=[],
                )

            return fetch

        def close(self):
            return None

    for provider_name in (
        "NYFedMarketsProvider",
        "TreasuryRatesProvider",
        "FiscalDataProvider",
        "BLSProvider",
        "BEAPIOReleaseProvider",
        "DOLWeeklyClaimsProvider",
        "FederalReserveRSSProvider",
    ):
        monkeypatch.setattr(official_data, provider_name, BroadProvider)

    def fake_record(result, *, persist):
        _ = persist
        return SimpleNamespace(
            source=SimpleNamespace(key=result.provider),
            dataset=result.dataset,
            status="success",
            row_count=0,
            error="",
        )

    monkeypatch.setattr(official_data, "record_provider_result", fake_record)
    monkeypatch.setattr(official_data, "_has_publishable_run", lambda _runs: False)
    for coordinator_name in (
        "coordinate_employment_dashboard",
        "coordinate_inflation_dashboard",
        "_coordinate_fed_funds_dashboard",
        "_coordinate_reserves_rate_spreads_dashboard",
        "_coordinate_treasury_curve_dashboards",
        "_coordinate_liquidity_dashboard",
        "_coordinate_fed_balance_sheet_dashboard",
        "_coordinate_subsurface_dashboard",
        "_coordinate_operations_dashboard",
        "_coordinate_assets_fx_dashboard",
        "coordinate_fx_vol_dashboard",
        "_coordinate_global_dollar_dashboard",
        "_coordinate_transmission_chain_dashboard",
        "_coordinate_auction_dashboard",
        "_coordinate_rrp_tga_dashboard",
    ):
        monkeypatch.setattr(
            official_data,
            coordinator_name,
            lambda *args, **kwargs: ([], set()),
        )

    order = []

    def coordinate_consumer(runs):
        assert runs
        order.append("consumer")
        return [], set()

    def coordinate_economy(*_args):
        order.append("economy")
        return [], set()

    monkeypatch.setattr(
        official_data,
        "coordinate_consumer_dashboard",
        coordinate_consumer,
    )
    monkeypatch.setattr(
        official_data,
        "_coordinate_economy_dashboard",
        coordinate_economy,
    )

    result = official_data.refresh_official_data(current_year=2026)

    assert order == ["consumer", "economy"]
    assert result["dashboard_keys"] == []


def _install_isolation_providers(monkeypatch):
    """Stub every provider so refresh runs without network and without publish."""

    class StubProvider:
        def __getattr__(self, method_name):
            def fetch(**_kwargs):
                return ProviderResult(
                    provider=f"fixture-{method_name.replace('_', '-')}",
                    dataset=f"fixture:{method_name}",
                    records=[],
                )

            return fetch

        def close(self):
            return None

    for provider_name in (
        "BEAGDPReleaseProvider",
        "CensusMARTSProvider",
        "CensusMARTSReleaseProvider",
        "BEAPIOReleaseProvider",
        "FederalReserveG19Provider",
        "NYFedHouseholdDebtProvider",
        "NYFedMarketsProvider",
        "TreasuryRatesProvider",
        "FiscalDataProvider",
        "BLSProvider",
        "DOLWeeklyClaimsProvider",
        "FederalReserveRSSProvider",
    ):
        monkeypatch.setattr(official_data, provider_name, StubProvider)

    def fake_record(result, *, persist):
        _ = persist
        return SimpleNamespace(
            source=SimpleNamespace(key=result.provider),
            dataset=result.dataset,
            status="success",
            row_count=0,
            error="",
            metadata={},
        )

    monkeypatch.setattr(official_data, "record_provider_result", fake_record)
    monkeypatch.setattr(official_data, "_record_and_coordinate_gdp_result", lambda *a, **k: ([], set()))
    monkeypatch.setattr(official_data, "_has_publishable_run", lambda _runs: False)
    monkeypatch.setattr(
        official_data, "_keys_with_current_required_batches", lambda _a, _b: set()
    )
    monkeypatch.setattr(
        official_data, "_publishable_keys_for_source_groups", lambda _a, _b: set()
    )
    monkeypatch.setattr(official_data, "publish_official_dashboards", lambda **_k: [])


def _stub_non_strict_coordinators(monkeypatch):
    for coordinator_name in (
        "_coordinate_fed_funds_dashboard",
        "_coordinate_reserves_rate_spreads_dashboard",
        "_coordinate_treasury_curve_dashboards",
        "_coordinate_liquidity_dashboard",
        "_coordinate_fed_balance_sheet_dashboard",
        "_coordinate_subsurface_dashboard",
        "_coordinate_operations_dashboard",
        "_coordinate_assets_fx_dashboard",
        "coordinate_fx_vol_dashboard",
        "_coordinate_global_dollar_dashboard",
        "_coordinate_transmission_chain_dashboard",
        "_coordinate_auction_dashboard",
        "_coordinate_rrp_tga_dashboard",
    ):
        monkeypatch.setattr(
            official_data,
            coordinator_name,
            lambda *args, **kwargs: ([], set()),
        )


def test_macro_refresh_isolates_inflation_postcondition_failure(monkeypatch, db):
    """An inflation postcondition error must not abort consumer/economy publication."""
    from research.inflation_contract import InflationPublicationPostconditionError

    _install_isolation_providers(monkeypatch)
    _stub_non_strict_coordinators(monkeypatch)

    executed = []

    def coordinate_inflation(runs):
        executed.append("inflation")
        raise InflationPublicationPostconditionError(
            "inflation publication is not the current replayable revision"
        )

    def coordinate_consumer(runs):
        executed.append("consumer")
        return [], set()

    def coordinate_economy(*_args):
        executed.append("economy")
        return [], set()

    monkeypatch.setattr(
        official_data, "coordinate_inflation_dashboard", coordinate_inflation
    )
    monkeypatch.setattr(
        official_data, "coordinate_consumer_dashboard", coordinate_consumer
    )
    monkeypatch.setattr(
        official_data, "_coordinate_economy_dashboard", coordinate_economy
    )

    result = official_data.refresh_macro_official_data(current_year=2026)

    # All three coordinators ran; inflation's failure did not abort the rest.
    assert executed == ["inflation", "consumer", "economy"]
    # The failed child is reported stale, not as a published dashboard.
    assert "inflation" in result["stale_dashboard_keys"]
    assert result["dashboard_keys"] == []


def test_broad_refresh_isolates_employment_postcondition_failure(monkeypatch, db):
    """An employment postcondition error must not abort inflation/consumer/economy."""
    from research.employment_contract import EmploymentPublicationPostconditionError

    _install_isolation_providers(monkeypatch)
    _stub_non_strict_coordinators(monkeypatch)

    executed = []

    def coordinate_employment(runs):
        executed.append("employment")
        raise EmploymentPublicationPostconditionError(
            "employment publication is not the current replayable revision"
        )

    def coordinate_inflation(runs):
        executed.append("inflation")
        return [], set()

    def coordinate_consumer(runs):
        executed.append("consumer")
        return [], set()

    def coordinate_economy(*_args):
        executed.append("economy")
        return [], set()

    monkeypatch.setattr(
        official_data, "coordinate_employment_dashboard", coordinate_employment
    )
    monkeypatch.setattr(
        official_data, "coordinate_inflation_dashboard", coordinate_inflation
    )
    monkeypatch.setattr(
        official_data, "coordinate_consumer_dashboard", coordinate_consumer
    )
    monkeypatch.setattr(
        official_data, "_coordinate_economy_dashboard", coordinate_economy
    )

    result = official_data.refresh_official_data(current_year=2026)

    assert executed == ["employment", "inflation", "consumer", "economy"]
    assert "employment" in result["stale_dashboard_keys"]
    assert result["dashboard_keys"] == []


def test_broad_refresh_re_raises_unrelated_coordinator_errors(monkeypatch, db):
    """A non-postcondition coordinator bug must still abort the refresh."""
    import pytest

    _install_isolation_providers(monkeypatch)
    _stub_non_strict_coordinators(monkeypatch)

    def coordinate_employment(runs):
        raise RuntimeError("genuine coordinator corruption")

    monkeypatch.setattr(
        official_data, "coordinate_employment_dashboard", coordinate_employment
    )
    monkeypatch.setattr(
        official_data,
        "coordinate_inflation_dashboard",
        lambda runs: ([], set()),
    )
    monkeypatch.setattr(
        official_data,
        "coordinate_consumer_dashboard",
        lambda runs: ([], set()),
    )
    monkeypatch.setattr(
        official_data, "_coordinate_economy_dashboard", lambda *a, **k: ([], set())
    )

    # A RuntimeError is not a postcondition error: it must propagate unchanged.
    with pytest.raises(RuntimeError, match="genuine coordinator corruption"):
        official_data.refresh_official_data(current_year=2026)
