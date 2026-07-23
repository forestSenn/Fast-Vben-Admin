import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlmodel import Session

from app.core.database import engine
from app.models import ModuleObservedState
from app.modules.migrations import (
    migrate_edition,
    migration_order,
    module_alembic_config,
)


def test_module_migration_configuration_is_namespaced() -> None:
    items_config = module_alembic_config("items")

    assert migration_order(edition="base") == ["platform"]
    assert migration_order(edition="suite") == ["platform", "items", "erp"]
    assert items_config.get_main_option("script_location") == "app/modules/items/migrations"
    assert items_config.get_main_option("version_table") == "alembic_version_items"
    assert items_config.get_main_option("version_table_schema") == "public"


def test_suite_migration_records_independent_items_revision(db: Session) -> None:
    _ = db
    items_config = module_alembic_config("items")
    expected_items_head = ScriptDirectory.from_config(items_config).get_current_head()
    assert expected_items_head is not None

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE moduleregistry SET observed_state = 'bundled' WHERE code = 'items'")
        )
    assert migrate_edition(edition="suite") == ["platform", "items", "erp"]

    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT to_regclass('items.item'), to_regclass('public.item')")
        ).one() == ("items.item", None)
        assert connection.execute(
            text("SELECT version_num FROM public.alembic_version_items")
        ).scalar_one() == expected_items_head
        assert connection.execute(
            text("SELECT actual_revision FROM moduleregistry WHERE code = 'items'")
        ).scalar_one() == "items-head"
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM modulestateaudit "
                "WHERE module_code = 'items' "
                "AND action = 'module.observed_state.changed' "
                "AND next_value = 'ready'"
            )
        ).scalar_one() >= 1
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM outboxevent "
                "WHERE event_type = 'platform.module.observed_state.changed' "
                "AND aggregate_id = 'items'"
            )
        ).scalar_one() >= 1
        event_count = connection.execute(
            text(
                "SELECT COUNT(*) FROM outboxevent "
                "WHERE event_type = 'platform.module.observed_state.changed' "
                "AND aggregate_id = 'items'"
            )
        ).scalar_one()

    assert migrate_edition(edition="suite") == ["platform", "items", "erp"]
    with engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM outboxevent "
                "WHERE event_type = 'platform.module.observed_state.changed' "
                "AND aggregate_id = 'items'"
            )
        ).scalar_one() == event_count


def test_failed_module_migration_marks_only_the_failed_module_degraded(
    monkeypatch, db: Session
) -> None:
    _ = db
    from app.modules import migrations

    original_upgrade = migrations.command.upgrade
    original_is_current = migrations.migration_is_current

    def fail_items_upgrade(config, revision):
        if config.get_main_option("script_location") == "app/modules/items/migrations":
            raise RuntimeError("simulated items migration failure")
        return original_upgrade(config, revision)

    def items_need_migration(*, config, connection):
        if config.get_main_option("script_location") == "app/modules/items/migrations":
            return False
        return original_is_current(config=config, connection=connection)

    monkeypatch.setattr(migrations.command, "upgrade", fail_items_upgrade)
    monkeypatch.setattr(migrations, "migration_is_current", items_need_migration)
    with pytest.raises(RuntimeError, match="simulated items"):
        migrate_edition(edition="suite")

    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT observed_state FROM moduleregistry WHERE code = 'platform'")
        ).scalar_one() == ModuleObservedState.READY
        assert connection.execute(
            text("SELECT observed_state FROM moduleregistry WHERE code = 'items'")
        ).scalar_one() == ModuleObservedState.DEGRADED
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM modulestateaudit "
                "WHERE module_code = 'items' "
                "AND action = 'module.observed_state.changed' "
                "AND next_value = 'degraded'"
            )
        ).scalar_one() >= 1
        assert connection.execute(
            text(
                "SELECT COUNT(*) FROM outboxevent "
                "WHERE event_type = 'platform.module.observed_state.changed' "
                "AND aggregate_id = 'items'"
            )
        ).scalar_one() >= 1

    monkeypatch.setattr(migrations.command, "upgrade", original_upgrade)
    monkeypatch.setattr(migrations, "migration_is_current", original_is_current)
    assert migrate_edition(edition="suite") == ["platform", "items", "erp"]
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT observed_state FROM moduleregistry WHERE code = 'items'")
        ).scalar_one() == ModuleObservedState.READY
