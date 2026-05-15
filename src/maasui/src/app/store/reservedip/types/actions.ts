import type { ReservedIp } from "./base";
import type { ReservedIpMeta } from "./enum";

export type CreateParams = {
  ip: ReservedIp["ip"];
  mac_address?: ReservedIp["mac_address"];
  comment?: ReservedIp["comment"];
  subnet?: ReservedIp["subnet"];
};

export type UpdateParams = Partial<CreateParams> & {
  [ReservedIpMeta.PK]: ReservedIp[ReservedIpMeta.PK];
};

export type DeleteParams = {
  [ReservedIpMeta.PK]: ReservedIp[ReservedIpMeta.PK];
  ip: ReservedIp["ip"];
};
