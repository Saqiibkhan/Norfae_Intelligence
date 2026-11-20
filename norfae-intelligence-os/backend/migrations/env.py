from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

from alembic import context


# Keep Alembic independent from the current working directory and avoid importing
# app.main, whose startup handlers launch schedulers and background work.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
import app.models  # noqa: E402


# Import each model module so autogeneration sees the complete metadata even when
# a model is not re-exported by app.models.__init__.
for module in pkgutil.iter_modules(app.models.__path__):
    if module.name.endswith("_model"):
        importlib.import_module(f"app.models.{module.name}")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
