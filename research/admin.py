from django.contrib import admin

from . import models


@admin.register(models.Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "license_status", "redistribution_allowed")
    search_fields = ("name", "key")


@admin.register(models.IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ("dataset", "source", "status", "row_count", "started_at", "completed_at")
    list_filter = ("status", "source")
    readonly_fields = ("batch_id",)


@admin.register(models.Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = ("series", "instrument", "value", "value_date", "quality_status", "source")
    list_filter = ("quality_status", "source")
    date_hierarchy = "value_date"


@admin.register(models.Thesis)
class ThesisAdmin(admin.ModelAdmin):
    list_display = ("date", "regime", "confidence", "status", "hit_rate", "simulated_return")
    list_filter = ("status", "confidence", "regime")
    search_fields = ("summary", "regime")


@admin.register(models.NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ("title", "source_name", "category", "published_at", "relevance")
    list_filter = ("source_name", "category", "sentiment")
    search_fields = ("title", "summary")


@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "ticker", "primary_node", "rating", "quality_grade", "data_as_of")
    list_filter = ("primary_node__layer", "rating", "quality_grade")
    search_fields = ("name", "name_en", "ticker")
    prepopulated_fields = {"slug": ("name_en",)}


@admin.register(models.SupplyChainNode)
class SupplyChainNodeAdmin(admin.ModelAdmin):
    list_display = ("name", "layer", "quadrant", "narrative_score", "revenue_growth")
    list_filter = ("layer", "quadrant")
    search_fields = ("name", "description")


for model in [
    models.SourceLicense,
    models.DataRequirement,
    models.RawArtifact,
    models.Instrument,
    models.SeriesDefinition,
    models.MarketBar,
    models.MetricSnapshot,
    models.DashboardSnapshot,
    models.QualityCheck,
    models.FallbackEvent,
    models.GeneratedAnalysis,
    models.EvidenceItem,
    models.Trigger,
    models.Invalidation,
    models.Outcome,
    models.ResearchMention,
    models.FundLetter,
    models.FedDocument,
    models.FinancialFact,
    models.SupplyChainEdge,
    models.ModelProfile,
    models.CodingAgentProfile,
    models.GitHubProject,
    models.GlossaryTerm,
    models.OptionContract,
    models.CFTCPosition,
    models.TreasuryAuction,
]:
    admin.site.register(model)

admin.site.site_header = "Atlas Macro 数据与内容后台"
admin.site.site_title = "Atlas Macro Admin"
admin.site.index_title = "研究平台运维"
