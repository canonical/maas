import { actions } from "./slice";

describe("token actions", () => {
  it("should handle fetching tokens", () => {
    expect(actions.fetch()).toEqual({
      type: "token/fetch",
      meta: {
        model: "token",
        method: "list",
      },
      payload: null,
    });
  });

  it("can handle creating tokens", () => {
    expect(actions.create({ name: "secret token" })).toEqual({
      type: "token/create",
      meta: {
        model: "token",
        method: "create",
      },
      payload: {
        params: {
          name: "secret token",
        },
      },
    });
  });

  it("can handle deleting tokens", () => {
    expect(actions.delete(808)).toEqual({
      type: "token/delete",
      meta: {
        model: "token",
        method: "delete",
      },
      payload: {
        params: {
          id: 808,
        },
      },
    });
  });

  it("can clean up", () => {
    expect(actions.cleanup()).toEqual({
      type: "token/cleanup",
    });
  });
});
