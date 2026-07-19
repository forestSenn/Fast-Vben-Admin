from alembic import context
from sqlalchemy import MetaData, engine_from_config, pool

from app.core.config import settings
from app.modules.items.infrastructure.models import Item

config = context.config
target_metadata = MetaData()
Item.__table__.to_metadata(target_metadata)


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "schema":
        return name == "items"
    if type_ == "table":
        return parent_names.get("schema_name") == "items"
    return True


def get_url() -> str:
    return str(settings.SQLALCHEMY_DATABASE_URI)


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        literal_binds=True,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        version_table="alembic_version_items",
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            version_table="alembic_version_items",
            version_table_schema="public",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
