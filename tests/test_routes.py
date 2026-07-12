from __future__ import annotations

import pytest

from research.context_processors import NAV_GROUPS
from research.models import (
    CodingAgentProfile,
    Company,
    FedDocument,
    FundLetter,
    ModelProfile,
    SupplyChainNode,
    Thesis,
)

STATIC_PUBLIC_PATHS = [
    "/",
    "/regime-log/",
    "/daily-report/",
    "/search/",
    "/news/",
    "/semiconductor-news/",
    "/research/reports/",
    "/research/reports/all/",
    "/research/fund-letters/",
    "/glossary/",
    "/assets/",
    "/assets/equities/",
    "/assets/etfs/",
    "/assets/equities/options/",
    "/assets/equities/positioning/",
    "/assets/bonds/",
    "/assets/commodities/",
    "/assets/fx/",
    "/assets/crypto/",
    "/assets/crypto/derivatives/",
    "/rates/",
    "/rates/fed-funds/",
    "/rates/yield-curve/",
    "/rates/auctions/",
    "/rates/real-rates/",
    "/rates/expectations/",
    "/fed/",
    "/fed/statements/",
    "/fed/speeches/",
    "/fed/news/",
    "/fed/hawkish-dovish/",
    "/liquidity/",
    "/liquidity/transmission-chain/",
    "/liquidity/fed-balance-sheet/",
    "/liquidity/operations/",
    "/liquidity/rrp-tga/",
    "/liquidity/reserves/",
    "/liquidity/global-dollar/",
    "/liquidity/subsurface/",
    "/economy/",
    "/economy/gdp/",
    "/economy/employment/",
    "/economy/inflation/",
    "/economy/consumer/",
    "/volatility/",
    "/volatility/dashboard/",
    "/volatility/vix/",
    "/credit/",
    "/credit/spreads/",
    "/credit/cds/",
    "/credit/stress/",
    "/ai-industry/",
    "/ai-industry/market-map/",
    "/ai-industry/graph/",
    "/ai-industry/news/",
    "/ai-industry/chain/",
    "/ai-industry/chain/semiconductor-manufacturing/",
    "/ai-industry/chain/model-evolution/",
    "/ai-industry/chain/applications/",
    "/ai-industry/chain/glossary/",
    "/ai-industry/chain/teardown/",
]


def test_route_contract_covers_every_navigation_item():
    nav_paths = {path for group in NAV_GROUPS for _label, path in group["items"]}
    assert nav_paths <= set(STATIC_PUBLIC_PATHS)


@pytest.mark.django_db
@pytest.mark.parametrize("path", STATIC_PUBLIC_PATHS)
def test_public_routes_render(client, seeded_platform, path):
    response = client.get(path)
    assert response.status_code == 200, path


@pytest.mark.django_db
def test_dynamic_detail_routes_render(client, seeded_platform):
    objects = [
        Thesis.objects.order_by("date").first(),
        FundLetter.objects.order_by("pk").first(),
        SupplyChainNode.objects.order_by("pk").first(),
        Company.objects.order_by("pk").first(),
    ]

    assert all(objects), "seed_platform must provide one example of every detail page"
    for obj in objects:
        response = client.get(obj.get_absolute_url())
        assert response.status_code == 200, obj.get_absolute_url()

    fed_document = FedDocument.objects.order_by("pk").first()
    model = ModelProfile.objects.order_by("pk").first()
    agent = CodingAgentProfile.objects.order_by("pk").first()
    assert fed_document and model and agent

    fed_prefix = {
        FedDocument.DocumentType.STATEMENT: "statements",
        FedDocument.DocumentType.SPEECH: "speeches",
        FedDocument.DocumentType.NEWS: "news",
    }[fed_document.document_type]
    dynamic_paths = [
        f"/fed/{fed_prefix}/{fed_document.slug}/",
        f"/ai-industry/chain/model-evolution/model/{model.slug}/",
        f"/ai-industry/vibe-coding/{agent.slug}/",
    ]
    for path in dynamic_paths:
        assert client.get(path).status_code == 200, path


@pytest.mark.django_db
@pytest.mark.parametrize("path", ["/credit/issuance/", "/credit/events/"])
def test_retired_credit_routes_return_gone(client, path):
    response = client.get(path)
    assert response.status_code == 410
    assert "不再提供" in response.content.decode() or "gone" in response.content.decode().lower()


@pytest.mark.django_db
def test_unknown_route_returns_404(client):
    assert client.get("/this-route-must-never-exist/").status_code == 404


@pytest.mark.django_db
def test_health_endpoint_is_cache_safe(client):
    response = client.get("/healthz/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
