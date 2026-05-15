import LXDClusterDetailsRedirect, { Label } from "./LXDClusterDetailsRedirect";

import urls from "@/app/base/urls";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, waitFor, renderWithProviders } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    pod: factory.podState({
      items: [factory.podDetails({ id: 2, type: PodType.LXD, cluster: 1 })],
      loaded: true,
    }),
    vmcluster: factory.vmClusterState({
      items: [factory.vmCluster({ id: 1 })],
      loaded: true,
    }),
  });
});

it("displays a spinner while loading", () => {
  state.pod.loaded = false;
  renderWithProviders(<LXDClusterDetailsRedirect clusterId={1} />, {
    initialEntries: [
      urls.kvm.lxd.cluster.host.index({ clusterId: 1, hostId: 2 }),
    ],
    state,
  });
  expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
});

it("displays a message if the host is not found", () => {
  state.pod.items = [];
  renderWithProviders(<LXDClusterDetailsRedirect clusterId={1} />, {
    initialEntries: [
      urls.kvm.lxd.cluster.host.index({ clusterId: 1, hostId: 2 }),
    ],
    state,
  });
  expect(screen.getByText("LXD host not found")).toBeInTheDocument();
});

it("redirects to the config form", async () => {
  const { router } = renderWithProviders(
    <LXDClusterDetailsRedirect clusterId={1} />,
    {
      state,
      initialEntries: [
        urls.kvm.lxd.cluster.host.index({ clusterId: 1, hostId: 2 }),
      ],
      pattern: urls.kvm.lxd.cluster.host.index(null),
    }
  );
  await waitFor(() => {
    expect(router.state.location.pathname).toEqual(
      urls.kvm.lxd.cluster.host.edit({ clusterId: 1, hostId: 2 })
    );
  });
});
