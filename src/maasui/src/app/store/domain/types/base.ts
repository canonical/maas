import type { RecordType } from "./enum";

import type { UserResponse } from "@/app/apiclient";
import type { APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { BaseNode, NodeType } from "@/app/store/types/node";
import type { GenericState } from "@/app/store/types/state";

export type DomainResource = {
  dnsdata_id: number | null;
  dnsresource_id: number | null;
  name: string | null;
  node_type: NodeType | null;
  rrdata: string | null;
  rrtype: RecordType;
  system_id: BaseNode["system_id"] | null;
  ttl: number | null;
  user_id: UserResponse["id"] | null;
};

export type BaseDomain = TimestampedModel & {
  authoritative: boolean;
  displayname: string;
  hosts: number;
  is_default: boolean;
  name: string;
  resource_count: number;
  ttl: number | null;
};

export type DomainDetails = BaseDomain & {
  rrsets: DomainResource[];
};

export type Domain = BaseDomain | DomainDetails;

export type DomainState = GenericState<Domain, APIError> & {
  active: number | null;
};
