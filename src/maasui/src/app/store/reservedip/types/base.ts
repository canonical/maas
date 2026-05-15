import type { APIError } from "@/app/base/types";
import type { Subnet, SubnetMeta } from "@/app/store/subnet/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { NetworkInterface, Node, NodeType } from "@/app/store/types/node";
import type { GenericState } from "@/app/store/types/state";

export type ReservedIp = TimestampedModel & {
  ip: string;
  mac_address: string;
  comment?: string;
  subnet: Subnet[SubnetMeta.PK];
  node_summary?: ReservedIpNodeSummary;
};

export type ReservedIpNodeSummary = {
  fqdn: Node["fqdn"];
  hostname: Node["hostname"];
  node_type: NodeType;
  system_id: Node["system_id"];
  via?: NetworkInterface["name"];
};

export type ReservedIpState = GenericState<ReservedIp, APIError>;
