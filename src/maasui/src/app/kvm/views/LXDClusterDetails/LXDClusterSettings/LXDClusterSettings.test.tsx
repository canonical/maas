import LXDClusterSettings from "./LXDClusterSettings";

import { podActions } from "@/app/store/pod";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("LXDClusterSettings", () => {
  it("sets the cluster's first host as active", () => {
    const state = factory.rootState({
      pod: factory.podState({
        items: [factory.pod({ id: 11 }), factory.pod({ id: 22 })],
      }),
      vmcluster: factory.vmClusterState({
        items: [
          factory.vmCluster({
            id: 1,
            hosts: [factory.vmHost({ id: 11 }), factory.vmHost({ id: 22 })],
          }),
        ],
      }),
    });
    const { store } = renderWithProviders(
      <LXDClusterSettings clusterId={1} />,
      { state }
    );

    const expectedAction = podActions.setActive(11);
    const actualActions = store.getActions();
    expect(
      actualActions.find((action) => action.type === expectedAction.type)
    ).toStrictEqual(expectedAction);
  });
});
