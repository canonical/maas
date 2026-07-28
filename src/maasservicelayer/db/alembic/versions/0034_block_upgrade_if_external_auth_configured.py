"""Block the upgrade if Candid/RBAC external authentication was in use

Support for the legacy Candid/RBAC (macaroon-based) external authentication has
been removed. Upgrading a deployment that still relies on it would silently
disable external logins and could lock out administrators. To make this an
explicit, recoverable action, this migration aborts the upgrade when the
deployment still shows signs of Candid/RBAC usage.

Detection is done with signals that live in the database regardless of where
secrets are stored:

* The external authentication config secret is present in ``maasserver_secret``
  (the local/database secret backend).
* External users created by Candid/RBAC still exist. These are non-local users
  without an OIDC provider, i.e. ``maasserver_userprofile`` rows with
  ``is_local = false`` and ``provider_id IS NULL`` (OIDC users are also
  non-local but always have a ``provider_id``).

The ``maasserver_vaultsecret`` reference table is intentionally NOT used: it is
only maintained by the legacy code path and is not populated when secrets are
managed through the v3 stack, so it cannot be relied upon.

Revision ID: 0034
Revises: 0033
Create Date: 2026-07-28 09:50:00.000000+00:00

"""

from typing import Sequence

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTERNAL_AUTH_SECRET_PATH = "global/external-auth"

ERROR_MESSAGE = (
    "This MAAS version has removed support for Candid/RBAC external "
    "authentication, but this deployment still relies on it.\n"
    "Upgrading now would disable external logins and could lock out "
    "administrators.\n\n"
    "Before upgrading, on your current MAAS release:\n"
    "  1. Make sure a local administrator account with a usable password "
    "exists (create one with `maas createadmin` if needed).\n"
    "  2. Disable external authentication by running `maas configauth` and "
    "leaving the RBAC URL and Candid agent file blank.\n"
    "  3. Remove or convert any remaining Candid/RBAC users, since they will "
    "no longer be able to authenticate.\n"
    "Once external authentication is cleared, retry the upgrade."
)


def upgrade() -> None:
    conn = op.get_bind()

    secret_configured = conn.execute(
        text("SELECT 1 FROM maasserver_secret WHERE path = :path LIMIT 1"),
        {"path": EXTERNAL_AUTH_SECRET_PATH},
    ).scalar()

    external_users_exist = conn.execute(
        text(
            "SELECT 1 FROM maasserver_userprofile "
            "WHERE is_local = false AND provider_id IS NULL LIMIT 1"
        )
    ).scalar()

    if secret_configured or external_users_exist:
        raise RuntimeError(ERROR_MESSAGE)


def downgrade() -> None:
    # we don't support migration downgrade
    pass
