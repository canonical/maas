"""Normalise leftover VM host (Pod) BMC rows to plain BMCs

Revision ID: 0038
Revises: 0037
Create Date: 2026-07-28 08:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# maascommon.enums.bmc.BmcType values.
BMC_TYPE_BMC = 0
BMC_TYPE_POD = 1


def upgrade() -> None:
    # VM host (KVM) support has been removed. The pod-only columns and tables
    # were dropped in 0037, but the shared maasserver_bmc rows that used to
    # represent VM hosts remain. They are now plain power BMCs (their
    # power_type/power_parameters still drive the lxd/virsh power drivers), so
    # normalise their type to BMC.
    op.execute(
        f"UPDATE maasserver_bmc SET bmc_type = {BMC_TYPE_BMC} "
        f"WHERE bmc_type = {BMC_TYPE_POD}"
    )


def downgrade() -> None:
    # we don't support migration downgrade
    pass
