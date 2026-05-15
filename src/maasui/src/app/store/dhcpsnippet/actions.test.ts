import { actions } from "./slice";

describe("dhcpsnippet actions", () => {
  it("returns a fetch action", () => {
    expect(actions.fetch()).toEqual({
      type: "dhcpsnippet/fetch",
      meta: {
        model: "dhcpsnippet",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns a create action", () => {
    expect(
      actions.create({ name: "dhcpsnippet1", description: "a dhcpsnippet" })
    ).toEqual({
      type: "dhcpsnippet/create",
      meta: {
        model: "dhcpsnippet",
        method: "create",
      },
      payload: {
        params: {
          name: "dhcpsnippet1",
          description: "a dhcpsnippet",
        },
      },
    });
  });

  it("returns an update action", () => {
    expect(
      actions.update({
        id: 1,
        name: "dhcpsnippet1",
        description: "a dhcpsnippet",
      })
    ).toEqual({
      type: "dhcpsnippet/update",
      meta: {
        model: "dhcpsnippet",
        method: "update",
      },
      payload: {
        params: {
          id: 1,
          name: "dhcpsnippet1",
          description: "a dhcpsnippet",
        },
      },
    });
  });

  it("returns a delete action", () => {
    expect(actions.delete(1)).toEqual({
      type: "dhcpsnippet/delete",
      meta: {
        model: "dhcpsnippet",
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
      type: "dhcpsnippet/cleanup",
      payload: undefined,
    });
  });
});
