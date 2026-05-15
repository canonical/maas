import type { NetworkValues } from "../NetworkFields/NetworkFields";

import type {
  BondLacpRate,
  BondMode,
  BondXmitHashPolicy,
} from "@/app/store/general/types";
import type {
  NetworkInterface,
  NetworkInterfaceParams,
} from "@/app/store/types/node";

export enum LinkMonitoring {
  MII = "mii",
}

export enum MacSource {
  NIC = "nic",
  MANUAL = "manual",
}

export type BondFormValues = NetworkValues & {
  bond_downdelay: NetworkInterfaceParams["bond_downdelay"];
  bond_lacp_rate: BondLacpRate | "";
  bond_miimon: NetworkInterfaceParams["bond_miimon"];
  bond_mode: BondMode;
  bond_updelay: NetworkInterfaceParams["bond_updelay"];
  bond_xmit_hash_policy: BondXmitHashPolicy | "";
  linkMonitoring: LinkMonitoring | "";
  mac_address: NetworkInterface["mac_address"];
  macNic: NetworkInterface["mac_address"];
  name: NetworkInterface["name"];
  macSource: MacSource;
  tags: NetworkInterface["tags"];
};
