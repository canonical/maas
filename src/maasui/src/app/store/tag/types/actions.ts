import type { Tag } from "./base";
import type { TagMeta } from "./enum";

export type CreateParams = {
  comment?: Tag["comment"];
  definition?: Tag["definition"];
  kernel_opts?: Tag["kernel_opts"];
  name: Tag["name"];
};

export type UpdateParams = CreateParams & {
  [TagMeta.PK]: Tag[TagMeta.PK];
};
