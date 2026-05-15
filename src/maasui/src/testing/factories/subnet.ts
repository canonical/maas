import { array, define, extend, random } from "cooky-cutter";

import { timestamp } from "./general";
import { model, timestampedModel } from "./model";

import { PodType } from "@/app/store/pod/constants";
import { IPAddressType } from "@/app/store/subnet/types";
import type {
  BaseSubnet,
  SubnetBMC,
  SubnetBMCNode,
  SubnetDetails,
  SubnetDNSRecord,
  SubnetIP,
  SubnetIPNodeSummary,
  SubnetStatistics,
  SubnetStatisticsRange,
  SubnetScanFailure,
  SubnetScanResult,
} from "@/app/store/subnet/types";
import type { Model, TimestampedModel } from "@/app/store/types/model";
import { NodeType } from "@/app/store/types/node";

export const subnetStatisticsRange = define<SubnetStatisticsRange>({
  end: "172.16.2.1",
  num_addresses: random,
  purpose: () => [],
  start: "172.16.2.1",
});

export const subnetStatistics = define<SubnetStatistics>({
  available_string: "99%",
  first_address: "172.16.1.1",
  ip_version: 4,
  largest_available: random,
  last_address: "172.16.1.254",
  num_available: random,
  num_unavailable: random,
  ranges: array(subnetStatisticsRange),
  suggested_dynamic_range: subnetStatisticsRange,
  suggested_gateway: null,
  total_addresses: random,
  usage_string: "1%",
  usage: random,
});

export const subnetBMCNode = define<SubnetBMCNode>({
  hostname: "bmc-node",
  system_id: () => random().toString(),
});

export const subnetBMC = extend<Model, SubnetBMC>(model, {
  nodes: () => [],
  power_type: PodType.LXD,
});

export const subnetDNSRecord = extend<Model, SubnetDNSRecord>(model, {
  domain: "dns-domain",
  name: "dns-name",
});

export const subnetIPNodeSummary = define<SubnetIPNodeSummary>({
  fqdn: "subnet-node-fqdn",
  hostname: "subnet-node-hostname",
  is_container: false,
  node_type: NodeType.MACHINE,
  system_id: () => random().toString(),
});

export const subnetIP = define<SubnetIP>({
  alloc_type: IPAddressType.AUTO,
  created: () => timestamp("Wed, 08 Jul. 2020 05:35:04"),
  ip: "192.168.1.1",
  updated: () => timestamp("Wed, 08 Jul. 2020 05:35:04"),
});

export const subnetScanFailure = define<SubnetScanFailure>({
  message: "it failed",
  type: "error",
});

export const subnetScanResult = define<SubnetScanResult>({
  failed_to_connect_to: () => [],
  failures: () => [],
  result: "Scanning is in-progress on all rack controllers.",
  rpc_call_timed_out_on: () => [],
  scan_attempted_on: () => [],
  scan_failed_on: () => [],
  scan_started_on: () => [],
});

export const subnet = extend<TimestampedModel, BaseSubnet>(timestampedModel, {
  active_discovery: false,
  allow_dns: false,
  allow_proxy: false,
  cidr: "172.16.1.0/24",
  description: "test description",
  disabled_boot_architectures: () => [],
  dns_servers: "fd89:8724:81f1:5512:557f:99c3:6967:8d63",
  gateway_ip: null,
  managed: false,
  name: (i: number) => `test subnet ${i}`,
  rdns_mode: random,
  space: null,
  statistics: subnetStatistics,
  version: 4,
  vlan: random,
});

export const subnetDetails = extend<BaseSubnet, SubnetDetails>(subnet, {
  ip_addresses: () => [],
});
