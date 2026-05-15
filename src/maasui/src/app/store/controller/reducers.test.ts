import reducers, { actions } from "./slice";
import { ControllerMeta } from "./types";
import { ImageSyncStatus } from "./types/enum";

import * as factory from "@/testing/factories";

describe("controller reducers", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      active: null,
      errors: null,
      eventErrors: [],
      imageSyncStatuses: {},
      items: [],
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
      selected: [],
      statuses: {},
    });
  });

  it("reduces checkImagesStart", () => {
    expect(
      reducers(
        factory.controllerState({
          statuses: {
            abc123: factory.controllerStatus({ checkingImages: false }),
            def456: factory.controllerStatus({ checkingImages: false }),
          },
        }),
        actions.checkImagesStart([
          { [ControllerMeta.PK]: "abc123" },
          { [ControllerMeta.PK]: "def456" },
        ])
      )
    ).toEqual(
      factory.controllerState({
        statuses: {
          abc123: factory.controllerStatus({ checkingImages: true }),
          def456: factory.controllerStatus({ checkingImages: true }),
        },
      })
    );
  });

  it("reduces checkImagesError", () => {
    const items = [factory.controller({ system_id: "abc123" })];
    expect(
      reducers(
        factory.controllerState({
          errors: "It's realllll bad",
          eventErrors: [],
          items,
          statuses: {
            abc123: factory.controllerStatus({ checkingImages: true }),
            def456: factory.controllerStatus({ checkingImages: true }),
          },
        }),
        actions.checkImagesError(
          [
            { [ControllerMeta.PK]: "abc123" },
            { [ControllerMeta.PK]: "def456" },
          ],
          "It's realllll bad"
        )
      )
    ).toEqual(
      factory.controllerState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.controllerEventError({
            error: "It's realllll bad",
            event: "checkImages",
            id: "abc123",
          }),
          factory.controllerEventError({
            error: "It's realllll bad",
            event: "checkImages",
            id: "def456",
          }),
        ],
        items,
        statuses: {
          abc123: factory.controllerStatus({ checkingImages: false }),
          def456: factory.controllerStatus({ checkingImages: false }),
        },
      })
    );
  });

  it("reduces checkImagesSuccess", () => {
    expect(
      reducers(
        factory.controllerState({
          imageSyncStatuses: factory.controllerImageSyncStatuses({
            abc123: ImageSyncStatus.Synced,
            ghi789: ImageSyncStatus.Synced,
          }),
          statuses: {
            abc123: factory.controllerStatus({ checkingImages: true }),
            def456: factory.controllerStatus({ checkingImages: true }),
          },
        }),
        actions.checkImagesSuccess(
          [
            { [ControllerMeta.PK]: "abc123" },
            { [ControllerMeta.PK]: "def456" },
          ],
          factory.controllerImageSyncStatuses({
            abc123: ImageSyncStatus.OutOfSync,
            def456: ImageSyncStatus.Syncing,
          })
        )
      )
    ).toEqual(
      factory.controllerState({
        imageSyncStatuses: factory.controllerImageSyncStatuses({
          abc123: ImageSyncStatus.OutOfSync,
          def456: ImageSyncStatus.Syncing,
          ghi789: ImageSyncStatus.Synced,
        }),
        statuses: {
          abc123: factory.controllerStatus({ checkingImages: false }),
          def456: factory.controllerStatus({ checkingImages: false }),
        },
      })
    );
  });

  it("reduces pollCheckImagesStart", () => {
    expect(
      reducers(
        factory.controllerState({
          statuses: {
            abc123: factory.controllerStatus({ checkingImages: false }),
            def456: factory.controllerStatus({ checkingImages: false }),
          },
        }),
        actions.pollCheckImagesStart([
          { [ControllerMeta.PK]: "abc123" },
          { [ControllerMeta.PK]: "def456" },
        ])
      )
    ).toEqual(
      factory.controllerState({
        statuses: {
          abc123: factory.controllerStatus({ checkingImages: true }),
          def456: factory.controllerStatus({ checkingImages: true }),
        },
      })
    );
  });

  it("reduces pollCheckImagesError", () => {
    expect(
      reducers(
        factory.controllerState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.controllerStatus({ checkingImages: true }),
            def456: factory.controllerStatus({ checkingImages: true }),
          },
        }),
        actions.pollCheckImagesError(
          [
            { [ControllerMeta.PK]: "abc123" },
            { [ControllerMeta.PK]: "def456" },
          ],
          "It's realllll bad"
        )
      )
    ).toEqual(
      factory.controllerState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.controllerEventError({
            error: "It's realllll bad",
            event: "checkImages",
            id: "abc123",
          }),
          factory.controllerEventError({
            error: "It's realllll bad",
            event: "checkImages",
            id: "def456",
          }),
        ],
        statuses: {
          abc123: factory.controllerStatus({ checkingImages: false }),
          def456: factory.controllerStatus({ checkingImages: false }),
        },
      })
    );
  });

  it("reduces pollCheckImagesSuccess", () => {
    expect(
      reducers(
        factory.controllerState({
          imageSyncStatuses: factory.controllerImageSyncStatuses({
            abc123: ImageSyncStatus.Synced,
            ghi789: ImageSyncStatus.Synced,
          }),
          statuses: {
            abc123: factory.controllerStatus({ checkingImages: true }),
            def456: factory.controllerStatus({ checkingImages: true }),
          },
        }),
        actions.pollCheckImagesSuccess(
          [
            { [ControllerMeta.PK]: "abc123" },
            { [ControllerMeta.PK]: "def456" },
          ],
          factory.controllerImageSyncStatuses({
            abc123: ImageSyncStatus.OutOfSync,
            def456: ImageSyncStatus.Syncing,
          })
        )
      )
    ).toEqual(
      factory.controllerState({
        imageSyncStatuses: factory.controllerImageSyncStatuses({
          abc123: ImageSyncStatus.OutOfSync,
          def456: ImageSyncStatus.Syncing,
          ghi789: ImageSyncStatus.Synced,
        }),
        statuses: {
          abc123: factory.controllerStatus({ checkingImages: false }),
          def456: factory.controllerStatus({ checkingImages: false }),
        },
      })
    );
  });

  it("reduces fetchStart", () => {
    expect(reducers(undefined, actions.fetchStart())).toEqual(
      factory.controllerState({
        loaded: false,
        loading: true,
      })
    );
  });

  it("reduces fetchSuccess", () => {
    const controllers = [factory.controller(), factory.controller()];
    expect(
      reducers(
        factory.controllerState({
          items: [],
          loaded: false,
          loading: true,
        }),
        actions.fetchSuccess(controllers)
      )
    ).toEqual(
      factory.controllerState({
        loading: false,
        loaded: true,
        items: controllers,
        statuses: {
          [controllers[0][ControllerMeta.PK]]: factory.controllerStatus(),
          [controllers[1][ControllerMeta.PK]]: factory.controllerStatus(),
        },
      })
    );
  });

  it("reduces createNotify", () => {
    const initialState = factory.controllerState({
      items: [factory.controller({ system_id: "abc123" })],
      statuses: { abc123: factory.controllerStatus() },
    });
    const newController = factory.controller({ system_id: "def456" });

    expect(reducers(initialState, actions.createNotify(newController))).toEqual(
      factory.controllerState({
        items: [...initialState.items, newController],
        statuses: {
          abc123: factory.controllerStatus(),
          def456: factory.controllerStatus(),
        },
      })
    );
  });

  it("should update if controller exists on createNotify", () => {
    const initialState = factory.controllerState({
      items: [
        factory.controller({ hostname: "controller1", system_id: "abc123" }),
      ],
      statuses: { abc123: factory.controllerStatus() },
    });
    const updatedController = factory.controller({
      hostname: "controller1-newname",
      system_id: "abc123",
    });

    expect(
      reducers(initialState, actions.createNotify(updatedController))
    ).toEqual(
      factory.controllerState({
        items: [updatedController],
        statuses: {
          abc123: factory.controllerStatus(),
        },
      })
    );
  });

  it("reduces updateNotify", () => {
    const initialState = factory.controllerState({
      items: [
        factory.controller({ system_id: "abc123", hostname: "controller1" }),
        factory.controller({ system_id: "def456", hostname: "controller2" }),
      ],
    });
    const updatedController = factory.controller({
      system_id: "abc123",
      hostname: "controller1-new",
    });

    expect(
      reducers(initialState, actions.updateNotify(updatedController))
    ).toEqual(
      factory.controllerState({
        items: [updatedController, initialState.items[1]],
      })
    );
  });

  it("reduces deleteNotify", () => {
    const initialState = factory.controllerState({
      items: [
        factory.controller({ system_id: "abc123" }),
        factory.controller({ system_id: "def456" }),
      ],
      selected: ["abc123"],
      statuses: {
        abc123: factory.controllerStatus(),
        def456: factory.controllerStatus(),
      },
    });

    expect(reducers(initialState, actions.deleteNotify("abc123"))).toEqual(
      factory.controllerState({
        items: [initialState.items[1]],
        selected: [],
        statuses: { def456: factory.controllerStatus() },
      })
    );
  });

  it("reduces getStart", () => {
    const initialState = factory.controllerState({ loading: false });

    expect(reducers(initialState, actions.getStart())).toEqual(
      factory.controllerState({ loading: true })
    );
  });

  it("reduces getError", () => {
    const initialState = factory.controllerState({
      errors: null,
      loading: true,
    });

    expect(
      reducers(
        initialState,
        actions.getError({ system_id: "id was not supplied" })
      )
    ).toEqual(
      factory.controllerState({
        errors: { system_id: "id was not supplied" },
        eventErrors: [
          factory.controllerEventError({
            error: { system_id: "id was not supplied" },
            event: "get",
            id: null,
          }),
        ],
        loading: false,
      })
    );
  });

  it("should update if controller exists on getSuccess", () => {
    const initialState = factory.controllerState({
      items: [
        factory.controller({ system_id: "abc123", hostname: "controller1" }),
      ],
      loading: false,
      statuses: {
        abc123: factory.controllerStatus(),
      },
    });
    const updatedController = factory.controllerDetails({
      system_id: "abc123",
      hostname: "controller1-newname",
    });

    expect(
      reducers(initialState, actions.getSuccess(updatedController))
    ).toEqual(
      factory.controllerState({
        items: [updatedController],
        loading: false,
        statuses: {
          abc123: factory.controllerStatus(),
        },
      })
    );
  });

  it("reduces getSuccess", () => {
    const initialState = factory.controllerState({
      items: [factory.controller({ system_id: "abc123" })],
      loading: true,
      statuses: {
        abc123: factory.controllerStatus(),
      },
    });
    const newController = factory.controllerDetails({ system_id: "def456" });

    expect(reducers(initialState, actions.getSuccess(newController))).toEqual(
      factory.controllerState({
        items: [...initialState.items, newController],
        loading: false,
        statuses: {
          abc123: factory.controllerStatus(),
          def456: factory.controllerStatus(),
        },
      })
    );
  });

  it("reduces setActiveSuccess", () => {
    const initialState = factory.controllerState({ active: null });

    expect(
      reducers(
        initialState,
        actions.setActiveSuccess(
          factory.controllerDetails({ system_id: "abc123" })
        )
      )
    ).toEqual(factory.controllerState({ active: "abc123" }));
  });

  it("reduces setActiveError", () => {
    const initialState = factory.controllerState({
      active: "abc123",
      errors: null,
    });

    expect(
      reducers(
        initialState,
        actions.setActiveError("Controller does not exist")
      )
    ).toEqual(
      factory.controllerState({
        active: null,
        errors: "Controller does not exist",
        eventErrors: [
          factory.controllerEventError({
            error: "Controller does not exist",
            event: "setActive",
            id: null,
          }),
        ],
      })
    );
  });

  it("reduces deleteStart", () => {
    expect(
      reducers(
        factory.controllerState({
          statuses: {
            abc123: factory.controllerStatus({ deleting: false }),
          },
        }),
        actions.deleteStart({
          item: {
            [ControllerMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.controllerState({
        statuses: {
          abc123: factory.controllerStatus({ deleting: true }),
        },
      })
    );
  });

  it("reduces deleteError", () => {
    expect(
      reducers(
        factory.controllerState({
          errors: "It's realllll bad",
          eventErrors: [],
          statuses: {
            abc123: factory.controllerStatus({ deleting: true }),
          },
        }),
        actions.deleteError({
          error: true,
          item: {
            [ControllerMeta.PK]: "abc123",
          },
          payload: "It's realllll bad",
        })
      )
    ).toEqual(
      factory.controllerState({
        errors: "It's realllll bad",
        eventErrors: [
          factory.controllerEventError({
            error: "It's realllll bad",
            event: "delete",
            id: "abc123",
          }),
        ],
        statuses: {
          abc123: factory.controllerStatus({ deleting: false }),
        },
      })
    );
  });

  it("reduces deleteSuccess", () => {
    expect(
      reducers(
        factory.controllerState({
          statuses: {
            abc123: factory.controllerStatus({ deleting: true }),
          },
        }),
        actions.deleteSuccess({
          item: {
            [ControllerMeta.PK]: "abc123",
          },
        })
      )
    ).toEqual(
      factory.controllerState({
        statuses: {
          abc123: factory.controllerStatus({ deleting: false }),
        },
      })
    );
  });
});
