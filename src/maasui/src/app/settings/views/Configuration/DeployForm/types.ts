import type { TimeSpan } from "@/app/base/types";

export type DeployFormValues = {
  default_osystem: string;
  default_distro_series: string;
  hardware_sync_interval: TimeSpan;
};
