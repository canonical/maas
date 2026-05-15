import { actions } from "./slice";

describe("vmcluster actions", () => {
  it("can create an action for deleting a vmcluster", () => {
    expect(actions.delete({ decompose: true, id: 1 })).toEqual({
      type: "vmcluster/delete",
      meta: {
        model: "vmcluster",
        method: "delete",
      },
      payload: {
        params: {
          decompose: true,
          id: 1,
        },
      },
    });
  });

  it("can create a fetch action", () => {
    expect(actions.fetch()).toEqual({
      type: "vmcluster/fetch",
      meta: {
        cache: true,
        model: "vmcluster",
        method: "list_by_physical_cluster",
      },
      payload: null,
    });
  });

  it("can create a get action", () => {
    expect(actions.get(1)).toEqual({
      type: "vmcluster/get",
      meta: {
        model: "vmcluster",
        method: "get",
      },
      payload: {
        params: { id: 1 },
      },
    });
  });

  it("can create a cleanup action", () => {
    expect(actions.cleanup()).toEqual({
      type: "vmcluster/cleanup",
    });
  });
});
