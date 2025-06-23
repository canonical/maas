#  Copyright 2023-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    desc,
    Float,
    ForeignKey,
    func,
    Identity,
    Index,
    Integer,
    Interval,
    MetaData,
    String,
    Table,
    Text,
    text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, INET, JSONB

METADATA = MetaData()

# Keep them in alphabetical order!

BlockDeviceTable = Table(
    "maasserver_blockdevice",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False),
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
    UniqueConstraint("node_config_id", "name"),
    Index("maasserver_blockdevice_node_config_id_5b310b67", "node_config_id"),
)

BMCTable = Table(
    "maasserver_bmc",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Column("local_storage", BigInteger, nullable=False),
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
    Column("default_storage_pool_id", BigInteger, nullable=True),
    Column("power_parameters", JSONB, nullable=False),
    Column("default_macvlan_mode", String(32), nullable=True),
    Column("version", Text, nullable=False),
    Column("created_with_cert_expiration_days", Integer, nullable=True),
    Column("created_with_maas_generated_cert", Boolean, nullable=True),
    Column("created_with_trust_password", Boolean, nullable=True),
    Column("created_by_commissioning", Boolean, nullable=True),
    Index("maasserver__power_p_511df2_hash", "power_parameters"),
    Index("maasserver_bmc_default_pool_id_848e4429", "pool_id"),
    Index(
        "maasserver_bmc_default_storage_pool_id_5f48762b",
        "default_storage_pool_id",
    ),
    Index("maasserver_bmc_ip_address_id_79362d14", "ip_address_id"),
    Index("maasserver_bmc_power_type_93755dda", "power_type"),
    Index(
        "maasserver_bmc_power_type_93755dda_like",
        "power_type",
        postgresql_ops={"power_type": "varchar_pattern_ops"},
    ),
    Index(
        "maasserver_bmc_power_type_parameters_idx",
        "power_type",
        func.md5(text("power_parameters::text")),
        unique=True,
        postgresql_where=text("(power_type)::text <> 'manual'::text"),
    ),
    Index("maasserver_bmc_zone_id_774ea0de", "zone_id"),
)

BootResourceTable = Table(
    "maasserver_bootresource",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("rtype", Integer, nullable=False),
    Column("name", String(255), nullable=False),
    Column("architecture", String(255), nullable=False),
    Column("extra", JSONB, nullable=False),
    Column("kflavor", String(32), nullable=True),
    Column("bootloader_type", String(32), nullable=True),
    Column("rolling", Boolean, nullable=False),
    Column("base_image", String(255), nullable=False),
    Column("alias", String(255), nullable=True),
    Column("last_deployed", DateTime(timezone=False), nullable=True),
)

CacheSetTable = Table(
    "maasserver_cacheset",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
)

ConfigTable = Table(
    "maasserver_config",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("name", String(255), nullable=False, unique=True),
    Column("value", JSONB, nullable=True),
    Index("maasserver_config_name_ad989064_like", "name"),
)

ConsumerTable = Table(
    "piston3_consumer",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False),
    Column("key", String(18), nullable=False),
    Column("secret", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    Index("piston3_consumer_user_id_ede69093", "user_id"),
)

DefaultResourceTable = Table(
    "maasserver_defaultresource",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column(
        "zone_id", BigInteger, ForeignKey("maasserver_zone.id"), nullable=False
    ),
    Index("maasserver_defaultresource_zone_id_29a5153a", "zone_id"),
)

DHCPSnippetTable = Table(
    "maasserver_dhcpsnippet",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False),
    Column("description", Text, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=True
    ),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=True,
    ),
    Column(
        "value_id",
        BigInteger,
        ForeignKey("maasserver_versionedtextfile.id"),
        nullable=False,
    ),
    Column(
        "iprange_id",
        BigInteger,
        ForeignKey("maasserver_iprange.id"),
        nullable=True,
    ),
    Index("maasserver_dhcpsnippet_value_id_58a6a467", "value_id"),
    Index("maasserver_dhcpsnippet_subnet_id_f626b848", "subnet_id"),
    Index("maasserver_dhcpsnippet_node_id_8f31c564", "node_id"),
    Index("maasserver_dhcpsnippet_iprange_id_6a257e4d", "iprange_id"),
)

DiscoveryView = Table(
    "maasserver_discovery",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("discovery_id", Text, nullable=False),
    Column(
        "neighbour_id",
        BigInteger,
        ForeignKey("maasserver_neighbour.id"),
        nullable=False,
    ),
    Column("ip", INET, nullable=False),
    Column("mac_address", Text, nullable=False),
    Column("vid", Integer, nullable=False),
    Column("first_seen", DateTime(timezone=True), nullable=False),
    Column("last_seen", DateTime(timezone=True), nullable=False),
    Column("mdns_id", BigInteger, nullable=False),
    Column("hostname", String(256), nullable=False),
    Column("observer_id", BigInteger, nullable=False),
    Column("observer_system_id", String(41), nullable=False),
    Column("observer_hostname", String(255), nullable=False),
    Column("observer_interface_id", BigInteger, nullable=False),
    Column("observer_interface_name", String(255), nullable=False),
    Column("fabric_id", Integer, nullable=False),
    Column("fabric_name", String(256), nullable=False),
    Column("vlan_id", BigInteger, nullable=False),
    Column("is_external_dhcp", Boolean, nullable=False),
    Column("subnet_id", BigInteger, nullable=False),
    Column("subnet_cidr", CIDR, nullable=False),
    Column("subnet_prefixlen", Integer, nullable=False),
)

DNSDataTable = Table(
    "maasserver_dnsdata",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_dnsdata_dnsresource_id_9a9b5788", "dnsresource_id"),
)

DNSPublicationTable = Table(
    "maasserver_dnspublication",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("serial", BigInteger, nullable=False, unique=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("source", String(255), nullable=False),
    Column("update", String(255), nullable=False),
)

DNSResourceTable = Table(
    "maasserver_dnsresource",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(191), nullable=True, unique=False),
    Column(
        "domain_id",
        Integer,
        ForeignKey("maasserver_domain.id"),
        nullable=False,
    ),
    Column("address_ttl", Integer, nullable=True, unique=False),
    Index("maasserver_dnsresource_domain_id_c5abb245", "domain_id"),
)

DNSResourceIPAddressTable = Table(
    "maasserver_dnsresource_ip_addresses",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index(
        "maasserver_dnsresource_ip_addresses_staticipaddress_id_794f210e",
        "staticipaddress_id",
    ),
    Index(
        "maasserver_dnsresource_ip_addresses_dnsresource_id_49f1115e",
        "dnsresource_id",
    ),
)

DomainTable = Table(
    "maasserver_domain",
    METADATA,
    Column("id", Integer, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False, unique=True),
    Column("authoritative", Boolean, nullable=True),
    Column("ttl", Integer, nullable=True),
    Index("maasserver_domain_name_4267a38e_like", "name"),
    Index("maasserver_domain_authoritative_1d49b1f6", "authoritative"),
)

EventTable = Table(
    "maasserver_event",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_event_type_id_702a532f", "type_id"),
    Index("maasserver_event_node_id_dd4495a7", "node_id"),
    Index("maasserver_event__created", "created"),
    Index(
        "maasserver__node_id_e4a8dd_idx",
        "node_id",
        desc("created"),
        desc("id"),
    ),
    Index("maasserver_event_node_id_id_a62e1358_idx", "node_id", "id"),
)

EventTypeTable = Table(
    "maasserver_eventtype",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(255), nullable=False, unique=True),
    Column("description", String(255), nullable=False),
    Column("level", Integer, nullable=False),
    Index("maasserver_eventtype_name_49878f67_like", "name"),
    Index("maasserver_eventtype_level_468acd98", "level"),
)

FabricTable = Table(
    "maasserver_fabric",
    METADATA,
    Column("id", Integer, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=True),
    Column("class_type", String(256), nullable=True),
    Column("description", Text, nullable=False),
    Index("maasserver_fabric_name_3aaa3e4d_like", "name"),
)

FileSystemTable = Table(
    "maasserver_filesystem",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("uuid", Text, nullable=False),
    Column("fstype", String(20), nullable=False),
    Column("label", String(255), nullable=True),
    Column("create_params", String(255), nullable=True),
    Column("mount_point", String(255), nullable=True),
    Column("mount_options", String(255), nullable=True),
    Column("acquired", Boolean, nullable=False),
    Column(
        "block_device_id",
        BigInteger,
        ForeignKey(
            "maasserver_blockdevice.id", deferrable=True, initially="DEFERRED"
        ),
        nullable=True,
    ),
    Column(
        "cache_set_id",
        BigInteger,
        ForeignKey(
            "maasserver_cacheset.id", deferrable=True, initially="DEFERRED"
        ),
        nullable=True,
    ),
    Column(
        "filesystem_group_id",
        BigInteger,
        ForeignKey(
            "maasserver_filesystemgroup.id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=True,
    ),
    Column(
        "partition_id",
        BigInteger,
        ForeignKey(
            "maasserver_partition.id", deferrable=True, initially="DEFERRED"
        ),
        nullable=True,
    ),
    Column(
        "node_config_id",
        BigInteger,
        ForeignKey(
            "maasserver_nodeconfig.id", deferrable=True, initially="DEFERRED"
        ),
        nullable=False,
    ),
    UniqueConstraint("block_device_id", "acquired"),
    UniqueConstraint("partition_id", "acquired"),
    Index("maasserver_filesystem_partition_id_6174cd8b", "partition_id"),
    Index("maasserver_filesystem_node_config_id_741ff095", "node_config_id"),
    Index(
        "maasserver_filesystem_filesystem_group_id_9bc05fe7",
        "filesystem_group_id",
    ),
    Index("maasserver_filesystem_cache_set_id_f87650ce", "cache_set_id"),
    Index("maasserver_filesystem_block_device_id_5d3ba742", "block_device_id"),
)

FilesystemGroupTable = Table(
    "maasserver_filesystemgroup",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("uuid", Text, nullable=False),
    Column("group_type", String(20), nullable=False),
    Column("name", String(255), nullable=False),
    Column("create_params", String(255), nullable=True),
    Column("cache_mode", String(20), nullable=True),
    Column(
        "cache_set_id",
        BigInteger,
        ForeignKey(
            "maasserver_cacheset.id", deferrable=True, initially="DEFERRED"
        ),
        nullable=True,
    ),
    Index("maasserver_filesystemgroup_cache_set_id_608e115e", "cache_set_id"),
)

FileStorageTable = Table(
    "maasserver_filestorage",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("filename", String(255), nullable=False),
    Column("content", Text, nullable=False),
    Column("key", String(36), nullable=False, unique=True),
    Column("owner_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    UniqueConstraint("filename", "owner_id"),
    Index("maasserver_filestorage_owner_id_24d47e43", "owner_id"),
    Index("maasserver_filestorage_key_4458fcee_like", "key"),
)

ForwardDNSServerTable = Table(
    "maasserver_forwarddnsserver",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("ip_address", INET, nullable=False, unique=True),
    Column("port", Integer, nullable=False, unique=False),
)

ForwardDNSServerDomainsTable = Table(
    "maasserver_forwarddnsserver_domains",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column(
        "domain_id",
        Integer,
        ForeignKey("maasserver_domain.id"),
        nullable=False,
    ),
    Column(
        "forwarddnsserver_id",
        BigInteger,
        ForeignKey("maasserver_forwarddnsserver.id"),
        nullable=False,
    ),
    Index(
        "maasserver_forwarddnsserver_domains_domain_id_02e252ac", "domain_id"
    ),
    Index(
        "maasserver_forwarddnsserve_forwarddnsserver_id_c975e5df",
        "forwarddnsserver_id",
    ),
)

GlobalDefaultTable = Table(
    "maasserver_globaldefault",
    METADATA,
    Column("id", Integer, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column(
        "domain_id",
        Integer,
        ForeignKey("maasserver_domain.id"),
        nullable=False,
    ),
    Index("maasserver_globaldefault_domain_id_11c3ee74", "domain_id"),
)

InterfaceIPAddressTable = Table(
    "maasserver_interface_ip_addresses",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("interface_id", BigInteger, nullable=False),
    Column("staticipaddress_id", BigInteger, nullable=False),
    Index(
        "maasserver_interface_ip_addresses_staticipaddress_id_5fa63951",
        "staticipaddress_id",
    ),
    Index(
        "maasserver_interface_ip_addresses_interface_id_d3d873df",
        "interface_id",
    ),
)

InterfaceTable = Table(
    "maasserver_interface",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_interface_vlan_id_5f39995d", "vlan_id"),
    Index("maasserver_interface_numa_node_id_6e790407", "numa_node_id"),
    Index("maasserver_interface_node_config_id_a52b0f8a", "node_config_id"),
    Index(
        "maasserver_interface_node_config_mac_address_uniq",
        "node_config_id",
        "mac_address",
        unique=True,
        postgresql_where=text("(type)::text = 'physical'::text"),
    ),
)

IPRangeTable = Table(
    "maasserver_iprange",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
    Column("type", String(20), nullable=False, unique=False),
    Column("start_ip", INET, nullable=False, unique=False),
    Column("end_ip", INET, nullable=False, unique=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    Column("comment", String(255), nullable=True, unique=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Index("maasserver_iprange_user_id_5d0f7718", "user_id"),
    Index("maasserver_iprange_subnet_id_de83b8f1", "subnet_id"),
)

MDNSTable = Table(
    "maasserver_mdns",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("ip", INET, nullable=True),
    Column("hostname", String(256), nullable=True),
    Column("count", Integer, nullable=False),
    Column(
        "interface_id",
        BigInteger,
        ForeignKey("maasserver_interface.id"),
        nullable=False,
    ),
    Index("maasserver_mdns_interface_id_ef297041", "interface_id"),
)

PartitionTable = Table(
    "maasserver_partition",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("uuid", Text, nullable=True),
    Column("size", BigInteger, nullable=False),
    Column("bootable", Boolean, nullable=False),
    Column(
        "partition_table_id",
        BigInteger,
        ForeignKey(
            "maasserver_partitiontable.id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
    ),
    Column("tags", ARRAY(Text), nullable=True),
    Column("index", Integer, nullable=False),
    UniqueConstraint("partition_table_id", "index"),
    Index(
        "maasserver_partition_partition_table_id_c94faed6",
        "partition_table_id",
    ),
)

PartitionTableTable = Table(
    "maasserver_partitiontable",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("table_type", String(20), nullable=False),
    Column(
        "block_device_id",
        BigInteger,
        ForeignKey(
            "maasserver_blockdevice.id", deferrable=True, initially="DEFERRED"
        ),
        nullable=False,
    ),
    Index(
        "maasserver_partitiontable_block_device_id_ee132cc5", "block_device_id"
    ),
)

NeighbourTable = Table(
    "maasserver_neighbour",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("ip", INET, nullable=True),
    Column("time", Integer, nullable=False),
    Column("count", Integer, nullable=False),
    Column("mac_address", Text, nullable=True),
    Column("vid", Integer, nullable=True),
    Column(
        "interface_id",
        BigInteger,
        ForeignKey("maasserver_interface.id"),
        nullable=False,
    ),
    Index("maasserver_neighbour_interface_id_dd458d65", "interface_id"),
)

NodeConfigTable = Table(
    "maasserver_nodeconfig",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", Text, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
    Index("maasserver_nodeconfig_node_id_c9235109", "node_id"),
)

NodeDeviceTable = Table(
    "maasserver_nodedevice",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
        ForeignKey("maasserver_physicalblockdevice.blockdevice_ptr_id"),
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
    Index("maasserver_nodedevice_numa_node_id_fadf5b46", "numa_node_id"),
    Index("maasserver_nodedevice_node_config_id_3f91f0a0", "node_config_id"),
)

NodeDeviceVpdTable = Table(
    "maasserver_nodedevicevpd",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("key", Text, nullable=False),
    Column("value", Text, nullable=False),
    Column(
        "node_device_id",
        ForeignKey("maasserver_nodedevice.id"),
        nullable=False,
    ),
    Index(
        "maasserver_nodedevicevpd_node_device_id_9c998e15", "node_device_id"
    ),
    Index("maasserver__key_ecce38_idx", "key", "value"),
)

NodeGroupToRackControllerTable = Table(
    "maasserver_nodegrouptorackcontroller",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("uuid", String(36), nullable=False),
    Column(
        "subnet_id",
        BigInteger,
        ForeignKey("maasserver_subnet.id"),
        nullable=False,
    ),
    Index(
        "maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b", "subnet_id"
    ),
)

NodeTable = Table(
    "maasserver_node",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Column("boot_interface_id", BigInteger, nullable=True),
    Column("gateway_link_ipv4_id", BigInteger, nullable=True),
    Column("gateway_link_ipv6_id", BigInteger, nullable=True),
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
        BigInteger,
        ForeignKey("maasserver_physicalblockdevice.blockdevice_ptr_id"),
        nullable=True,
    ),
    Column("node_type", Integer, nullable=False),
    Column(
        "domain_id", Integer, ForeignKey("maasserver_domain.id"), nullable=True
    ),
    Column("dns_process_id", BigInteger, nullable=True),
    Column(
        "bmc_id", BigInteger, ForeignKey("maasserver_bmc.id"), nullable=True
    ),
    Column("address_ttl", Integer, nullable=True),
    Column("status_expires", DateTime(timezone=True), nullable=True),
    Column("power_state_queried", DateTime(timezone=True), nullable=True),
    Column("url", String(255), nullable=False),
    Column("managing_process_id", BigInteger, nullable=True),
    Column("last_image_sync", DateTime(timezone=True), nullable=True),
    Column("previous_status", Integer, nullable=False),
    Column("default_user", String(32), nullable=False),
    Column("cpu_speed", Integer, nullable=False),
    Column(
        "current_commissioning_script_set_id",
        BigInteger,
        ForeignKey("maasserver_scriptset.id"),
        nullable=True,
    ),
    Column(
        "current_installation_script_set_id",
        BigInteger,
        ForeignKey("maasserver_scriptset.id"),
        nullable=True,
    ),
    Column(
        "current_testing_script_set_id",
        BigInteger,
        ForeignKey("maasserver_scriptset.id"),
        nullable=True,
    ),
    Column(
        "current_release_script_set_id",
        BigInteger,
        ForeignKey("maasserver_scriptset.id"),
        nullable=True,
    ),
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
    Column("is_dpu", Boolean, nullable=False),
    Index("maasserver_node_zone_id_97213f69", "zone_id"),
    Index(
        "maasserver_node_hardware_uuid_6b491c84_like",
        "hardware_uuid",
        postgresql_ops={"hardware_uuid": "varchar_pattern_ops"},
    ),
    Index("maasserver_node_pool_id_42cdfac9", "pool_id"),
    Index("maasserver_node_parent_id_d0ac1fac", "parent_id"),
    Index("maasserver_node_owner_id_455bec7f", "owner_id"),
    Index(
        "maasserver_node_managing_process_id_0f9f8640", "managing_process_id"
    ),
    Index(
        "maasserver_node_hostname_23fbebec_like",
        "hostname",
        postgresql_ops={"hostname": "varchar_pattern_ops"},
    ),
    Index(
        "maasserver_node_system_id_b9f4e3e8_like",
        "system_id",
        postgresql_ops={"system_id": "varchar_pattern_ops"},
    ),
    Index(
        "maasserver_node_gateway_link_ipv6_id_b8542fea", "gateway_link_ipv6_id"
    ),
    Index(
        "maasserver_node_gateway_link_ipv4_id_620a3c36", "gateway_link_ipv4_id"
    ),
    Index("maasserver_node_domain_id_7b592cbf", "domain_id"),
    Index(
        "maasserver_node_current_testing_script_set_id_4636f4f9",
        "current_testing_script_set_id",
    ),
    Index(
        "maasserver_node_current_release_script_set_id_1c3d13f5",
        "current_release_script_set_id",
    ),
    Index(
        "maasserver_node_current_installation_script_set_id_a6e40738",
        "current_installation_script_set_id",
    ),
    Index("maasserver_node_current_config_id_d9cbacad", "current_config_id"),
    Index(
        "maasserver_node_current_commissioning_script_set_id_9ae2ec39",
        "current_commissioning_script_set_id",
    ),
    Index("maasserver_node_boot_interface_id_fad48090", "boot_interface_id"),
    Index("maasserver_node_boot_disk_id_db8131e9", "boot_disk_id"),
    Index("maasserver_node_bmc_id_a2d33e12", "bmc_id"),
)

NodeTagTable = Table(
    "maasserver_node_tags",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
    Column(
        "tag_id", BigInteger, ForeignKey("maasserver_tag.id"), nullable=False
    ),
    Index("maasserver_node_tags_tag_id_f4728372", "tag_id"),
    Index("maasserver_node_tags_node_id_a662a9f1", "node_id"),
)

NotificationTable = Table(
    "maasserver_notification",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_notification_user_id_5a4d1d18", "user_id"),
    Index(
        "maasserver_notification_ident_d81e5931_like",
        "ident",
        postgresql_ops={"ident": "varchar_pattern_ops"},
    ),
)

NotificationDismissalTable = Table(
    "maasserver_notificationdismissal",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=False),
    Column(
        "notification_id",
        BigInteger,
        ForeignKey("maasserver_notification.id"),
        nullable=False,
    ),
    Index("maasserver_notificationdismissal_user_id_87cc11da", "user_id"),
    Index(
        "maasserver_notificationdismissal_notification_id_fe4f68d4",
        "notification_id",
    ),
)

NumaNodeTable = Table(
    "maasserver_numanode",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_numanode_node_id_539a7e2f", "node_id"),
)

PackageRepositoryTable = Table(
    "maasserver_packagerepository",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(41), nullable=False, unique=True),
    Column("url", String(200), nullable=False),
    Column("components", ARRAY(Text), nullable=True),
    Column("arches", ARRAY(Text), nullable=True),
    Column("key", Text, nullable=False),
    Column("default", Boolean, nullable=False),
    Column("enabled", Boolean, nullable=False),
    Column("disabled_pockets", ARRAY(Text), nullable=True),
    Column("distributions", ARRAY(Text), nullable=True),
    Column("disabled_components", ARRAY(Text), nullable=True),
    Column("disable_sources", Boolean, nullable=False),
    Index("maasserver_packagerepository_name_ae83c436_like", "name"),
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
    Index(
        "maasserver_physicalblockdevice_numa_node_id_8bd61f48", "numa_node_id"
    ),
)
RDNSTable = Table(
    "maasserver_rdns",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("ip", INET, nullable=False),
    Column("hostname", String(256), nullable=True),
    Column("hostnames", ARRAY(Text), nullable=False),
    Column(
        "observer_id",
        BigInteger,
        ForeignKey("maasserver_node.id"),
        nullable=False,
    ),
    Index("maasserver_rdns_observer_id_85a64c6b", "observer_id"),
)

ReservedIPTable = Table(
    "maasserver_reservedip",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_reservedip_subnet_id_548dd59f", "subnet_id"),
)

ResourcePoolTable = Table(
    "maasserver_resourcepool",
    METADATA,
    Column("id", Integer, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False),
    Column("description", Text, nullable=False),
    Index(
        "maasserver_resourcepool_name_dc5d41eb_like",
        "name",
        postgresql_ops={"name": "varchar_pattern_ops"},
    ),
)

RootKeyTable = Table(
    "maasserver_rootkey",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("expiration", DateTime(timezone=True), nullable=False),
)

ScriptResultTable = Table(
    "maasserver_scriptresult",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
        BigInteger,
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
    Index(
        "metadataserver_scriptresult_script_version_id_932ffdd1",
        "script_version_id",
    ),
    Index(
        "metadataserver_scriptresult_script_set_id_625a037b", "script_set_id"
    ),
    Index("metadataserver_scriptresult_script_id_c5ff7318", "script_id"),
    Index(
        "metadataserver_scriptresult_physical_blockdevice_id_c728b2ad",
        "physical_blockdevice_id",
    ),
    Index("metadataserver_scriptresult_interface_id_a120e25e", "interface_id"),
)

ScriptSetTable = Table(
    "maasserver_scriptset",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("last_ping", DateTime(timezone=True), nullable=True),
    Column("result_type", Integer, nullable=False),
    Column(
        "node_id", BigInteger, ForeignKey("maasserver_node.id"), nullable=False
    ),
    Column("power_state_before_transition", String(10), nullable=False),
    Column("tags", Text, nullable=True),
    Index("metadataserver_scriptset_node_id_72b6537b", "node_id"),
)

ScriptTable = Table(
    "maasserver_script",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
        BigInteger,
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
    Index("metadataserver_script_name_b2be1ba5_like", "name"),
)

SecretTable = Table(
    "maasserver_secret",
    METADATA,
    Column("path", Text, primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("value", JSONB, nullable=False),
    Index(
        "maasserver_secret_path_1e974fd1_like",
        "path",
        postgresql_ops={"path": "text_pattern_ops"},
    ),
)

ServiceStatusTable = Table(
    "maasserver_service",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_service_node_id_891637d4", "node_id"),
)

SessionTable = Table(
    "django_session",
    METADATA,
    Column("session_key", String(40), nullable=False),
    Column("session_data", Text, nullable=False),
    Column("expire_date", DateTime(timezone=True), nullable=False),
    Index(
        "django_session_session_key_c0390e0f_like",
        "session_key",
        postgresql_ops={"session_key": "varchar_pattern_ops"},
    ),
    Index("django_session_expire_date_a5c62663", "expire_date"),
)

SshKeyTable = Table(
    "maasserver_sshkey",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("key", Text, nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=False),
    Column("auth_id", String(255), nullable=True),
    Column("protocol", String(64), nullable=True),
    Index("maasserver_sshkey_user_id_84b68559", "user_id"),
)

SpaceTable = Table(
    "maasserver_space",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=True),
    Column("description", Text, nullable=False),
    Index(
        "maasserver_space_name_38f1b4f5_like",
        "name",
        postgresql_ops={"name": "varchar_pattern_ops"},
    ),
)

SSLKeyTable = Table(
    "maasserver_sslkey",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("key", Text, nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=False),
    UniqueConstraint("key", "user_id", name="unique_id_sslkey"),
    Index("maasserver_sslkey_user_id_d871db8c", "user_id"),
)

StaticIPAddressTable = Table(
    "maasserver_staticipaddress",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_staticipaddress_user_id_a7e5e455", "user_id"),
    Index(
        "maasserver_staticipaddress_temp_expires_on_1cb8532a",
        "temp_expires_on",
    ),
    Index("maasserver_staticipaddress_subnet_id_b30d84c3", "subnet_id"),
    Index(
        "maasserver_staticipaddress_discovered_uniq",
        "ip",
        unique=True,
        postgresql_where=~("alloc_type" == 6),
    ),
    Index("maasserver_staticipaddress__ip_family", func.family("ip")),
)

StaticRouteTable = Table(
    "maasserver_staticroute",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_staticroute_source_id_3321277a", "source_id"),
    Index("maasserver_staticroute_destination_id_4d1b294b", "destination_id"),
)

SubnetTable = Table(
    "maasserver_subnet",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index("maasserver_subnet_vlan_id_d4e96e9a", "vlan_id"),
)

TagTable = Table(
    "maasserver_tag",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=False, unique=True),
    Column("definition", Text, nullable=False),
    Column("comment", Text, nullable=False),
    Column("kernel_opts", Text, nullable=False),
    Index("maasserver_tag_name_7bda8c06_like", "name"),
)

TokenTable = Table(
    "piston3_token",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
        ForeignKey("piston3_consumer.id"),
        nullable=False,
    ),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=True),
    Index("piston3_token_user_id_e5cd818c", "user_id"),
    Index("piston3_token_consumer_id_b178993d", "consumer_id"),
)

UserProfileTable = Table(
    "maasserver_userprofile",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("completed_intro", Boolean, nullable=False),
    Column("auth_last_check", DateTime(timezone=True), nullable=True),
    Column("is_local", Boolean, nullable=False),
    Column("user_id", Integer, ForeignKey("auth_user.id"), nullable=False),
)

UserTable = Table(
    "auth_user",
    METADATA,
    Column("id", Integer, Identity(), primary_key=True),
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
    Index("auth_user_username_6821ab7c_like", "username"),
    Index(
        "auth_user_email_1c89df09_like",
        "email",
        postgresql_ops={"email": "varchar_pattern_ops"},
    ),
)

VaultSecretTable = Table(
    "maasserver_vaultsecret",
    METADATA,
    Column("path", Text, primary_key=True),
    Column("deleted", Boolean, nullable=False),
    Index(
        "maasserver_vaultsecret_path_4127e219_like",
        "path",
        postgresql_ops={"path": "text_pattern_ops"},
    ),
)

VersionedTextFileTable = Table(
    "maasserver_versionedtextfile",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
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
    Index(
        "maasserver_versionedtextfile_previous_version_id_8c3734e6",
        "previous_version_id",
    ),
)

VirtualBlockDeviceTable = Table(
    "maasserver_virtualblockdevice",
    METADATA,
    Column(
        "blockdevice_ptr_id",
        BigInteger,
        ForeignKey("maasserver_blockdevice.id"),
        primary_key=True,
    ),
    Column(
        "filesystem_group_id",
        BigInteger,
        ForeignKey("maasserver_filesystem.filesystem_group_id"),
        nullable=False,
    ),
    Column("uuid", Text, nullable=False, unique=True),
    Index(
        "maasserver_virtualblockdevice_filesystem_group_id_405a7fc4",
        "filesystem_group_id",
    ),
)

VlanTable = Table(
    "maasserver_vlan",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", String(256), nullable=True),
    Column("vid", Integer, nullable=False),
    Column("mtu", Integer, nullable=False),
    Column(
        "fabric_id",
        Integer,
        ForeignKey("maasserver_fabric.id"),
        nullable=False,
    ),
    Column("dhcp_on", Boolean, nullable=False),
    Column("primary_rack_id", BigInteger, nullable=True),
    Column("secondary_rack_id", BigInteger, nullable=True),
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
    Index("maasserver_vlan_space_id_5e1dc51f", "space_id"),
    Index("maasserver_vlan_secondary_rack_id_3b97d19a", "secondary_rack_id"),
    Index("maasserver_vlan_relay_vlan_id_c026b672", "relay_vlan_id"),
    Index("maasserver_vlan_primary_rack_id_016c2af3", "primary_rack_id"),
    Index("maasserver_vlan_fabric_id_af5275c8", "fabric_id"),
)

VmClusterTable = Table(
    "maasserver_vmcluster",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Column("name", Text, nullable=False, unique=True),
    Column("project", Text, nullable=False, unique=False),
    Column(
        "pool_id",
        Integer,
        ForeignKey("maasserver_resourcepool.id"),
        nullable=True,
    ),
    Column(
        "zone_id",
        BigInteger,
        ForeignKey("maasserver_zone.id"),
        nullable=False,
    ),
    Index("maasserver_vmcluster_zone_id_07623572", "zone_id"),
    Index("maasserver_vmcluster_pool_id_aad02386", "pool_id"),
    Index(
        "maasserver_vmcluster_name_dbc3c69c_like",
        "name",
        postgresql_ops={"name": "text_pattern_ops"},
    ),
)

ZoneTable = Table(
    "maasserver_zone",
    METADATA,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("name", String(256), nullable=False, unique=True),
    Column("description", Text, nullable=False),
    Column("created", DateTime(timezone=True), nullable=False),
    Column("updated", DateTime(timezone=True), nullable=False),
    Index(
        "maasserver_zone_name_a0aef207_like",
        "name",
        postgresql_ops={"name": "varchar_pattern_ops"},
    ),
)

# Before you are going to add something to this file, please ensure that
# you keep things in alphabetical order!
