"""add_unique_constraints_for_custom_boot_assets

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-05 13:47:25.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Partial unique index for bootloader identity (name + architecture)
    # Only applies to uploaded (rtype=2) bootloaders (bootloader_type IS NOT NULL)
    op.create_index(
        "uk_bootresource_bootloader_identity",
        "maasserver_bootresource",
        ["name", "architecture"],
        unique=True,
        postgresql_where="(rtype = 2 AND bootloader_type IS NOT NULL)",
    )

    # Partial unique index for kernel identity (name + architecture + kflavor)
    # Only applies to uploaded (rtype=2) kernels (bootloader_type IS NULL and kflavor IS NOT NULL)
    op.create_index(
        "uk_bootresource_kernel_identity",
        "maasserver_bootresource",
        ["name", "architecture", "kflavor"],
        unique=True,
        postgresql_where="(rtype = 2 AND bootloader_type IS NULL AND kflavor IS NOT NULL)",
    )

    # Regular index for efficient asset lookup/filtering by rtype + name + architecture
    op.create_index(
        "idx_bootresource_rtype_name_arch",
        "maasserver_bootresource",
        ["rtype", "name", "architecture"],
        unique=False,
    )


def downgrade() -> None:
    # We do not support migration downgrade
    pass
