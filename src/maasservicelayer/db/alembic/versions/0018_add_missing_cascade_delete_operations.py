"""Add missing cascade delete operations to foreign key constraints.

Revision ID: 0018
Revises: 0017
Create Date: 2026-02-15 15:03:43.090193+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "maasserver_notificat_user_id_87cc11da_fk_auth_user",
        "maasserver_notificationdismissal",
        type_="foreignkey",
    )
    op.create_foreign_key(
        None,
        "maasserver_notificationdismissal",
        "auth_user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )
    op.drop_constraint(
        "maasserver_oidcrevokedtoken_provider_id_fkey",
        "maasserver_oidcrevokedtoken",
        type_="foreignkey",
    )
    op.create_foreign_key(
        None,
        "maasserver_oidcrevokedtoken",
        "maasserver_oidc_provider",
        ["provider_id"],
        ["id"],
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )
    op.drop_constraint(
        "maasserver_refreshtoken_user_id_fkey",
        "maasserver_refreshtoken",
        type_="foreignkey",
    )
    op.create_foreign_key(
        None,
        "maasserver_refreshtoken",
        "auth_user",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
        initially="DEFERRED",
        deferrable=True,
    )


def downgrade() -> None:
    # We do not support migration downgrade.
    pass
