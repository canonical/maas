import vlan from "./selectors";

import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";

describe("vlan selectors", () => {
  it("can get all items", () => {
    const items = [factory.vlan()];
    const state = factory.rootState({
      vlan: factory.vlanState({
        items,
      }),
    });
    expect(vlan.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        loading: true,
      }),
    });
    expect(vlan.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        loaded: true,
      }),
    });
    expect(vlan.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        saving: true,
      }),
    });
    expect(vlan.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        saved: true,
      }),
    });
    expect(vlan.saved(state)).toEqual(true);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        errors: "errors!",
      }),
    });
    expect(vlan.errors(state)).toEqual("errors!");
  });

  it("can get a vlan by id", () => {
    const items = [factory.vlan({ id: 10 }), factory.vlan({ id: 42 })];
    const state = factory.rootState({
      vlan: factory.vlanState({
        items,
      }),
    });
    expect(vlan.getById(state, 42)).toStrictEqual(items[1]);
  });

  it("can get VLANs in a fabric", () => {
    const vlans = [
      factory.vlan({ fabric: 1 }),
      factory.vlan({ fabric: 2 }),
      factory.vlan({ fabric: 1 }),
    ];
    const state = factory.rootState({
      vlan: factory.vlanState({
        items: vlans,
      }),
    });
    expect(vlan.getByFabric(state, 1)).toStrictEqual([vlans[0], vlans[2]]);
  });

  it("can get VLAN with DHCP", () => {
    const vlans = [
      factory.vlan({ dhcp_on: true }),
      factory.vlan({ dhcp_on: false }),
      factory.vlan({ dhcp_on: true }),
    ];
    const state = factory.rootState({
      vlan: factory.vlanState({
        items: vlans,
      }),
    });
    expect(vlan.getWithDHCP(state)).toStrictEqual([vlans[0], vlans[2]]);
  });

  it("can filter vlans by name", () => {
    const items = [
      factory.vlan({ name: "abc" }),
      factory.vlan({ name: "def" }),
    ];
    const state = factory.rootState({
      vlan: factory.vlanState({
        items,
      }),
    });
    expect(vlan.search(state, "d")).toStrictEqual([items[1]]);
  });

  describe("getUnusedForInterface", () => {
    it("does not include the default vlan", () => {
      const fabric = factory.fabric();
      const items = [
        factory.vlan({ fabric: fabric.id, vid: 0 }),
        factory.vlan({ fabric: fabric.id }),
      ];
      const nic = factory.machineInterface({
        vlan_id: items[0].id,
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      const state = factory.rootState({
        fabric: factory.fabricState({
          items: [fabric],
        }),
        machine: factory.machineState({
          items: [machine],
        }),
        vlan: factory.vlanState({
          items,
        }),
      });
      expect(vlan.getUnusedForInterface(state, machine, nic)).toStrictEqual([
        items[1],
      ]);
    });

    it("does not include vlans used by a child", () => {
      const fabric = factory.fabric();
      const items = [
        factory.vlan({ fabric: fabric.id, vid: 0 }),
        factory.vlan({ fabric: fabric.id }),
        factory.vlan({ fabric: fabric.id }),
      ];
      const nic = factory.machineInterface({
        vlan_id: items[0].id,
      });
      const machine = factory.machineDetails({
        interfaces: [
          nic,
          factory.machineInterface({
            type: NetworkInterfaceTypes.VLAN,
            parents: [nic.id],
            vlan_id: items[2].id,
          }),
        ],
      });
      const state = factory.rootState({
        fabric: factory.fabricState({
          items: [fabric],
        }),
        machine: factory.machineState({
          items: [machine],
        }),
        vlan: factory.vlanState({
          items,
        }),
      });
      expect(vlan.getUnusedForInterface(state, machine, nic)).toStrictEqual([
        items[1],
      ]);
    });

    it("does not include vlans on another fabric", () => {
      const fabric = factory.fabric({ id: 1 });
      const items = [
        factory.vlan({ fabric: fabric.id, vid: 0 }),
        factory.vlan({ fabric: 2 }),
      ];
      const nic = factory.machineInterface({
        vlan_id: items[0].id,
      });
      const machine = factory.machineDetails({
        interfaces: [nic],
      });
      const state = factory.rootState({
        fabric: factory.fabricState({
          items: [fabric],
        }),
        machine: factory.machineState({
          items: [machine],
        }),
        vlan: factory.vlanState({
          items,
        }),
      });
      expect(vlan.getUnusedForInterface(state, machine, nic)).toStrictEqual([]);
    });
  });

  it("can get the active vlan's id", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        active: 0,
      }),
    });
    expect(vlan.activeID(state)).toEqual(0);
  });

  it("can get the active vlan", () => {
    const activeFabric = factory.vlan();
    const state = factory.rootState({
      vlan: factory.vlanState({
        active: activeFabric.id,
        items: [activeFabric],
      }),
    });
    expect(vlan.active(state)).toEqual(activeFabric);
  });

  it("can get a status for a vlan", () => {
    const state = factory.rootState({
      vlan: factory.vlanState({
        items: [factory.vlan({ id: 0 })],
        statuses: factory.vlanStatuses({
          0: factory.vlanStatus({ configuringDHCP: true }),
        }),
      }),
    });
    expect(vlan.getStatusForVLAN(state, 0, "configuringDHCP")).toBe(true);
  });

  it("can get event errors for a vlan", () => {
    const vlanEventErrors = [
      factory.vlanEventError({ id: 123 }),
      factory.vlanEventError(),
    ];
    const state = factory.rootState({
      vlan: factory.vlanState({
        eventErrors: vlanEventErrors,
      }),
    });
    expect(vlan.eventErrorsForVLANs(state, 123)).toStrictEqual([
      vlanEventErrors[0],
    ]);
  });

  it("can get event errors for a vlan and a provided event", () => {
    const vlanEventErrors = [
      factory.vlanEventError({ id: 123, event: "configureDHCP" }),
      factory.vlanEventError({ id: 123, event: "something-else" }),
    ];
    const state = factory.rootState({
      vlan: factory.vlanState({
        eventErrors: vlanEventErrors,
      }),
    });
    expect(vlan.eventErrorsForVLANs(state, 123, "configureDHCP")).toStrictEqual(
      [vlanEventErrors[0]]
    );
  });
});
