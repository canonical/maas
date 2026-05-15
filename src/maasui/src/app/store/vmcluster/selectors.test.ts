import selectors from "./selectors";

import * as factory from "@/testing/factories";

describe("vmcluster selectors", () => {
  it("can get the items", () => {
    const items = [
      factory.vmCluster(),
      factory.vmCluster(),
      factory.vmCluster(),
    ];
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items,
      }),
    });
    expect(selectors.all(state)).toStrictEqual(items);
  });

  it("can get the statuses", () => {
    const statuses = factory.vmClusterStatuses();
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        statuses,
      }),
    });
    expect(selectors.statuses(state)).toStrictEqual(statuses);
  });

  it("can get a status", () => {
    const statuses = factory.vmClusterStatuses({
      getting: true,
    });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        statuses,
      }),
    });
    expect(selectors.status(state, "getting")).toBe(true);
  });

  it("can get the event errors", () => {
    const eventErrors = [factory.vmClusterEventError()];
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        eventErrors,
      }),
    });
    expect(selectors.eventErrors(state)).toStrictEqual(eventErrors);
  });

  it("can get an event error", () => {
    const eventError = factory.vmClusterEventError({
      event: "listByPhysicalCluster",
    });
    const state = factory.rootState({
      vmcluster: factory.vmClusterState({
        eventErrors: [eventError],
      }),
    });
    expect(selectors.eventError(state, "listByPhysicalCluster")).toStrictEqual([
      eventError,
    ]);
  });
});
