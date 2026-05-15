import { vlanActions } from "./";

describe("vlan actions", () => {
  it("returns an action for fetching vlans", () => {
    expect(vlanActions.fetch()).toEqual({
      type: "vlan/fetch",
      meta: {
        model: "vlan",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns an action for creating vlans", () => {
    expect(
      vlanActions.create({ name: "vlan1", description: "a vlan", vid: 99 })
    ).toEqual({
      type: "vlan/create",
      meta: {
        model: "vlan",
        method: "create",
      },
      payload: {
        params: {
          name: "vlan1",
          description: "a vlan",
          vid: 99,
        },
      },
    });
  });

  it("returns an action for updating vlans", () => {
    expect(
      vlanActions.update({
        id: 1,
        name: "vlan1",
        description: "a vlan",
        vid: 99,
      })
    ).toEqual({
      type: "vlan/update",
      meta: {
        model: "vlan",
        method: "update",
      },
      payload: {
        params: {
          id: 1,
          name: "vlan1",
          description: "a vlan",
          vid: 99,
        },
      },
    });
  });

  it("returns an action for deleting vlans", () => {
    expect(vlanActions.delete(1)).toEqual({
      type: "vlan/delete",
      meta: {
        model: "vlan",
        method: "delete",
      },
      payload: {
        params: {
          id: 1,
        },
      },
    });
  });

  it("returns an action for cleaning vlans", () => {
    expect(vlanActions.cleanup()).toEqual({
      type: "vlan/cleanup",
    });
  });

  it("can create an action to get a vlan", () => {
    expect(vlanActions.get(0)).toEqual({
      type: "vlan/get",
      meta: {
        model: "vlan",
        method: "get",
      },
      payload: {
        params: { id: 0 },
      },
    });
  });

  it("can create an action to set an active vlan", () => {
    expect(vlanActions.setActive(0)).toEqual({
      type: "vlan/setActive",
      meta: {
        model: "vlan",
        method: "set_active",
      },
      payload: {
        params: { id: 0 },
      },
    });
  });

  it("can create an action for configuring DHCP", () => {
    expect(
      vlanActions.configureDHCP({
        id: 0,
        controllers: ["abc123"],
        extra: {
          end: "192.168.1.2",
          gateway: "172.0.0.1",
          start: "192.168.1.1",
          subnet: 0,
        },
        relay_vlan: 1,
      })
    ).toEqual({
      type: "vlan/configureDHCP",
      meta: {
        model: "vlan",
        method: "configure_dhcp",
      },
      payload: {
        params: {
          id: 0,
          controllers: ["abc123"],
          extra: {
            end: "192.168.1.2",
            gateway: "172.0.0.1",
            start: "192.168.1.1",
            subnet: 0,
          },
          relay_vlan: 1,
        },
      },
    });
  });
});
