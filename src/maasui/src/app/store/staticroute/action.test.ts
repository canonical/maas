import { actions } from "./slice";

it("can create an action for fetching static routes", () => {
  expect(actions.fetch()).toEqual({
    type: "staticroute/fetch",
    meta: {
      model: "staticroute",
      method: "list",
    },
    payload: null,
  });
});

it("can create an action for creating a static route", () => {
  expect(
    actions.create({
      destination: 123,
      gateway_ip: "192.168.1.1",
      metric: 0,
      source: 456,
    })
  ).toEqual({
    type: "staticroute/create",
    meta: {
      model: "staticroute",
      method: "create",
    },
    payload: {
      params: {
        destination: 123,
        gateway_ip: "192.168.1.1",
        metric: 0,
        source: 456,
      },
    },
  });
});

it("can create an action for deleting a static route", () => {
  expect(actions.delete(1)).toEqual({
    type: "staticroute/delete",
    meta: {
      model: "staticroute",
      method: "delete",
    },
    payload: {
      params: {
        id: 1,
      },
    },
  });
});

it("can create an action for updating a static route", () => {
  expect(actions.update({ id: 1, source: 456 })).toEqual({
    type: "staticroute/update",
    meta: {
      model: "staticroute",
      method: "update",
    },
    payload: {
      params: {
        id: 1,
        source: 456,
      },
    },
  });
});

it("can clean up", () => {
  expect(actions.cleanup()).toEqual({
    type: "staticroute/cleanup",
  });
});
