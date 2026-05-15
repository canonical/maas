import { define, random } from "cooky-cutter";

import type { ResourcePoolStatisticsResponse } from "@/app/apiclient";

export const resourcePool = define<ResourcePoolStatisticsResponse>({
  description: "test description",
  is_default: false,
  machine_ready_count: random,
  machine_total_count: random,
  name: (i: number) => `test name ${i}`,
  permissions: () => [],
  id: (i: number) => i,
});
