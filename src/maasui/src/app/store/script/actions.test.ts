import { actions } from "./slice";
import { ScriptType } from "./types";

describe("script actions", () => {
  it("should handle fetching scripts", () => {
    expect(actions.fetch()).toEqual({
      meta: {
        method: "list",
        model: "script",
      },
      payload: null,
      type: "script/fetch",
    });
  });

  it("should handle uploading scripts", () => {
    expect(actions.upload(ScriptType.TESTING, "contents", "script-1")).toEqual({
      type: "script/upload",
      payload: {
        name: "script-1",
        type: ScriptType.TESTING,
        contents: "contents",
      },
    });
  });

  it("should handle uploading scripts with an optional name", () => {
    expect(actions.upload(ScriptType.TESTING, "contents")).toEqual({
      type: "script/upload",
      payload: {
        type: ScriptType.TESTING,
        contents: "contents",
      },
    });
  });

  it("can handle deleting scripts", () => {
    expect(actions.delete(1)).toEqual({
      meta: {
        method: "delete",
        model: "script",
      },
      type: "script/delete",
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("can handle cleaning scripts", () => {
    expect(actions.cleanup()).toEqual({
      type: "script/cleanup",
    });
  });
});
