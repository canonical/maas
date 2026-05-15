import { actions } from "./slice";

describe("service actions", () => {
  it("returns a fetch action", () => {
    expect(actions.fetch()).toEqual({
      type: "service/fetch",
      meta: {
        model: "service",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns a delete action", () => {
    expect(actions.delete(1)).toEqual({
      type: "service/delete",
      meta: {
        model: "service",
        method: "delete",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("returns a cleanup action", () => {
    expect(actions.cleanup()).toEqual({
      type: "service/cleanup",
      payload: undefined,
    });
  });
});
