import type { VLAN } from "./base";
import type { VLANMeta } from "./enum";

import type { Controller, ControllerMeta } from "@/app/store/controller/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";

export type ConfigureDHCPParams = {
  [VLANMeta.PK]: VLAN[VLANMeta.PK];
  controllers: Controller[ControllerMeta.PK][];
  extra?: {
    end?: string;
    gateway?: string | null;
    start?: string;
    subnet?: Subnet[SubnetMeta.PK];
  };
  relay_vlan?: VLAN[VLANMeta.PK] | null;
};

export type CreateParams = {
  description?: VLAN["description"];
  dhcp_on?: VLAN["dhcp_on"];
  fabric?: VLAN["fabric"];
  mtu?: VLAN["mtu"];
  name?: VLAN["name"];
  primary_rack?: VLAN["primary_rack"];
  relay_vlan?: VLAN["relay_vlan"];
  secondary_rack?: VLAN["secondary_rack"];
  space?: VLAN["space"];
  vid: VLAN["vid"];
};

export type UpdateParams = CreateParams & {
  [VLANMeta.PK]: VLAN[VLANMeta.PK];
};
