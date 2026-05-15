import LXDClusterHosts from "./LXDClusterHosts";

import urls from "@/app/base/urls";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("LXDClusterHosts", () => {
  let state: RootState;

  beforeEach(() => {
    const pods = [
      factory.pod({ id: 111, name: "cluster-member-1", type: PodType.LXD }),
      factory.pod({ id: 222, name: "cluster-member-2", type: PodType.LXD }),
    ];
    const cluster = factory.vmCluster({
      id: 1,
      hosts: pods.map((pod) => factory.vmHost({ id: pod.id, name: pod.name })),
    });
    state = factory.rootState({
      pod: factory.podState({
        items: pods,
        loaded: true,
      }),
      vmcluster: factory.vmClusterState({
        items: [cluster],
        loaded: true,
      }),
    });
  });

  it("displays a spinner if pods haven't loaded", () => {
    state.pod.loaded = false;
    renderWithProviders(<LXDClusterHosts clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })],
      state,
    });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });
});
