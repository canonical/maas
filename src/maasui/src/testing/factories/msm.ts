import { define } from "cooky-cutter";

import { timestamp } from "./general";

import type { MsmState, MsmStatus } from "@/app/store/msm/types/base";

const msmStatus = define<MsmStatus | null>({
  smUrl: "https://example.com",
  running: "not_connected",
  startTime: timestamp("Wed, 08 Jul. 2022 05:35:45"),
});

export const msm = define<MsmState>({
  status: msmStatus,
  loading: false,
  loaded: false,
  errors: null,
});
