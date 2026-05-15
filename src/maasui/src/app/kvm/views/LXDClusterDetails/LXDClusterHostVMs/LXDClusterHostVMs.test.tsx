import LXDClusterHostVMs, { Label } from "./LXDClusterHostVMs";

import urls from "@/app/base/urls";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    pod: factory.podState({
      items: [factory.podDetails({ id: 2, type: PodType.LXD, cluster: 1 })],
      loaded: true,
    }),
    vmcluster: factory.vmClusterState({
      items: [
        factory.vmCluster({
          id: 1,
          hosts: [factory.vmHost({ id: 1 })],
        }),
      ],
      loaded: true,
    }),
  });
});

describe("LXDClusterHostVMs", () => {
  it("renders the LXD host VM table if the host is part of the cluster", () => {
    renderWithProviders(
      <LXDClusterHostVMs
        clusterId={1}
        searchFilter=""
        setSearchFilter={vi.fn()}
      />,
      {
        initialEntries: [
          urls.kvm.lxd.cluster.vms.host({ clusterId: 1, hostId: 2 }),
        ],
        state,
        pattern: urls.kvm.lxd.cluster.vms.host(null),
      }
    );
    expect(screen.getByText("VMs on pod1")).toBeInTheDocument();
  });

  it("renders a spinner if cluster hasn't loaded", () => {
    state.pod.loaded = false;
    renderWithProviders(
      <LXDClusterHostVMs
        clusterId={1}
        searchFilter=""
        setSearchFilter={vi.fn()}
      />,
      {
        initialEntries: [
          urls.kvm.lxd.cluster.vms.host({ clusterId: 1, hostId: 2 }),
        ],
        state,
      }
    );
    expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
  });

  it("displays a message if the host is not found", () => {
    state.pod.items = [];
    renderWithProviders(
      <LXDClusterHostVMs
        clusterId={1}
        searchFilter=""
        setSearchFilter={vi.fn()}
      />,
      {
        initialEntries: [
          urls.kvm.lxd.cluster.vms.host({ clusterId: 1, hostId: 2 }),
        ],
        state,
      }
    );
    expect(screen.getByText("LXD host not found")).toBeInTheDocument();
  });
});
