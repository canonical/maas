import { define, extend, random, sequence } from "cooky-cutter";

import { timestamp } from "./general";

import type {
  Model,
  ModelRef,
  TimestampedModel,
} from "@/app/store/types/model";

export const model = define<Model>({
  id: sequence,
});

export const timestampedModel = extend<Model, TimestampedModel>(model, {
  created: () => timestamp("Wed, 19 Feb. 2020 11:59:19"),
  updated: () => timestamp("Fri, 03 Jul. 2020 02:44:12"),
});

export const modelRef = extend<Model, ModelRef>(model, {
  name: `modelref-${random()}`,
});
