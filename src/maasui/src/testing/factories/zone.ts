import { define, random } from "cooky-cutter";

import type { ZoneResponse, ZoneWithStatisticsResponse } from "@/app/apiclient";

export const zone = define<ZoneResponse>({
  description: "test description",
  name: (i: number) => `zone-${i}`,
  id: (i: number) => i,
});

export const zoneWithStatistics = define<ZoneWithStatisticsResponse>({
  id: (i: number) => i,
  controllers_count: random,
  devices_count: random,
  machines_count: random,
});
