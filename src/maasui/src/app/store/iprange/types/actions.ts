import type { IPRange } from "./base";
import type { IPRangeMeta } from "./enum";

export type CreateParams = {
  comment: IPRange["comment"];
  end_ip: IPRange["end_ip"];
  start_ip: IPRange["start_ip"];
  subnet?: IPRange["subnet"];
  type: IPRange["type"];
  user?: IPRange["user"];
};

export type UpdateParams = Partial<CreateParams> & {
  [IPRangeMeta.PK]: IPRange[IPRangeMeta.PK];
};
