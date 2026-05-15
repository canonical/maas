import VirshDetailsHeader from "./VirshDetailsHeader";

import { PodType } from "@/app/store/pod/constants";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { zoneResolvers } from "@/testing/resolvers/zones";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

setupMockServer(zoneResolvers.getZone.handler());

describe("VirshDetailsHeader", () => {
  let state: RootState;
  const route = ["/kvm/1/resources"];

  beforeEach(() => {
    state = factory.rootState({
      pod: factory.podState({
        errors: {},
        loading: false,
        loaded: true,
        items: [
          factory.pod({
            id: 1,
            name: "pod-1",
            resources: factory.podResources({
              vm_count: factory.podVmCount({ tracked: 10 }),
            }),
            type: PodType.VIRSH,
          }),
        ],
        statuses: factory.podStatuses({
          1: factory.podStatus(),
        }),
      }),
    });
  });

  it("displays a spinner if pod has not loaded", () => {
    state.pod.items = [];
    renderWithProviders(<VirshDetailsHeader id={1} />, {
      initialEntries: ["/kvm/1"],
      state,
    });
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays the virsh power address", () => {
    state.pod.items[0].power_parameters = factory.podPowerParameters({
      power_address: "qemu+ssh://ubuntu@192.168.1.1/system",
    });
    renderWithProviders(<VirshDetailsHeader id={1} />, {
      initialEntries: route,
      state,
    });
    expect(screen.getAllByTestId("block-subtitle")[0]).toHaveTextContent(
      "qemu+ssh://ubuntu@192.168.1.1/system"
    );
  });

  it("displays the tracked VMs count", () => {
    state.pod.items[0].resources = factory.podResources({
      vm_count: factory.podVmCount({ tracked: 5 }),
    });
    renderWithProviders(<VirshDetailsHeader id={1} />, {
      initialEntries: route,
      state,
    });
    expect(screen.getAllByTestId("block-subtitle")[1]).toHaveTextContent(
      "5 available"
    );
  });

  it("displays the pod zone name", async () => {
    state.pod.items[0].zone = 1;
    renderWithProviders(<VirshDetailsHeader id={1} />, {
      initialEntries: route,
      state,
    });
    await waitFor(() => {
      expect(screen.getAllByTestId("block-subtitle")[2]).toHaveTextContent(
        "zone-1"
      );
    });
  });
});
