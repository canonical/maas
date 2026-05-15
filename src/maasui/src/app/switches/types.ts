import type { SwitchResponse } from "@/app/apiclient";

// TODO: Remove SwitchItem and use SwitchResponse directly once the API includes these fields.
export type SwitchItem = SwitchResponse & {
  name?: string;
  mac_address?: string;
  status?: string;
  ztp_enabled?: boolean;
};
