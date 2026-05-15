import { actions } from "./slice";
import { IPRangeType } from "./types";

it("can create an action for fetching IP ranges", () => {
  expect(actions.fetch()).toEqual({
    type: "iprange/fetch",
    meta: {
      model: "iprange",
      method: "list",
    },
    payload: null,
  });
});

it("can create an action for creating an IP range", () => {
  const params = {
    comment: "It's an IP range",
    end_ip: "1.1.1.1",
    start_ip: "1.1.1.99",
    type: IPRangeType.Dynamic,
  };
  expect(actions.create(params)).toEqual({
    type: "iprange/create",
    meta: {
      model: "iprange",
      method: "create",
    },
    payload: {
      params,
    },
  });
});

it("can create an action for deleting an IP range", () => {
  expect(actions.delete(1)).toEqual({
    type: "iprange/delete",
    meta: {
      model: "iprange",
      method: "delete",
    },
    payload: {
      params: {
        id: 1,
      },
    },
  });
});

it("can create an action for updating an IP range", () => {
  const params = {
    comment: "It's an IP range",
    end_ip: "1.1.1.1",
    id: 1,
    start_ip: "1.1.1.99",
    type: IPRangeType.Dynamic,
  };
  expect(actions.update(params)).toEqual({
    type: "iprange/update",
    meta: {
      model: "iprange",
      method: "update",
    },
    payload: {
      params,
    },
  });
});

it("can clean up", () => {
  expect(actions.cleanup()).toEqual({
    type: "iprange/cleanup",
  });
});

it("can create an action for getting an iprange", () => {
  expect(actions.get(1)).toEqual({
    type: "iprange/get",
    meta: {
      model: "iprange",
      method: "get",
    },
    payload: {
      params: {
        id: 1,
      },
    },
  });
});
