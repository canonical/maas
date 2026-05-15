import { actions } from "./slice";

describe("fabric actions", () => {
  it("returns a fetch action", () => {
    expect(actions.fetch()).toEqual({
      type: "fabric/fetch",
      meta: {
        model: "fabric",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns a create action", () => {
    expect(
      actions.create({
        name: "fabric1",
        description: "a fabric",
        class_type: "first class",
      })
    ).toEqual({
      type: "fabric/create",
      meta: {
        model: "fabric",
        method: "create",
      },
      payload: {
        params: {
          class_type: "first class",
          name: "fabric1",
          description: "a fabric",
        },
      },
    });
  });

  it("returns an update action", () => {
    expect(
      actions.update({
        id: 1,
        name: "fabric1",
        description: "a fabric",
        class_type: "first class",
      })
    ).toEqual({
      type: "fabric/update",
      meta: {
        model: "fabric",
        method: "update",
      },
      payload: {
        params: {
          id: 1,
          class_type: "first class",
          name: "fabric1",
          description: "a fabric",
        },
      },
    });
  });

  it("returns a delete action", () => {
    expect(actions.delete(1)).toEqual({
      type: "fabric/delete",
      meta: {
        model: "fabric",
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
      type: "fabric/cleanup",
      payload: undefined,
    });
  });

  it("can create an action to get a fabric", () => {
    expect(actions.get(0)).toEqual({
      type: "fabric/get",
      meta: {
        model: "fabric",
        method: "get",
      },
      payload: {
        params: { id: 0 },
      },
    });
  });

  it("can create an action to set an active fabric", () => {
    expect(actions.setActive(0)).toEqual({
      type: "fabric/setActive",
      meta: {
        model: "fabric",
        method: "set_active",
      },
      payload: {
        params: { id: 0 },
      },
    });
  });
});
