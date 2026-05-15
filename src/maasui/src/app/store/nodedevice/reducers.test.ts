import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("node device reducer", () => {
  it("returns the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      errors: null,
      items: [],
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
    });
  });

  it("reduces getByNodeIdStart", () => {
    const state = factory.nodeDeviceState({
      loading: false,
    });

    expect(reducers(state, actions.getByNodeIdStart(null))).toEqual(
      factory.nodeDeviceState({ loading: true })
    );
  });

  it("reduces getByNodeIdSuccess", () => {
    const existingNodeDevice = factory.nodeDevice();
    const newNodeDevice = factory.nodeDevice();
    const newNodeDevice2 = factory.nodeDevice();

    const nodeDeviceState = factory.nodeDeviceState({
      items: [existingNodeDevice],
      loading: true,
    });

    expect(
      reducers(
        nodeDeviceState,
        actions.getByNodeIdSuccess("abc123", [newNodeDevice, newNodeDevice2])
      )
    ).toEqual(
      factory.nodeDeviceState({
        items: [existingNodeDevice, newNodeDevice, newNodeDevice2],
        loading: false,
        loaded: true,
      })
    );
  });

  it("reduces getByNodeIdError", () => {
    const nodeDeviceState = factory.nodeDeviceState({ loading: true });

    expect(
      reducers(
        nodeDeviceState,
        actions.getByNodeIdError("Could not get node device")
      )
    ).toEqual(
      factory.nodeDeviceState({
        errors: "Could not get node device",
        loading: false,
      })
    );
  });
});
