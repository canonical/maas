"""Add last_deployed to bootresources

Revision ID: 0001
Revises: 0000
Create Date: 2025-06-05 08:10:12.377883+00:00

"""

from typing import Sequence

from alembic import op  # type: ignore
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = "0000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maasserver_bootresource", sa.Column("last_deployed", sa.DateTime)
    )
    # maasserver_event.description is in the form 'deployed ubuntu/noble/amd64/generic'
    # we use substring with a regex to take the image name and image architecture.
    # (A bit hard to read, look at capturing groups ())
    op.execute("""
UPDATE maasserver_bootresource SET last_deployed = deployed_image.last_deployed FROM
  (
    SELECT
      substring(maasserver_event.description from '(\\w*\\/\\w*)\\/\\w*\\/\\w*') as name,
      substring(maasserver_event.description from '\\w*\\/\\w*\\/(\\w*)\\/\\w*') as arch,
      MAX(maasserver_event.created) AS last_deployed
    FROM maasserver_event
    WHERE
      maasserver_event.type_id = (SELECT et.id FROM maasserver_eventtype et WHERE et.name = 'IMAGE_DEPLOYED')
    GROUP BY (name, arch)
  ) AS deployed_image
WHERE
  maasserver_bootresource.name = deployed_image.name AND
  substring( maasserver_bootresource.architecture from '^(\\w*)\\/') = deployed_image.arch;
""")


def downgrade() -> None:
    op.drop_column("maasserver_bootresource", "last_deployed")
