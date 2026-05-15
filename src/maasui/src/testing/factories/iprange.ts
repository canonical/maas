import { extend, random } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { IPRange } from "@/app/store/iprange/types";
import { IPRangeType } from "@/app/store/iprange/types";
import type { TimestampedModel } from "@/app/store/types/model";

export const ipRange = extend<TimestampedModel, IPRange>(timestampedModel, {
  comment: "",
  end_ip: "1.1.1.1",
  start_ip: "1.1.1.99",
  subnet: random,
  type: IPRangeType.Dynamic,
  user: "",
  vlan: null,
});
