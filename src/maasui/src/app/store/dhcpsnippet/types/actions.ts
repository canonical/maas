import type { DHCPSnippet } from "./base";
import type { DHCPSnippetMeta } from "./enum";

export type CreateParams = {
  description?: DHCPSnippet["description"];
  enabled?: DHCPSnippet["enabled"];
  global_snippet?: boolean;
  iprange?: DHCPSnippet["iprange"];
  name?: DHCPSnippet["name"];
  node?: DHCPSnippet["node"];
  subnet?: DHCPSnippet["subnet"];
  value?: DHCPSnippet["value"];
};

export type UpdateParams = CreateParams & {
  [DHCPSnippetMeta.PK]: DHCPSnippet[DHCPSnippetMeta.PK];
};
