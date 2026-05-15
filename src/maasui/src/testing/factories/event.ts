import { define, extend } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { EventRecord, EventType } from "@/app/store/event/types";
import { EventTypeLevel } from "@/app/store/event/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const eventType = define<EventType>({
  description: "description-2HCo4f",
  level: EventTypeLevel.INFO,
  name: "name-9pJmiYbyjNLfuAeVkxlc",
});

export const eventRecord = extend<TimestampedModel, EventRecord>(
  timestampedModel,
  {
    action: "action-h7Jza3",
    description: "desc-LRv9EV",
    endpoint: 1,
    ip_address: "152.26.96.176",
    node_hostname: "honest-bear",
    node_id: 11,
    node_system_id: "tftrtd",
    type: eventType,
    user_agent: "user_agent-HY93gV",
    user_id: 572,
    username: "RYKeTLTLIp",
  }
);
