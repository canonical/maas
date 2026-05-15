import { actions } from "./slice";

describe("tag actions", () => {
  it("returns an action for fetching tags", () => {
    expect(actions.fetch()).toEqual({
      type: "tag/fetch",
      meta: {
        model: "tag",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns an action for fetching tags with a filter", () => {
    expect(actions.fetch({ node_filter: { id: "abc123" } }, "123456")).toEqual({
      type: "tag/fetch",
      meta: {
        model: "tag",
        method: "list",
        callId: "123456",
        nocache: true,
      },
      payload: { params: { node_filter: { id: "abc123" } } },
    });
  });

  it("can create an action for creating a tag", () => {
    const params = {
      comment: "It's a tag",
      definition: "tag def",
      kernel_opts: "opts",
      name: "tag1",
    };
    expect(actions.create(params)).toEqual({
      type: "tag/create",
      meta: {
        model: "tag",
        method: "create",
      },
      payload: {
        params,
      },
    });
  });

  it("can create an action for deleting a tag", () => {
    expect(actions.delete(1)).toEqual({
      type: "tag/delete",
      meta: {
        model: "tag",
        method: "delete",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("can create an action for updating a tag", () => {
    const params = {
      comment: "It's a tag",
      definition: "tag def",
      id: 1,
      kernel_opts: "opts",
      name: "tag1",
    };
    expect(actions.update(params)).toEqual({
      type: "tag/update",
      meta: {
        model: "tag",
        method: "update",
      },
      payload: {
        params,
      },
    });
  });
});
