import reducers, { actions } from "./slice";
import { ScriptResultDataType } from "./types";

import * as factory from "@/testing/factories";

describe("script result reducer", () => {
  it("returns the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      errors: null,
      items: [],
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
      history: {},
      logs: null,
    });
  });

  describe("get", () => {
    it("reduces getStart", () => {
      const scriptResultState = factory.scriptResultState({
        items: [],
        loading: false,
      });
      expect(reducers(scriptResultState, actions.getStart(null))).toEqual(
        factory.scriptResultState({ loading: true })
      );
    });

    it("reduces getSuccess", () => {
      const existingScriptResult = factory.scriptResult();
      const newScriptResult = factory.scriptResult({ id: 2 });
      const scriptResultState = factory.scriptResultState({
        items: [existingScriptResult],
        loading: true,
      });
      expect(
        reducers(scriptResultState, actions.getSuccess(newScriptResult))
      ).toEqual(
        factory.scriptResultState({
          items: [existingScriptResult, newScriptResult],
          loading: false,
          history: { 2: [] },
        })
      );
    });

    it("reduces getError", () => {
      const scriptResultState = factory.scriptResultState({ loading: true });
      expect(
        reducers(
          scriptResultState,
          actions.getError("Could not get script result")
        )
      ).toEqual(
        factory.scriptResultState({
          errors: "Could not get script result",
          loading: false,
        })
      );
    });
  });

  it("reduces getByNodeIdStart", () => {
    const scriptResultState = factory.scriptResultState({
      items: [],
      loading: false,
    });

    expect(reducers(scriptResultState, actions.getByNodeIdStart(null))).toEqual(
      factory.scriptResultState({ loading: true })
    );
  });

  it("reduces getByNodeIdSuccess", () => {
    const existingScriptResult = factory.scriptResult({ id: 1 });
    const newScriptResult = factory.scriptResult({ id: 2 });
    const newScriptResult2 = factory.scriptResult({ id: 3 });

    const scriptResultState = factory.scriptResultState({
      items: [existingScriptResult],
      loading: true,
    });

    expect(
      reducers(
        scriptResultState,
        actions.getByNodeIdSuccess("abc123", [
          newScriptResult,
          newScriptResult2,
        ])
      )
    ).toEqual(
      factory.scriptResultState({
        items: [existingScriptResult, newScriptResult, newScriptResult2],
        loading: false,
        loaded: true,
        history: { 2: [], 3: [] },
      })
    );
  });

  it("reduces getError", () => {
    const scriptResultState = factory.scriptResultState({ loading: true });

    expect(
      reducers(
        scriptResultState,
        actions.getByNodeIdError("Could not get script result")
      )
    ).toEqual(
      factory.scriptResultState({
        errors: "Could not get script result",
        loading: false,
      })
    );
  });

  it("reduces createNotify", () => {
    const scriptResultState = factory.scriptResultState({
      items: [],
    });
    const newScriptResult = factory.scriptResult({ id: 1 });

    expect(
      reducers(scriptResultState, {
        type: "noderesult/createNotify",
        payload: newScriptResult,
      })
    ).toEqual(
      factory.scriptResultState({
        items: [newScriptResult],
      })
    );
  });

  it("reduces createNotify for a script result that already exists", () => {
    const scriptResultState = factory.scriptResultState({
      items: [factory.scriptResult({ id: 1 })],
    });
    const newScriptResult = factory.scriptResult({ id: 1 });

    expect(
      reducers(scriptResultState, {
        type: "noderesult/createNotify",
        payload: newScriptResult,
      })
    ).toEqual(
      factory.scriptResultState({
        items: [newScriptResult],
      })
    );
  });

  it("reduce updateNotify for noderesult", () => {
    const scriptResultState = factory.scriptResultState({
      items: [factory.scriptResult({ id: 1 })],
    });
    const updatedScriptResult = factory.scriptResult({ id: 1 });

    expect(
      reducers(scriptResultState, {
        type: "noderesult/updateNotify",
        payload: updatedScriptResult,
      })
    ).toEqual(
      factory.scriptResultState({
        items: [updatedScriptResult],
      })
    );
  });

  it("reduces updateNotify for a script result that doesn't exist", () => {
    const scriptResultState = factory.scriptResultState({
      items: [],
    });
    const updatedScriptResult = factory.scriptResult({ id: 1 });

    expect(
      reducers(scriptResultState, {
        type: "noderesult/updateNotify",
        payload: updatedScriptResult,
      })
    ).toEqual(
      factory.scriptResultState({
        items: [updatedScriptResult],
      })
    );
  });

  it("reduces getHistoryStart", () => {
    const scriptResultState = factory.scriptResultState({
      items: [],
      loading: false,
      history: {},
    });

    expect(reducers(scriptResultState, actions.getHistoryStart(null))).toEqual(
      factory.scriptResultState({ loading: true })
    );
  });

  it("reduces getHistorySuccess", () => {
    const scriptResult = factory.scriptResult({ id: 123 });
    const partialScriptResult = factory.partialScriptResult({
      id: scriptResult.id,
    });

    const scriptResultState = factory.scriptResultState({
      items: [scriptResult],
      loading: true,
      history: { 123: [] },
    });

    expect(
      reducers(
        scriptResultState,
        actions.getHistorySuccess(123, [partialScriptResult])
      )
    ).toEqual(
      factory.scriptResultState({
        items: [scriptResult],
        loading: false,
        loaded: true,
        history: { 123: [partialScriptResult] },
      })
    );
  });

  it("reduces getLogsStart", () => {
    const scriptResultState = factory.scriptResultState({
      items: [],
      loading: false,
      history: {},
      logs: null,
    });

    expect(reducers(scriptResultState, actions.getLogsStart(null))).toEqual(
      factory.scriptResultState({ loading: true })
    );
  });

  it("reduces getLogsSuccess", () => {
    const scriptResult = factory.scriptResult({ id: 123 });

    const scriptResultState = factory.scriptResultState({
      items: [scriptResult],
      loading: true,
      logs: null,
    });

    expect(
      reducers(
        scriptResultState,
        actions.getLogsSuccess(123, ScriptResultDataType.COMBINED, "foo")
      )
    ).toEqual(
      factory.scriptResultState({
        items: [scriptResult],
        loading: false,
        loaded: true,
        logs: { 123: { combined: "foo" } },
      })
    );
  });

  it("reduces getLogsSuccess with additional logs", () => {
    const scriptResult = factory.scriptResult({ id: 123 });

    const scriptResultState = factory.scriptResultState({
      items: [scriptResult],
      loading: true,
      logs: { 123: { combined: "foo" } },
    });

    expect(
      reducers(
        scriptResultState,
        actions.getLogsSuccess(123, ScriptResultDataType.RESULT, "bar")
      )
    ).toEqual(
      factory.scriptResultState({
        items: [scriptResult],
        loading: false,
        loaded: true,
        logs: { 123: { combined: "foo", result: "bar" } },
      })
    );
  });
});
