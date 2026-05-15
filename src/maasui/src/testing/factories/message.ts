import { extend } from "cooky-cutter";

import { model } from "./model";

import type { Message } from "@/app/store/message/types";
import type { Model } from "@/app/store/types/model";

export const message = extend<Model, Message>(model, {
  message: "Test message",
  severity: "caution",
  temporary: true,
});
