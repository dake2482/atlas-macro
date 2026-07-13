from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module

import pytest
from django.apps import apps
from django.db import connection, migrations, models
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from research.models import Source, SourceLicense, Thesis
from tests.thesis_factories import build_complete_thesis


@pytest.mark.django_db
def test_thesis_review_migration_fails_closed_for_legacy_publications():
    migration = import_module(
        "research.migrations.0015_thesis_review_publication_contract"
    )
    legitimate = build_complete_thesis("migration-reviewed", report_date=date(1901, 1, 1))
    demo = Thesis.objects.create(
        date=date(1901, 1, 2),
        regime="demo",
        summary="演示日报 1901-01-02：仅用于测试",
        evidence=[],
        triggers=[],
        invalidation="test",
    )

    migration.unpublish_legacy_theses(apps, schema_editor=None)

    legitimate.refresh_from_db()
    demo.refresh_from_db()
    assert legitimate.is_published is False
    assert legitimate.published_at is None
    assert legitimate.review_status == Thesis.ReviewStatus.DRAFT
    assert legitimate.reviewed_by == ""
    assert legitimate.reviewed_at is None
    assert legitimate.publication_fingerprint == ""
    assert demo.is_published is False
    assert demo.published_at is None


def test_thesis_review_migration_orders_cleanup_before_constraint():
    migration = import_module(
        "research.migrations.0015_thesis_review_publication_contract"
    )
    operations = migration.Migration.operations
    cleanup_index = next(
        index for index, operation in enumerate(operations) if isinstance(operation, migrations.RunPython)
    )
    constraint_index = next(
        index
        for index, operation in enumerate(operations)
        if isinstance(operation, migrations.AddConstraint)
    )
    review_fields = {
        operation.name: index
        for index, operation in enumerate(operations)
        if isinstance(operation, migrations.AddField)
        and operation.name
        in {"review_status", "reviewed_at", "reviewed_by", "publication_fingerprint"}
    }

    assert set(review_fields) == {
        "review_status",
        "reviewed_at",
        "reviewed_by",
        "publication_fingerprint",
    }
    assert all(index < cleanup_index for index in review_fields.values())
    assert cleanup_index < constraint_index
    assert migration.Migration.dependencies == [
        ("research", "0014_releasevintageobservation")
    ]


@pytest.mark.django_db(transaction=True)
def test_real_0014_to_0015_migration_fails_closed():
    executor = MigrationExecutor(connection)
    old_target = [("research", "0014_releasevintageobservation")]
    new_target = [("research", "0015_thesis_review_publication_contract")]
    executor.migrate(old_target)
    old_apps = executor.loader.project_state(old_target).apps
    OldSource = old_apps.get_model("research", "Source")
    OldDashboardSnapshot = old_apps.get_model("research", "DashboardSnapshot")
    OldThesis = old_apps.get_model("research", "Thesis")
    source = OldSource.objects.create(
        key="migration-executor-internal",
        name="Migration executor source",
    )
    snapshot = OldDashboardSnapshot.objects.create(
        key="daily-evidence",
        title="Legacy daily evidence",
        as_of=timezone.now(),
        data={},
        source=source,
        is_published=True,
    )
    legacy = OldThesis.objects.create(
        date=date(1901, 1, 3),
        regime="legacy-publication",
        summary="Legacy public row",
        evidence=[],
        triggers=[],
        invalidation="legacy",
        source_snapshot=snapshot,
        is_published=True,
        published_at=timezone.now(),
    )

    executor = MigrationExecutor(connection)
    executor.migrate(new_target)
    new_apps = executor.loader.project_state(new_target).apps
    NewThesis = new_apps.get_model("research", "Thesis")
    migrated = NewThesis.objects.get(pk=legacy.pk)

    assert migrated.is_published is False
    assert migrated.published_at is None
    assert migrated.review_status == "draft"
    assert migrated.reviewed_by == ""
    assert migrated.reviewed_at is None
    assert migrated.publication_fingerprint == ""


@pytest.mark.django_db
def test_source_license_migration_keeps_only_latest_created_decision_current():
    migration = import_module("research.migrations.0009_sourcelicense_is_current_and_more")
    source = Source.objects.create(key="migration-licence", name="Migration licence")
    older = SourceLicense.objects.create(
        source=source,
        status=Source.LicenseStatus.OPEN,
        scope="older",
        is_current=True,
        reviewed_at=timezone.now(),
    )
    newer = SourceLicense.objects.create(
        source=source,
        status=Source.LicenseStatus.RESTRICTED,
        scope="newer",
        is_current=False,
        reviewed_at=None,
    )
    now = timezone.now()
    SourceLicense.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=1))
    SourceLicense.objects.filter(pk=newer.pk).update(created_at=now)

    migration.keep_latest_license_current(apps, schema_editor=None)

    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.is_current is False
    assert newer.is_current is True
    assert SourceLicense.objects.filter(source=source, is_current=True).count() == 1
    # A nullable ``reviewed_at`` must not put the older reviewed row first.
    assert SourceLicense.objects.filter(source=source).first() == newer


def test_source_license_schema_operations_are_ordered_safely():
    data_migration = import_module("research.migrations.0009_sourcelicense_is_current_and_more")
    constraint_migration = import_module(
        "research.migrations.0010_sourcelicense_current_constraint"
    )
    operations = data_migration.Migration.operations

    is_current_index = next(
        index
        for index, operation in enumerate(operations)
        if isinstance(operation, migrations.AddField) and operation.name == "is_current"
    )
    required_notice_index = next(
        index
        for index, operation in enumerate(operations)
        if isinstance(operation, migrations.AddField) and operation.name == "required_notice"
    )
    cleanup_index = next(
        index
        for index, operation in enumerate(operations)
        if isinstance(operation, migrations.RunPython)
    )
    constraint = next(
        operation
        for operation in constraint_migration.Migration.operations
        if isinstance(operation, migrations.AddConstraint)
        and operation.constraint.name == "one_current_license_per_source"
    )
    index_operation = next(
        operation
        for operation in constraint_migration.Migration.operations
        if isinstance(operation, migrations.AlterField) and operation.name == "is_current"
    )

    assert is_current_index < cleanup_index
    assert required_notice_index < cleanup_index
    assert index_operation.field.db_index is True
    assert constraint.constraint.condition == models.Q(is_current=True)
    assert constraint_migration.Migration.dependencies == [
        ("research", "0009_sourcelicense_is_current_and_more")
    ]
    assert SourceLicense._meta.ordering == ["-created_at", "-pk"]
