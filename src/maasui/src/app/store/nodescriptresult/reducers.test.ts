import { actions as scriptResultActions } from "../scriptresult/slice";

import reducers from "./slice";

import * as factory from "@/testing/factories";

describe("nodescriptresult reducer", () => {
  it("reduces getByNodeIdSuccess", () => {
    const nodeScriptResultState = factory.nodeScriptResultState();

    const scriptResults = [
      factory.scriptResult({ id: 1 }),
      factory.scriptResult({ id: 2 }),
    ];

    expect(
      reducers(
        nodeScriptResultState,
        scriptResultActions.getByNodeIdSuccess("abc123", scriptResults)
      )
    ).toEqual({
      items: {
        abc123: [1, 2],
      },
    });
  });
});
