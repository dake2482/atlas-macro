from __future__ import annotations

import uuid

from django.db import models
from django.urls import reverse


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Source(TimestampedModel):
    class LicenseStatus(models.TextChoices):
        OPEN = "open", "开放"
        REVIEW = "review", "待审核"
        LICENSED = "licensed", "已授权"
        RESTRICTED = "restricted", "受限制"

    key = models.SlugField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    homepage = models.URLField(blank=True)
    kind = models.CharField(max_length=60, default="official")
    license_status = models.CharField(
        max_length=20, choices=LicenseStatus.choices, default=LicenseStatus.REVIEW
    )
    license_scope = models.TextField(blank=True)
    redistribution_allowed = models.BooleanField(default=False)
    attribution = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SourceLicense(TimestampedModel):
    """Versioned licence decision for an upstream source.

    Keeping this separate from ``Source`` preserves the review history when a
    provider changes terms or a commercial redistribution agreement expires.
    """

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="licenses")
    status = models.CharField(
        max_length=20,
        choices=Source.LicenseStatus.choices,
        default=Source.LicenseStatus.REVIEW,
    )
    scope = models.TextField()
    terms_url = models.URLField(max_length=800, blank=True)
    redistribution_allowed = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    reviewed_by = models.CharField(max_length=160, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-reviewed_at", "-created_at"]


class IngestionRun(TimestampedModel):
    class Status(models.TextChoices):
        RUNNING = "running", "运行中"
        SUCCESS = "success", "成功"
        FAILED = "failed", "失败"
        PARTIAL = "partial", "部分成功"

    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="runs")
    dataset = models.CharField(max_length=120)
    batch_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    started_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    row_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]


class RawArtifact(TimestampedModel):
    run = models.ForeignKey(IngestionRun, on_delete=models.CASCADE, related_name="artifacts")
    uri = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    content_type = models.CharField(max_length=120, blank=True)
    size_bytes = models.PositiveBigIntegerField(default=0)


class Instrument(TimestampedModel):
    symbol = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=160)
    asset_class = models.CharField(max_length=40)
    exchange = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=12, default="USD")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["asset_class", "symbol"]

    def __str__(self) -> str:
        return f"{self.symbol} · {self.name}"


class SeriesDefinition(TimestampedModel):
    key = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=180)
    unit = models.CharField(max_length=40, blank=True)
    frequency = models.CharField(max_length=30, default="daily")
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="series")
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class Observation(TimestampedModel):
    class Quality(models.TextChoices):
        FRESH = "fresh", "正常"
        STALE = "stale", "过期"
        FALLBACK = "fallback", "备用源"
        ESTIMATED = "estimated", "估算"
        ERROR = "error", "异常"

    series = models.ForeignKey(
        SeriesDefinition,
        on_delete=models.CASCADE,
        related_name="observations",
        null=True,
        blank=True,
    )
    instrument = models.ForeignKey(
        Instrument, on_delete=models.CASCADE, related_name="observations", null=True, blank=True
    )
    value = models.DecimalField(max_digits=28, decimal_places=8)
    value_date = models.DateTimeField()
    as_of = models.DateTimeField()
    fetched_at = models.DateTimeField()
    batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="observations")
    fallback_source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="fallback_observations",
        null=True,
        blank=True,
    )
    quality_status = models.CharField(max_length=20, choices=Quality.choices, default=Quality.FRESH)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["instrument", "-value_date"]),
            models.Index(fields=["series", "-value_date"]),
            models.Index(fields=["batch_id"]),
        ]
        ordering = ["-value_date"]


class MarketBar(TimestampedModel):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="bars")
    interval = models.CharField(max_length=20, default="1d")
    value_date = models.DateTimeField()
    open = models.DecimalField(max_digits=28, decimal_places=8)
    high = models.DecimalField(max_digits=28, decimal_places=8)
    low = models.DecimalField(max_digits=28, decimal_places=8)
    close = models.DecimalField(max_digits=28, decimal_places=8)
    volume = models.DecimalField(max_digits=30, decimal_places=4, null=True, blank=True)
    fetched_at = models.DateTimeField()
    batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    source = models.ForeignKey(Source, on_delete=models.PROTECT, related_name="market_bars")
    fallback_source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="fallback_market_bars",
        null=True,
        blank=True,
    )
    quality_status = models.CharField(
        max_length=20, choices=Observation.Quality.choices, default=Observation.Quality.FRESH
    )
    license_scope = models.CharField(max_length=240, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-value_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "interval", "value_date", "source"],
                name="market_bar_source_interval_time",
            )
        ]
        indexes = [models.Index(fields=["instrument", "interval", "-value_date"])]


class MetricSnapshot(TimestampedModel):
    key = models.SlugField(max_length=140)
    label = models.CharField(max_length=180)
    value = models.DecimalField(max_digits=28, decimal_places=8, null=True, blank=True)
    display_value = models.CharField(max_length=80, blank=True)
    change = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=30, blank=True)
    value_date = models.DateTimeField()
    as_of = models.DateTimeField()
    fetched_at = models.DateTimeField()
    batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    fallback_source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="fallback_metrics",
        null=True,
        blank=True,
    )
    quality_status = models.CharField(
        max_length=20, choices=Observation.Quality.choices, default=Observation.Quality.FRESH
    )
    license_scope = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["key", "batch_id"], name="metric_batch_key")]
        ordering = ["key"]


class DashboardSnapshot(TimestampedModel):
    key = models.SlugField(max_length=120)
    title = models.CharField(max_length=180)
    as_of = models.DateTimeField()
    batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    quality_status = models.CharField(
        max_length=20, choices=Observation.Quality.choices, default=Observation.Quality.FRESH
    )
    summary = models.TextField(blank=True)
    data = models.JSONField(default=dict)
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["-as_of"]
        constraints = [
            models.UniqueConstraint(fields=["key", "batch_id"], name="dashboard_batch_key")
        ]


class QualityCheck(TimestampedModel):
    class Status(models.TextChoices):
        PASS = "pass", "通过"
        WARN = "warn", "警告"
        FAIL = "fail", "失败"

    run = models.ForeignKey(
        IngestionRun,
        on_delete=models.CASCADE,
        related_name="quality_checks",
        null=True,
        blank=True,
    )
    batch_id = models.UUIDField(db_index=True)
    scope_key = models.CharField(max_length=160, db_index=True)
    check_name = models.CharField(max_length=160)
    status = models.CharField(max_length=12, choices=Status.choices)
    observed_at = models.DateTimeField()
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-observed_at", "scope_key"]


class FallbackEvent(TimestampedModel):
    dataset = models.CharField(max_length=160, db_index=True)
    primary_source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="primary_fallback_events"
    )
    fallback_source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="activated_fallback_events"
    )
    batch_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    reason = models.TextField()
    began_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    resolved = models.BooleanField(default=False)

    class Meta:
        ordering = ["-began_at"]


class GeneratedAnalysis(TimestampedModel):
    class ReviewStatus(models.TextChoices):
        DRAFT = "draft", "草稿"
        AI = "ai", "AI 生成"
        REVIEWED = "reviewed", "已审核"
        REJECTED = "rejected", "已拒绝"

    slug = models.SlugField(max_length=180, unique=True)
    title = models.CharField(max_length=240)
    body = models.TextField()
    model_name = models.CharField(max_length=120, blank=True)
    prompt_version = models.CharField(max_length=80, blank=True)
    generated_at = models.DateTimeField()
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT
    )
    evidence = models.JSONField(default=list, blank=True)
    data_as_of = models.DateTimeField(null=True, blank=True)
    stale = models.BooleanField(default=False)


class Thesis(TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "待复盘"
        HIT = "hit", "命中"
        PARTIAL = "partial", "部分命中"
        MISSED = "missed", "未命中"

    date = models.DateField(unique=True)
    regime = models.CharField(max_length=80)
    confidence = models.CharField(max_length=20, default="中")
    summary = models.TextField()
    evidence = models.JSONField(default=list)
    triggers = models.JSONField(default=list)
    invalidation = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    hit_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    simulated_return = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def get_absolute_url(self) -> str:
        return reverse("daily-detail", kwargs={"report_date": self.date.isoformat()})


class EvidenceItem(TimestampedModel):
    analysis = models.ForeignKey(
        GeneratedAnalysis,
        on_delete=models.CASCADE,
        related_name="evidence_items",
        null=True,
        blank=True,
    )
    thesis = models.ForeignKey(
        Thesis,
        on_delete=models.CASCADE,
        related_name="evidence_items",
        null=True,
        blank=True,
    )
    label = models.CharField(max_length=180)
    body = models.TextField()
    source = models.ForeignKey(Source, on_delete=models.PROTECT, null=True, blank=True)
    source_url = models.URLField(max_length=800, blank=True)
    observation = models.ForeignKey(Observation, on_delete=models.SET_NULL, null=True, blank=True)
    snapshot = models.ForeignKey(MetricSnapshot, on_delete=models.SET_NULL, null=True, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=3, null=True, blank=True)
    value_date = models.DateTimeField(null=True, blank=True)


class Trigger(TimestampedModel):
    class Status(models.TextChoices):
        WATCHING = "watching", "观察中"
        TRIGGERED = "triggered", "已触发"
        EXPIRED = "expired", "已过期"

    thesis = models.ForeignKey(Thesis, on_delete=models.CASCADE, related_name="trigger_items")
    name = models.CharField(max_length=180)
    condition = models.TextField()
    display_threshold = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WATCHING)
    triggered_at = models.DateTimeField(null=True, blank=True)


class Invalidation(TimestampedModel):
    thesis = models.OneToOneField(
        Thesis, on_delete=models.CASCADE, related_name="invalidation_record"
    )
    condition = models.TextField()
    is_triggered = models.BooleanField(default=False)
    observed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=list, blank=True)


class Outcome(TimestampedModel):
    thesis = models.OneToOneField(Thesis, on_delete=models.CASCADE, related_name="outcome")
    evaluated_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Thesis.Status.choices)
    hit_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    simulated_return = models.DecimalField(max_digits=7, decimal_places=3, null=True, blank=True)
    notes = models.TextField(blank=True)


class NewsItem(TimestampedModel):
    title = models.CharField(max_length=320)
    original_title = models.CharField(max_length=320, blank=True)
    summary = models.TextField(blank=True)
    source_name = models.CharField(max_length=120)
    source_url = models.URLField(max_length=800)
    category = models.CharField(max_length=80, db_index=True)
    published_at = models.DateTimeField(db_index=True)
    tickers = models.JSONField(default=list, blank=True)
    themes = models.JSONField(default=list, blank=True)
    sentiment = models.CharField(max_length=40, blank=True)
    relevance = models.PositiveSmallIntegerField(default=0)
    license_status = models.CharField(max_length=20, default="link-only")

    class Meta:
        ordering = ["-published_at"]


class ResearchMention(TimestampedModel):
    bank = models.CharField(max_length=120, db_index=True)
    title = models.CharField(max_length=320)
    summary = models.TextField(blank=True)
    category = models.CharField(max_length=80, db_index=True)
    stance = models.CharField(max_length=30, blank=True)
    importance = models.PositiveSmallIntegerField(default=5)
    published_at = models.DateTimeField()
    source_url = models.URLField(max_length=800)
    review_status = models.CharField(max_length=20, default="ai")

    class Meta:
        ordering = ["-published_at"]


class FundLetter(TimestampedModel):
    fund_name = models.CharField(max_length=180, db_index=True)
    fund_name_en = models.CharField(max_length=180, blank=True)
    manager = models.CharField(max_length=180, blank=True)
    quarter = models.CharField(max_length=30, db_index=True)
    strategy = models.CharField(max_length=60, db_index=True)
    stance = models.CharField(max_length=30, db_index=True)
    aum_usd_m = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    summary = models.TextField()
    key_points = models.JSONField(default=list)
    asset_views = models.JSONField(default=list, blank=True)
    original_url = models.URLField(max_length=800)
    source_label = models.CharField(max_length=120, default="基金官网")
    license_status = models.CharField(max_length=20, default="link-only")
    published_at = models.DateField()

    class Meta:
        ordering = ["-published_at", "fund_name"]

    def get_absolute_url(self) -> str:
        return reverse("fund-letter-detail", kwargs={"pk": self.pk})


class FedDocument(TimestampedModel):
    class DocumentType(models.TextChoices):
        STATEMENT = "statement", "FOMC 声明"
        SPEECH = "speech", "官员演讲"
        NEWS = "news", "联储公告"

    document_type = models.CharField(max_length=20, choices=DocumentType.choices, db_index=True)
    slug = models.SlugField(max_length=180, unique=True)
    title = models.CharField(max_length=320)
    speaker = models.CharField(max_length=120, blank=True)
    summary = models.TextField()
    key_points = models.JSONField(default=list)
    published_at = models.DateTimeField()
    hawkish_score = models.SmallIntegerField(default=0)
    original_url = models.URLField(max_length=800)

    class Meta:
        ordering = ["-published_at"]


class SupplyChainNode(TimestampedModel):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    layer = models.CharField(max_length=80, db_index=True)
    description = models.TextField()
    thesis = models.TextField(blank=True)
    quadrant = models.CharField(max_length=40, default="观察", db_index=True)
    narrative_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    revenue_growth = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    gross_margin = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    median_pe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    median_ps = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    market_cap_usd_m = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    source_note = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ["layer", "name"]

    def get_absolute_url(self) -> str:
        return reverse("ai-node", kwargs={"slug": self.slug})


class Company(TimestampedModel):
    slug = models.SlugField(max_length=140, unique=True)
    name = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180, blank=True)
    ticker = models.CharField(max_length=40, db_index=True)
    exchange = models.CharField(max_length=80, blank=True)
    country = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=12, default="USD")
    primary_node = models.ForeignKey(
        SupplyChainNode, on_delete=models.PROTECT, related_name="companies"
    )
    description = models.TextField()
    business = models.TextField(blank=True)
    price = models.DecimalField(max_digits=20, decimal_places=4, null=True, blank=True)
    market_cap_usd_m = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    return_1m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    return_6m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    revenue_growth = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    gross_margin = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    pe = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    ps = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    rating = models.CharField(max_length=40, default="中性")
    quality_grade = models.CharField(max_length=10, default="B+")
    data_source_note = models.CharField(max_length=240, blank=True)
    investor_relations_url = models.URLField(max_length=800, blank=True)
    data_as_of = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def get_absolute_url(self) -> str:
        return reverse("ai-company", kwargs={"slug": self.slug})


class FinancialFact(TimestampedModel):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="financials")
    fiscal_year = models.PositiveSmallIntegerField()
    revenue_usd_m = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    revenue_growth = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    gross_margin = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    net_income_usd_m = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    operating_cash_flow_usd_m = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    filed_at = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-fiscal_year"]
        constraints = [
            models.UniqueConstraint(fields=["company", "fiscal_year"], name="company_fiscal_year")
        ]


class SupplyChainEdge(TimestampedModel):
    source_node = models.ForeignKey(
        SupplyChainNode, on_delete=models.CASCADE, related_name="outbound_edges"
    )
    target_node = models.ForeignKey(
        SupplyChainNode, on_delete=models.CASCADE, related_name="inbound_edges"
    )
    relation = models.CharField(max_length=120)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, default=0.7)
    evidence_url = models.URLField(max_length=800, blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_node", "target_node", "relation"], name="unique_supply_edge"
            )
        ]


class ModelProfile(TimestampedModel):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    provider = models.CharField(max_length=120)
    release_date = models.DateField()
    context_tokens = models.PositiveIntegerField(default=0)
    input_price = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    output_price = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    capability_score = models.DecimalField(max_digits=5, decimal_places=2)
    tier = models.CharField(max_length=10, default="T1")
    description = models.TextField()
    sources = models.JSONField(default=list)

    class Meta:
        ordering = ["-capability_score"]


class CodingAgentProfile(TimestampedModel):
    slug = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=160)
    provider = models.CharField(max_length=120)
    product_type = models.CharField(max_length=80)
    release_date = models.DateField()
    price_label = models.CharField(max_length=120)
    capability_score = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField()
    homepage = models.URLField(blank=True)

    class Meta:
        ordering = ["-capability_score"]


class GitHubProject(TimestampedModel):
    repo = models.CharField(max_length=180, unique=True)
    category = models.CharField(max_length=80, db_index=True)
    description = models.TextField(blank=True)
    stars = models.PositiveIntegerField(default=0)
    stars_7d = models.IntegerField(default=0)
    forks = models.PositiveIntegerField(default=0)
    open_issues = models.PositiveIntegerField(default=0)
    pushed_at = models.DateTimeField(null=True, blank=True)
    momentum_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    homepage = models.URLField(max_length=800)

    class Meta:
        ordering = ["-momentum_score", "-stars"]


class GlossaryTerm(TimestampedModel):
    slug = models.SlugField(max_length=120, unique=True)
    term = models.CharField(max_length=160)
    term_en = models.CharField(max_length=160, blank=True)
    category = models.CharField(max_length=80, db_index=True)
    subcategory = models.CharField(max_length=80, blank=True)
    difficulty = models.CharField(max_length=30, default="中级")
    definition = models.TextField()
    formula = models.TextField(blank=True)
    interpretation = models.TextField(blank=True)
    tags = models.JSONField(default=list)
    source_url = models.URLField(max_length=800, blank=True)

    class Meta:
        ordering = ["category", "term"]


class OptionContract(TimestampedModel):
    instrument = models.ForeignKey(Instrument, on_delete=models.CASCADE, related_name="options")
    expiry = models.DateField()
    strike = models.DecimalField(max_digits=16, decimal_places=4)
    option_type = models.CharField(max_length=4, choices=[("call", "Call"), ("put", "Put")])
    open_interest = models.PositiveIntegerField(default=0)
    volume = models.PositiveIntegerField(default=0)
    implied_volatility = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    delta = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    gamma = models.DecimalField(max_digits=12, decimal_places=8, null=True, blank=True)
    as_of = models.DateTimeField()
    source = models.ForeignKey(Source, on_delete=models.PROTECT)
    quality_status = models.CharField(
        max_length=20, choices=Observation.Quality.choices, default=Observation.Quality.ESTIMATED
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrument", "expiry", "strike", "option_type"],
                name="unique_option_contract",
            )
        ]
