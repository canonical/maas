export enum ControllerVLANsColumns {
  FABRIC = "fabric",
  VLAN = "vlan",
  DHCP = "dhcp",
  SUBNET = "subnet",
  PRIMARY_RACK = "primary_rack",
  SECONDARY_RACK = "secondary_rack",
}

export const columnLabels = {
  [ControllerVLANsColumns.FABRIC]: "Fabric",
  [ControllerVLANsColumns.VLAN]: "VLAN",
  [ControllerVLANsColumns.DHCP]: "DHCP",
  [ControllerVLANsColumns.SUBNET]: "Subnets",
  [ControllerVLANsColumns.PRIMARY_RACK]: "Primary rack",
  [ControllerVLANsColumns.SECONDARY_RACK]: "Secondary rack",
} as const;
