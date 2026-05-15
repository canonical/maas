import LXDClusterDetailsHeader from "./LXDClusterDetailsHeader";

import urls from "@/app/base/urls";
import RefreshForm from "@/app/kvm/components/RefreshForm";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  userEvent,
  screen,
  renderWithProviders,
  waitFor,
  setupMockServer,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();
setupMockServer(zoneResolvers.getZone.handler());

describe("LXDClusterDetailsHeader", () => {
  let state: RootState;

  beforeEach(() => {
    const cluster = factory.vmCluster({
      availability_zone: 1,
      id: 1,
      name: "vm-cluster",
      project: "cluster-project",
    });
    state = factory.rootState({
      vmcluster: factory.vmClusterState({
        items: [cluster],
      }),
    });
  });

  it("displays a spinner if cluster hasn't loaded", () => {
    state.vmcluster.items = [];
    renderWithProviders(<LXDClusterDetailsHeader clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.index({ clusterId: 1 })],
      state,
    });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("displays the cluster member count", () => {
    state.vmcluster.items[0].hosts = [factory.vmHost(), factory.vmHost()];

    renderWithProviders(<LXDClusterDetailsHeader clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.index({ clusterId: 1 })],
      state,
    });

    expect(screen.getAllByTestId("block-subtitle")[0]).toHaveTextContent(
      "2 members"
    );
  });

  it("displays the tracked VMs count", () => {
    state.vmcluster.items[0].virtual_machines = [
      factory.virtualMachine(),
      factory.virtualMachine(),
      factory.virtualMachine(),
    ];
    renderWithProviders(<LXDClusterDetailsHeader clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.index({ clusterId: 1 })],
      state,
    });

    expect(screen.getAllByTestId("block-subtitle")[1]).toHaveTextContent(
      "3 available"
    );
  });

  it("displays the cluster's zone's name", async () => {
    renderWithProviders(<LXDClusterDetailsHeader clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.index({ clusterId: 1 })],
      state,
    });

    await waitFor(() => {
      expect(screen.getAllByTestId("block-subtitle")[2]).toHaveTextContent(
        "zone-1"
      );
    });
  });

  it("displays the cluster's project", () => {
    renderWithProviders(<LXDClusterDetailsHeader clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.index({ clusterId: 1 })],
      state,
    });

    expect(screen.getAllByTestId("block-subtitle")[3]).toHaveTextContent(
      "cluster-project"
    );
  });

  it("can open the refresh cluster form if it has hosts", async () => {
    const hosts = [factory.vmHost(), factory.vmHost()];
    state.vmcluster.items[0].hosts = hosts;
    renderWithProviders(<LXDClusterDetailsHeader clusterId={1} />, {
      initialEntries: [urls.kvm.lxd.cluster.index({ clusterId: 1 })],
      state,
    });

    await userEvent.click(
      screen.getByRole("button", { name: "Refresh cluster" })
    );

    expect(mockOpen).toHaveBeenCalledWith({
      component: RefreshForm,
      title: "Refresh",
      props: { hostIds: hosts.map((host) => host.id) },
    });
  });
});
