import { NodeType } from "../types/node";

import controller from "./selectors";
import { ImageSyncStatus } from "./types/enum";

import * as factory from "@/testing/factories";

describe("controller selectors", () => {
  it("can get all items", () => {
    const items = [factory.controller(), factory.controller()];
    const state = factory.rootState({
      controller: factory.controllerState({
        items,
      }),
    });
    expect(controller.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      controller: factory.controllerState({
        loading: true,
      }),
    });
    expect(controller.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      controller: factory.controllerState({
        loaded: true,
      }),
    });
    expect(controller.loaded(state)).toEqual(true);
  });

  it("can get a controller by id", () => {
    const items = [
      factory.controller({ system_id: "808" }),
      factory.controller({ system_id: "909" }),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items,
      }),
    });
    expect(controller.getById(state, "909")).toStrictEqual(items[1]);
  });

  it("can get controllers by a list of IDs", () => {
    const controllers = [
      factory.controller({ system_id: "abc123" }),
      factory.controller({ system_id: "def456" }),
      factory.controller({ system_id: "ghi789" }),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items: controllers,
      }),
    });
    expect(controller.getByIDs(state, ["abc123", "ghi789"])).toStrictEqual([
      controllers[0],
      controllers[2],
    ]);
  });

  it("can get the controller statuses", () => {
    const statuses = factory.controllerStatuses();
    const state = factory.rootState({
      controller: factory.controllerState({
        statuses,
      }),
    });
    expect(controller.statuses(state)).toStrictEqual(statuses);
  });

  it("can get the statuses for a controller", () => {
    const controllerStatuses = factory.controllerStatus();
    const state = factory.rootState({
      controller: factory.controllerState({
        statuses: factory.controllerStatuses({
          abc123: controllerStatuses,
        }),
      }),
    });
    expect(controller.getStatuses(state, "abc123")).toStrictEqual(
      controllerStatuses
    );
  });

  it("can get a status for a controller", () => {
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [factory.controller({ system_id: "abc123" })],
        statuses: factory.controllerStatuses({
          abc123: factory.controllerStatus({ importingImages: true }),
        }),
      }),
    });
    expect(
      controller.getStatusForController(state, "abc123", "importingImages")
    ).toBe(true);
  });

  it("can get controllers that are processing", () => {
    const statuses = factory.controllerStatuses({
      abc123: factory.controllerStatus({ testing: true }),
      def456: factory.controllerStatus(),
    });
    const state = factory.rootState({
      controller: factory.controllerState({
        statuses,
      }),
    });
    expect(controller.processing(state)).toStrictEqual(["abc123"]);
  });

  it("can get the image sync state for all controllers", () => {
    const state = factory.rootState({
      controller: factory.controllerState({
        imageSyncStatuses: factory.controllerImageSyncStatuses({
          abc123: ImageSyncStatus.OutOfSync,
          def456: ImageSyncStatus.Syncing,
        }),
      }),
    });
    expect(controller.imageSyncStatuses(state)).toStrictEqual(
      factory.controllerImageSyncStatuses({
        abc123: ImageSyncStatus.OutOfSync,
        def456: ImageSyncStatus.Syncing,
      })
    );
  });

  it("can get the image sync state for a controller", () => {
    const state = factory.rootState({
      controller: factory.controllerState({
        imageSyncStatuses: factory.controllerImageSyncStatuses({
          abc123: ImageSyncStatus.OutOfSync,
          def456: ImageSyncStatus.Syncing,
        }),
      }),
    });
    expect(controller.imageSyncStatusesForController(state, "abc123")).toBe(
      ImageSyncStatus.OutOfSync
    );
  });

  it("can get the services for a controller", () => {
    const services = [factory.service(), factory.service()];
    const state = factory.rootState({
      controller: factory.controllerState({
        items: [
          factory.controller({
            system_id: "abc123",
            service_ids: services.map(({ id }) => id),
          }),
        ],
      }),
      service: factory.serviceState({
        items: services,
      }),
    });
    expect(controller.servicesForController(state, "abc123")).toStrictEqual(
      services
    );
  });

  it("can search tags", () => {
    const items = [factory.controller({ tags: [1] }), factory.controller()];
    const state = factory.rootState({
      controller: factory.controllerState({
        items,
      }),
      tag: factory.tagState({
        items: [factory.tag({ id: 1, name: "echidna" })],
      }),
    });
    expect(controller.search(state, "echidna", [])).toStrictEqual([items[0]]);
  });

  it("can get all region/region-and-rack controllers", () => {
    const items = [
      factory.controller({
        node_type: NodeType.REGION_CONTROLLER,
      }),
      factory.controller({
        node_type: NodeType.REGION_AND_RACK_CONTROLLER,
      }),
      factory.controller({
        node_type: NodeType.RACK_CONTROLLER,
      }),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items,
      }),
    });

    expect(controller.getRegionControllers(state)).toStrictEqual([
      items[0],
      items[1],
    ]);
  });

  it("can separate region controllers by their Vault configuration status", () => {
    const items = [
      factory.controller({
        vault_configured: true,
        node_type: NodeType.REGION_CONTROLLER,
      }),
      factory.controller({
        vault_configured: false,
        node_type: NodeType.REGION_AND_RACK_CONTROLLER,
      }),
      factory.controller({
        node_type: NodeType.RACK_CONTROLLER,
      }),
    ];
    const state = factory.rootState({
      controller: factory.controllerState({
        items,
      }),
    });

    const { unconfiguredControllers, configuredControllers } =
      controller.getVaultConfiguredControllers(state);

    expect(unconfiguredControllers).toStrictEqual([items[1]]);
    expect(configuredControllers).toStrictEqual([items[0]]);
  });
});
