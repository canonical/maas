import type { Token } from "./base";
import type { TokenMeta } from "./enum";

export type CreateParams = {
  name?: string;
};

export type UpdateParams = CreateParams & {
  [TokenMeta.PK]: Token[TokenMeta.PK];
};
