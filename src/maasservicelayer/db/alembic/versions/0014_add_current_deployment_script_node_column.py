"""
Add current_deployment_script column to the node table to keep track of the deployment script set.

Revision ID: 0014
Revises: 0013
Create Date: 2025-11-25 13:59:58.438358+00:00

"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "maasserver_node",
        sa.Column(
            "current_deployment_script_set_id",
            sa.BIGINT(),
            nullable=True,
        ),
    )

    op.execute("""
    CREATE INDEX maasserver_node_current_deployment_script_set_id_0013 ON maasserver_node USING btree (
    current_deployment_script_set_id);
    """)

    op.execute("""
    ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT maasserver_node_current_deployment_0013_fk_maasserve FOREIGN KEY (current_deployment_script_set_id)
    REFERENCES maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;
    """)


def downgrade() -> None:
    # We do not support migration downgrade
    pass
