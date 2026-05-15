import { extend, random } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { TimestampedModel } from "@/app/store/types/model";
import type { BaseVLAN, VLANDetails } from "@/app/store/vlan/types";

export const vlan = extend<TimestampedModel, BaseVLAN>(timestampedModel, {
  description: "a vlan",
  dhcp_on: false,
  external_dhcp: null,
  fabric: random,
  mtu: random,
  name: (i: number) => `test-vlan-${i}`,
  primary_rack: null,
  rack_sids: () => [],
  relay_vlan: null,
  secondary_rack: null,
  space: random,
  subnet_ids: () => [],
  vid: random,
});

export const vlanDetails = extend<BaseVLAN, VLANDetails>(vlan, {
  node_ids: () => [],
  space_ids: () => [],
});
