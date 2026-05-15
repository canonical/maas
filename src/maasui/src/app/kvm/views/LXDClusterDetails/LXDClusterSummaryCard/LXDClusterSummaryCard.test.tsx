import LXDClusterSummaryCard from "./LXDClusterSummaryCard";

import { PodType } from "@/app/store/pod/constants";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, within } from "@/testing/utils";

describe("LXDClusterSummaryCard", () => {
  it("can show the section for storage", () => {
    const state = factory.rootState({
      pod: factory.podState({
        loaded: true,
      }),
      vmcluster: factory.vmClusterState({
        items: [factory.vmCluster({ id: 1 })],
      }),
    });
    renderWithProviders(<LXDClusterSummaryCard clusterId={1} showStorage />, {
      state,
    });

    expect(screen.getByTestId("lxd-cluster-storage")).toBeInTheDocument();
  });

  it("displays a spinner when loading pods", () => {
    const state = factory.rootState({
      pod: factory.podState({
        loading: true,
      }),
    });
    renderWithProviders(<LXDClusterSummaryCard clusterId={1} showStorage />, {
      state,
    });

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("can hide the section for storage", () => {
    const state = factory.rootState({
      pod: factory.podState({
        loaded: true,
      }),
      vmcluster: factory.vmClusterState({
        items: [factory.vmCluster({ id: 1 })],
      }),
    });
    renderWithProviders(
      <LXDClusterSummaryCard clusterId={1} showStorage={false} />,
      { state }
    );

    expect(screen.queryByTestId("lxd-cluster-storage")).not.toBeInTheDocument();
  });

  it("aggregates the interfaces in the cluster hosts", () => {
    const interfaces = [
      factory.podNetworkInterface({
        virtual_functions: factory.podResource({
          allocated_other: 2,
          allocated_tracked: 1,
          free: 3,
        }),
      }),
      factory.podNetworkInterface({
        virtual_functions: factory.podResource({
          allocated_other: 2,
          allocated_tracked: 1,
          free: 3,
        }),
      }),
    ];
    const state = factory.rootState({
      pod: factory.podState({
        items: [
          factory.pod({
            cluster: 1,
            id: 11,
            resources: factory.podResources({
              interfaces: [interfaces[0]],
            }),
            type: PodType.LXD,
          }),
          factory.pod({
            cluster: 1,
            id: 22,
            resources: factory.podResources({
              interfaces: [interfaces[1]],
            }),
            type: PodType.LXD,
          }),
        ],
        loaded: true,
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
    renderWithProviders(<LXDClusterSummaryCard clusterId={1} />, { state });

    const ifaceMeter = screen.getByLabelText("vf-resources-meter");
    expect(ifaceMeter).toBeInTheDocument();
    expect(
      within(ifaceMeter).getByTestId("kvm-resource-allocated")
    ).toHaveTextContent("2");
    expect(
      within(ifaceMeter).getByTestId("kvm-resource-other")
    ).toHaveTextContent("4");
    expect(
      within(ifaceMeter).getByTestId("kvm-resource-free")
    ).toHaveTextContent("6");
    expect(within(ifaceMeter).getByTestId("meter-label")).toHaveTextContent(
      "2"
    );
  });
});
