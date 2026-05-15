import type { Space } from "./base";
import type { SpaceMeta } from "./enum";

export type CreateParams = {
  description?: Space["description"];
  name: Space["name"];
};

export type UpdateParams = CreateParams & {
  [SpaceMeta.PK]: Space[SpaceMeta.PK];
};
