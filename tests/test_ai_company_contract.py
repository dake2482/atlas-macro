from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.models import Company, SupplyChainNode
from research.public_ai_contract import PUBLIC_AI_COMPANY_CONTRACT_SLUGS

CONTRACT_FILE = Path(__file__).resolve().parents[1] / "assets/timsun_public_ai_contract.json"
COMPANY_ROUTE_PREFIX = "/ai-industry/company/"


def _manifest_company_paths() -> list[str]:
    payload = json.loads(CONTRACT_FILE.read_text(encoding="utf-8"))
    return [
        item["path"]
        for item in payload["routes"]
        if item.get("family") == "company"
    ]


def _slug_from_path(path: str) -> str:
    assert path.startswith(COMPANY_ROUTE_PREFIX) and path.endswith("/")
    return path.removeprefix(COMPANY_ROUTE_PREFIX).removesuffix("/")


def test_compiled_company_contract_exactly_matches_audit_manifest():
    paths = _manifest_company_paths()

    assert len(paths) == 219
    assert len(paths) == len(set(paths))
    assert {_slug_from_path(path) for path in paths} == PUBLIC_AI_COMPANY_CONTRACT_SLUGS


@pytest.mark.django_db
def test_all_219_missing_company_contract_routes_return_transparent_pending_pages(client):
    paths = _manifest_company_paths()
    original_company_count = Company.objects.count()

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "公司数据待接入".encode() in response.content, path
        assert _slug_from_path(path).encode() in response.content, path
        assert b'<meta name="robots" content="noindex,nofollow">' in response.content, path
        assert b'class="metric-card"' not in response.content, path

    assert Company.objects.count() == original_company_count


@pytest.mark.django_db
def test_public_database_company_keeps_the_sourced_company_detail(client):
    node = SupplyChainNode.objects.create(
        slug="verified-gpu-node",
        name="Verified GPU node",
        layer="compute",
        description="Reviewed node",
        source_note="Official company filing",
    )
    Company.objects.create(
        slug="nvidia",
        name="VERIFIED-COMPANY-DETAIL",
        ticker="NVDA",
        primary_node=node,
        description="Reviewed company record",
        data_source_note="SEC filing and official investor relations",
        investor_relations_url="https://investor.nvidia.com/",
    )

    response = client.get("/ai-industry/company/nvidia/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "VERIFIED-COMPANY-DETAIL" in body
    assert "公司数据待接入" not in body
    assert '<meta name="robots" content="index,follow">' in body


@pytest.mark.django_db
def test_unreviewed_database_row_does_not_replace_contract_pending_page(client):
    node = SupplyChainNode.objects.create(
        slug="unreviewed-contract-node",
        name="Unreviewed contract node",
        layer="test",
        description="Unreviewed node",
        source_note="Official source",
    )
    Company.objects.create(
        slug="nvidia",
        name="UNREVIEWED-COMPANY-MUST-NOT-LEAK",
        ticker="NVDA",
        primary_node=node,
        description="No source record",
        data_source_note="",
    )

    response = client.get("/ai-industry/company/nvidia/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "公司数据待接入" in body
    assert "UNREVIEWED-COMPANY-MUST-NOT-LEAK" not in body
    assert Company.objects.count() == 1


@pytest.mark.django_db
def test_unknown_company_slug_remains_not_found(client):
    response = client.get("/ai-industry/company/not-in-the-audited-contract/")

    assert response.status_code == 404
    assert Company.objects.count() == 0
