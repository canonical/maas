import { spaceActions } from "./";

describe("space actions", () => {
  it("returns a fetch action", () => {
    expect(spaceActions.fetch()).toEqual({
      type: "space/fetch",
      meta: {
        model: "space",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns a create action", () => {
    expect(
      spaceActions.create({ name: "space1", description: "a space" })
    ).toEqual({
      type: "space/create",
      meta: {
        model: "space",
        method: "create",
      },
      payload: {
        params: {
          name: "space1",
          description: "a space",
        },
      },
    });
  });

  it("returns an update action", () => {
    expect(
      spaceActions.update({ id: 1, name: "space1", description: "a space" })
    ).toEqual({
      type: "space/update",
      meta: {
        model: "space",
        method: "update",
      },
      payload: {
        params: {
          id: 1,
          name: "space1",
          description: "a space",
        },
      },
    });
  });

  it("returns a delete action", () => {
    expect(spaceActions.delete(1)).toEqual({
      type: "space/delete",
      meta: {
        model: "space",
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
    expect(spaceActions.cleanup()).toEqual({
      type: "space/cleanup",
      payload: undefined,
    });
  });

  it("can create an action to get a space", () => {
    expect(spaceActions.get(0)).toEqual({
      type: "space/get",
      meta: {
        model: "space",
        method: "get",
      },
      payload: {
        params: { id: 0 },
      },
    });
  });

  it("can create an action to set an active space", () => {
    expect(spaceActions.setActive(0)).toEqual({
      type: "space/setActive",
      meta: {
        model: "space",
        method: "set_active",
      },
      payload: {
        params: { id: 0 },
      },
    });
  });
});
