import { PodType } from "./constants";
import { actions } from "./slice";
import { PodMeta } from "./types";

describe("pod actions", () => {
  it("can create an action for fetching pods", () => {
    expect(actions.fetch()).toEqual({
      type: "pod/fetch",
      meta: {
        model: "pod",
        method: "list",
      },
      payload: null,
    });
  });

  it("can create an action for creating a pod", () => {
    expect(actions.create({ name: "pod1" })).toEqual({
      type: "pod/create",
      meta: {
        model: "pod",
        method: "create",
      },
      payload: {
        params: { name: "pod1" },
      },
    });
  });

  it("can create an action for getting a pod", () => {
    expect(actions.get(1)).toEqual({
      type: "pod/get",
      meta: {
        model: "pod",
        method: "get",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("can create an action for updating a pod", () => {
    expect(actions.update({ id: 1, name: "pod1", tags: "tag1, tag2" })).toEqual(
      {
        type: "pod/update",
        meta: {
          model: "pod",
          method: "update",
        },
        payload: {
          params: { id: 1, name: "pod1", tags: "tag1, tag2" },
        },
      }
    );
  });

  it("can create an action for deleting a pod", () => {
    expect(actions.delete({ decompose: true, id: 1 })).toEqual({
      type: "pod/delete",
      meta: {
        model: "pod",
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

  it("can create an action for refreshing a pod", () => {
    expect(actions.refresh(1)).toEqual({
      type: "pod/refresh",
      meta: {
        model: "pod",
        method: "refresh",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("can create an action for composing a pod", () => {
    const params = { hostname: "kool koala" };
    expect(actions.compose(params)).toEqual({
      type: "pod/compose",
      meta: {
        model: "pod",
        method: "compose",
      },
      payload: {
        params,
      },
    });
  });

  it("can create an action for setting an active pod", () => {
    expect(actions.setActive(1)).toEqual({
      type: "pod/setActive",
      meta: {
        model: "pod",
        method: "set_active",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("can create an action for pods cleanup", () => {
    expect(actions.cleanup()).toEqual({
      type: "pod/cleanup",
    });
  });

  it("can create an action for clearing projects", () => {
    expect(actions.clearProjects()).toEqual({
      type: "pod/clearProjects",
    });
  });

  it("can create an action for polling a LXD server", () => {
    expect(actions.pollLxdServer({ power_address: "172.0.0.1" })).toEqual({
      type: "pod/pollLxdServer",
      meta: {
        method: "get_projects",
        model: PodMeta.MODEL,
        poll: true,
      },
      payload: {
        params: {
          power_address: "172.0.0.1",
          type: PodType.LXD,
        },
      },
    });
  });
});
