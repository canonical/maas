import reducers, { actions } from "./slice";
import { DeviceMeta } from "./types";

import * as factory from "@/testing/factories";

describe("device reducers", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      active: null,
      errors: null,
      eventErrors: [],
      items: [],
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
      selected: [],
      statuses: {},
    });
  });

  it("reduces fetchStart", () => {
    expect(reducers(undefined, actions.fetchStart())).toEqual(
      factory.deviceState({
        loaded: false,
        loading: true,
      })
    );
  });

  it("reduces fetchSuccess", () => {
    const devices = [factory.device(), factory.device()];
    expect(
      reducers(
        factory.deviceState({
          items: [],
          loaded: false,
          loading: true,
        }),
        actions.fetchSuccess(devices)
      )
    ).toEqual(
      factory.deviceState({
        loading: false,
        loaded: true,
        items: devices,
        statuses: {
          [devices[0][DeviceMeta.PK]]: factory.deviceStatus(),
          [devices[1][DeviceMeta.PK]]: factory.deviceStatus(),
        },
      })
    );
  });

  it("reduces createNotify", () => {
    const initialState = factory.deviceState({
      items: [factory.device({ system_id: "abc123" })],
      statuses: { abc123: factory.deviceStatus() },
    });
    const newDevice = factory.device({ system_id: "def456" });

    expect(reducers(initialState, actions.createNotify(newDevice))).toEqual(
      factory.deviceState({
        items: [...initialState.items, newDevice],
        statuses: {
          abc123: factory.deviceStatus(),
          def456: factory.deviceStatus(),
        },
      })
    );
  });

  it("should update if device exists on createNotify", () => {
    const initialState = factory.deviceState({
      items: [factory.device({ hostname: "device1", system_id: "abc123" })],
      statuses: { abc123: factory.deviceStatus() },
    });
    const updatedDevice = factory.device({
      hostname: "device1-newname",
      system_id: "abc123",
    });

    expect(reducers(initialState, actions.createNotify(updatedDevice))).toEqual(
      factory.deviceState({
        items: [updatedDevice],
        statuses: {
          abc123: factory.deviceStatus(),
        },
      })
    );
  });

  it("reduces updateNotify", () => {
    const initialState = factory.deviceState({
      items: [
        factory.device({ system_id: "abc123", hostname: "device1" }),
        factory.device({ system_id: "def456", hostname: "device2" }),
      ],
    });
    const updatedDevice = factory.device({
      system_id: "abc123",
      hostname: "device1-new",
    });

    expect(reducers(initialState, actions.updateNotify(updatedDevice))).toEqual(
      factory.deviceState({
        items: [updatedDevice, initialState.items[1]],
      })
    );
  });

  it("reduces deleteNotify", () => {
    const initialState = factory.deviceState({
      items: [
        factory.device({ system_id: "abc123" }),
        factory.device({ system_id: "def456" }),
      ],
      selected: ["abc123"],
      statuses: {
        abc123: factory.deviceStatus(),
        def456: factory.deviceStatus(),
      },
    });

    expect(reducers(initialState, actions.deleteNotify("abc123"))).toEqual(
      factory.deviceState({
        items: [initialState.items[1]],
        selected: [],
        statuses: { def456: factory.deviceStatus() },
      })
    );
  });

  it("reduces createInterfaceStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ creatingInterface: false }),
          },
        }),
        actions.createInterfaceStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ creatingInterface: true }),
        },
      })
    );
  });

  it("reduces createInterfaceError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ creatingInterface: true }),
          },
        }),
        actions.createInterfaceError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "createInterface",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ creatingInterface: false }),
        },
      })
    );
  });

  it("reduces createInterfaceSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ creatingInterface: true }),
          },
        }),
        actions.createInterfaceSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ creatingInterface: false }),
        },
      })
    );
  });

  it("reduces createPhysicalStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ creatingPhysical: false }),
          },
        }),
        actions.createPhysicalStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ creatingPhysical: true }),
        },
      })
    );
  });

  it("reduces createPhysicalError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ creatingPhysical: true }),
          },
        }),
        actions.createPhysicalError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "createPhysical",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ creatingPhysical: false }),
        },
      })
    );
  });

  it("reduces createPhysicalSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ creatingPhysical: true }),
          },
        }),
        actions.createPhysicalSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ creatingPhysical: false }),
        },
      })
    );
  });

  it("reduces getStart", () => {
    const initialState = factory.deviceState({ loading: false });

    expect(reducers(initialState, actions.getStart())).toEqual(
      factory.deviceState({ loading: true })
    );
  });

  it("reduces getError", () => {
    const initialState = factory.deviceState({ errors: null, loading: true });

    expect(
      reducers(
        initialState,
        actions.getError({ system_id: "id was not supplied" })
      )
    ).toEqual(
      factory.deviceState({
        errors: { system_id: "id was not supplied" },
        eventErrors: [
          factory.deviceEventError({
            error: { system_id: "id was not supplied" },
            event: "get",
            id: null,
          }),
        ],
        loading: false,
      })
    );
  });

  it("should update if device exists on getSuccess", () => {
    const initialState = factory.deviceState({
      items: [factory.device({ system_id: "abc123", hostname: "device1" })],
      loading: false,
      statuses: {
        abc123: factory.deviceStatus(),
      },
    });
    const updatedDevice = factory.deviceDetails({
      system_id: "abc123",
      hostname: "device1-newname",
    });

    expect(reducers(initialState, actions.getSuccess(updatedDevice))).toEqual(
      factory.deviceState({
        items: [updatedDevice],
        loading: false,
        statuses: {
          abc123: factory.deviceStatus(),
        },
      })
    );
  });

  it("reduces getSuccess", () => {
    const initialState = factory.deviceState({
      items: [factory.device({ system_id: "abc123" })],
      loading: true,
      statuses: {
        abc123: factory.deviceStatus(),
      },
    });
    const newDevice = factory.deviceDetails({ system_id: "def456" });

    expect(reducers(initialState, actions.getSuccess(newDevice))).toEqual(
      factory.deviceState({
        items: [...initialState.items, newDevice],
        loading: false,
        statuses: {
          abc123: factory.deviceStatus(),
          def456: factory.deviceStatus(),
        },
      })
    );
  });

  it("reduces setActiveSuccess", () => {
    const initialState = factory.deviceState({ active: null });

    expect(
      reducers(
        initialState,
        actions.setActiveSuccess(factory.deviceDetails({ system_id: "abc123" }))
      )
    ).toEqual(factory.deviceState({ active: "abc123" }));
  });

  it("reduces setActiveError", () => {
    const initialState = factory.deviceState({
      active: "abc123",
      errors: null,
    });

    expect(
      reducers(initialState, actions.setActiveError("Device does not exist"))
    ).toEqual(
      factory.deviceState({
        active: null,
        errors: "Device does not exist",
        eventErrors: [
          factory.deviceEventError({
            error: "Device does not exist",
            event: "setActive",
            id: null,
          }),
        ],
      })
    );
  });

  it("reduces updateInterfaceStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ updatingInterface: false }),
          },
        }),
        actions.updateInterfaceStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ updatingInterface: true }),
        },
      })
    );
  });

  it("reduces updateInterfaceError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ updatingInterface: true }),
          },
        }),
        actions.updateInterfaceError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "updateInterface",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ updatingInterface: false }),
        },
      })
    );
  });

  it("reduces updateInterfaceSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ updatingInterface: true }),
          },
        }),
        actions.updateInterfaceSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ updatingInterface: false }),
        },
      })
    );
  });

  it("reduces deleteStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ deleting: false }),
          },
        }),
        actions.deleteStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ deleting: true }),
        },
      })
    );
  });

  it("reduces deleteError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ deleting: true }),
          },
        }),
        actions.deleteError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "delete",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ deleting: false }),
        },
      })
    );
  });

  it("reduces deleteSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ deleting: true }),
          },
        }),
        actions.deleteSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ deleting: false }),
        },
      })
    );
  });

  it("reduces setZoneStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ settingZone: false }),
          },
        }),
        actions.setZoneStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ settingZone: true }),
        },
      })
    );
  });

  it("reduces setZoneError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ settingZone: true }),
          },
        }),
        actions.setZoneError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "setZone",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ settingZone: false }),
        },
      })
    );
  });

  it("reduces setZoneSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ settingZone: true }),
          },
        }),
        actions.setZoneSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ settingZone: false }),
        },
      })
    );
  });

  it("reduces linkSubnetStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ linkingSubnet: false }),
          },
        }),
        actions.linkSubnetStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ linkingSubnet: true }),
        },
      })
    );
  });

  it("reduces linkSubnetError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ linkingSubnet: true }),
          },
        }),
        actions.linkSubnetError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "linkSubnet",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ linkingSubnet: false }),
        },
      })
    );
  });

  it("reduces linkSubnetSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ linkingSubnet: true }),
          },
        }),
        actions.linkSubnetSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ linkingSubnet: false }),
        },
      })
    );
  });

  it("reduces unlinkSubnetStart", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ unlinkingSubnet: false }),
          },
        }),
        actions.unlinkSubnetStart({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ unlinkingSubnet: true }),
        },
      })
    );
  });

  it("reduces unlinkSubnetError", () => {
    expect(
      reducers(
        factory.deviceState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.deviceStatus({ unlinkingSubnet: true }),
          },
        }),
        actions.unlinkSubnetError({
          error: true,
          item: {
            [DeviceMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.deviceState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.deviceEventError({
            error: "It's realllll bad",
            event: "unlinkSubnet",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.deviceStatus({ unlinkingSubnet: false }),
        },
      })
    );
  });

  it("reduces unlinkSubnetSuccess", () => {
    expect(
      reducers(
        factory.deviceState({
          statuses: {
            abc123: factory.deviceStatus({ unlinkingSubnet: true }),
          },
        }),
        actions.unlinkSubnetSuccess({
          item: {
            [DeviceMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.deviceState({
        statuses: {
          abc123: factory.deviceStatus({ unlinkingSubnet: false }),
        },
      })
    );
  });
});
