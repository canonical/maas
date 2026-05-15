import ipRange from "./selectors";

import * as factory from "@/testing/factories";

describe("all", () => {
  it("returns list of all IP ranges", () => {
    const items = [factory.ipRange(), factory.ipRange()];
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        items,
      }),
    });
    expect(ipRange.all(state)).toStrictEqual(items);
  });
});

describe("loading", () => {
  it("returns iprange loading state", () => {
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        loading: false,
      }),
    });
    expect(ipRange.loading(state)).toStrictEqual(false);
  });
});

describe("loaded", () => {
  it("returns iprange loaded state", () => {
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        loaded: true,
      }),
    });
    expect(ipRange.loaded(state)).toStrictEqual(true);
  });
});

describe("errors", () => {
  it("returns iprange error state", () => {
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        errors: "Unable to list IP ranges.",
      }),
    });
    expect(ipRange.errors(state)).toEqual("Unable to list IP ranges.");
  });
});

describe("saving", () => {
  it("returns iprange saving state", () => {
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        saving: true,
      }),
    });
    expect(ipRange.saving(state)).toStrictEqual(true);
  });
});

describe("saved", () => {
  it("returns iprange saved state", () => {
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        saved: true,
      }),
    });
    expect(ipRange.saved(state)).toStrictEqual(true);
  });
});

describe("getBySubnet", () => {
  it("returns IP ranges that are in a subnet", () => {
    const subnet = factory.subnet();
    const subnet2 = factory.subnet();
    const items = [
      factory.ipRange({ subnet: subnet.id }),
      factory.ipRange({ subnet: subnet.id }),
      factory.ipRange({ subnet: subnet2.id }),
    ];
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        items,
      }),
      subnet: factory.subnetState({
        items: [subnet, subnet2],
      }),
    });
    expect(ipRange.getBySubnet(state, subnet.id)).toStrictEqual([
      items[0],
      items[1],
    ]);
  });

  it("handles a null subnet", () => {
    const state = factory.rootState();
    expect(ipRange.getBySubnet(state, null)).toStrictEqual([]);
  });
});

describe("getByVLAN", () => {
  it("returns IP ranges that are in a VLAN", () => {
    const vlan = factory.vlan();
    const vlan2 = factory.vlan();
    const items = [
      factory.ipRange({ vlan: vlan.id }),
      factory.ipRange({ vlan: vlan.id }),
      factory.ipRange({ vlan: vlan2.id }),
    ];
    const state = factory.rootState({
      iprange: factory.ipRangeState({
        items,
      }),
      vlan: factory.vlanState({
        items: [vlan, vlan2],
      }),
    });
    expect(ipRange.getByVLAN(state, vlan.id)).toStrictEqual([
      items[0],
      items[1],
    ]);
  });

  it("handles a null VLAN", () => {
    const state = factory.rootState();
    expect(ipRange.getByVLAN(state, null)).toStrictEqual([]);
  });
});
