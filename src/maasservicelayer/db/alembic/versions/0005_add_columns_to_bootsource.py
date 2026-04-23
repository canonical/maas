# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Add columns to bootsource

Revision ID: 0005
Revises: 0004
Create Date: 2025-06-24 11:16:07.410600+00:00

"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import auto, IntFlag
import os
from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

now = datetime.now(timezone.utc)

# Copied from src/maascommon/constants.py
KEYRINGS_PATH = (
    "/snap/maas/current/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
    if os.environ.get("SNAP")
    else "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
)

STABLE_IMAGES_STREAM_URL = "http://images.maas.io/ephemeral-v3/stable"
STABLE_IMAGES_STREAM_NAME = "MAAS Stable"

CANDIDATE_IMAGES_STREAM_URL = "http://images.maas.io/ephemeral-v3/candidate"
CANDIDATE_IMAGES_STREAM_NAME = "MAAS Candidate"


class BootSourceFlag(IntFlag):
    NO_BOOT_SOURCE = auto()
    STABLE = auto()
    CANDIDATE = auto()


def get_boot_source_status() -> BootSourceFlag:
    res = op.get_bind().execute(text("SELECT * FROM maasserver_bootsource"))
    boot_sources = [row._asdict() for row in res.all()]

    if len(boot_sources) == 0:
        return BootSourceFlag.NO_BOOT_SOURCE

    flag = BootSourceFlag(0)

    for boot_source in boot_sources:
        if boot_source["url"] == STABLE_IMAGES_STREAM_URL:
            flag |= BootSourceFlag.STABLE
        elif boot_source["url"] == CANDIDATE_IMAGES_STREAM_URL:
            flag |= BootSourceFlag.CANDIDATE

    return flag


@dataclass
class BootSourceCreateModel:
    name: str
    url: str
    priority: int
    enabled: bool = field(init=False, default=False)

    def create(self):
        return (
            op.get_bind()
            .execute(
                text("""
                INSERT INTO maasserver_bootsource (created, updated, name, url, keyring_filename, keyring_data, priority, skip_keyring_verification, enabled)
                VALUES (:created, :updated, :name, :url, :keyring_filename, '', :priority, false, :enabled)
                ON CONFLICT (url) DO UPDATE SET name = EXCLUDED.name, priority = EXCLUDED.priority, enabled = EXCLUDED.enabled
                RETURNING id
            """),
                {
                    "created": now,
                    "updated": now,
                    "name": self.name,
                    "url": self.url,
                    "keyring_filename": KEYRINGS_PATH,
                    "priority": self.priority,
                    "enabled": self.enabled,
                },
            )
            .scalar_one()
        )


def get_architecture():
    """Get the Debian architecture of the running system."""
    arch = os.getenv("SNAP_ARCH")
    if not arch:
        # assume it's a deb environment
        import apt_pkg

        apt_pkg.init()
        arch = apt_pkg.get_architectures()[0]
    return arch


def create_selection_stable(stable_boot_source_id: int):
    arch = get_architecture()
    if arch in ("", "amd64"):
        arches = ["amd64"]
    else:
        arches = [arch, "amd64"]

    op.get_bind().execute(
        text("""
            INSERT INTO maasserver_bootsourceselection (created, updated, os, release, arches, subarches, labels, boot_source_id)
            VALUES (:created, :updated, :os, :release, :arches, '{*}', '{*}', :boot_source_id)
        """),
        {
            "created": now,
            "updated": now,
            "os": "ubuntu",
            "release": "noble",
            "arches": arches,
            "boot_source_id": stable_boot_source_id,
        },
    )


def upgrade() -> None:
    op.add_column(
        "maasserver_bootsource",
        sa.Column("priority", sa.Integer(), nullable=True),
    )
    op.add_column(
        "maasserver_bootsource",
        sa.Column("name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "maasserver_bootsource",
        sa.Column("enabled", sa.Boolean(), server_default=sa.true()),
    )
    op.add_column(
        "maasserver_bootsource",
        sa.Column(
            "skip_keyring_verification",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )

    # Make sure that the URLs for stable and candidate don't have a trailing slash.
    # In this way we'll make sure to find them in any case.
    op.execute(f"""
        UPDATE maasserver_bootsource
        SET url = RTRIM(url, '/')
        WHERE url IN ('{STABLE_IMAGES_STREAM_URL}/', '{CANDIDATE_IMAGES_STREAM_URL}/')
    """)

    status = get_boot_source_status()

    stable_boot_source = BootSourceCreateModel(
        name=STABLE_IMAGES_STREAM_NAME,
        url=STABLE_IMAGES_STREAM_URL,
        priority=2,
    )
    candidate_boot_source = BootSourceCreateModel(
        name=CANDIDATE_IMAGES_STREAM_NAME,
        url=CANDIDATE_IMAGES_STREAM_URL,
        priority=1,
    )

    if status & BootSourceFlag.NO_BOOT_SOURCE:
        stable_boot_source.enabled = True
        candidate_boot_source.enabled = False
        create_default_selection = True
    else:
        stable_boot_source.enabled = (
            True if status & BootSourceFlag.STABLE else False
        )
        candidate_boot_source.enabled = (
            True if status & BootSourceFlag.CANDIDATE else False
        )
        create_default_selection = True

    id = stable_boot_source.create()
    candidate_boot_source.create()

    if create_default_selection:
        create_selection_stable(id)

    # Backfill priority based on creation order:
    # - newer boot sources (later 'created' timestamps) get higher priority
    # - values are spaced out (e.g., 10, 20, 30...) to leave room for future
    #   insertions without immediate reordering
    # - a unique constraint will be added later, so all priorities must be
    #   distinct
    # - stable and candidate boot sources are excluded as they were created
    #   earlier
    op.execute(f"""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (ORDER BY created ASC) AS priority
            FROM maasserver_bootsource
            WHERE url NOT IN ('{STABLE_IMAGES_STREAM_URL}', '{CANDIDATE_IMAGES_STREAM_URL}')
        )
        UPDATE maasserver_bootsource
        SET priority = ranked.priority*10
        FROM ranked
        WHERE maasserver_bootsource.id = ranked.id
    """)

    op.execute(f"""
        UPDATE maasserver_bootsource
        SET name = url
        WHERE url NOT IN ('{STABLE_IMAGES_STREAM_URL}', '{CANDIDATE_IMAGES_STREAM_URL}')
    """)

    # Set skip_keyring_verification to False for the unsigned streams (until
    # this change the keyring was verified)
    op.execute("""
        UPDATE maasserver_bootsource
        SET skip_keyring_verification = TRUE
        WHERE url LIKE '%%.json'
    """)

    # Alter the columns to be non-nullable
    op.alter_column("maasserver_bootsource", "name", nullable=False)
    op.alter_column("maasserver_bootsource", "priority", nullable=False)

    op.alter_column("maasserver_bootsource", "enabled", server_default=None)

    op.alter_column(
        "maasserver_bootsource",
        "skip_keyring_verification",
        server_default=None,
    )

    # Add constraints
    op.create_unique_constraint(
        constraint_name="maasserver_bootsource_priority_key",
        table_name="maasserver_bootsource",
        columns=["priority"],
    )
    op.create_unique_constraint(
        constraint_name="maasserver_bootsource_name_key",
        table_name="maasserver_bootsource",
        columns=["name"],
    )


def downgrade() -> None:
    pass
