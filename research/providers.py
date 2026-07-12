"""Small, side-effect-free adapters for public and official upstream APIs.

Providers never perform I/O during construction.  Every fetch returns a
``ProviderResult`` so a missing credential, rate limit, or upstream outage can
be persisted as ingestion metadata instead of crashing a Celery worker.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime
from pathlib import PurePosixPath
from typing import Any, Protocol, runtime_checkable
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx


@dataclass(slots=True)
class ProviderResult:
    provider: str
    dataset: str
    records: list[dict[str, Any]] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    skipped: bool = False
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.error and not self.skipped

    @property
    def row_count(self) -> int:
        return len(self.records)

    @classmethod
    def skip(cls, provider: str, dataset: str, reason: str) -> ProviderResult:
        return cls(provider=provider, dataset=dataset, skipped=True, metadata={"reason": reason})

    @classmethod
    def failure(cls, provider: str, dataset: str, error: str) -> ProviderResult:
        return cls(provider=provider, dataset=dataset, error=error[:2000])


@runtime_checkable
class DataProvider(Protocol):
    key: str

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult: ...


class HTTPProvider:
    key = "http"
    base_url = ""

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout: float = 20.0,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self._owns_client = client is None
        self.client = client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
            headers=dict(headers or {}),
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def __enter__(self) -> HTTPProvider:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def _get_json(
        self,
        dataset: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> tuple[Any | None, ProviderResult | None]:
        try:
            response = self.client.get(path, params=params, headers=headers)
            response.raise_for_status()
            return response.json(), None
        except (httpx.HTTPError, ValueError) as exc:
            return None, ProviderResult.failure(self.key, dataset, f"{type(exc).__name__}: {exc}")

    def _post_json(
        self,
        dataset: str,
        path: str,
        *,
        json: Mapping[str, Any],
        headers: Mapping[str, str] | None = None,
    ) -> tuple[Any | None, ProviderResult | None]:
        try:
            response = self.client.post(path, json=dict(json), headers=headers)
            response.raise_for_status()
            return response.json(), None
        except (httpx.HTTPError, ValueError) as exc:
            return None, ProviderResult.failure(self.key, dataset, f"{type(exc).__name__}: {exc}")

    def _get_text(
        self,
        dataset: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[str | None, ProviderResult | None]:
        try:
            response = self.client.get(path, params=params)
            response.raise_for_status()
            return response.text, None
        except httpx.HTTPError as exc:
            return None, ProviderResult.failure(self.key, dataset, f"{type(exc).__name__}: {exc}")

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        method = getattr(self, dataset, None)
        if method is None or dataset.startswith("_"):
            return ProviderResult.failure(self.key, dataset, f"unsupported dataset: {dataset}")
        return method(**kwargs)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, "", "."):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


class FREDProvider(HTTPProvider):
    """Federal Reserve Economic Data adapter.

    FRED requires an API key.  With no key the provider returns a skipped
    result without making a network call.
    """

    key = "fred"
    base_url = "https://api.stlouisfed.org/fred"

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        self.api_key = api_key or os.getenv("FRED_API_KEY", "")
        super().__init__(**kwargs)

    def series_observations(
        self,
        series_id: str,
        *,
        observation_start: str | None = None,
        limit: int | None = None,
    ) -> ProviderResult:
        dataset = f"series:{series_id}"
        if not self.api_key:
            return ProviderResult.skip(self.key, dataset, "FRED_API_KEY is not configured")
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "asc",
        }
        if observation_start:
            params["observation_start"] = observation_start
        if limit:
            params["limit"] = limit
        payload, failure = self._get_json(dataset, "/series/observations", params=params)
        if failure:
            return failure
        records = []
        for item in payload.get("observations", []):
            value = _decimal_or_none(item.get("value"))
            if value is None:
                continue
            records.append(
                {
                    "series_id": series_id,
                    "date": item.get("date"),
                    "value": value,
                    "realtime_start": item.get("realtime_start"),
                    "realtime_end": item.get("realtime_end"),
                }
            )
        return ProviderResult(
            provider=self.key,
            dataset=dataset,
            records=records,
            metadata={"count": payload.get("count", len(records))},
        )

    def fetch(self, dataset: str, **kwargs: Any) -> ProviderResult:
        if dataset in {"series", "series_observations"}:
            return self.series_observations(**kwargs)
        return self.series_observations(dataset, **kwargs)


class NYFedMarketsProvider(HTTPProvider):
    """New York Fed reference rates published for unrestricted public use."""

    key = "ny-fed-markets"
    base_url = "https://markets.newyorkfed.org"

    RATE_GROUPS = {"SOFR": "secured", "EFFR": "unsecured"}

    def reference_rate(self, rate_type: str, *, limit: int = 120) -> ProviderResult:
        rate_type = rate_type.upper()
        dataset = f"reference-rate:{rate_type.lower()}"
        group = self.RATE_GROUPS.get(rate_type)
        if group is None:
            return ProviderResult.failure(self.key, dataset, f"unsupported rate: {rate_type}")
        payload, failure = self._get_json(
            dataset,
            f"/api/rates/{group}/{rate_type.lower()}/last/{int(limit)}.json",
        )
        if failure:
            return failure
        records = []
        for item in payload.get("refRates", []):
            value = _decimal_or_none(item.get("percentRate"))
            if value is None or not item.get("effectiveDate"):
                continue
            metadata = {
                key: item.get(key)
                for key in (
                    "percentPercentile1",
                    "percentPercentile25",
                    "percentPercentile75",
                    "percentPercentile99",
                    "targetRateFrom",
                    "targetRateTo",
                    "volumeInBillions",
                    "revisionIndicator",
                )
                if item.get(key) is not None
            }
            records.append(
                {
                    "series_id": rate_type,
                    "date": item["effectiveDate"],
                    "value": value,
                    "metadata": metadata,
                }
            )
        return ProviderResult(provider=self.key, dataset=dataset, records=records)

    def sofr(self, *, limit: int = 120) -> ProviderResult:
        return self.reference_rate("SOFR", limit=limit)

    def effr(self, *, limit: int = 120) -> ProviderResult:
        return self.reference_rate("EFFR", limit=limit)


class TreasuryRatesProvider(HTTPProvider):
    """Direct U.S. Treasury nominal and real par-yield curve adapter."""

    key = "us-treasury-rates"
    base_url = "https://home.treasury.gov"
    NOMINAL_FIELDS = {
        "BC_1MONTH": "UST-1M",
        "BC_2MONTH": "UST-2M",
        "BC_3MONTH": "UST-3M",
        "BC_4MONTH": "UST-4M",
        "BC_6MONTH": "UST-6M",
        "BC_1YEAR": "UST-1Y",
        "BC_2YEAR": "UST-2Y",
        "BC_3YEAR": "UST-3Y",
        "BC_5YEAR": "UST-5Y",
        "BC_7YEAR": "UST-7Y",
        "BC_10YEAR": "UST-10Y",
        "BC_20YEAR": "UST-20Y",
        "BC_30YEAR": "UST-30Y",
    }
    REAL_FIELDS = {
        "TC_5YEAR": "TIPS-5Y",
        "TC_7YEAR": "TIPS-7Y",
        "TC_10YEAR": "TIPS-10Y",
        "TC_20YEAR": "TIPS-20Y",
        "TC_30YEAR": "TIPS-30Y",
    }
    XML_NS = {
        "atom": "http://www.w3.org/2005/Atom",
        "meta": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
    }

    def _curve(self, *, curve: str, fields: Mapping[str, str], year: int) -> ProviderResult:
        dataset = f"{curve}:{year}"
        payload, failure = self._get_text(
            dataset,
            "/resource-center/data-chart-center/interest-rates/pages/xml",
            params={"data": curve, "field_tdr_date_value": str(year)},
        )
        if failure:
            return failure
        try:
            root = ElementTree.fromstring(payload or "")
        except ElementTree.ParseError as exc:
            return ProviderResult.failure(self.key, dataset, f"ParseError: {exc}")

        records = []
        for entry in root.findall("atom:entry", self.XML_NS):
            properties = entry.find("atom:content/meta:properties", self.XML_NS)
            if properties is None:
                continue
            values = {child.tag.rsplit("}", 1)[-1]: child.text for child in properties}
            value_date = (values.get("NEW_DATE") or "")[:10]
            if not value_date:
                continue
            for field_name, series_id in fields.items():
                value = _decimal_or_none(values.get(field_name))
                if value is None:
                    continue
                records.append(
                    {
                        "series_id": series_id,
                        "date": value_date,
                        "value": value,
                        "metadata": {"treasury_field": field_name, "curve": curve},
                    }
                )
        return ProviderResult(provider=self.key, dataset=dataset, records=records)

    def yield_curve(self, *, year: int | None = None) -> ProviderResult:
        return self._curve(
            curve="daily_treasury_yield_curve",
            fields=self.NOMINAL_FIELDS,
            year=year or datetime.now(UTC).year,
        )

    def real_yield_curve(self, *, year: int | None = None) -> ProviderResult:
        return self._curve(
            curve="daily_treasury_real_yield_curve",
            fields=self.REAL_FIELDS,
            year=year or datetime.now(UTC).year,
        )


class FiscalDataProvider(HTTPProvider):
    """Treasury FiscalData adapter for the Daily Treasury Statement."""

    key = "treasury-fiscal-data"
    base_url = "https://api.fiscaldata.treasury.gov"

    def tga(self, *, page_size: int = 400) -> ProviderResult:
        dataset = "daily-treasury-statement:tga"
        payload, failure = self._get_json(
            dataset,
            "/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance",
            params={"sort": "-record_date", "page[size]": min(int(page_size), 10000)},
        )
        if failure:
            return failure
        records = []
        for item in payload.get("data", []):
            if item.get("account_type") != "Treasury General Account (TGA) Closing Balance":
                continue
            value = _decimal_or_none(item.get("open_today_bal"))
            if value is None:
                continue
            records.append(
                {
                    "series_id": "TGA",
                    "date": item.get("record_date"),
                    "value": value,
                    "metadata": {"unit": "USD millions", "account_type": item["account_type"]},
                }
            )
        return ProviderResult(provider=self.key, dataset=dataset, records=records)

    def treasury_auctions(self, *, page_size: int = 1000) -> ProviderResult:
        dataset = "treasury-securities-auctions"
        payload, failure = self._get_json(
            dataset,
            "/services/api/fiscal_service/v1/accounting/od/auctions_query",
            params={"sort": "-auction_date", "page[size]": min(int(page_size), 10000)},
        )
        if failure:
            return failure
        fields = (
            "offering_amt",
            "total_tendered",
            "total_accepted",
            "bid_to_cover_ratio",
            "high_yield",
            "indirect_bidder_accepted",
            "direct_bidder_accepted",
            "primary_dealer_accepted",
        )
        records = []
        for item in payload.get("data", []):
            if not item.get("cusip") or not item.get("auction_date"):
                continue
            record = {
                "cusip": item["cusip"],
                "security_type": item.get("security_type") or "",
                "security_term": item.get("security_term") or "",
                "announcement_date": item.get("announcemt_date"),
                "auction_date": item["auction_date"],
                "issue_date": item.get("issue_date"),
                "maturity_date": item.get("maturity_date"),
            }
            record.update({field: _decimal_or_none(item.get(field)) for field in fields})
            records.append(record)
        return ProviderResult(provider=self.key, dataset=dataset, records=records)


class BLSProvider(HTTPProvider):
    """BLS Public Data API v2 adapter; no registration key is required for small pulls."""

    key = "bls"
    base_url = "https://api.bls.gov"

    def series(
        self,
        series_ids: list[str] | tuple[str, ...],
        *,
        start_year: int,
        end_year: int,
    ) -> ProviderResult:
        dataset = "series:" + ",".join(series_ids)
        body: dict[str, Any] = {
            "seriesid": list(series_ids),
            "startyear": str(start_year),
            "endyear": str(end_year),
        }
        registration_key = os.getenv("BLS_REGISTRATION_KEY", "")
        if registration_key:
            body["registrationkey"] = registration_key
        payload, failure = self._post_json(
            dataset,
            "/publicAPI/v2/timeseries/data/",
            json=body,
        )
        if failure:
            return failure
        if payload.get("status") != "REQUEST_SUCCEEDED":
            return ProviderResult.failure(
                self.key,
                dataset,
                "; ".join(payload.get("message") or ["BLS request failed"]),
            )
        records = []
        for series in payload.get("Results", {}).get("series", []):
            series_id = series.get("seriesID")
            for item in series.get("data", []):
                period = item.get("period", "")
                if not series_id or not period.startswith("M") or period == "M13":
                    continue
                value = _decimal_or_none(item.get("value"))
                if value is None:
                    continue
                month = int(period[1:])
                records.append(
                    {
                        "series_id": series_id,
                        "date": f"{int(item['year']):04d}-{month:02d}-01",
                        "value": value,
                        "metadata": {
                            "period_name": item.get("periodName"),
                            "latest": item.get("latest") == "true",
                            "footnotes": item.get("footnotes", []),
                        },
                    }
                )
        return ProviderResult(provider=self.key, dataset=dataset, records=records)


class CFTCProvider(HTTPProvider):
    """CFTC Public Reporting Environment Commitments of Traders adapter."""

    key = "cftc"
    base_url = "https://publicreporting.cftc.gov"
    DATASETS = {
        "tff-futures": "gpe5-46if",
        "tff-combined": "yw9f-hn96",
        "disaggregated-futures": "72hh-3qpy",
        "disaggregated-combined": "kh3c-gbw2",
        "legacy-futures": "6dca-aqww",
        "legacy-combined": "jun7-fc8e",
    }

    def positions(
        self,
        *,
        report_type: str = "tff-futures",
        start_date: str | None = None,
        limit: int = 50000,
    ) -> ProviderResult:
        dataset_id = self.DATASETS.get(report_type)
        dataset = f"cot:{report_type}"
        if dataset_id is None:
            return ProviderResult.failure(self.key, dataset, f"unsupported report: {report_type}")
        params: dict[str, Any] = {
            "$select": (
                "report_date_as_yyyy_mm_dd,contract_market_name,"
                "cftc_contract_market_code,open_interest_all,"
                "asset_mgr_positions_long,asset_mgr_positions_short,"
                "lev_money_positions_long,lev_money_positions_short"
            ),
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": min(int(limit), 50000),
        }
        if start_date:
            params["$where"] = (
                f"report_date_as_yyyy_mm_dd >= '{start_date}T00:00:00.000'"
            )
        payload, failure = self._get_json(dataset, f"/resource/{dataset_id}.json", params=params)
        if failure:
            return failure
        groups = {
            "asset-manager": ("asset_mgr_positions_long", "asset_mgr_positions_short"),
            "leveraged-money": ("lev_money_positions_long", "lev_money_positions_short"),
        }
        records = []
        for item in payload:
            market_code = item.get("cftc_contract_market_code")
            report_date = (item.get("report_date_as_yyyy_mm_dd") or "")[:10]
            if not market_code or not report_date:
                continue
            open_interest = _decimal_or_none(item.get("open_interest_all"))
            for trader_group, (long_key, short_key) in groups.items():
                long_positions = _decimal_or_none(item.get(long_key))
                short_positions = _decimal_or_none(item.get(short_key))
                if long_positions is None or short_positions is None:
                    continue
                records.append(
                    {
                        "report_type": report_type,
                        "report_date": report_date,
                        "market_code": market_code,
                        "market_name": item.get("contract_market_name") or market_code,
                        "trader_group": trader_group,
                        "long_positions": int(long_positions),
                        "short_positions": int(short_positions),
                        "open_interest": int(open_interest) if open_interest is not None else None,
                    }
                )
        return ProviderResult(
            provider=self.key,
            dataset=dataset,
            records=records,
            metadata={"dataset_id": dataset_id, "source_rows": len(payload)},
        )


class FederalReserveRSSProvider(HTTPProvider):
    """Federal Reserve Board RSS metadata for statements, releases and speeches."""

    key = "federal-reserve"
    base_url = "https://www.federalreserve.gov"
    FEEDS = {
        "press-monetary": "/feeds/press_monetary.xml",
        "press-all": "/feeds/press_all.xml",
        "speeches": "/feeds/speeches.xml",
    }

    def feed(self, feed_name: str, *, document_type: str) -> ProviderResult:
        dataset = f"rss:{feed_name}"
        path = self.FEEDS.get(feed_name)
        if path is None:
            return ProviderResult.failure(self.key, dataset, f"unsupported feed: {feed_name}")
        payload, failure = self._get_text(dataset, path)
        if failure:
            return failure
        try:
            root = ElementTree.fromstring((payload or "").lstrip("\ufeff"))
        except ElementTree.ParseError as exc:
            return ProviderResult.failure(self.key, dataset, f"ParseError: {exc}")
        records = []
        for item in root.findall(".//item"):
            values = {child.tag: (child.text or "").strip() for child in item}
            url = values.get("link") or values.get("guid")
            title = values.get("title")
            if not url or not title:
                continue
            filename = PurePosixPath(urlparse(url).path).stem
            published = parsedate_to_datetime(values["pubDate"]) if values.get("pubDate") else None
            records.append(
                {
                    "slug": filename.lower(),
                    "document_type": document_type,
                    "title": title,
                    "summary": values.get("description", ""),
                    "published_at": published.isoformat() if published else None,
                    "original_url": url,
                    "category": values.get("category", ""),
                }
            )
        return ProviderResult(provider=self.key, dataset=dataset, records=records)


class SECProvider(HTTPProvider):
    """SEC submissions and company-facts adapter."""

    key = "sec"
    base_url = "https://data.sec.gov"

    def __init__(self, user_agent: str | None = None, **kwargs: Any) -> None:
        self.user_agent = user_agent or os.getenv("SEC_USER_AGENT", "")
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        headers.setdefault("Accept-Encoding", "gzip, deflate")
        super().__init__(headers=headers, **kwargs)

    def _require_identity(self, dataset: str) -> ProviderResult | None:
        if self.user_agent:
            return None
        return ProviderResult.skip(
            self.key,
            dataset,
            "SEC_USER_AGENT is not configured (use 'product contact@example.com')",
        )

    @staticmethod
    def normalize_cik(cik: str | int) -> str:
        digits = "".join(character for character in str(cik) if character.isdigit())
        if not digits:
            raise ValueError("CIK must contain digits")
        return digits.zfill(10)

    def submissions(self, cik: str | int) -> ProviderResult:
        normalized = self.normalize_cik(cik)
        dataset = f"submissions:{normalized}"
        if skipped := self._require_identity(dataset):
            return skipped
        payload, failure = self._get_json(dataset, f"/submissions/CIK{normalized}.json")
        if failure:
            return failure
        return ProviderResult(provider=self.key, dataset=dataset, records=[payload])

    def company_facts(self, cik: str | int) -> ProviderResult:
        normalized = self.normalize_cik(cik)
        dataset = f"companyfacts:{normalized}"
        if skipped := self._require_identity(dataset):
            return skipped
        payload, failure = self._get_json(dataset, f"/api/xbrl/companyfacts/CIK{normalized}.json")
        if failure:
            return failure
        return ProviderResult(provider=self.key, dataset=dataset, records=[payload])


class GitHubProvider(HTTPProvider):
    key = "github"
    base_url = "https://api.github.com"

    def __init__(self, token: str | None = None, **kwargs: Any) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.setdefault("Accept", "application/vnd.github+json")
        headers.setdefault("X-GitHub-Api-Version", "2022-11-28")
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        super().__init__(headers=headers, **kwargs)

    def repository(self, repo: str) -> ProviderResult:
        dataset = f"repository:{repo}"
        if repo.count("/") != 1:
            return ProviderResult.failure(self.key, dataset, "repo must be in owner/name form")
        payload, failure = self._get_json(dataset, f"/repos/{repo}")
        if failure:
            return failure
        record = {
            "repo": payload.get("full_name", repo),
            "description": payload.get("description") or "",
            "stars": payload.get("stargazers_count", 0),
            "forks": payload.get("forks_count", 0),
            "open_issues": payload.get("open_issues_count", 0),
            "pushed_at": payload.get("pushed_at"),
            "homepage": payload.get("html_url", f"https://github.com/{repo}"),
            "topics": payload.get("topics", []),
        }
        return ProviderResult(
            provider=self.key,
            dataset=dataset,
            records=[record],
            metadata={"authenticated": bool(self.token)},
        )


class OKXProvider(HTTPProvider):
    key = "okx"
    base_url = "https://www.okx.com"

    def market_tickers(self, inst_type: str = "SPOT") -> ProviderResult:
        dataset = f"market-tickers:{inst_type.upper()}"
        payload, failure = self._get_json(
            dataset, "/api/v5/market/tickers", params={"instType": inst_type.upper()}
        )
        if failure:
            return failure
        if str(payload.get("code", "0")) != "0":
            return ProviderResult.failure(self.key, dataset, payload.get("msg", "OKX API error"))
        return ProviderResult(
            provider=self.key, dataset=dataset, records=list(payload.get("data", []))
        )

    def ticker(self, instrument_id: str) -> ProviderResult:
        dataset = f"ticker:{instrument_id}"
        payload, failure = self._get_json(
            dataset, "/api/v5/market/ticker", params={"instId": instrument_id}
        )
        if failure:
            return failure
        if str(payload.get("code", "0")) != "0":
            return ProviderResult.failure(self.key, dataset, payload.get("msg", "OKX API error"))
        return ProviderResult(
            provider=self.key, dataset=dataset, records=list(payload.get("data", []))
        )


class DeribitProvider(HTTPProvider):
    key = "deribit"
    base_url = "https://www.deribit.com"

    def book_summary(self, currency: str = "BTC", kind: str = "option") -> ProviderResult:
        dataset = f"book-summary:{currency.upper()}:{kind}"
        payload, failure = self._get_json(
            dataset,
            "/api/v2/public/get_book_summary_by_currency",
            params={"currency": currency.upper(), "kind": kind},
        )
        if failure:
            return failure
        if payload.get("error"):
            return ProviderResult.failure(self.key, dataset, str(payload["error"]))
        return ProviderResult(
            provider=self.key,
            dataset=dataset,
            records=list(payload.get("result", [])),
        )

    def instruments(
        self, currency: str = "BTC", kind: str = "option", expired: bool = False
    ) -> ProviderResult:
        dataset = f"instruments:{currency.upper()}:{kind}"
        payload, failure = self._get_json(
            dataset,
            "/api/v2/public/get_instruments",
            params={"currency": currency.upper(), "kind": kind, "expired": str(expired).lower()},
        )
        if failure:
            return failure
        if payload.get("error"):
            return ProviderResult.failure(self.key, dataset, str(payload["error"]))
        return ProviderResult(
            provider=self.key,
            dataset=dataset,
            records=list(payload.get("result", [])),
        )


# Conventional aliases keep imports ergonomic without weakening the canonical
# acronym-preserving class names.
FredProvider = FREDProvider
SecProvider = SECProvider
GithubProvider = GitHubProvider
OkxProvider = OKXProvider
NyFedMarketsProvider = NYFedMarketsProvider
TreasuryProvider = TreasuryRatesProvider
FiscalDataTreasuryProvider = FiscalDataProvider
