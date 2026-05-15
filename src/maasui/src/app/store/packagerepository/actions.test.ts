import { actions } from "./slice";

describe("packagerepository actions", () => {
  it("should handle fetching repositories", () => {
    expect(actions.fetch()).toEqual({
      type: "packagerepository/fetch",
      meta: {
        model: "packagerepository",
        method: "list",
      },
      payload: null,
    });
  });

  it("can handle creating repositories", () => {
    expect(actions.create({ name: "foo", url: "ppa:this/ppa" })).toEqual({
      type: "packagerepository/create",
      meta: {
        model: "packagerepository",
        method: "create",
      },
      payload: {
        params: {
          name: "foo",
          url: "ppa:this/ppa",
        },
      },
    });
  });

  it("can handle updating repositories", () => {
    expect(actions.update({ id: 1, name: "bar", url: "ppa:this/ppa" })).toEqual(
      {
        type: "packagerepository/update",
        meta: {
          model: "packagerepository",
          method: "update",
        },
        payload: {
          params: {
            id: 1,
            name: "bar",
            url: "ppa:this/ppa",
          },
        },
      }
    );
  });

  it("can handle deleting repositories", () => {
    expect(actions.delete(911)).toEqual({
      type: "packagerepository/delete",
      meta: {
        model: "packagerepository",
        method: "delete",
      },
      payload: {
        params: {
          id: 911,
        },
      },
    });
  });

  it("can handle cleaning repositories", () => {
    expect(actions.cleanup()).toEqual({
      type: "packagerepository/cleanup",
    });
  });
});
