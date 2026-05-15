export enum BridgeType {
  STANDARD = "standard",
  OVS = "ovs",
}

export enum NetworkInterfaceTypes {
  ALIAS = "alias",
  BOND = "bond",
  BRIDGE = "bridge",
  PHYSICAL = "physical",
  VLAN = "vlan",
}

export enum NetworkLinkMode {
  AUTO = "auto",
  DHCP = "dhcp",
  LINK_UP = "link_up",
  STATIC = "static",
}

export enum DiskTypes {
  BCACHE = "bcache",
  CACHE_SET = "cache-set",
  ISCSI = "iscsi",
  PHYSICAL = "physical",
  RAID_0 = "raid-0",
  RAID_1 = "raid-1",
  RAID_5 = "raid-5",
  RAID_6 = "raid-6",
  RAID_10 = "raid-10",
  VIRTUAL = "virtual",
  VMFS6 = "vmfs6",
  VMFS7 = "vmfs7",
  VOLUME_GROUP = "lvm-vg",
}

export enum StorageLayout {
  BCACHE = "bcache",
  BLANK = "blank",
  CUSTOM = "custom",
  FLAT = "flat",
  LVM = "lvm",
  UNKNOWN = "unknown",
  VMFS6 = "vmfs6",
  VMFS7 = "vmfs7",
}

export enum PowerState {
  ERROR = "error",
  OFF = "off",
  ON = "on",
  UNKNOWN = "unknown",
}

export enum VLANMTURange {
  Min = 552,
  Max = 65535,
}

export enum VLANVidRange {
  Min = 0,
  Max = 4094,
}
