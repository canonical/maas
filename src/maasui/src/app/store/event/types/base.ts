import type { EventTypeLevel } from "./enum";

import type { UserResponse } from "@/app/apiclient";
import type { TimestampedModel } from "@/app/store/types/model";
import type { BaseNode } from "@/app/store/types/node";
import type { GenericState } from "@/app/store/types/state";

export type EventType = {
  description: string;
  level: EventTypeLevel;
  name: string;
};

// This is named `EventRecord` as there is already a DOM `Event` type. "Event
// record" is the verbose_name in the MAAS code.
export type EventRecord = TimestampedModel & {
  action: string;
  description: string;
  endpoint: number;
  ip_address: string | null;
  node_hostname: BaseNode["hostname"];
  node_id: BaseNode["id"] | null;
  node_system_id: BaseNode["system_id"] | null;
  type: EventType;
  user_agent: string;
  user_id: UserResponse["id"] | null;
  username: UserResponse["username"];
};

export type EventState = GenericState<EventRecord, string | null>;
