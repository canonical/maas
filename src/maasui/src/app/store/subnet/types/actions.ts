import type { Subnet } from "./base";
import type { SubnetMeta } from "./enum";

import type { Fabric, FabricMeta } from "@/app/store/fabric/types";
import type { VLAN } from "@/app/store/vlan/types";

export type CreateParams = {
  active_discovery?: Subnet["active_discovery"];
  allow_dns?: Subnet["allow_dns"];
  allow_proxy?: Subnet["allow_proxy"];
  cidr?: Subnet["cidr"];
  description?: Subnet["description"];
  disabled_boot_architectures?: string;
  dns_servers?: Subnet["dns_servers"];
  fabric?: Fabric[FabricMeta.PK];
  gateway_ip?: Subnet["gateway_ip"];
  managed?: Subnet["managed"];
  name: Subnet["name"];
  rdns_mode?: Subnet["rdns_mode"];
  vid?: VLAN["vid"];
  vlan?: Subnet["vlan"];
};

export type UpdateParams = {
  [SubnetMeta.PK]: Subnet[SubnetMeta.PK];
  active_discovery?: Subnet["active_discovery"];
  allow_dns?: Subnet["allow_dns"];
  allow_proxy?: Subnet["allow_proxy"];
  cidr?: Subnet["cidr"];
  description?: Subnet["description"];
  disabled_boot_architectures?: string;
  dns_servers?: Subnet["dns_servers"];
  fabric?: Fabric[FabricMeta.PK];
  gateway_ip?: Subnet["gateway_ip"];
  managed?: Subnet["managed"];
  name?: Subnet["name"];
  rdns_mode?: Subnet["rdns_mode"];
  vid?: VLAN["vid"];
  vlan?: Subnet["vlan"];
};
