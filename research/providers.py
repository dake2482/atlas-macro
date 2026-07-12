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
from typing import Any, Protocol, runtime_checkable

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
