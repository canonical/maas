import type { Device, DeviceDetails, DeviceNetworkInterface } from "./base";
import type { DeviceIpAssignment, DeviceMeta } from "./enum";

import type { ZoneResponse } from "@/app/apiclient";
import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { Domain } from "@/app/store/domain/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import type { NetworkInterface, NetworkLink } from "@/app/store/types/node";

export type CreateParams = {
  description?: DeviceDetails["description"];
  domain?: {
    name: Domain["name"];
  };
  extra_macs?: Device["extra_macs"];
  hostname?: Device["hostname"];
  interfaces: {
    ip_address?: DeviceNetworkInterface["ip_address"];
    ip_assignment: DeviceIpAssignment;
    mac: DeviceNetworkInterface["mac_address"];
    name?: DeviceNetworkInterface["name"];
    subnet?: Subnet[SubnetMeta.PK] | null;
  }[];
  parent?: Controller[ControllerMeta.PK];
  primary_mac: Device["primary_mac"];
  swap_size?: DeviceDetails["swap_size"];
  zone?: {
    name: ZoneResponse["name"];
  };
};

export type CreateInterfaceParams = {
  [DeviceMeta.PK]: Device[DeviceMeta.PK];
  enabled?: NetworkInterface["enabled"];
  interface_speed?: NetworkInterface["interface_speed"];
  ip_address?: Device["ip_address"];
  ip_assignment: Device["ip_assignment"];
  link_connected?: NetworkInterface["link_connected"];
  link_speed?: NetworkInterface["link_speed"];
  mac_address: NetworkInterface["mac_address"];
  name?: NetworkInterface["name"];
  numa_node?: NetworkInterface["numa_node"];
  subnet?: string;
  tags?: NetworkInterface["tags"];
  vlan?: NetworkInterface["vlan_id"];
};

// This endpoint is an alias for create_interface.
export type CreatePhysicalParams = CreateInterfaceParams;

export type DeleteInterfaceParams = {
  interface_id: NetworkInterface["id"];
  [DeviceMeta.PK]: Device[DeviceMeta.PK];
};

export type LinkSubnetParams = {
  [DeviceMeta.PK]: Device[DeviceMeta.PK];
  interface_id: NetworkInterface["id"];
  ip_address?: NetworkLink["ip_address"];
  ip_assignment?: DeviceIpAssignment;
  link_id?: NetworkLink["id"];
  subnet?: Subnet[SubnetMeta.PK];
};

export type UnlinkSubnetParams = {
  [DeviceMeta.PK]: Device[DeviceMeta.PK];
  interface_id: NetworkInterface["id"];
  link_id: NetworkLink["id"];
};

export type UpdateParams = Partial<CreateParams> & {
  [DeviceMeta.PK]: Device[DeviceMeta.PK];
  tags?: Device["tags"];
};
