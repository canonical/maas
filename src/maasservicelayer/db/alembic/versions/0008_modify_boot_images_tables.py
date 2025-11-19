"""Modify Boot images tables

Revision ID: 0008
Revises: 0007
Create Date: 2025-09-17 13:45:55.606761+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Set constraints to immediate. Necessary because all the constraints
    # defined in Django are of type INITIALLY DEFERRED. This causes problems
    # when we want to execute more than one statement (e.g. update & alter on
    # same table) since there will be pending triggers.
    # Django ticket: https://code.djangoproject.com/ticket/25105
    # NOTE: `SET CONSTRAINTS` only affects the current transaction,
    # no need to do any rollback logic.
    # https://www.postgresql.org/docs/current/sql-set-constraints.html
    op.execute(
        "SET CONSTRAINTS maasserver_bootsourceselection_boot_source_id_b911aa0f_fk IMMEDIATE"
    )
    op.drop_column("maasserver_bootsourceselection", "labels")
    op.drop_column("maasserver_bootsourceselection", "subarches")

    op.add_column(
        "maasserver_bootsourceselection",
        sa.Column("arch", sa.Text(), nullable=True),
    )

    op.drop_constraint(
        "maasserver_bootsourcesel_boot_source_id_os_releas_0b0d402c_uniq",
        "maasserver_bootsourceselection",
        type_="unique",
    )

    # For each existing selection, create a new selection for each arch in arches
    op.execute("""
    INSERT INTO maasserver_bootsourceselection (created, updated, os, release, arch, boot_source_id)
    SELECT
        created,
        updated,
        os,
        release,
        unnest(arches) as arch,
        boot_source_id
    FROM maasserver_bootsourceselection
    WHERE arches IS NOT NULL AND array_length(arches, 1) > 0 AND arches != '{*}';
    """)

    # If arches is set to wildcard, create a selection for all supported arches
    op.execute("""
    INSERT INTO maasserver_bootsourceselection (created, updated, os, release, arch, boot_source_id)
    SELECT
        created,
        updated,
        os,
        release,
        unnest('{amd64,arm64,armhf,i386,ppc64el,s390x}'::text[]) as arch,
        boot_source_id
    FROM maasserver_bootsourceselection
    WHERE arches = '{*}'
    """)

    # Delete old records
    op.execute("""
    DELETE FROM maasserver_bootsourceselection
    WHERE arches IS NOT NULL AND array_length(arches, 1) > 0;
    """)

    # Make arch column NOT NULL and add the new unique constraint
    op.alter_column("maasserver_bootsourceselection", "arch", nullable=False)
    op.create_unique_constraint(
        "maasserver_bootsourceselection_sourceid_os_release_arch_unique",
        "maasserver_bootsourceselection",
        ["boot_source_id", "os", "release", "arch"],
    )

    op.drop_column("maasserver_bootsourceselection", "arches")

    # Add a column to reference the selection. This can be null as the manual uploaded
    # boot resources don't have a selection.
    op.add_column(
        "maasserver_bootresource",
        sa.Column(
            "selection_id",
            sa.BigInteger(),
            sa.ForeignKey("maasserver_bootsourceselection.id"),
            nullable=True,
        ),
    )

    op.execute("""
    UPDATE maasserver_bootresource
    SET selection_id = selection.id
    FROM maasserver_bootsourceselection selection
    WHERE maasserver_bootresource.name = selection.os || '/' || selection.release AND starts_with(maasserver_bootresource.architecture, selection.arch)
    """)

    op.add_column(
        "maasserver_bootsourcecache",
        sa.Column("latest_version", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    pass
