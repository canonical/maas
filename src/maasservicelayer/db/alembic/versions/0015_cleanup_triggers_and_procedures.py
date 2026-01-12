"""
Cleanup old functions that were not deleted when we moved away from django migrations (affects only environments initialized
before 3.7).

Revision ID: 0015
Revises: 0014
Create Date: 2026-01-09 13:59:58.438358+00:00

"""

from typing import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    old_functions = {
        "gen_random_prefix",
        "delete_boot_interface_dns_notification",
        "delete_dns_notification",
        "delete_iface_ip_dns_notification",
        "delete_ip_dns_notification",
        "delete_non_boot_interface_dns_notification",
        "insert_boot_interface_dns_notification",
        "insert_data_dns_notification",
        "insert_non_boot_interface_dns_notification",
        "node_resourcepool_update_notify",
        "reload_dns_notification",
        "resourcepool_create_notify",
        "resourcepool_delete_notify",
        "resourcepool_link_notify",
        "resourcepool_unlink_notify",
        "resourcepool_update_notify",
        "sshkey_create_notify",
        "sshkey_delete_notify",
        "sshkey_update_notify",
        "sslkey_create_notify",
        "sslkey_delete_notify",
        "sslkey_update_notify",
        "sys_dhcp_alert",
        "sys_dhcp_config_ntp_servers_delete",
        "sys_dhcp_config_ntp_servers_insert",
        "sys_dhcp_config_ntp_servers_update",
        "sys_dhcp_config_reserved_ip",
        "sys_dhcp_config_reservedip_delete",
        "sys_dhcp_config_reservedip_insert",
        "sys_dhcp_interface_update",
        "sys_dhcp_iprange_delete",
        "sys_dhcp_iprange_insert",
        "sys_dhcp_iprange_update",
        "sys_dhcp_node_update",
        "sys_dhcp_snippet_delete",
        "sys_dhcp_snippet_insert",
        "sys_dhcp_snippet_update",
        "sys_dhcp_snippet_update_node",
        "sys_dhcp_snippet_update_subnet",
        "sys_dhcp_snippet_update_value",
        "sys_dhcp_staticipaddress_delete",
        "sys_dhcp_staticipaddress_insert",
        "sys_dhcp_staticipaddress_update",
        "sys_dhcp_subnet_delete",
        "sys_dhcp_subnet_update",
        "sys_dhcp_update_all_vlans",
        "sys_dhcp_vlan_update",
        "sys_dns_config_insert",
        "sys_dns_config_update",
        "sys_dns_dnsdata_delete",
        "sys_dns_dnsdata_insert",
        "sys_dns_dnsdata_update",
        "sys_dns_dnsresource_delete",
        "sys_dns_dnsresource_insert",
        "sys_dns_dnsresource_ip_link",
        "sys_dns_dnsresource_ip_unlink",
        "sys_dns_dnsresource_update",
        "sys_dns_domain_delete",
        "sys_dns_domain_insert",
        "sys_dns_domain_update",
        "sys_dns_interface_update",
        "sys_dns_nic_ip_link",
        "sys_dns_nic_ip_unlink",
        "sys_dns_node_delete",
        "sys_dns_node_update",
        "sys_dns_publish",
        "sys_dns_publish_update",
        "sys_dns_staticipaddress_update",
        "sys_dns_subnet_delete",
        "sys_dns_subnet_insert",
        "sys_dns_subnet_update",
        "sys_dns_updates_dns_ip_delete",
        "sys_dns_updates_dns_ip_insert",
        "sys_dns_updates_interface_ip_delete",
        "sys_dns_updates_interface_ip_insert",
        "sys_dns_updates_ip_update",
        "sys_dns_updates_maasserver_dnsdata_delete",
        "sys_dns_updates_maasserver_dnsdata_insert",
        "sys_dns_updates_maasserver_dnsdata_update",
        "sys_dns_updates_maasserver_dnsresource_delete",
        "sys_dns_updates_maasserver_dnsresource_update",
        "sys_dns_updates_maasserver_domain_delete",
        "sys_dns_updates_maasserver_domain_insert",
        "sys_dns_updates_maasserver_domain_update",
        "sys_dns_updates_maasserver_interface_delete",
        "sys_dns_updates_maasserver_node_delete",
        "sys_dns_updates_maasserver_node_insert",
        "sys_dns_updates_maasserver_node_update",
        "sys_dns_updates_maasserver_subnet_delete",
        "sys_dns_updates_maasserver_subnet_insert",
        "sys_dns_updates_maasserver_subnet_update",
        "update_boot_interface_dns_notification",
        "update_data_dns_notification",
        "user_create_notify",
        "user_delete_notify",
        "user_sshkey_link_notify",
        "user_sshkey_unlink_notify",
        "user_sslkey_link_notify",
        "user_sslkey_unlink_notify",
        "user_token_link_notify",
        "user_token_unlink_notify",
        "user_update_notify",
        "zone_create_notify",
        "zone_delete_notify",
        "zone_update_notify",
    }

    for function in old_functions:
        op.execute(f"DROP FUNCTION IF EXISTS {function};")


def downgrade() -> None:
    # We do not support migration downgrade
    pass
