import { define, extend, sequence } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { ReservedIp } from "@/app/store/reservedip/types";
import type { ReservedIpNodeSummary } from "@/app/store/reservedip/types/base";
import type { TimestampedModel } from "@/app/store/types/model";
import { NodeType } from "@/app/store/types/node";

export const reservedIpNodeSummary = define<ReservedIpNodeSummary>({
  fqdn: "springbok.maas",
  hostname: "springbok",
  node_type: NodeType.MACHINE,
  system_id: "abc123",
  via: "eth0",
});

export const reservedIp = extend<TimestampedModel, ReservedIp>(
  timestampedModel,
  {
    id: sequence,
    comment: "Lorem ipsum dolor sit amet",
    ip: (i: number) => `192.168.1.${i}`,
    mac_address: (i: number) => `00:00:00:00:00:${i}`,
    subnet: 1,
    node_summary: reservedIpNodeSummary,
  }
);
