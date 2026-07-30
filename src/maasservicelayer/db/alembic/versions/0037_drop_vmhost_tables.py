"""Drop VM host (Pod) tables, columns and notification triggers

Revision ID: 0037
Revises: 0036
Create Date: 2026-07-27 08:00:00.000000+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Notification trigger functions created for VM hosts (pods) and VM host
# clusters. Dropping them with CASCADE also removes the triggers that use
# them on the kept tables (maasserver_bmc, maasserver_node,
# maasserver_interface) as well as on the tables removed below.
VMHOST_TRIGGER_FUNCTIONS = (
    "vmcluster_insert_notify",
    "vmcluster_update_notify",
    "vmcluster_delete_notify",
    "node_vmcluster_insert_notify",
    "node_vmcluster_update_notify",
    "node_vmcluster_delete_notify",
    "pod_insert_notify",
    "pod_update_notify",
    "pod_delete_notify",
    "node_pod_insert_notify",
    "node_pod_update_notify",
    "node_pod_delete_notify",
    "interface_pod_notify",
)

# Pod-only columns on the shared maasserver_bmc table.
BMC_VMHOST_COLUMNS = (
    "bmc_type",
    "default_storage_pool_id",
    "pool_id",
    "zone_id",
    "architectures",
    "capabilities",
    "cores",
    "cpu_speed",
    "local_storage",
    "memory",
    "name",
    "tags",
    "cpu_over_commit_ratio",
    "memory_over_commit_ratio",
    "default_macvlan_mode",
    "version",
    "created_with_cert_expiration_days",
    "created_with_maas_generated_cert",
    "created_with_trust_password",
)

# Tables dependent on maasserver_bmc are removed child-first.
VMHOST_TABLES = (
    "maasserver_virtualmachineinterface",
    "maasserver_virtualmachinedisk",
    "maasserver_virtualmachine",
    "maasserver_podhints_nodes",
    "maasserver_podhints",
    "maasserver_podstoragepool",
    "maasserver_vmcluster",
)


def upgrade() -> None:
    # The maasserver_podhost view joins VM hosts (pods) to the nodes they
    # host and depends on pod-only columns of maasserver_bmc. Drop it before
    # removing those columns.
    op.execute("DROP VIEW IF EXISTS maasserver_podhost")

    for function in VMHOST_TRIGGER_FUNCTIONS:
        op.execute(f"DROP FUNCTION IF EXISTS {function}() CASCADE")

    for column in BMC_VMHOST_COLUMNS:
        op.drop_column("maasserver_bmc", column)

    for table in VMHOST_TABLES:
        op.drop_table(table)


def downgrade() -> None:
    # we don't support migration downgrade
    pass
