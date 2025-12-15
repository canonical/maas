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
    op.execute("""
    ALTER TABLE maasserver_bootsourceselection RENAME TO maasserver_bootsourceselectionlegacy;
    """)

    op.create_table(
        "maasserver_bootsourceselection",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("created", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
        sa.Column("os", sa.String(20), nullable=False),
        sa.Column("release", sa.String(20), nullable=False),
        sa.Column("arch", sa.Text(), nullable=False),
        sa.Column("boot_source_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["boot_source_id"],
            ["maasserver_bootsource.id"],
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.Column("legacyselection_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["legacyselection_id"],
            ["maasserver_bootsourceselectionlegacy.id"],
            initially="DEFERRED",
            deferrable=True,
        ),
        sa.UniqueConstraint("os", "release", "arch", "boot_source_id"),
    )

    # For each existing legacy selection, create a new selection for each arch in arches
    op.execute("""
    INSERT INTO maasserver_bootsourceselection (created, updated, os, release, arch, boot_source_id, legacyselection_id)
    SELECT
        created,
        updated,
        os,
        release,
        unnest(arches) as arch,
        boot_source_id,
        id
    FROM maasserver_bootsourceselectionlegacy
    WHERE arches IS NOT NULL AND array_length(arches, 1) > 0 AND arches != '{*}';
    """)

    # For arches set to wildcard don't do anything. The creation of the necessary
    # selections will be handled by the fetch-manifest workflow.

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
