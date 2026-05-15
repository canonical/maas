import selectors from "./selectors";

import * as factory from "@/testing/factories";

describe("nodeDevice selectors", () => {
  it("can get all items", () => {
    const items = [factory.nodeDevice(), factory.nodeDevice()];
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        items,
      }),
    });
    expect(selectors.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        loading: true,
      }),
    });
    expect(selectors.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        loaded: true,
      }),
    });
    expect(selectors.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        saving: true,
      }),
    });
    expect(selectors.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        saved: true,
      }),
    });
    expect(selectors.saved(state)).toEqual(true);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        errors: "it's all ruined",
      }),
    });
    expect(selectors.errors(state)).toEqual("it's all ruined");
  });

  it("can get a node device by its id", () => {
    const [thisNodeDevice, otherNodeDevice] = [
      factory.nodeDevice(),
      factory.nodeDevice(),
    ];
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        items: [thisNodeDevice, otherNodeDevice],
      }),
    });
    expect(selectors.getById(state, thisNodeDevice.id)).toStrictEqual(
      thisNodeDevice
    );
  });

  it("can get node devices for a machine", () => {
    const machine = factory.machine();
    const machineNodeDevices = [
      factory.nodeDevice({ node_id: machine.id }),
      factory.nodeDevice({ node_id: machine.id }),
    ];
    const items = [...machineNodeDevices, factory.nodeDevice()];
    const state = factory.rootState({
      nodedevice: factory.nodeDeviceState({
        items,
      }),
    });
    expect(selectors.getByNodeId(state, machine.id)).toStrictEqual(
      machineNodeDevices
    );
  });
});
