import type { Device, DeviceMeta } from "@/app/store/device/types";
import { argPath } from "@/app/utils";

const withId = argPath<{ id: Device[DeviceMeta.PK] }>;

const urls = {
  index: "/devices",
  device: {
    configuration: withId("/device/:id/configuration"),
    index: withId("/device/:id"),
    network: withId("/device/:id/network"),
    summary: withId("/device/:id/summary"),
  },
} as const;

export default urls;
