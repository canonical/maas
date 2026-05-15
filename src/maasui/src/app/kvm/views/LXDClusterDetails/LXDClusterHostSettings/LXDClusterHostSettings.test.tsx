import LXDClusterHostSettings, { Label } from "./LXDClusterHostSettings";

import urls from "@/app/base/urls";
import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("LXDClusterHostSettings", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        items: [
          factory.podDetails({
            cluster: 1,
            id: 2,
            name: "pod1",
            type: PodType.LXD,
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("displays a spinner if data is loading", () => {
    state.pod.loading = true;
    renderWithProviders(<LXDClusterHostSettings clusterId={2} />, {
      initialEntries: [
        urls.kvm.lxd.cluster.host.edit({ clusterId: 1, hostId: 2 }),
      ],
      state,
      pattern: urls.kvm.lxd.cluster.host.edit(null),
    });
    expect(screen.getByLabelText(Label.Loading)).toBeInTheDocument();
  });

  it("displays a message if the host is not found", () => {
    state.pod.items = [];
    renderWithProviders(<LXDClusterHostSettings clusterId={2} />, {
      initialEntries: [
        urls.kvm.lxd.cluster.host.edit({ clusterId: 1, hostId: 2 }),
      ],
      state,
      pattern: urls.kvm.lxd.cluster.host.edit(null),
    });
    expect(screen.getByText("LXD host not found")).toBeInTheDocument();
  });

  it("has a disabled zone field", () => {
    renderWithProviders(<LXDClusterHostSettings clusterId={2} />, {
      initialEntries: [
        urls.kvm.lxd.cluster.host.edit({ clusterId: 1, hostId: 2 }),
      ],
      state,
      pattern: urls.kvm.lxd.cluster.host.edit(null),
    });
    expect(screen.getByRole("combobox", { name: "Zone" })).toBeDisabled();
  });
});
