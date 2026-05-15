import type { ScriptResult } from "@/app/store/scriptresult/types";

export type NodeScriptResultState = {
  items: Record<string, ScriptResult["id"][]>;
};
