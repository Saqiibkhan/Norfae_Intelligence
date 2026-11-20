"""Baseline marker for the pre-existing Norfae schema.

This revision records the schema already present in the development database.
It intentionally contains no schema operations. Apply it to that existing
database with ``alembic stamp``; it is not a schema-creation migration for a
new, empty database.
"""

from typing import Sequence, Union


revision: str = "20261116_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
