from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction

from . import models
from .thesis_publication import publish_theses, unpublish_theses


@admin.register(models.Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "license_status", "redistribution_allowed")
    search_fields = ("name", "key")


@admin.register(models.SourceLicense)
class SourceLicenseAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "status",
        "is_current",
        "public_display_allowed",
        "valid_from",
        "valid_until",
        "reviewed_at",
    )
    list_filter = ("is_current", "status", "public_display_allowed")
    search_fields = ("source__name", "source__key", "scope")


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


@admin.register(models.ReleaseVintageObservation)
class ReleaseVintageObservationAdmin(admin.ModelAdmin):
    list_display = (
        "series",
        "value_date",
        "release_date",
        "estimate_round",
        "value",
        "quality_status",
        "source",
    )
    list_filter = ("estimate_round", "quality_status", "source")
    search_fields = ("series__name", "series__key", "vintage_label")
    date_hierarchy = "release_date"
    readonly_fields = ("batch_id",)


@admin.register(models.Thesis)
class ThesisAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "regime",
        "confidence",
        "status",
        "review_status",
        "is_published",
        "published_at",
        "hit_rate",
        "simulated_return",
    )
    list_filter = ("is_published", "review_status", "status", "confidence", "regime")
    search_fields = ("summary", "regime")
    readonly_fields = (
        "review_status",
        "reviewed_by",
        "reviewed_at",
        "publication_fingerprint",
        "is_published",
        "published_at",
    )
    actions = ("publish_selected", "unpublish_selected")

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.is_published:
            fields.extend(field.name for field in self.model._meta.fields)
        return tuple(dict.fromkeys(fields))

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and models.Thesis.objects.filter(pk=obj.pk, is_published=True).exists():
            raise PermissionDenied("已发布日报必须先撤回，才能编辑。")
        super().save_model(request, obj, form, change)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not request.user.has_perm("research.publish_thesis"):
            actions.pop("publish_selected", None)
        if not request.user.has_perm("research.withdraw_thesis"):
            actions.pop("unpublish_selected", None)
        return actions

    @admin.action(description="审核并发布所选日报")
    def publish_selected(self, request, queryset):
        if not request.user.has_perm("research.publish_thesis"):
            raise PermissionDenied("缺少日报审核发布权限。")
        with transaction.atomic():
            outcome = publish_theses(queryset, reviewer=request.user.get_username())
            if outcome.ok:
                for thesis in models.Thesis.objects.filter(pk__in=outcome.published_ids):
                    self.log_change(
                        request,
                        thesis,
                        "通过 daily-evidence v1 安全门；相同版本保持原发布时间",
                    )
        if not outcome.ok:
            details = "; ".join(
                f"Thesis {pk}: {', '.join(reasons)}"
                for pk, reasons in sorted(outcome.errors.items())
            )
            self.message_user(
                request,
                f"发布被安全门拒绝，所选日报均未更改。{details}",
                level=messages.ERROR,
            )
            return
        self.message_user(
            request,
            f"已原子审核并发布 {len(outcome.published_ids)} 篇日报。",
            level=messages.SUCCESS,
        )

    @admin.action(description="撤回所选日报")
    def unpublish_selected(self, request, queryset):
        if not request.user.has_perm("research.withdraw_thesis"):
            raise PermissionDenied("缺少日报撤回权限。")
        with transaction.atomic():
            withdrawn_ids = unpublish_theses(queryset)
            for thesis in models.Thesis.objects.filter(pk__in=withdrawn_ids):
                self.log_change(request, thesis, "撤回公开日报，保留审核记录")
        self.message_user(
            request,
            f"已撤回 {len(withdrawn_ids)} 篇日报。",
            level=messages.SUCCESS,
        )


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


class ImmutableSnapshotAdmin(admin.ModelAdmin):
    """Snapshots are written by coordinators and inspected read-only in Admin."""

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):  # pragma: no cover - defence in depth
        raise PermissionDenied("快照只能由经过验证的数据发布器写入。")


@admin.register(models.MetricSnapshot)
class MetricSnapshotAdmin(ImmutableSnapshotAdmin):
    list_display = ("key", "display_value", "value_date", "quality_status", "source")
    list_filter = ("quality_status", "source")
    search_fields = ("key", "label")


@admin.register(models.DashboardSnapshot)
class DashboardSnapshotAdmin(ImmutableSnapshotAdmin):
    list_display = ("key", "title", "as_of", "quality_status", "is_published")
    list_filter = ("key", "quality_status", "is_published")
    search_fields = ("key", "title", "summary")


class ThesisRelationAdmin(admin.ModelAdmin):
    """Require withdrawal before changing any part of a published report graph."""

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and obj.thesis_id and obj.thesis.is_published:
            return tuple(field.name for field in self.model._meta.fields)
        return super().get_readonly_fields(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "thesis":
            kwargs["queryset"] = models.Thesis.objects.filter(is_published=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        existing_published = bool(
            change
            and self.model.objects.filter(pk=obj.pk, thesis__is_published=True).exists()
        )
        target_published = bool(obj.thesis_id and obj.thesis.is_published)
        if existing_published or target_published:
            raise PermissionDenied("已发布日报必须先撤回，才能修改关联内容。")
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.thesis_id and obj.thesis.is_published:
            return False
        return super().has_delete_permission(request, obj)

    def delete_queryset(self, request, queryset):
        if queryset.filter(thesis__is_published=True).exists():
            raise PermissionDenied("已发布日报必须先撤回，才能删除关联内容。")
        super().delete_queryset(request, queryset)


@admin.register(models.EvidenceItem)
class EvidenceItemAdmin(ThesisRelationAdmin):
    list_display = ("label", "thesis", "analysis", "source", "value_date")
    search_fields = ("label", "body", "thesis__regime")


@admin.register(models.Trigger)
class TriggerAdmin(ThesisRelationAdmin):
    list_display = ("name", "thesis", "status", "triggered_at")
    list_filter = ("status",)
    search_fields = ("name", "condition", "thesis__regime")


@admin.register(models.Invalidation)
class InvalidationAdmin(ThesisRelationAdmin):
    list_display = ("thesis", "is_triggered", "observed_at")
    list_filter = ("is_triggered",)
    search_fields = ("condition", "thesis__regime")


for model in [
    models.DataRequirement,
    models.RawArtifact,
    models.Instrument,
    models.SeriesDefinition,
    models.MarketBar,
    models.QualityCheck,
    models.FallbackEvent,
    models.GeneratedAnalysis,
    models.Outcome,
    models.ResearchMention,
    models.FundLetter,
    models.FedDocument,
    models.FinancialFact,
    models.SupplyChainEdge,
    models.ModelProfile,
    models.CodingAgentProfile,
    models.GitHubProject,
    models.GitHubProjectSnapshot,
    models.GlossaryTerm,
    models.OptionContract,
    models.CFTCPosition,
    models.TreasuryAuction,
]:
    admin.site.register(model)

admin.site.site_header = "Atlas Macro 数据与内容后台"
admin.site.site_title = "Atlas Macro Admin"
admin.site.index_title = "研究平台运维"
