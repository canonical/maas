"""Drop RBAC and macaroon root key tables and triggers

Removes the legacy Candid/RBAC external authentication support:
the ``maasserver_rbacsync``, ``maasserver_rbaclastsync`` and
``maasserver_rootkey`` tables together with the RBAC sync triggers and
procedures.

This also drops the legacy ``sys_rbac_config_insert``/``sys_rbac_config_update``
triggers on ``maasserver_config``. They were removed from the trigger code in an
earlier release without a migration to drop them, so databases upgraded from
older releases still carry them; fresh installs never had them (hence the
``IF EXISTS`` guards).

Revision ID: 0039
Revises: 0038
Create Date: 2026-07-30 09:57:54.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the RBAC sync triggers.
    op.execute(
        "DROP TRIGGER IF EXISTS resourcepool_sys_rbac_rpool_insert "
        "ON maasserver_resourcepool;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS resourcepool_sys_rbac_rpool_update "
        "ON maasserver_resourcepool;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS resourcepool_sys_rbac_rpool_delete "
        "ON maasserver_resourcepool;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS rbacsync_sys_rbac_sync ON maasserver_rbacsync;"
    )

    # Drop the legacy Candid/RBAC config triggers. These fired on
    # maasserver_config insert/update for the external_auth_*/rbac_url keys and
    # called sys_rbac_sync_update(). They were removed from the trigger code
    # long ago, but no migration ever dropped them, so databases upgraded from
    # older releases still have them. A fresh install never created them, hence
    # the IF EXISTS. Left in place they would call the now-removed
    # sys_rbac_sync_update() and break config writes.
    op.execute(
        "DROP TRIGGER IF EXISTS config_sys_rbac_config_insert "
        "ON maasserver_config;"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS config_sys_rbac_config_update "
        "ON maasserver_config;"
    )

    # Drop the RBAC sync procedures.
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_rpool_insert() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_rpool_update() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_rpool_delete() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_config_insert() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_config_update() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_sync_update CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sys_rbac_sync() CASCADE;")

    # Drop the tables.
    op.execute("DROP TABLE IF EXISTS maasserver_rbacsync CASCADE;")
    op.execute("DROP TABLE IF EXISTS maasserver_rbaclastsync CASCADE;")
    op.execute("DROP TABLE IF EXISTS maasserver_rootkey CASCADE;")


def downgrade() -> None:
    # we don't support migration downgrade
    pass
