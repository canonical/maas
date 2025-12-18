"""
Add for_ephemeral_environment column to maasserver_nodeuserdata to differentiate between the user data of the ephemeral and the
user data submitted by the user during deployment.

Revision ID: 0013
Revises: 0012
Create Date: 2025-11-25 13:59:58.438358+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maasserver_nodeuserdata",
        sa.Column(
            "for_ephemeral_environment",
            sa.Boolean(),
            nullable=False,
        ),
    )

    # If the node is in DEPLOYED(6) or DEPLOYING(9) status, then assume the userdata is not ephemeral.
    op.execute("""
        UPDATE maasserver_nodeuserdata AS nud
        SET for_ephemeral_environment = CASE
            WHEN EXISTS (
                SELECT 1
                FROM maasserver_node AS n
                WHERE n.id = nud.node_id
                  AND n.status IN (6, 9)
            ) THEN FALSE
            ELSE TRUE
        END;
        """)

    op.drop_constraint(
        "metadataserver_nodeuserdata_node_id_key",
        "maasserver_nodeuserdata",
        type_="unique",
    )

    op.execute("""
    ALTER TABLE ONLY maasserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_node_id_for_ephemeral_environment_key UNIQUE (node_id, for_ephemeral_environment);
    """)


def downgrade() -> None:
    # We do not support migration downgrade
    pass
