import { define, random } from "cooky-cutter";

import type {
  EntitlementResponse,
  UserGroupMemberResponse,
  UserGroupResponse,
  UserGroupStatisticsResponse,
} from "@/app/apiclient";
import { Entitlement } from "@/app/settings/views/UserManagement/views/Groups/constants";

export const group = define<UserGroupResponse>({
  id: random,
  name: (i: number) => `group-${i}`,
  description: "A sample group",
});

export const groupStatistics = define<UserGroupStatisticsResponse>({
  id: random,
  user_count: random,
});

export const groupEntitlements = define<EntitlementResponse>({
  entitlement: Entitlement.CAN_DEPLOY_MACHINES,
  resource_id: 0,
  resource_type: "maas",
});

export const groupMember = define<UserGroupMemberResponse>({
  email: (i: number) => `member${i}@example.com`,
  user_id: random,
  username: (i: number) => `member${i}`,
});
