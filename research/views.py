from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

from django.conf import settings
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
)
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Avg, Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

from .calculations import percentile_rank
from .models import (
    CFTCPosition,
    CodingAgentProfile,
    Company,
    DashboardSnapshot,
    DataRequirement,
    FedDocument,
    FundLetter,
    GitHubProject,
    GlossaryTerm,
    Instrument,
    MarketBar,
    ModelProfile,
    NewsItem,
    Observation,
    OptionContract,
    ResearchMention,
    Source,
    SourceLicense,
    SupplyChainEdge,
    SupplyChainNode,
    Thesis,
)
from .page_registry import get_page_config


def _breadcrumbs(*items):
    return [{"label": label, "url": url} for label, url in items]


def _text_search(queryset, query: str, fields: list[str], similarity_field: str):
    """Use PostgreSQL FTS/trigram in production and deterministic LIKE in SQLite."""

    if not query:
        return queryset
    if connection.vendor == "postgresql":
        vector = SearchVector(*fields, config="simple")
        search_query = SearchQuery(query, config="simple", search_type="plain")
        return (
            queryset.annotate(
                _search_rank=SearchRank(vector, search_query),
                _trigram_rank=TrigramSimilarity(similarity_field, query),
            )
            .filter(Q(_search_rank__gte=0.01) | Q(_trigram_rank__gte=0.1))
            .order_by("-_search_rank", "-_trigram_rank")
        )
    condition = Q()
    for field in fields:
        condition |= Q(**{f"{field}__icontains": query})
    return queryset.filter(condition)


def _latest_observation(symbol: str):
    return (
        Observation.objects.filter(instrument__symbol=symbol)
        .exclude(source__key="demo-market")
        .filter(source__licenses__public_display_allowed=True)
        .select_related("instrument", "source", "fallback_source")
        .distinct()
        .order_by("-value_date")
        .first()
    )


def _market_card(symbol: str, fallback_name: str):
    obs = _latest_observation(symbol)
    if not obs:
        return {
            "symbol": symbol,
            "name": fallback_name,
            "value": "—",
            "change": "—",
            "as_of": "等待首批数据",
            "source": "未连接",
            "status": "stale",
        }
    previous = (
        Observation.objects.filter(instrument=obs.instrument, value_date__lt=obs.value_date)
        .exclude(source__key="demo-market")
        .filter(source__licenses__public_display_allowed=True)
        .distinct()
        .order_by("-value_date")
        .first()
    )
    change = None
    if previous and previous.value:
        change = (obs.value - previous.value) / previous.value * Decimal("100")
    return {
        "symbol": symbol,
        "name": obs.instrument.name,
        "value": f"{obs.value:,.2f}",
        "change": f"{change:+.2f}%" if change is not None else "—",
        "as_of": obs.as_of,
        "source": obs.source.name,
        "status": obs.quality_status,
    }


def home(request):
    thesis = Thesis.objects.exclude(summary__startswith="演示日报 ").order_by("-date").first()
    market_cards = [
        _market_card("SPY", "标普 500 ETF"),
        _market_card("QQQ", "纳斯达克 100 ETF"),
        _market_card("TLT", "长久期美债"),
        _market_card("HYG", "高收益信用"),
        _market_card("CL=F", "WTI 原油"),
        _market_card("BTC-USD", "比特币"),
    ]
    evidence = thesis.evidence[:3] if thesis and isinstance(thesis.evidence, list) else []
    normalized_evidence = []
    for item in evidence:
        if isinstance(item, dict):
            normalized_evidence.append(item)
        else:
            normalized_evidence.append({"label": "已审核证据", "value": "—", "detail": str(item)})
    latest_snapshot = (
        DashboardSnapshot.objects.filter(is_published=True)
        .filter(Q(data__demo=False) | ~Q(data__has_key="demo"))
        .exclude(source__key="demo-market")
        .select_related("source")
        .order_by("-as_of", "-created_at")
        .first()
    )
    context = {
        "title": "今日跨资产判断",
        "today": timezone.localdate(),
        "thesis": thesis,
        "current_thesis": thesis,
        "evidence": normalized_evidence,
        "market_cards": market_cards,
        "news_items": NewsItem.objects.exclude(source_url__contains="example.com/clean-room")[:5],
        "research_items": ResearchMention.objects.exclude(
            source_url__contains="example.com/clean-room"
        )[:4],
        "letters": FundLetter.objects.exclude(
            original_url__contains="example.com/clean-room"
        )[:3],
        "breadcrumbs": [],
        "data_sources": Source.objects.exclude(key="demo-market").order_by("name")[:8],
        "as_of": latest_snapshot.as_of if latest_snapshot else None,
        "source": latest_snapshot.source if latest_snapshot else None,
    }
    return render(request, "research/home.html", context)


def regime_log(request):
    theses = Thesis.objects.exclude(summary__startswith="演示日报 ").order_by("-date")
    reviewed = theses.exclude(hit_rate__isnull=True)
    aggregates = reviewed.aggregate(avg_hit=Avg("hit_rate"), avg_return=Avg("simulated_return"))
    context = {
        "title": "判断复盘账本",
        "current": theses.first(),
        "theses": theses[:60],
        "sample_count": reviewed.count(),
        "avg_hit": aggregates["avg_hit"],
        "avg_return": aggregates["avg_return"],
        "breadcrumbs": _breadcrumbs(("首页", "/"), ("复盘账本", "")),
    }
    return render(request, "research/regime_log.html", context)


def daily_list(request):
    queryset = Thesis.objects.exclude(summary__startswith="演示日报 ").order_by("-date")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        queryset = queryset.filter(Q(regime__icontains=query) | Q(summary__icontains=query))
    if status:
        queryset = queryset.filter(status=status)
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "research/daily_list.html",
        {
            "title": "每日宏观研究报告",
            "page_obj": page_obj,
            "total_count": queryset.count(),
            "filters": {"q": query, "status": status},
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("每日报告", "")),
        },
    )


def daily_detail(request, report_date: str):
    try:
        parsed_date = date.fromisoformat(report_date)
    except ValueError as exc:
        raise Http404("无效报告日期") from exc
    thesis = get_object_or_404(
        Thesis.objects.exclude(summary__startswith="演示日报 "), date=parsed_date
    )
    previous = Thesis.objects.filter(date__lt=thesis.date).order_by("-date").first()
    following = Thesis.objects.filter(date__gt=thesis.date).order_by("date").first()
    return render(
        request,
        "research/daily_detail.html",
        {
            "title": f"{thesis.date} · {thesis.regime}",
            "item": thesis,
            "object": thesis,
            "thesis": thesis,
            "previous": previous,
            "following": following,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("每日报告", "/daily-report/"), (str(thesis.date), "")
            ),
        },
    )


def assets_overview(request):
    groups = []
    labels = {
        "equity": "美股",
        "etf": "ETF",
        "bond": "债券",
        "commodity": "商品",
        "fx": "外汇",
        "crypto": "加密货币",
    }
    for asset_class, label in labels.items():
        instruments = list(
            Instrument.objects.filter(
                asset_class=asset_class,
                observations__source__licenses__public_display_allowed=True,
            )
            .exclude(
                observations__source__key="demo-market"
            )
            .distinct()[:8]
        )
        rows = []
        for instrument in instruments:
            observations = (
                instrument.observations.exclude(source__key="demo-market")
                .filter(source__licenses__public_display_allowed=True)
                .distinct()
            )
            latest = observations.order_by("-value_date").first()
            previous = (
                observations.filter(
                    value_date__lt=latest.value_date if latest else timezone.now()
                )
                .order_by("-value_date")
                .first()
            )
            change = None
            if latest and previous and previous.value:
                change = (latest.value - previous.value) / previous.value * Decimal("100")
            rows.append(
                {
                    "symbol": instrument.symbol,
                    "name": instrument.name,
                    "value": latest.value if latest else None,
                    "change": change,
                    "as_of": latest.as_of if latest else None,
                    "status": latest.quality_status if latest else "stale",
                }
            )
        groups.append({"key": asset_class, "label": label, "rows": rows})
    config = {
        "title": "大类资产",
        "eyebrow": "Cross-Asset Dashboard",
        "description": "把权益、久期、信用、商品、外汇和加密放在同一证据框架下。",
        "metrics": [
            {"label": "资产类别", "value": "6", "change": "统一口径", "status": "fresh"},
            {"label": "相关性窗口", "value": "30 / 90D", "change": "可切换", "status": "fresh"},
            {"label": "数据血缘", "value": "逐组件", "change": "可追溯", "status": "fresh"},
        ],
        "chart_data": [],
        "analysis": "尚未取得可公开展示的跨资产行情授权；页面只展示已通过许可校验的数据。",
        "sections": [],
        "source_notes": ["证券与商品行情在外部展示授权完成前保持空缺，不使用合成价格。"],
    }
    return render(
        request,
        "research/dashboard.html",
        {
            **config,
            "dashboard": {
                "title": config["title"],
                "summary": config["description"],
                "as_of": None,
                "source": "数据源采购台账",
                "quality_status": "stale",
                "data": {"chart": config["chart_data"]},
            },
            "asset_groups": groups,
            "page_key": "assets",
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("大类资产", "")),
        },
    )


def dashboard_page(request, page_key: str):
    try:
        config = get_page_config(page_key)
    except KeyError as exc:
        raise Http404("未知仪表盘") from exc
    snapshot = (
        DashboardSnapshot.objects.filter(key=page_key, is_published=True)
        .filter(Q(data__demo=False) | ~Q(data__has_key="demo"))
        .exclude(source__key="demo-market")
        .select_related("source")
        .order_by("-as_of", "-created_at")
        .first()
    )
    if snapshot:
        config["snapshot"] = snapshot
        config["analysis"] = snapshot.summary or config.get("analysis", "")
        if snapshot.data.get("metrics"):
            config["metrics"] = snapshot.data["metrics"]
        if snapshot.data.get("chart_data"):
            config["chart_data"] = snapshot.data["chart_data"]
        if snapshot.data.get("sections"):
            config["sections"] = snapshot.data["sections"]
    else:
        static_metrics = config.get("metrics", [])
        requirements = list(DataRequirement.objects.filter(page_key=page_key))
        labels = [item.get("label", "指标") for item in static_metrics]
        if not labels:
            labels = [requirement.metric_name for requirement in requirements[:6]]
        config["metrics"] = [
            {
                "label": label,
                "value": None,
                "display_value": "—",
                "change": None,
                "status": "stale",
                "source": "等待已授权数据源",
            }
            for label in labels
        ]
        config["chart_data"] = []
        config["sections"] = []
        config["analysis"] = (
            "本页尚无通过来源许可与质量检查的可发布快照。缺失项目和采购建议见页面下方数据覆盖台账。"
        )
        config["source_notes"] = ["没有真实数据时显示空缺，不回退到演示或合成数值。"]
    config.update(
        {
            "page_key": page_key,
            "dashboard": {
                "title": config["title"],
                "summary": config.get("analysis") or config.get("description", ""),
                "as_of": snapshot.as_of if snapshot else None,
                "source": snapshot.source if snapshot else "数据源覆盖台账",
                "quality_status": snapshot.quality_status if snapshot else "stale",
                "data": {"chart": config.get("chart_data", [])},
            },
            "breadcrumbs": _breadcrumbs(("首页", "/"), (config["title"], "")),
        }
    )
    return render(request, "research/dashboard.html", config)


def options_view(request):
    requested_symbol = request.GET.get("symbol", "SPY").upper()
    available = list(
        Instrument.objects.filter(
            options__isnull=False,
            options__source__licenses__public_display_allowed=True,
        )
        .exclude(options__source__key="demo-market")
        .distinct()
        .order_by("symbol")
    )
    instrument = next((item for item in available if item.symbol.upper() == requested_symbol), None)
    if not instrument:
        instrument = available[0] if available else None
    contract_query = (
        OptionContract.objects.filter(
            instrument=instrument,
            source__licenses__public_display_allowed=True,
        )
        .exclude(source__key="demo-market")
        .distinct()
        .order_by("expiry", "strike")
        if instrument
        else OptionContract.objects.none()
    )
    expiry = request.GET.get("expiry", "").strip()
    if expiry:
        contract_query = contract_query.filter(expiry=expiry)
    contracts = list(contract_query)
    latest = _latest_observation(instrument.symbol) if instrument else None
    spot = float(latest.value) if latest else None
    net_gex = 0.0
    net_dex = 0.0
    call_wall = None
    put_wall = None
    max_call = -1
    max_put = -1
    option_rows = []
    for contract in contracts:
        sign = 1 if contract.option_type == "call" else -1
        gamma = float(contract.gamma or 0)
        delta = float(contract.delta or 0)
        if spot is None:
            continue
        gex = sign * gamma * contract.open_interest * 100 * spot * spot / 100
        dex = sign * delta * contract.open_interest * 100 * spot
        net_gex += gex
        net_dex += dex
        if contract.option_type == "call" and contract.open_interest > max_call:
            max_call = contract.open_interest
            call_wall = contract.strike
        if contract.option_type == "put" and contract.open_interest > max_put:
            max_put = contract.open_interest
            put_wall = contract.strike
        option_rows.append(
            {
                "expiry": contract.expiry,
                "strike": float(contract.strike),
                "type": contract.option_type,
                "oi": contract.open_interest,
                "volume": contract.volume,
                "iv": float(contract.implied_volatility or 0),
                "gex": gex,
                "dex": dex,
            }
        )
    gamma_state = "等待授权期权链" if not option_rows else "正 Gamma" if net_gex >= 0 else "负 Gamma"
    context = {
        "title": "期权市场结构",
        "instrument": instrument,
        "selected_symbol": requested_symbol,
        "available_symbols": available,
        "spot": spot,
        "contracts": contracts,
        "option_rows": option_rows,
        "chart_data": option_rows,
        "net_gex": net_gex if option_rows else None,
        "net_dex": net_dex if option_rows else None,
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gamma_state": gamma_state,
        "tabs": ["GEX 分布", "DEX", "IV 期限结构", "Skew", "Vanna / Charm", "OI 热力", "结构解读"],
        "expiries": sorted({contract.expiry for contract in contracts}),
        "breadcrumbs": _breadcrumbs(("首页", "/"), ("大类资产", "/assets/"), ("期权 / GEX", "")),
    }
    return render(request, "research/options.html", context)


def positioning_view(request):
    report = request.GET.get("report", "tff-futures").strip() or "tff-futures"
    query = request.GET.get("q", "").strip()
    latest_date = (
        CFTCPosition.objects.filter(report_type=report)
        .order_by("-report_date")
        .values_list("report_date", flat=True)
        .first()
    )
    latest_rows = CFTCPosition.objects.filter(report_type=report, report_date=latest_date)
    if query:
        latest_rows = latest_rows.filter(
            Q(market_name__icontains=query) | Q(market_code__icontains=query)
        )
    latest_rows = latest_rows.order_by("-open_interest", "market_name")[:30]
    positions = []
    for row in latest_rows:
        history = list(
            CFTCPosition.objects.filter(
                report_type=report,
                market_code=row.market_code,
                trader_group=row.trader_group,
            ).order_by("report_date")
        )
        nets = [item.net_position for item in history]
        rank = percentile_rank(nets) if nets else 0
        previous = history[-2].net_position if len(history) > 1 else None
        weekly_change = row.net_position - previous if previous is not None else None
        positions.append(
            {
                "name": row.market_name,
                "symbol": row.market_code,
                "value": "—",
                "group": "资产管理机构" if row.trader_group == "asset-manager" else "杠杆资金",
                "net_position": row.net_position,
                "weekly_change": weekly_change,
                "percentile": rank,
                "crowding": "拥挤" if rank >= 80 else "中性" if rank >= 30 else "低配",
            }
        )
    return render(
        request,
        "research/positioning.html",
        {
            "title": "CFTC 持仓追踪",
            "positions": positions,
            "report_types": [
                ("tff-futures", "TFF Futures Only"),
                ("tff-combined", "TFF Futures + Options"),
            ],
            "as_of": latest_date,
            "source": "CFTC Public Reporting Environment" if latest_date else None,
            "quality_status": "fresh" if latest_date else "stale",
            "chart_data": [item["net_position"] for item in positions[:20]],
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("大类资产", "/assets/"), ("CFTC 持仓", "")),
        },
    )


def crypto_derivatives(request):
    btc = _market_card("BTC-USD", "比特币")
    return render(
        request,
        "research/crypto_derivatives.html",
        {
            "title": "加密衍生品雷达",
            "btc": btc,
            "score": None,
            "confidence": None,
            "bias_24h": "等待公开展示授权",
            "structure_7d": "暂无可发布快照",
            "layers": [],
            "kpis": [],
            "methodology": (
                "OKX 与 Deribit 公共 API 不自动授予公开再分发权。取得书面授权或采购合规聚合源前，"
                "Funding、OI、IV、Skew、清算与 ETF 流量均保持空缺。"
            ),
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("大类资产", "/assets/"), ("加密衍生品", "")
            ),
        },
    )


def fed_hub(request):
    documents = FedDocument.objects.exclude(original_url__contains="example.com/clean-room")
    latest = {
        key: documents.filter(document_type=key).first()
        for key in [
            FedDocument.DocumentType.STATEMENT,
            FedDocument.DocumentType.SPEECH,
            FedDocument.DocumentType.NEWS,
        ]
    }
    average = documents.aggregate(score=Avg("hawkish_score"))["score"] or 0
    return render(
        request,
        "research/fed_list.html",
        {
            "title": "美联储",
            "mode": "hub",
            "latest": latest,
            "average_score": average,
            "documents": documents[:8],
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("美联储", "")),
        },
    )


def fed_list(request, doc_type: str):
    valid_types = {choice[0] for choice in FedDocument.DocumentType.choices}
    if doc_type not in valid_types:
        raise Http404("未知文档类型")
    queryset = FedDocument.objects.filter(document_type=doc_type).exclude(
        original_url__contains="example.com/clean-room"
    )
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    labels = dict(FedDocument.DocumentType.choices)
    return render(
        request,
        "research/fed_list.html",
        {
            "title": labels[doc_type],
            "mode": doc_type,
            "page_obj": page_obj,
            "documents": page_obj.object_list,
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("美联储", "/fed/"), (labels[doc_type], "")),
        },
    )


def fed_detail(request, doc_type: str, slug: str):
    document = get_object_or_404(
        FedDocument.objects.exclude(original_url__contains="example.com/clean-room"),
        document_type=doc_type,
        slug=slug,
    )
    return render(
        request,
        "research/fed_detail.html",
        {
            "title": document.title,
            "item": document,
            "object": document,
            "document": document,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"),
                ("美联储", "/fed/"),
                (document.get_document_type_display(), ""),
            ),
        },
    )


def _news_queryset(request, semiconductor_only=False, ai_only=False):
    queryset = NewsItem.objects.exclude(source_url__contains="example.com/clean-room")
    if semiconductor_only:
        queryset = queryset.filter(
            Q(category__in=["ai", "foundry", "memory", "packaging", "materials", "supply-chain"])
            | Q(themes__icontains="半导体")
        )
    if ai_only:
        queryset = queryset.filter(Q(category="ai") | Q(themes__icontains="AI"))
    query = request.GET.get("q", "").strip()
    source = request.GET.get("source", "").strip()
    category = request.GET.get("category", "").strip()
    if query:
        queryset = _text_search(queryset, query, ["title", "original_title", "summary"], "title")
    if source:
        queryset = queryset.filter(source_name=source)
    if category:
        queryset = queryset.filter(category=category)
    return queryset, {"q": query, "source": source, "category": category}


def news_list(request, semiconductor_only=False, ai_only=False):
    queryset, filters = _news_queryset(request, semiconductor_only, ai_only)
    page_obj = Paginator(queryset, 20).get_page(request.GET.get("page"))
    sources = (
        NewsItem.objects.exclude(source_url__contains="example.com/clean-room")
        .order_by("source_name")
        .values_list("source_name", flat=True)
        .distinct()
    )
    categories = (
        NewsItem.objects.exclude(source_url__contains="example.com/clean-room")
        .order_by("category")
        .values_list("category", flat=True)
        .distinct()
    )
    title = "AI 资讯" if ai_only else "半导体行业资讯" if semiconductor_only else "新闻 / 事件"
    return render(
        request,
        "research/news_list.html",
        {
            "title": title,
            "page_obj": page_obj,
            "filters": filters,
            "filter_options": {"sources": sources, "categories": categories},
            "semiconductor_only": semiconductor_only,
            "ai_only": ai_only,
            "breadcrumbs": _breadcrumbs(("首页", "/"), (title, "")),
        },
    )


def reports(request, all_reports=False):
    public_research = ResearchMention.objects.exclude(
        source_url__contains="example.com/clean-room"
    )
    queryset = public_research
    query = request.GET.get("q", "").strip()
    bank = request.GET.get("bank", "").strip()
    category = request.GET.get("category", "").strip()
    stance = request.GET.get("stance", "").strip()
    if query:
        queryset = _text_search(queryset, query, ["title", "summary", "bank"], "title")
    if bank:
        queryset = queryset.filter(bank=bank)
    if category:
        queryset = queryset.filter(category=category)
    if stance:
        queryset = queryset.filter(stance=stance)
    page_obj = Paginator(queryset, 24).get_page(request.GET.get("page"))
    matrix = list(
        public_research.values("category", "stance")
        .annotate(count=Count("id"))
        .order_by("category", "stance")
    )
    banks = public_research.order_by("bank").values_list("bank", flat=True).distinct()
    categories = (
        public_research.order_by("category").values_list("category", flat=True).distinct()
    )
    stances = public_research.order_by("stance").values_list("stance", flat=True).distinct()
    return render(
        request,
        "research/reports.html",
        {
            "title": "全部机构观点" if all_reports else "机构观点合成",
            "all_reports": all_reports,
            "page_obj": page_obj,
            "matrix": matrix,
            "stance_matrix": [
                {
                    "label": item["stance"] or "中性",
                    "stance": item["stance"],
                    "count": item["count"],
                    "banks": [],
                }
                for item in matrix
            ],
            "filters": {"q": query, "bank": bank, "category": category, "stance": stance},
            "filter_options": {"banks": banks, "categories": categories, "stances": stances},
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("研究库", "")),
        },
    )


def fund_letters(request):
    public_letters = FundLetter.objects.exclude(original_url__contains="example.com/clean-room")
    queryset = public_letters
    query = request.GET.get("q", "").strip()
    if query:
        queryset = _text_search(
            queryset,
            query,
            ["fund_name", "fund_name_en", "manager", "summary"],
            "fund_name",
        )
    filters = {key: request.GET.get(key, "").strip() for key in ["quarter", "strategy", "stance"]}
    for key, value in filters.items():
        if value:
            queryset = queryset.filter(**{key: value})
    page_obj = Paginator(queryset, 24).get_page(request.GET.get("page"))
    options = {
        key: public_letters.order_by(key).values_list(key, flat=True).distinct()
        for key in ["quarter", "strategy", "stance"]
    }
    fund_count = public_letters.values("fund_name").distinct().count()
    filters["q"] = query
    return render(
        request,
        "research/fund_letters.html",
        {
            "title": "基金信函",
            "page_obj": page_obj,
            "filters": filters,
            "filter_options": options,
            "total_count": queryset.count(),
            "fund_count": fund_count,
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("基金信函", "")),
        },
    )


def fund_letter_detail(request, pk: int):
    public_letters = FundLetter.objects.exclude(original_url__contains="example.com/clean-room")
    letter = get_object_or_404(public_letters, pk=pk)
    related = public_letters.filter(fund_name=letter.fund_name).exclude(pk=letter.pk)[:8]
    return render(
        request,
        "research/fund_letter_detail.html",
        {
            "title": f"{letter.fund_name} · {letter.quarter}",
            "item": letter,
            "object": letter,
            "letter": letter,
            "related": related,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("基金信函", "/research/fund-letters/"), (letter.fund_name, "")
            ),
        },
    )


def glossary(request, ai_only=False):
    public_terms = GlossaryTerm.objects.exclude(source_url__contains="example.com/")
    queryset = public_terms
    filters = {
        key: request.GET.get(key, "").strip()
        for key in ["q", "category", "subcategory", "difficulty", "tag"]
    }
    if filters["q"]:
        queryset = _text_search(
            queryset,
            filters["q"],
            ["term", "term_en", "definition"],
            "term",
        )
    for key in ["category", "subcategory", "difficulty"]:
        if filters[key]:
            queryset = queryset.filter(**{key: filters[key]})
    if filters["tag"]:
        queryset = queryset.filter(tags__icontains=filters["tag"])
    options = {
        key: public_terms.order_by(key).values_list(key, flat=True).distinct()
        for key in ["category", "subcategory", "difficulty"]
    }
    return render(
        request,
        "research/glossary.html",
        {
            "title": "AI 专业术语库" if ai_only else "专业术语库",
            "terms": queryset,
            "filters": filters,
            "filter_options": options,
            "ai_only": ai_only,
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("术语库", "")),
        },
    )


def search(request):
    query = request.GET.get("q", "").strip()
    company_results = Company.objects.none()
    news_results = NewsItem.objects.none()
    research_results = ResearchMention.objects.none()
    letter_results = FundLetter.objects.none()
    glossary_results = GlossaryTerm.objects.none()
    if query:
        company_results = _text_search(
            Company.objects.exclude(data_source_note__icontains="合成演示"),
            query,
            ["name", "name_en", "ticker", "description"],
            "name",
        )[:10]
        news_results = _text_search(
            NewsItem.objects.exclude(source_url__contains="example.com/clean-room"),
            query,
            ["title", "original_title", "summary"],
            "title",
        )[:10]
        research_results = _text_search(
            ResearchMention.objects.exclude(source_url__contains="example.com/clean-room"),
            query,
            ["title", "summary", "bank"],
            "title",
        )[:10]
        letter_results = _text_search(
            FundLetter.objects.exclude(original_url__contains="example.com/clean-room"),
            query,
            ["fund_name", "fund_name_en", "manager", "summary"],
            "fund_name",
        )[:10]
        glossary_results = _text_search(
            GlossaryTerm.objects.exclude(source_url__contains="example.com/"),
            query,
            ["term", "term_en", "definition"],
            "term",
        )[:10]

    company_results = list(company_results)
    news_results = list(news_results)
    research_results = list(research_results)
    letter_results = list(letter_results)
    glossary_results = list(glossary_results)
    result_count = sum(
        map(
            len,
            [
                company_results,
                news_results,
                research_results,
                letter_results,
                glossary_results,
            ],
        )
    )
    return render(
        request,
        "research/search.html",
        {
            "title": "全站搜索",
            "query": query,
            "results": {},
            "company_results": company_results,
            "news_results": news_results,
            "report_results": research_results + letter_results,
            "glossary_results": glossary_results,
            "result_count": result_count,
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("搜索", "")),
        },
    )


def data_sources(request):
    requirements = DataRequirement.objects.all()
    status_counts = {
        status: requirements.filter(status=status).count()
        for status, _ in DataRequirement.Status.choices
    }
    return render(
        request,
        "research/data_sources.html",
        {
            "title": "数据源与采购台账",
            "requirements": requirements,
            "status_counts": status_counts,
            "sources": Source.objects.exclude(key="demo-market").prefetch_related("licenses"),
            "licenses": SourceLicense.objects.select_related("source").all(),
            "breadcrumbs": _breadcrumbs(("首页", "/"), ("数据源与采购", "")),
        },
    )


def ai_hub(request, chain_mode=False):
    nodes = SupplyChainNode.objects.exclude(source_note__icontains="合成演示").annotate(
        company_count=Count("companies")
    )
    companies = Company.objects.exclude(data_source_note__icontains="合成演示")
    models = ModelProfile.objects.exclude(slug__startswith="clean-room-model-")
    agents = CodingAgentProfile.objects.exclude(homepage__contains="example.com/clean-room")
    projects = GitHubProject.objects.exclude(repo__startswith="atlas-clean-room/")
    context = {
        "title": "AI 产业链" if chain_mode else "AI 产业观察",
        "chain_mode": chain_mode,
        "node_count": nodes.count(),
        "company_count": companies.count(),
        "model_count": models.count(),
        "agent_count": agents.count(),
        "project_count": projects.count(),
        "top_nodes": nodes.order_by("-narrative_score")[:9],
        "top_companies": companies.order_by("-return_1m")[:8],
        "top_models": models[:4],
        "top_agents": agents[:4],
        "top_projects": projects[:8],
        "news_items": NewsItem.objects.exclude(source_url__contains="example.com/clean-room")
        .filter(Q(category="ai") | Q(themes__icontains="AI"))[:5],
        "breadcrumbs": _breadcrumbs(("首页", "/"), ("AI 产业观察", "")),
    }
    return render(request, "research/ai_hub.html", context)


def ai_market_map(request):
    nodes = SupplyChainNode.objects.exclude(source_note__icontains="合成演示").annotate(
        company_count=Count("companies")
    )
    companies = Company.objects.exclude(data_source_note__icontains="合成演示")
    query = request.GET.get("q", "").strip()
    layer = request.GET.get("layer", "").strip()
    quadrant = request.GET.get("quadrant", "").strip()
    sort = request.GET.get("sort", "narrative").strip()
    if query:
        nodes = nodes.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(companies__name__icontains=query)
            | Q(companies__ticker__icontains=query)
        ).distinct()
    if layer:
        nodes = nodes.filter(layer=layer)
    if quadrant:
        nodes = nodes.filter(quadrant=quadrant)
    if query:
        companies = companies.filter(
            Q(name__icontains=query)
            | Q(name_en__icontains=query)
            | Q(ticker__icontains=query)
            | Q(primary_node__name__icontains=query)
        )
    if layer:
        companies = companies.filter(primary_node__layer=layer)
    if quadrant:
        companies = companies.filter(primary_node__quadrant=quadrant)
    sort_fields = {
        "name": "name",
        "narrative": "-narrative_score",
        "companies": "-company_count",
        "growth": "-revenue_growth",
        "market_cap": "-market_cap_usd_m",
    }
    nodes = nodes.order_by(sort_fields.get(sort, "-narrative_score"), "name")
    company_sort_fields = {
        "name": "name",
        "market_cap": "-market_cap_usd_m",
        "revenue_growth": "-revenue_growth",
        "gross_margin": "-gross_margin",
        "return_6m": "-return_6m",
        "pe": "pe",
    }
    companies = companies.select_related("primary_node").order_by(
        company_sort_fields.get(sort, "-market_cap_usd_m"), "name"
    )
    page_obj = Paginator(companies, 100).get_page(request.GET.get("page"))
    layers = nodes.order_by("layer").values_list("layer", flat=True).distinct()
    quadrants = (
        nodes.order_by("quadrant").values_list("quadrant", flat=True).distinct()
    )
    return render(
        request,
        "research/ai_market_map.html",
        {
            "title": "AI 产业链资本地图",
            "nodes": nodes,
            "companies": page_obj.object_list,
            "page_obj": page_obj,
            "company_count": companies.count(),
            "layers": layers,
            "quadrants": quadrants,
            "filters": {"q": query, "layer": layer, "quadrant": quadrant, "sort": sort},
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("AI 产业观察", "/ai-industry/"), ("资本地图", "")
            ),
        },
    )


def ai_graph(request):
    node_query = SupplyChainNode.objects.exclude(source_note__icontains="合成演示").annotate(
        company_count=Count("companies")
    )
    query = request.GET.get("q", "").strip()
    layer = request.GET.get("layer", "").strip()
    confidence = request.GET.get("confidence", "").strip()
    if query:
        node_query = node_query.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if layer:
        node_query = node_query.filter(layer=layer)
    nodes = list(node_query)
    node_ids = [node.pk for node in nodes]
    edge_query = SupplyChainEdge.objects.filter(
        source_node_id__in=node_ids, target_node_id__in=node_ids, reviewed=True
    ).exclude(evidence_url__contains="example.com/clean-room")
    if confidence:
        try:
            edge_query = edge_query.filter(confidence__gte=Decimal(confidence))
        except (ArithmeticError, ValueError):
            pass
    edges = list(edge_query.select_related("source_node", "target_node"))
    graph_nodes = [
        {
            "id": node.slug,
            "name": node.name,
            "category": node.layer,
            "value": node.company_count,
            "url": node.get_absolute_url(),
        }
        for node in nodes
    ]
    graph_edges = [
        {
            "source": edge.source_node.slug,
            "target": edge.target_node.slug,
            "name": edge.relation,
            "confidence": float(edge.confidence),
        }
        for edge in edges
    ]
    return render(
        request,
        "research/ai_graph.html",
        {
            "title": "AI 产业关系图谱",
            "nodes": nodes,
            "companies": Company.objects.exclude(data_source_note__icontains="合成演示")
            .filter(primary_node_id__in=node_ids)
            .select_related("primary_node"),
            "edges": edges,
            "layers": sorted({node.layer for node in nodes}),
            "filters": {"q": query, "layer": layer, "confidence": confidence},
            "graph_data": {"nodes": graph_nodes, "edges": graph_edges},
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("AI 产业观察", "/ai-industry/"), ("关系图谱", "")
            ),
        },
    )


def ai_node(request, slug: str):
    node = get_object_or_404(
        SupplyChainNode.objects.exclude(source_note__icontains="合成演示"), slug=slug
    )
    companies = node.companies.exclude(data_source_note__icontains="合成演示").order_by(
        "-market_cap_usd_m"
    )
    inbound = node.inbound_edges.exclude(evidence_url__contains="example.com/clean-room").select_related(
        "source_node"
    )
    outbound = node.outbound_edges.exclude(
        evidence_url__contains="example.com/clean-room"
    ).select_related("target_node")
    return render(
        request,
        "research/ai_node.html",
        {
            "title": node.name,
            "item": node,
            "object": node,
            "node": node,
            "companies": companies,
            "inbound_edges": inbound,
            "outbound_edges": outbound,
            "chart_data": [
                float(value or 0)
                for value in [
                    node.narrative_score,
                    node.revenue_growth,
                    node.gross_margin,
                    node.median_pe,
                    node.median_ps,
                ]
            ],
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"),
                ("AI 产业观察", "/ai-industry/"),
                ("产业链", "/ai-industry/chain/"),
                (node.name, ""),
            ),
        },
    )


def ai_company(request, slug: str):
    company = get_object_or_404(
        Company.objects.exclude(data_source_note__icontains="合成演示").select_related(
            "primary_node"
        ),
        slug=slug,
    )
    financials = company.financials.select_related("source").all()
    latest_fact = financials.first()
    chart_data = list(
        MarketBar.objects.filter(
            instrument__symbol=company.ticker,
            source__licenses__public_display_allowed=True,
        )
        .exclude(source__key="demo-market")
        .order_by("value_date")
        .values_list("close", flat=True)[:240]
    )
    related = (
        Company.objects.exclude(data_source_note__icontains="合成演示")
        .filter(primary_node=company.primary_node)
        .exclude(pk=company.pk)[:8]
    )
    return render(
        request,
        "research/ai_company.html",
        {
            "title": f"{company.name} / {company.name_en}",
            "item": company,
            "object": company,
            "company": company,
            "financials": financials,
            "latest_fact": latest_fact,
            "related": related,
            "chart_data": chart_data,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"),
                ("AI 产业观察", "/ai-industry/"),
                ("公司档案", ""),
                (company.name, ""),
            ),
        },
    )


def model_evolution(request):
    return render(
        request,
        "research/model_evolution.html",
        {
            "title": "大模型演变",
            "models": ModelProfile.objects.exclude(slug__startswith="clean-room-model-"),
            "agents": CodingAgentProfile.objects.exclude(
                homepage__contains="example.com/clean-room"
            ),
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("AI 产业观察", "/ai-industry/"), ("大模型演变", "")
            ),
        },
    )


def model_detail(request, slug: str):
    public_models = ModelProfile.objects.exclude(slug__startswith="clean-room-model-")
    profile = get_object_or_404(public_models, slug=slug)
    peers = public_models.exclude(pk=profile.pk)[:5]
    return render(
        request,
        "research/model_detail.html",
        {
            "title": profile.name,
            "item": profile,
            "object": profile,
            "profile": profile,
            "model": profile,
            "peers": peers,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"),
                ("大模型演变", "/ai-industry/chain/model-evolution/"),
                (profile.name, ""),
            ),
        },
    )


def coding_agent_detail(request, slug: str):
    public_agents = CodingAgentProfile.objects.exclude(homepage__contains="example.com/clean-room")
    profile = get_object_or_404(public_agents, slug=slug)
    peers = public_agents.exclude(pk=profile.pk)[:5]
    return render(
        request,
        "research/coding_agent_detail.html",
        {
            "title": profile.name,
            "item": profile,
            "object": profile,
            "profile": profile,
            "agent": profile,
            "peers": peers,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"),
                ("Coding Agent", "/ai-industry/chain/model-evolution/"),
                (profile.name, ""),
            ),
        },
    )


def applications(request):
    category = request.GET.get("category", "").strip()
    projects = GitHubProject.objects.exclude(repo__startswith="atlas-clean-room/")
    if category:
        projects = projects.filter(category=category)
    categories = (
        projects.order_by("category").values_list("category", flat=True).distinct()
    )
    return render(
        request,
        "research/applications.html",
        {
            "title": "AI 应用开源雷达",
            "projects": projects,
            "top_weekly": projects.order_by("-stars_7d")[:8],
            "categories": categories,
            "selected_category": category,
            "total_stars": projects.aggregate(total=Sum("stars"))["total"] or 0,
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("AI 产业观察", "/ai-industry/"), ("AI 应用", "")
            ),
        },
    )


def ai_teardown(request):
    generations = []
    return render(
        request,
        "research/teardown.html",
        {
            "title": "AI 系统价值量拆解",
            "generations": generations,
            "chart_data": generations,
            "sections": [],
            "methodology": "价值量模型尚无逐项可追溯来源，授权数据与人工审核完成前不发布百分比。",
            "breadcrumbs": _breadcrumbs(
                ("首页", "/"), ("AI 产业观察", "/ai-industry/"), ("价值量拆解", "")
            ),
        },
    )


def gone(request, reason="该模块已下线，历史 URL 仅用于兼容。"):
    return render(
        request, "research/gone.html", {"title": "410 · 已下线", "reason": reason}, status=410
    )


def robots_txt(request):
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin/",
            "Disallow: /api/",
            "Disallow: /internal/",
            "Disallow: /search/",
            f"Sitemap: {settings.SITE_URL}/sitemap.xml",
            "",
        ]
    )
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    static_names = [
        "home",
        "trade-map",
        "regime-log",
        "daily-list",
        "assets-overview",
        "equities",
        "etfs",
        "options",
        "positioning",
        "bonds",
        "commodities",
        "fx",
        "crypto",
        "crypto-derivatives",
        "rates-overview",
        "fed-funds",
        "yield-curve",
        "auctions",
        "real-rates",
        "expectations",
        "fed-hub",
        "fed-statements",
        "fed-speeches",
        "fed-news",
        "hawkish-dovish",
        "liquidity-overview",
        "transmission-chain",
        "fed-balance-sheet",
        "operations",
        "rrp-tga",
        "reserves",
        "global-dollar",
        "subsurface",
        "economy-overview",
        "gdp",
        "employment",
        "inflation",
        "consumer",
        "volatility-overview",
        "volatility-dashboard",
        "vix",
        "volatility-move",
        "fx-vol",
        "implied-vs-realized",
        "credit-overview",
        "credit-spreads",
        "credit-cds",
        "credit-stress",
        "news",
        "semiconductor-news",
        "reports",
        "reports-all",
        "fund-letters",
        "glossary",
        "data-sources",
        "supply-chain",
        "supply-chain-foundry",
        "supply-chain-packaging",
        "supply-chain-hbm",
        "supply-chain-gpu",
        "supply-chain-demand",
        "ai-hub",
        "ai-market-map",
        "ai-graph",
        "ai-news",
        "ai-chain",
        "semiconductor-chain",
        "model-evolution",
        "applications",
        "ai-glossary",
        "ai-teardown",
    ]
    urls = [request.build_absolute_uri(reverse(name)) for name in static_names]
    urls.extend(
        request.build_absolute_uri(item.get_absolute_url())
        for item in Thesis.objects.exclude(summary__startswith="演示日报 ")
    )
    urls.extend(
        request.build_absolute_uri(item.get_absolute_url())
        for item in FundLetter.objects.exclude(original_url__contains="example.com/clean-room")
    )
    urls.extend(
        request.build_absolute_uri(item.get_absolute_url())
        for item in SupplyChainNode.objects.exclude(source_note__icontains="合成演示")
    )
    urls.extend(
        request.build_absolute_uri(item.get_absolute_url())
        for item in Company.objects.exclude(data_source_note__icontains="合成演示")
    )
    for item in FedDocument.objects.exclude(original_url__contains="example.com/clean-room"):
        route_name = {
            FedDocument.DocumentType.STATEMENT: "fed-detail",
            FedDocument.DocumentType.SPEECH: "fed-speech-detail",
            FedDocument.DocumentType.NEWS: "fed-news-detail",
        }[item.document_type]
        urls.append(request.build_absolute_uri(reverse(route_name, kwargs={"slug": item.slug})))
    urls.extend(
        request.build_absolute_uri(reverse("model-detail", kwargs={"slug": item.slug}))
        for item in ModelProfile.objects.exclude(slug__startswith="clean-room-model-")
    )
    urls.extend(
        request.build_absolute_uri(reverse("coding-agent-detail", kwargs={"slug": item.slug}))
        for item in CodingAgentProfile.objects.exclude(homepage__contains="example.com/clean-room")
    )
    now = timezone.localdate().isoformat()
    body = "".join(
        f"<url><loc>{escape(url)}</loc><lastmod>{now}</lastmod></url>"
        for url in dict.fromkeys(urls)
    )
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{body}</urlset>",
        content_type="application/xml; charset=utf-8",
    )


def manifest(request):
    payload = {
        "name": "Atlas Macro Research",
        "short_name": "Atlas Macro",
        "description": "可追溯的跨资产宏观与 AI 产业研究平台",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#08111d",
        "theme_color": "#0b1625",
        "lang": "zh-CN",
        "icons": [
            {
                "src": "/static/research/icon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            }
        ],
    }
    return HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        content_type="application/manifest+json; charset=utf-8",
    )


def service_worker(request):
    content = """
const CACHE = 'atlas-macro-v1';
const OFFLINE = '/offline/';
self.addEventListener('install', event => event.waitUntil(
  caches.open(CACHE).then(cache => cache.addAll([
    OFFLINE,
    '/static/research/css/app.css',
    '/static/research/js/app.js'
  ]))
));
self.addEventListener('activate', event => event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  const excluded = url.pathname.startsWith('/admin/') ||
    url.pathname.startsWith('/internal/');
  if (event.request.method !== 'GET' || excluded) return;
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(caches.match(event.request).then(hit => hit ||
      fetch(event.request).then(response => {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put(event.request, copy));
        return response;
      })
    ));
    return;
  }
  event.respondWith(fetch(event.request).then(response => {
    const copy = response.clone();
    caches.open(CACHE).then(cache => cache.put(event.request, copy));
    return response;
  }).catch(() => caches.match(event.request).then(hit => hit || caches.match(OFFLINE))));
});
""".strip()
    response = HttpResponse(content, content_type="application/javascript; charset=utf-8")
    response["Service-Worker-Allowed"] = "/"
    return response


def offline(request):
    return render(request, "research/offline.html", {"title": "离线模式"})


def health(request):
    latest_run = (
        DashboardSnapshot.objects.filter(Q(data__demo=False) | ~Q(data__has_key="demo"))
        .exclude(source__key="demo-market")
        .order_by("-updated_at")
        .values("key", "quality_status", "updated_at")
        .first()
    )
    return JsonResponse(
        {
            "status": "ok",
            "service": "atlas-macro",
            "time": timezone.now().isoformat(),
            "latest_snapshot": latest_run,
        }
    )


def page_not_found(request, exception):
    return render(request, "research/404.html", {"title": "页面不存在"}, status=404)
