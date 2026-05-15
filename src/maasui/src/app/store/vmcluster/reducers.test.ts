import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("vmCluster reducers", () => {
  it("returns the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      errors: null,
      eventErrors: [],
      items: [],
      loaded: false,
      loading: false,
      physicalClusters: [],
      saved: false,
      saving: false,
      statuses: {
        deleting: false,
        getting: false,
      },
    });
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      expect(
        reducers(
          factory.vmClusterState({
            loading: false,
          }),
          actions.fetchStart()
        )
      ).toEqual(
        factory.vmClusterState({
          loading: true,
        })
      );
    });

    it("reduces fetchSuccess", () => {
      const items = [factory.vmCluster()];
      expect(
        reducers(
          factory.vmClusterState({
            loaded: false,
            loading: true,
          }),
          actions.fetchSuccess([items])
        )
      ).toEqual(
        factory.vmClusterState({
          items,
          loading: false,
          loaded: true,
          physicalClusters: [[items[0].id]],
          statuses: factory.vmClusterStatuses({
            getting: false,
          }),
        })
      );
    });

    it("reduces fetchError", () => {
      expect(
        reducers(
          factory.vmClusterState({
            loading: true,
          }),
          actions.fetchError("Could not fetch")
        )
      ).toEqual(
        factory.vmClusterState({
          eventErrors: [
            factory.vmClusterEventError({
              error: "Could not fetch",
              event: "fetch",
            }),
          ],
          errors: "Could not fetch",
          loading: false,
        })
      );
    });
  });

  describe("get", () => {
    it("reduces getStart", () => {
      expect(
        reducers(
          factory.vmClusterState({
            statuses: factory.vmClusterStatuses({
              getting: false,
            }),
          }),
          actions.getStart()
        )
      ).toEqual(
        factory.vmClusterState({
          statuses: factory.vmClusterStatuses({
            getting: true,
          }),
        })
      );
    });

    it("reduces getSuccess", () => {
      const cluster = factory.vmCluster();
      expect(
        reducers(
          factory.vmClusterState({
            items: [],
            statuses: factory.vmClusterStatuses({
              getting: true,
            }),
          }),
          actions.getSuccess(cluster)
        )
      ).toEqual(
        factory.vmClusterState({
          items: [cluster],
          statuses: factory.vmClusterStatuses({
            getting: false,
          }),
        })
      );
    });

    it("reduces getError", () => {
      expect(
        reducers(
          factory.vmClusterState({
            statuses: factory.vmClusterStatuses({
              getting: true,
            }),
          }),
          actions.getError("Could not get")
        )
      ).toEqual(
        factory.vmClusterState({
          eventErrors: [
            factory.vmClusterEventError({
              error: "Could not get",
              event: "get",
            }),
          ],
          errors: "Could not get",
          statuses: factory.vmClusterStatuses({
            getting: false,
          }),
        })
      );
    });
  });

  it("reduces deleteStart", () => {
    const vmclusters = [factory.vmCluster({ id: 1 })];
    const state = factory.vmClusterState({
      items: vmclusters,
      statuses: factory.vmClusterStatuses({ deleting: false }),
    });

    expect(reducers(state, actions.deleteStart())).toEqual(
      factory.vmClusterState({
        items: vmclusters,
        statuses: factory.vmClusterStatuses({ deleting: true }),
      })
    );
  });

  it("reduces deleteSuccess", () => {
    const vmclusters = [factory.vmCluster({ id: 1 })];
    const state = factory.vmClusterState({
      items: vmclusters,
      statuses: factory.vmClusterStatuses({ deleting: true }),
    });

    expect(reducers(state, actions.deleteSuccess())).toEqual(
      factory.vmClusterState({
        items: vmclusters,
        statuses: factory.vmClusterStatuses({ deleting: false }),
      })
    );
  });

  it("reduces deleteError", () => {
    const vmclusters = [factory.vmCluster({ id: 1 })];
    const state = factory.vmClusterState({
      errors: null,
      items: vmclusters,
      statuses: factory.vmClusterStatuses({ deleting: true }),
    });

    expect(
      reducers(state, actions.deleteError("VMCluster cannot be deleted"))
    ).toEqual(
      factory.vmClusterState({
        errors: "VMCluster cannot be deleted",
        eventErrors: [
          factory.vmClusterEventError({
            error: "VMCluster cannot be deleted",
            event: "delete",
          }),
        ],
        items: vmclusters,
        statuses: factory.vmClusterStatuses({ deleting: false }),
      })
    );
  });

  it("reduces deleteNotify", () => {
    const vmclusters = [
      factory.vmCluster({ id: 1 }),
      factory.vmCluster({ id: 2 }),
    ];
    const state = factory.vmClusterState({
      items: vmclusters,
    });

    expect(reducers(state, actions.deleteNotify(1))).toEqual(
      factory.vmClusterState({
        items: [vmclusters[1]],
      })
    );
  });
});
