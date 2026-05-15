import LXDClusterHostsTable from "./LXDClusterHostsTable";

import urls from "@/app/base/urls";
import ComposeForm from "@/app/kvm/components/ComposeForm";
import { PodType } from "@/app/store/pod/constants";
import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { poolsResolvers } from "@/testing/resolvers/pools";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();
setupMockServer(poolsResolvers.listPools.handler());

describe("LXDClusterHostsTable", () => {
  let state: RootState;
  let host: Pod;
  beforeEach(() => {
    host = factory.pod({
      cluster: 1,
      id: 22,
      name: "cluster-host",
      pool: 1,
      type: PodType.LXD,
    });
    state = factory.rootState({
      pod: factory.podState({
        items: [host],
        loaded: true,
      }),
      vmcluster: factory.vmClusterState({
        items: [
          factory.vmCluster({
            id: 1,
            hosts: [factory.vmHost({ id: host.id, name: host.name })],
          }),
        ],
      }),
    });
  });

  it("shows a spinner if pods or pools haven't loaded yet", () => {
    renderWithProviders(
      <LXDClusterHostsTable
        clusterId={1}
        currentPage={1}
        hosts={state.pod.items}
        searchFilter=""
      />,
      { initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })], state }
    );
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("can link to a host's VMs tab", async () => {
    renderWithProviders(
      <LXDClusterHostsTable
        clusterId={1}
        currentPage={1}
        hosts={state.pod.items}
        searchFilter=""
      />,
      { initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })], state }
    );

    await waitFor(() => {
      expect(screen.getByRole("link", { name: host.name })).toHaveAttribute(
        "href",
        urls.kvm.lxd.cluster.vms.host({ clusterId: 1, hostId: 22 })
      );
    });
  });

  it("can show the name of the host's pool", async () => {
    renderWithProviders(
      <LXDClusterHostsTable
        clusterId={1}
        currentPage={1}
        hosts={state.pod.items}
        searchFilter=""
      />,
      { initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })], state }
    );
    await waitFor(() => {
      expect(poolsResolvers.listPools.resolved).toBeTruthy();
    });
    await waitFor(() => {
      expect(screen.getByTestId("host-pool-name")).toHaveTextContent(
        "swimming"
      );
    });
  });

  it("can open the compose VM form for a host", async () => {
    renderWithProviders(
      <LXDClusterHostsTable
        clusterId={1}
        currentPage={1}
        hosts={state.pod.items}
        searchFilter=""
      />,
      { initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })], state }
    );
    await waitFor(() => screen.getByTestId("vm-host-compose"));
    await userEvent.click(screen.getByTestId("vm-host-compose"));
    await waitFor(() => {
      expect(mockOpen).toHaveBeenCalledWith({
        component: ComposeForm,
        title: "Compose",
        props: { hostId: 22 },
      });
    });
  });

  it("can link to a host's settings page", async () => {
    renderWithProviders(
      <LXDClusterHostsTable
        clusterId={1}
        currentPage={1}
        hosts={state.pod.items}
        searchFilter=""
      />,
      { initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })], state }
    );
    await waitFor(() => {
      expect(poolsResolvers.listPools.resolved).toBeTruthy();
    });
    await waitFor(() => {
      expect(screen.getByTestId("vm-host-settings")).toHaveAttribute(
        "href",
        urls.kvm.lxd.cluster.host.edit({
          clusterId: 1,
          hostId: 22,
        })
      );
    });
  });

  it("displays a message if there are no search results", () => {
    renderWithProviders(
      <LXDClusterHostsTable
        clusterId={1}
        currentPage={1}
        hosts={[]}
        searchFilter="nothing"
      />,
      { initialEntries: [urls.kvm.lxd.cluster.hosts({ clusterId: 1 })], state }
    );

    expect(screen.getByTestId("no-hosts")).toBeInTheDocument();
  });
});
