import subnet from "./selectors";

import * as factory from "@/testing/factories";

describe("subnet selectors", () => {
  it("can get all items", () => {
    const items = [factory.subnet(), factory.subnet()];
    const state = factory.rootState({
      subnet: factory.subnetState({
        items,
      }),
    });
    expect(subnet.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      subnet: factory.subnetState({
        loading: true,
      }),
    });
    expect(subnet.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      subnet: factory.subnetState({
        loaded: true,
      }),
    });
    expect(subnet.loaded(state)).toEqual(true);
  });

  it("can get a subnet by id", () => {
    const items = [factory.subnet({ id: 808 }), factory.subnet({ id: 909 })];
    const state = factory.rootState({
      subnet: factory.subnetState({
        items,
      }),
    });
    expect(subnet.getById(state, 909)).toStrictEqual(items[1]);
  });

  it("can get multiple subnets by id", () => {
    const items = [
      factory.subnet({ id: 707 }),
      factory.subnet({ id: 808 }),
      factory.subnet({ id: 909 }),
    ];
    const state = factory.rootState({
      subnet: factory.subnetState({
        items,
      }),
    });
    expect(subnet.getByIds(state, [707, 909])).toStrictEqual([
      items[0],
      items[2],
    ]);
  });

  it("can get a subnet by cidr", () => {
    const items = [
      factory.subnet({ cidr: "cidr0" }),
      factory.subnet({ cidr: "cidr1" }),
    ];
    const state = factory.rootState({
      subnet: factory.subnetState({
        items,
      }),
    });
    expect(subnet.getByCIDR(state, "cidr1")).toStrictEqual(items[1]);
  });

  it("can get subnets that are available to a given pod", () => {
    const subnets = [
      factory.subnet({ vlan: 1 }),
      factory.subnet({ vlan: 2 }),
      factory.subnet({ vlan: 3 }),
    ];
    const pod = factory.podDetails({ attached_vlans: [1, 2] });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: subnets,
      }),
    });
    expect(subnet.getByPod(state, pod)).toStrictEqual([subnets[0], subnets[1]]);
  });

  it("can get subnets for a VLAN", () => {
    const subnets = [
      factory.subnet({ vlan: 1 }),
      factory.subnet({ vlan: 2 }),
      factory.subnet({ vlan: 1 }),
    ];
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: subnets,
      }),
    });
    expect(subnet.getByVLAN(state, 1)).toStrictEqual([subnets[0], subnets[2]]);
  });

  it("can get subnets for a fabric", () => {
    const subnets = [
      factory.subnet({ vlan: 1 }),
      factory.subnet({ vlan: 2 }),
      factory.subnet({ vlan: 3 }),
    ];
    const fabric = factory.fabric({ id: 101, vlan_ids: [1, 3] });
    const state = factory.rootState({
      fabric: factory.fabricState({ items: [fabric] }),
      subnet: factory.subnetState({
        items: subnets,
      }),
    });
    expect(subnet.getByFabric(state, 101)).toStrictEqual([
      subnets[0],
      subnets[2],
    ]);
  });

  it("can get PXE-enabled subnets that are available to a given pod", () => {
    const subnets = [
      factory.subnet({ vlan: 1 }),
      factory.subnet({ vlan: 2 }),
      factory.subnet({ vlan: 3 }),
    ];
    const pod = factory.podDetails({ boot_vlans: [1, 2] });
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: subnets,
      }),
    });
    expect(subnet.getPxeEnabledByPod(state, pod)).toStrictEqual([
      subnets[0],
      subnets[1],
    ]);
  });

  it("can get the active subnet's id", () => {
    const state = factory.rootState({
      subnet: factory.subnetState({
        active: 0,
      }),
    });
    expect(subnet.activeID(state)).toEqual(0);
  });

  it("can get the active subnet", () => {
    const activeFabric = factory.subnet();
    const state = factory.rootState({
      subnet: factory.subnetState({
        active: activeFabric.id,
        items: [activeFabric],
      }),
    });
    expect(subnet.active(state)).toEqual(activeFabric);
  });

  it("can get a status for a subnet", () => {
    const state = factory.rootState({
      subnet: factory.subnetState({
        items: [factory.subnet({ id: 0 })],
        statuses: factory.subnetStatuses({
          0: factory.subnetStatus({ scanning: true }),
        }),
      }),
    });
    expect(subnet.getStatusForSubnet(state, 0, "scanning")).toBe(true);
  });

  it("can get event errors for a subnet", () => {
    const subnetEventErrors = [
      factory.subnetEventError({ id: 123 }),
      factory.subnetEventError(),
    ];
    const state = factory.rootState({
      subnet: factory.subnetState({
        eventErrors: subnetEventErrors,
      }),
    });
    expect(subnet.eventErrorsForSubnets(state, 123)).toStrictEqual([
      subnetEventErrors[0],
    ]);
  });

  it("can get event errors for a subnet and a provided event", () => {
    const subnetEventErrors = [
      factory.subnetEventError({ id: 123, event: "scan" }),
      factory.subnetEventError({ id: 123, event: "something-else" }),
    ];
    const state = factory.rootState({
      subnet: factory.subnetState({
        eventErrors: subnetEventErrors,
      }),
    });
    expect(subnet.eventErrorsForSubnets(state, 123, "scan")).toStrictEqual([
      subnetEventErrors[0],
    ]);
  });
});
