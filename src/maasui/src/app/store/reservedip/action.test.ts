import { actions } from "./slice";

it("can create an action for fetching reserved IPs", () => {
  expect(actions.fetch()).toEqual({
    type: "reservedip/fetch",
    meta: {
      model: "reservedip",
      method: "list",
    },
    payload: null,
  });
});

it("can create an action for creating a reserved IP", () => {
  const params = {
    comment: "It's an IP address",
    ip: "192.168.0.2",
    mac_address: "00:00:00:00:00:00",
    subnet: 1,
  };

  expect(actions.create(params)).toEqual({
    type: "reservedip/create",
    meta: {
      model: "reservedip",
      method: "create",
    },
    payload: {
      params,
    },
  });
});

it("can create an action for deleting a reserved IP", () => {
  expect(actions.delete({ id: 1, ip: "10.0.0.2" })).toEqual({
    type: "reservedip/delete",
    meta: {
      model: "reservedip",
      method: "delete",
    },
    payload: {
      params: {
        id: 1,
        ip: "10.0.0.2",
      },
    },
  });
});

it("can create an action for updating a reserved IP", () => {
  const params = {
    id: 1,
    comment: "It's an IP address",
    ip: "192.168.0.2",
    mac_address: "00:00:00:00:00:00",
    subnet: 1,
  };

  expect(actions.update(params)).toEqual({
    type: "reservedip/update",
    meta: {
      model: "reservedip",
      method: "update",
    },
    payload: {
      params,
    },
  });
});

it("can clean up", () => {
  expect(actions.cleanup()).toEqual({
    type: "reservedip/cleanup",
  });
});

it("can create an action for getting a reserved IP", () => {
  expect(actions.get(1)).toEqual({
    type: "reservedip/get",
    meta: {
      model: "reservedip",
      method: "get",
    },
    payload: {
      params: {
        id: 1,
      },
    },
  });
});
