import type { IPAddressType, SubnetMeta } from "./enum";

import type { UserResponse } from "@/app/apiclient";
import type { APIError } from "@/app/base/types";
import type { Domain } from "@/app/store/domain/types";
import type { KnownBootArchitecture } from "@/app/store/general/types";
import type { Pod } from "@/app/store/pod/types";
import type {
  Model,
  TimestampedModel,
  TimestampFields,
} from "@/app/store/types/model";
import type { NetworkInterface, Node, NodeType } from "@/app/store/types/node";
import type { EventError, GenericState } from "@/app/store/types/state";
import type { VLAN } from "@/app/store/vlan/types";

export type SubnetStatisticsRange = {
  end: string;
  num_addresses: number;
  purpose: string[];
  start: string;
};

export type SubnetStatistics = {
  available_string: string;
  first_address: string;
  ip_version: 4 | 6;
  largest_available: number;
  last_address: string;
  num_available: number;
  num_unavailable: number;
  ranges: SubnetStatisticsRange[];
  suggested_dynamic_range: SubnetStatisticsRange;
  suggested_gateway: string | null;
  total_addresses: number;
  usage_string: string;
  usage: number;
};

export type SubnetBMCNode = {
  hostname: Node["hostname"];
  system_id: Node["system_id"];
};

export type SubnetBMC = Model & {
  nodes: SubnetBMCNode[];
  power_type: Pod["type"];
};

export type SubnetDNSRecord = Model & {
  domain: Domain["name"];
  name: string;
};

export type SubnetIPNodeSummary = {
  fqdn: Node["fqdn"];
  hostname: Node["hostname"];
  is_container: boolean;
  node_type: NodeType;
  system_id: Node["system_id"];
  via?: NetworkInterface["name"];
};

export type SubnetIP = TimestampFields & {
  alloc_type: IPAddressType;
  bmcs?: SubnetBMC[];
  dns_records?: SubnetDNSRecord[];
  ip: string;
  node_summary?: SubnetIPNodeSummary;
  user?: UserResponse["username"];
};

export type SubnetScanFailure = {
  message: string;
  type: string;
};

export type SubnetScanResult = {
  failed_to_connect_to: SubnetBMCNode[];
  failures: SubnetScanFailure[];
  result: string;
  rpc_call_timed_out_on: SubnetBMCNode[];
  scan_attempted_on: SubnetBMCNode[];
  scan_failed_on: SubnetBMCNode[];
  scan_started_on: SubnetBMCNode[];
};

export type BaseSubnet = TimestampedModel & {
  active_discovery: boolean;
  allow_dns: boolean;
  allow_proxy: boolean;
  cidr: string;
  description: string;
  disabled_boot_architectures: KnownBootArchitecture["name"][];
  dns_servers: string;
  gateway_ip: string | null;
  managed: boolean;
  name: string;
  rdns_mode: number;
  space: number | null;
  statistics: SubnetStatistics;
  version: 4 | 6;
  vlan: VLAN["id"];
};

export type SubnetDetails = BaseSubnet & {
  ip_addresses: SubnetIP[];
};

export type Subnet = BaseSubnet | SubnetDetails;

export type SubnetStatus = {
  scanning: boolean;
};

export type SubnetStatuses = Record<string, SubnetStatus>;

export type SubnetState = GenericState<Subnet, APIError> & {
  active: Subnet[SubnetMeta.PK] | null;
  eventErrors: EventError<Subnet, APIError, SubnetMeta.PK>[];
  statuses: SubnetStatuses;
};
