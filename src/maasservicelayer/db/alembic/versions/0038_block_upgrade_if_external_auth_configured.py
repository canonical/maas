"""Clean up legacy Candid/RBAC external authentication on upgrade

Support for the legacy Candid/RBAC (macaroon-based) external authentication has
been removed. Upgrading a deployment that still relies on it would silently
disable external logins and could lock out administrators. This migration makes
the transition explicit and cleans up the leftover state:

1. If external authentication is still configured (the config secret is present
   in ``maasserver_secret``, the local/database secret backend), the upgrade is
   aborted. External authentication must be disabled first so administrators do
   not get locked out.

2. Once external authentication is disabled, the Candid/RBAC user accounts are
   permanently deleted, together with their SSH keys, SSL keys, API tokens,
   OAuth consumers, notifications and stored files. Candid/RBAC users are
   identified as non-local accounts without an OIDC provider, i.e.
   ``maasserver_userprofile`` rows with ``is_local = false`` and
   ``provider_id IS NULL`` (OIDC users are also non-local but always have a
   ``provider_id``).

3. If any of those users still own resources (machines, IP ranges or static IP
   addresses), the upgrade is aborted with the list of offending users so an
   administrator can reassign or release those resources first. Users are never
   deleted while they still own something.

The ``maasserver_vaultsecret`` reference table is intentionally NOT used: it is
only maintained by the legacy code path and is not populated when secrets are
managed through the v3 stack, so it cannot be relied upon.

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-30 09:50:00.000000+00:00

"""

from typing import Sequence

from alembic import op
from sqlalchemy import bindparam, text

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTERNAL_AUTH_SECRET_PATH = "global/external-auth"

EXTERNAL_AUTH_CONFIGURED_MESSAGE = (
    "This MAAS version has removed support for Candid/RBAC external "
    "authentication, but this deployment still relies on it.\n"
    "Upgrading now would disable external logins and could lock out "
    "administrators.\n\n"
    "Before upgrading, on your current MAAS release:\n"
    "  1. Make sure a local administrator account with a usable password "
    "exists (create one with `maas createadmin` if needed).\n"
    "  2. Disable external authentication by running `maas configauth` and "
    "leaving the RBAC URL and Candid agent file blank.\n"
    "Once external authentication is cleared, retry the upgrade.\n\n"
    "WARNING: when you retry the upgrade, all Candid/RBAC user accounts "
    "(non-local users without an OIDC provider) will be PERMANENTLY DELETED, "
    "along with their SSH keys, SSL keys, API tokens, OAuth consumers, "
    "notifications and stored files. Reassign or release any machines, IP "
    "ranges or static IP addresses they own beforehand, otherwise the upgrade "
    "will abort and list the users that still own resources."
)

OWNED_RESOURCES_MESSAGE = (
    "This MAAS version has removed support for Candid/RBAC external "
    "authentication, so the following Candid/RBAC user accounts (non-local "
    "users without an OIDC provider) must be deleted during the upgrade. "
    "However, they still own machines, IP ranges or static IP addresses and "
    "cannot be deleted:\n\n"
    "{users}\n\n"
    "Reassign these resources to another user, or release them, and then "
    "retry the upgrade."
)

# Candid/RBAC users are non-local accounts without an OIDC provider.
CANDID_RBAC_USER_IDS_SQL = (
    "SELECT user_id FROM maasserver_userprofile "
    "WHERE is_local = false AND provider_id IS NULL"
)


def upgrade() -> None:
    conn = op.get_bind()

    secret_configured = conn.execute(
        text("SELECT 1 FROM maasserver_secret WHERE path = :path LIMIT 1"),
        {"path": EXTERNAL_AUTH_SECRET_PATH},
    ).scalar()
    if secret_configured:
        raise RuntimeError(EXTERNAL_AUTH_CONFIGURED_MESSAGE)

    user_ids = [
        row[0] for row in conn.execute(text(CANDID_RBAC_USER_IDS_SQL)).all()
    ]
    if not user_ids:
        return

    owners = (
        conn.execute(
            text(
                "SELECT u.username FROM auth_user u WHERE u.id IN :ids AND ("
                "  EXISTS (SELECT 1 FROM maasserver_node n "
                "WHERE n.owner_id = u.id)"
                "  OR EXISTS (SELECT 1 FROM maasserver_iprange r "
                "WHERE r.user_id = u.id)"
                "  OR EXISTS (SELECT 1 FROM maasserver_staticipaddress s "
                "WHERE s.user_id = u.id)"
                ") ORDER BY u.username"
            ).bindparams(bindparam("ids", expanding=True)),
            {"ids": user_ids},
        )
        .scalars()
        .all()
    )
    if owners:
        raise RuntimeError(
            OWNED_RESOURCES_MESSAGE.format(
                users="\n".join(f"  - {username}" for username in owners)
            )
        )

    # Delete the users' dependent rows before the users themselves. These are
    # the foreign keys to auth_user that use ON DELETE RESTRICT (rows with an
    # ON DELETE CASCADE constraint are removed automatically). Ownership FKs
    # (node, iprange, staticipaddress) are already guaranteed to be empty by
    # the check above.
    dependent_deletes = (
        "DELETE FROM piston3_token WHERE user_id IN :ids",
        "DELETE FROM piston3_consumer WHERE user_id IN :ids",
        "DELETE FROM maasserver_filestorage WHERE owner_id IN :ids",
        "DELETE FROM maasserver_sshkey WHERE user_id IN :ids",
        "DELETE FROM maasserver_sslkey WHERE user_id IN :ids",
        "DELETE FROM maasserver_notification WHERE user_id IN :ids",
        "DELETE FROM auth_user_groups WHERE user_id IN :ids",
        "DELETE FROM auth_user_user_permissions WHERE user_id IN :ids",
    )
    for statement in dependent_deletes:
        conn.execute(
            text(statement).bindparams(bindparam("ids", expanding=True)),
            {"ids": user_ids},
        )

    # maasserver_operation keeps an audit trail and its user_id is nullable, so
    # detach it from the user instead of deleting the records.
    conn.execute(
        text(
            "UPDATE maasserver_operation SET user_id = NULL "
            "WHERE user_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": user_ids},
    )

    conn.execute(
        text(
            "DELETE FROM maasserver_userprofile WHERE user_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": user_ids},
    )
    conn.execute(
        text("DELETE FROM auth_user WHERE id IN :ids").bindparams(
            bindparam("ids", expanding=True)
        ),
        {"ids": user_ids},
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
