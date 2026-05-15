import type { Fabric } from "./base";
import type { FabricMeta } from "./enum";

export type CreateParams = {
  class_type?: Fabric["class_type"];
  description?: Fabric["description"];
  name?: Fabric["name"];
};

export type UpdateParams = CreateParams & {
  [FabricMeta.PK]: Fabric[FabricMeta.PK];
};
