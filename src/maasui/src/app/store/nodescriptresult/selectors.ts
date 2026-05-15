import type { NodeScriptResultState } from "./types";

import type { RootState } from "@/app/store/root/types";

const all = (state: RootState): NodeScriptResultState["items"] =>
  state.nodescriptresult.items;

const nodeScriptResult = {
  all,
};

export default nodeScriptResult;
