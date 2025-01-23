#  Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Interval,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, INET, JSONB

METADATA = MetaData()

# Keep them in alphabetical order!

BlockDeviceTable = Table(
    "maasserver_blockdevice",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), primary_key=True),
    Column("id_path", String(4096), nullable=True),
    Column("size", BigInteger, nullable=False),
    Column("block_size", Integer, nullable=False),
    Column("tags", ARRAY(Text), nullable=True),
    Column(
        "node_config_id",
        BigInteger,
        ForeignKey("maasserver_nodeconfig.id"),
        nullable=False,
    ),
)

BMCTable = Table(
    "maasserver_bmc",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("power_type", String(10), nullable=False),
    Column(
        "ip_address_id",
        BigInteger,
        ForeignKey("maasserver_staticipaddress.id"),
        nullable=True,
    ),
    Column("architectures", ARRAY(Text), nullable=True),
    Column("bmc_type", Integer, nullable=False),
    Column("capabilities", ARRAY(Text), nullable=True),
    Column("cores", Integer, nullable=False),
    Column("cpu_speed", Integer, nullable=False),
    Column("local_storage", Integer, nullable=False),
    Column("memory", Integer, nullable=False),
    Column("name", String(255), nullable=False),
    Column(
        "pool_id",
        Integer,
        ForeignKey("maasserver_resourcepool.id"),
        nullable=True,
    ),
    Column(
        "zone_id", BigInteger, ForeignKey("maasserver_zone.id"), nullable=False
    ),
    Column("tags", ARRAY(Text), nullable=True),
    Column("cpu_over_commit_ratio", Float, nullable=False),
    Column("memory_over_commit_ratio", Float, nullable=False),
    Column("default_storage_pool_id", Integer, nullable=True),
    Column("power_parameters", JSONB, nullable=False),
    Column("default_macvlan_mode", String(32), nullable=True),
    Column("version", Text, nullable=False),
    Column("created_with_cert_expiration_days", Integer, nullable=True),
    Column("created_with_maas_generated_cert", Boolean, nullable=True),
    Column("created_with_trust_password", Boolean, nullable=True),
    Column("created_by_commissioning", Boolean, nullable=True),
)

ConfigTable = Table(
    "maasserver_config",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("value", JSONB, nullable=True),
)

ConsumerTable = Table(
    "piston3_consumer",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("name", String(255), nullable=False),
    Column("description", String, nullable=False),
    Column("key", String(18), nullable=False),
    Column("secret", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
)


DefaultResourceTable = Table(
    "maasserver_defaultresource",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column(
        "zone_id", BigInteger, ForeignKey("maasserver_zone.id"), nullable=False
    ),
)

DHCPSnippetTable = Table(
    "maasserver_dhcpsnippet",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
    Column(
        "value_id",
        BigInteger,
        ForeignKey("maasserver_versionedtextfile.id"),
        nullable=True,
    ),
    Column(
        "iprange_id",
        BigInteger,
        ForeignKey("maasserver_iprange.id"),
        nullable=False,
    ),
)

DNSDataTable = Table(
    "maasserver_dnsdata",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column(
        "dnsresource_id",
        BigInteger,
        ForeignKey("maasserver_dnsresource.id"),
        nullable=False,
    ),
    Column("ttl", Integer, nullable=True),
    Column("rrtype", String(8), nullable=False),
    Column("rrdata", Text, nullable=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
)

DNSPublicationTable = Table(
    "maasserver_dnspublication",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("serial", BigInteger, nullable=False, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("source", String(255), nullable=False),
    Column("update", String(255), nullable=False, key="update_str"),
)

DNSResourceTable = Table(
    "maasserver_dnsresource",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(191), nullable=True, unique=False),
    Column(
        "domain_id",
        BigInteger,
        ForeignKey("maasserver_domain.id"),
        nullable=False,
    ),
    Column("address_ttl", Integer, nullable=True, unique=False),
)

DNSResourceIPAddressTable = Table(
    "maasserver_dnsresource_ip_addresses",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column(
        "dnsresource_id",
        BigInteger,
        ForeignKey("maasserver_dnsresource.id"),
        nullable=False,
    ),
    Column(
        "staticipaddress_id",
        BigInteger,
        ForeignKey("maasserver_staticipaddress.id"),
        nullable=False,
    ),
)

DomainTable = Table(
    "maasserver_domain",
    METADATA,
    Column("id", Integer, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False, unique=True),
    Column("authoritative", Boolean, nullable=True),
    Column("ttl", Integer, nullable=True),
)

EventTable = Table(
    "maasserver_event",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("description", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=True
    ),
    Column(
        "type_id",
        BigInteger,
        ForeignKey("maasserver_eventtype.id"),
        nullable=False,
    ),
    Column("node_hostname", String(255), nullable=False),
    Column("username", String(150), nullable=False),
    Column("ip_address", INET, nullable=True),
    Column("user_agent", Text, nullable=False),
    Column("endpoint", Integer, nullable=False),
    Column("node_system_id", String(41), nullable=True),
    Column("user_id", Integer, nullable=True),
)

EventTypeTable = Table(
    "maasserver_eventtype",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False, unique=True),
    Column("description", String(255), nullable=False),
    Column("level", Integer, nullable=False),
)

FabricTable = Table(
    "maasserver_fabric",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=True),
    Column("class_type", String(256), nullable=True),
    Column("description", Text, nullable=False),
)

FileStorageTable = Table(
    "maasserver_filestorage",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("filename", String(255), nullable=False),
    Column("content", Text, nullable=False),
    Column("key", String(36), nullable=False, unique=True),
    Column("owner_id", BigInteger, ForeignKey("auth_user.id"), nullable=True),
    UniqueConstraint("filename", "owner_id"),
)

GlobalDefaultTable = Table(
    "maasserver_globaldefault",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column(
        "domain_id",
        BigInteger,
        ForeignKey("maasserver_domain.id"),
        nullable=False,
    ),
)

InterfaceIPAddressTable = Table(
    "maasserver_interface_ip_addresses",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("interface_id", BigInteger, nullable=False),
    Column("staticipaddress_id", BigInteger, nullable=False),
)

InterfaceTable = Table(
    "maasserver_interface",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("type", String(20), nullable=False),
    Column("mac_address", Text, nullable=True),
    Column("params", JSONB, nullable=False),
    Column("tags", Text, nullable=True),
    Column("enabled", Boolean, nullable=False),
    Column(
        "vlan_id", BigInteger, ForeignKey("maasserver_vlan.id"), nullable=True
    ),
    Column("acquired", Boolean, nullable=False),
    Column("mdns_discovery_state", Boolean, nullable=False),
    Column("neighbour_discovery_state", Boolean, nullable=False),
    Column("firmware_version", String(255), nullable=True),
    Column("product", String(255), nullable=True),
    Column("vendor", String(255), nullable=True),
    Column("interface_speed", Integer, nullable=False),
    Column("link_connected", Boolean, nullable=False),
    Column("link_speed", Integer, nullable=False),
    Column(
        "numa_node_id",
        BigInteger,
        ForeignKey("maasserver_numanode.id"),
        nullable=True,
    ),
    Column("sriov_max_vf", Integer, nullable=False),
    Column(
        "node_config_id",
        BigInteger,
        ForeignKey("maasserver_nodeconfig.id"),
        nullable=True,
    ),
)

IPRangeTable = Table(
    "maasserver_iprange",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
    Column("type", String(20), nullable=False, unique=False),
    Column("start_ip", INET, nullable=False, unique=False),
    Column("end_ip", INET, nullable=False, unique=False),
    Column("user_id", BigInteger, ForeignKey("auth_user.id"), nullable=True),
    Column("comment", String(255), nullable=True, unique=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
)

NodeConfigTable = Table(
    "maasserver_nodeconfig",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", Text, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
)

NodeDeviceTable = Table(
    "maasserver_nodedevice",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("bus", Integer, nullable=False),
    Column("hardware_type", Integer, nullable=False),
    Column("vendor_id", String(4), nullable=False),
    Column("product_id", String(4), nullable=False),
    Column("vendor_name", String(256), nullable=False),
    Column("product_name", String(256), nullable=False),
    Column("commissioning_driver", String(256), nullable=False),
    Column("bus_number", Integer, nullable=False),
    Column("device_number", Integer, nullable=False),
    Column("pci_address", String(64), nullable=True),
    Column(
        "numa_node_id",
        BigInteger,
        ForeignKey("maasserver_numanode.id"),
        nullable=False,
    ),
    Column(
        "physical_blockdevice_id",
        BigInteger,
        ForeignKey("maasserver_physicalblockdevice.id"),
        nullable=True,
    ),
    Column(
        "physical_interface_id",
        BigInteger,
        ForeignKey("maasserver_interface.id"),
        nullable=True,
    ),
    Column(
        "node_config_id",
        BigInteger,
        ForeignKey("maasserver_nodeconfig.id"),
        nullable=False,
    ),
)

NodeDeviceVpdTable = Table(
    "maasserver_nodedevicevpd",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("key", Text, nullable=False),
    Column("value", Text, nullable=False),
    Column(
        "node_device_id",
        ForeignKey("maasserver_nodedevice.id"),
        nullable=False,
    ),
)

NodeGroupToRackControllerTable = Table(
    "maasserver_nodegrouptorackcontroller",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("uuid", String(36), nullable=False),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
)

NodeTable = Table(
    "maasserver_node",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("system_id", String(41), nullable=False),
    Column("hostname", String(255), nullable=False),
    Column("status", Integer, nullable=False),
    Column("bios_boot_method", String(31), nullable=True),
    Column("osystem", String(255), nullable=False),
    Column("distro_series", String(255), nullable=False),
    Column("architecture", String(31), nullable=True),
    Column("min_hwe_kernel", String(31), nullable=True),
    Column("hwe_kernel", String(31), nullable=True),
    Column("agent_name", String(255), nullable=True),
    Column("error_description", Text, nullable=False),
    Column("cpu_count", Integer, nullable=False),
    Column("memory", Integer, nullable=False),
    Column("swap_size", BigInteger, nullable=True),
    Column("power_state", String(10), nullable=False),
    Column("power_state_updated", DateTime(timezone=True), nullable=True),
    Column("error", String(255), nullable=False),
    Column("netboot", Boolean, nullable=False),
    Column("license_key", String(30), nullable=True),
    Column("boot_cluster_ip", INET, nullable=True),
    Column("enable_ssh", Boolean, nullable=False),
    Column("skip_networking", Boolean, nullable=False),
    Column("skip_storage", Boolean, nullable=False),
    Column("boot_interface_id", Integer, nullable=True),
    Column("gateway_link_ipv4_id", Integer, nullable=True),
    Column("gateway_link_ipv6_id", Integer, nullable=True),
    Column("owner_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    Column(
        "parent_id",
        BigInteger,
        ForeignKey("maasserver_node.id"),
        nullable=True,
    ),
    Column(
        "zone_id", BigInteger, ForeignKey("maasserver_zone.id"), nullable=False
    ),
    Column(
        "boot_disk_id",
        Integer,
        ForeignKey("maasserver_physicalblockdevice.blockdevice_ptr_id"),
        nullable=True,
    ),
    Column("node_type", Integer, nullable=False),
    Column(
        "domain_id", Integer, ForeignKey("maasserver_domain.id"), nullable=True
    ),
    Column("dns_process_id", Integer, nullable=True),
    Column(
        "bmc_id", BigInteger, ForeignKey("maasserver_bmc.id"), nullable=True
    ),
    Column("address_ttl", Integer, nullable=True),
    Column("status_expires", DateTime(timezone=True), nullable=True),
    Column("power_state_queried", DateTime(timezone=True), nullable=True),
    Column("url", String(255), nullable=False),
    Column("managing_process_id", Integer, nullable=True),
    Column("last_image_sync", DateTime(timezone=True), nullable=True),
    Column("previous_status", Integer, nullable=False),
    Column("default_user", String(32), nullable=False),
    Column("cpu_speed", Integer, nullable=False),
    Column("current_commissioning_script_set_id", Integer, nullable=True),
    Column("current_installation_script_set_id", Integer, nullable=True),
    Column("current_testing_script_set_id", Integer, nullable=True),
    Column("current_release_script_set_id", Integer, nullable=True),
    Column("install_rackd", Boolean, nullable=False),
    Column("locked", Boolean, nullable=False),
    Column(
        "pool_id",
        Integer,
        ForeignKey("maasserver_resourcepool.id"),
        nullable=True,
    ),
    Column("instance_power_parameters", JSONB, nullable=False),
    Column("install_kvm", Boolean, nullable=False),
    Column("hardware_uuid", String(36), nullable=True),
    Column("ephemeral_deploy", Boolean, nullable=False),
    Column("description", Text, nullable=False),
    Column("dynamic", Boolean, nullable=False),
    Column("register_vmhost", Boolean, nullable=False),
    Column("last_applied_storage_layout", String(50), nullable=False),
    Column(
        "current_config_id",
        BigInteger,
        ForeignKey("maasserver_nodeconfig.id"),
        nullable=True,
    ),
    Column("enable_hw_sync", Boolean, nullable=False),
    Column("last_sync", DateTime(timezone=True), nullable=True),
    Column("sync_interval", Integer, nullable=True),
    Column("enable_kernel_crash_dump", Boolean, nullable=False),
)

NodeTagTable = Table(
    "maasserver_node_tags",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
    Column(
        "tag_id", BigInteger, ForeignKey("maasserver_tag.id"), nullable=False
    ),
)

NotificationTable = Table(
    "maasserver_notification",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("ident", String(40), nullable=True, unique=True),
    Column("users", Boolean, nullable=False),
    Column("admins", Boolean, nullable=False),
    Column("message", Text, nullable=False),
    Column("context", JSONB, nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    Column("category", String(10), nullable=False),
    Column("dismissable", Boolean, nullable=False),
)

NotificationDismissalTable = Table(
    "maasserver_notificationdismissal",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=False),
    Column(
        "notification_id",
        Integer,
        ForeignKey("maasserver_notification.id"),
        nullable=False,
    ),
)

NumaNodeTable = Table(
    "maasserver_numanode",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("index", Integer, nullable=False),
    Column("memory", Integer, nullable=False),
    Column("cores", ARRAY(Integer), nullable=False),
    Column(
        "node_id",
        BigInteger,
        ForeignKey(
            "maasserver_node.id",
            name="maasserver_numanode_node_id_539a7e2f_fkR",
        ),
        nullable=False,
    ),
)

PhysicalBlockDeviceTable = Table(
    "maasserver_physicalblockdevice",
    METADATA,
    Column(
        "blockdevice_ptr_id",
        BigInteger,
        ForeignKey("maasserver_blockdevice.id"),
        primary_key=True,
        unique=True,
    ),
    Column("model", String(255), nullable=False),
    Column("serial", String(255), nullable=False),
    Column("firmware_version", String(255), nullable=True),
    Column(
        "numa_node_id",
        BigInteger,
        ForeignKey("maasserver_numanode.id"),
        nullable=False,
    ),
)

ReservedIPTable = Table(
    "maasserver_reservedip",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
        unique=False,
    ),
    Column("ip", INET, nullable=False, unique=True),
    Column("mac_address", Text, nullable=False, unique=False),
    Column("comment", String(255), nullable=True, unique=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
)

ResourcePoolTable = Table(
    "maasserver_resourcepool",
    METADATA,
    Column("id", Integer, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False),
    Column("description", Text, nullable=False),
)

RootKeyTable = Table(
    "maasserver_rootkey",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("expiration", DateTime(timezone=True), nullable=False),
)

ScriptResultTable = Table(
    "maasserver_scriptresult",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("status", Integer, nullable=False),
    Column("exit_status", Integer, nullable=True),
    Column("script_name", String(255), nullable=True),
    Column("stdout", Text, nullable=False),
    Column("stderr", Text, nullable=False),
    Column("result", Text, nullable=False),
    Column(
        "script_id",
        BigInteger,
        ForeignKey("maasserver_script.id"),
        nullable=True,
    ),
    Column(
        "script_set_id",
        BigInteger,
        ForeignKey("maasserver_scriptset.id"),
        nullable=False,
    ),
    Column(
        "script_version_id",
        BigInteger,
        ForeignKey("maasserver_versionedtextfile.id"),
        nullable=True,
    ),
    Column("output", Text, nullable=False),
    Column("ended", DateTime(timezone=True), nullable=True),
    Column("started", DateTime(timezone=True), nullable=True),
    Column("parameters", JSONB, nullable=False),
    Column(
        "physical_blockdevice_id",
        Integer,
        ForeignKey("maasserver_physicalblockdevice.blockdevice_ptr_id"),
        nullable=True,
    ),
    Column("suppressed", Boolean, nullable=False),
    Column(
        "interface_id",
        BigInteger,
        ForeignKey("maasserver_interface.id"),
        nullable=True,
    ),
)

ScriptSetTable = Table(
    "maasserver_scriptset",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("last_ping", DateTime(timezone=True), nullable=True),
    Column("result_type", Integer, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
    Column("power_state_before_transition", String(10), nullable=False),
    Column("tags", Text, nullable=True),
)

ScriptTable = Table(
    "maasserver_script",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False),
    Column("tags", Text, nullable=True),
    Column("script_type", Integer, nullable=False),
    Column("timeout", Interval, nullable=False),
    Column("destructive", Boolean, nullable=False),
    Column("default", Boolean, nullable=False),
    Column(
        "script_id",
        Integer,
        ForeignKey("maasserver_versionedtextfile.id"),
        nullable=False,
    ),
    Column("title", String(255), nullable=False),
    Column("hardware_type", Integer, nullable=False),
    Column("packages", JSONB, nullable=False),
    Column("parallel", Integer, nullable=False),
    Column("parameters", JSONB, nullable=False),
    Column("results", JSONB, nullable=False),
    Column("for_hardware", String(255), nullable=False),
    Column("may_reboot", Boolean, nullable=False),
    Column("recommission", Boolean, nullable=False),
    Column("apply_configured_networking", Boolean, nullable=False),
)

SecretTable = Table(
    "maasserver_secret",
    METADATA,
    Column("path", Text, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("value", JSONB, nullable=False),
)

ServiceStatusTable = Table(
    "maasserver_service",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("name", String(255), nullable=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("status", String(10), nullable=False),
    Column("status_info", String(255), nullable=False),
    Column(
        "node_id",
        BigInteger,
        ForeignKey("maasserver_node.id"),
        nullable=False,
    ),
)

SessionTable = Table(
    "django_session",
    METADATA,
    Column("session_key", String(40), nullable=False),
    Column("session_data", Text, nullable=False),
    Column("expire_date", DateTime(timezone=True), nullable=False),
)

SshKeyTable = Table(
    "maasserver_sshkey",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("key", Text, nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=False),
    Column("auth_id", String(255), nullable=True),
    Column("protocol", String(64), nullable=True),
)

SpaceTable = Table(
    "maasserver_space",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=True),
    Column("description", Text, nullable=False),
)

SSLKeyTable = Table(
    "maasserver_sslkey",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("key", Text, nullable=False),
    Column("user_id", BigInteger, ForeignKey("auth_user.id"), nullable=False),
    UniqueConstraint("key", "user_id", name="unique_id_sslkey"),
)

StaticIPAddressTable = Table(
    "maasserver_staticipaddress",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("ip", INET, nullable=True),
    Column("alloc_type", Integer, nullable=False),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=True,
    ),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    Column("lease_time", Integer, nullable=False),
    Column("temp_expires_on", DateTime(timezone=True), nullable=True),
)

StaticRouteTable = Table(
    "maasserver_staticroute",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("gateway_ip", INET, nullable=False),
    Column("metric", Integer, nullable=False),
    Column(
        "destination_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
    Column(
        "source_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
)

SubnetTable = Table(
    "maasserver_subnet",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("cidr", CIDR, nullable=False),
    Column("gateway_ip", INET, nullable=True),
    Column("dns_servers", ARRAY(Text), nullable=True),
    Column(
        "vlan_id", BigInteger, ForeignKey("maasserver_vlan.id"), nullable=False
    ),
    Column("rdns_mode", Integer, nullable=False),
    Column("allow_proxy", Boolean, nullable=False),
    Column("description", Text, nullable=False),
    Column("active_discovery", Boolean, nullable=False),
    Column("managed", Boolean, nullable=False),
    Column("allow_dns", Boolean, nullable=False),
    Column("disabled_boot_architectures", ARRAY(String(64)), nullable=False),
)

TagTable = Table(
    "maasserver_tag",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False),
    Column("definition", Text, nullable=False),
    Column("comment", Text, nullable=False),
    Column("kernel_opts", Text, nullable=False),
)

TokenTable = Table(
    "piston3_token",
    METADATA,
    Column("id", BigInteger, primary_key=True),
    Column("key", String(18), nullable=False),
    Column("secret", String(32), nullable=False),
    Column("verifier", String(10), nullable=False),
    Column("token_type", Integer, nullable=False),
    Column("timestamp", Integer, nullable=False),
    Column("is_approved", Boolean, nullable=False),
    Column("callback", String(255), nullable=True),
    Column("callback_confirmed", Boolean, nullable=False),
    Column(
        "consumer_id",
        BigInteger,
        ForeignKey("piston3_cosumer.id"),
        nullable=False,
    ),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
)

UserProfileTable = Table(
    "maasserver_userprofile",
    METADATA,
    Column("id", Integer, primary_key=True, unique=True),
    Column("completed_intro", Boolean, nullable=False),
    Column("auth_last_check", DateTime(timezone=True), nullable=True),
    Column("is_local", Boolean, nullable=False),
    Column("user_id", BigInteger, ForeignKey("auth_user.id"), nullable=False),
)

UserTable = Table(
    "auth_user",
    METADATA,
    Column("id", Integer, primary_key=True, unique=True),
    Column("password", String(128), nullable=False),
    Column("last_login", DateTime(timezone=True), nullable=True),
    Column("is_superuser", Boolean, nullable=False),
    Column("username", String(150), nullable=False),
    Column("first_name", String(150), nullable=False),
    Column("last_name", String(150), nullable=False),
    Column("email", String(254), nullable=True),
    Column("is_staff", Boolean, nullable=False),
    Column("is_active", Boolean, nullable=False),
    Column("date_joined", DateTime(timezone=True), nullable=False),
)

VaultSecretTable = Table(
    "maasserver_vaultsecret",
    METADATA,
    Column("path", Text, primary_key=True, unique=True),
    Column("deleted", Boolean, nullable=False),
)

VersionedTextFileTable = Table(
    "maasserver_versionedtextfile",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("data", Text, nullable=True),
    Column("comment", String(255), nullable=True),
    Column(
        "previous_version_id",
        BigInteger,
        ForeignKey("maasserver_versionedtextfile.id"),
        nullable=True,
    ),
)

VirtualBlockDeviceTable = Table(
    "maasserver_virtualblockdevice",
    METADATA,
    Column(
        "blockdevice_ptr_id",
        BigInteger,
        ForeignKey("maasserver_blockdevice.id"),
        nullable=False,
    ),
    Column(
        "filesystem_ptr_id",
        BigInteger,
        ForeignKey("maasserver_filesystem.id"),
        nullable=False,
    ),
    Column("uuid", Text, nullable=False, unique=True),
)

VlanTable = Table(
    "maasserver_vlan",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False),
    Column("vid", Integer, nullable=False),
    Column("mtu", Integer, nullable=False),
    Column(
        "fabric_id",
        Integer,
        ForeignKey("maasserver_fabric.id"),
        nullable=False,
    ),
    Column("dhcp_on", Boolean, nullable=False),
    Column("primary_rack_id", Integer, nullable=True),
    Column("secondary_rack_id", Integer, nullable=True),
    Column("external_dhcp", INET, nullable=True),
    Column("description", Text, nullable=False),
    Column(
        "relay_vlan_id",
        BigInteger,
        ForeignKey("maasserver_vlan.id"),
        nullable=True,
    ),
    Column(
        "space_id",
        BigInteger,
        ForeignKey("maasserver_space.id"),
        nullable=True,
    ),
)

VmClusterTable = Table(
    "maasserver_vmcluster",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", Text, nullable=False, unique=True),
    Column("project", Text, nullable=False, unique=False),
    Column(
        "pool_id",
        BigInteger,
        ForeignKey("maasserver_resourcepool.id"),
        nullable=True,
    ),
    Column(
        "zone_id",
        BigInteger,
        ForeignKey("maasserver_zone.id"),
        nullable=True,
    ),
)

ZoneTable = Table(
    "maasserver_zone",
    METADATA,
    Column("id", BigInteger, primary_key=True, unique=True),
    Column("name", String(256), nullable=False, unique=True),
    Column("description", Text, nullable=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
)

# Before you are going to add something to this file, please ensure that
# you keep things in alphabetical order!
