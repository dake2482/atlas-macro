from __future__ import annotations

from datetime import date, timedelta
from importlib import import_module

import pytest
from django.apps import apps
from django.db import migrations, models
from django.utils import timezone

from research.models import Source, SourceLicense, Thesis


@pytest.mark.django_db
def test_thesis_migration_publishes_only_existing_non_demo_reports():
    migration = import_module(
        "research.migrations.0007_thesis_is_published_thesis_published_at_and_more"
    )
    legitimate = Thesis.objects.create(
        date=date(1901, 1, 1),
        regime="historical",
        summary="Existing reviewed report",
        evidence=[],
        triggers=[],
        invalidation="test",
    )
    demo = Thesis.objects.create(
        date=date(1901, 1, 2),
        regime="demo",
        summary="演示日报 1901-01-02：仅用于测试",
        evidence=[],
        triggers=[],
        invalidation="test",
    )

    migration.publish_existing_non_demo_theses(apps, schema_editor=None)

    legitimate.refresh_from_db()
    demo.refresh_from_db()
    assert legitimate.is_published is True
    assert legitimate.published_at == legitimate.updated_at
    assert demo.is_published is False
    assert demo.published_at is None


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

    assert is_current_index < cleanup_index
    assert required_notice_index < cleanup_index
    assert constraint.constraint.condition == models.Q(is_current=True)
    assert constraint_migration.Migration.dependencies == [
        ("research", "0009_sourcelicense_is_current_and_more")
    ]
    assert SourceLicense._meta.ordering == ["-created_at", "-pk"]
