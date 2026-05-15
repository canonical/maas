import type { PowerType } from "@/app/store/general/types";
import type { PowerParameters } from "@/app/store/types/node";

export type AddMachineValues = {
  architecture: string;
  domain: string;
  extra_macs: string[];
  hostname: string;
  is_dpu: boolean;
  min_hwe_kernel: string;
  pool: string;
  power_parameters: PowerParameters;
  power_type: PowerType["name"] | "";
  pxe_mac: string;
  zone: string;
};
