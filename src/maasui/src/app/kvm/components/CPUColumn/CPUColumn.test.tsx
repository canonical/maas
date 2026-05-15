import CPUColumn from "./CPUColumn";

import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("CPUColumn", () => {
  let state: RootState;
  let pod: Pod;

  beforeEach(() => {
    pod = factory.pod({
      id: 1,
      name: "pod-1",
    });
    state = factory.rootState({
      pod: factory.podState({
        items: [pod],
      }),
    });
  });

  it("can display correct cpu core information without overcommit", () => {
    pod.cpu_over_commit_ratio = 1;
    pod.resources = factory.podResources({
      cores: factory.podResource({
        allocated_other: 0,
        allocated_tracked: 4,
        free: 4,
      }),
    });

    renderWithProviders(
      <CPUColumn
        cores={pod.resources.cores}
        overCommit={pod.cpu_over_commit_ratio}
      />,
      { state }
    );
    expect(screen.getByText(/4 of 8/i)).toBeInTheDocument();
  });

  it("can display correct cpu core information with overcommit", () => {
    pod.cpu_over_commit_ratio = 2;
    pod.resources = factory.podResources({
      cores: factory.podResource({
        allocated_other: 0,
        allocated_tracked: 4,
        free: 4,
      }),
    });

    renderWithProviders(
      <CPUColumn
        cores={pod.resources.cores}
        overCommit={pod.cpu_over_commit_ratio}
      />,
      { state }
    );
    expect(screen.getByText(/4 of 16/i)).toBeInTheDocument();
  });

  it("can display when cpu has been overcommitted", () => {
    pod.cpu_over_commit_ratio = 1;
    pod.resources = factory.podResources({
      cores: factory.podResource({
        allocated_other: 0,
        allocated_tracked: 4,
        free: -1,
      }),
    });

    renderWithProviders(
      <CPUColumn
        cores={pod.resources.cores}
        overCommit={pod.cpu_over_commit_ratio}
      />,
      { state }
    );
    expect(screen.getByTestId("meter-overflow")).toBeInTheDocument();
    expect(screen.getByText(/4 of 3/i)).toBeInTheDocument();
  });

  it("can display correct cpu core information for vmclusters", () => {
    const resources = factory.vmClusterResource({
      allocated_other: 1,
      allocated_tracked: 2,
      free: 3,
    });

    renderWithProviders(<CPUColumn cores={resources} />, {
      state,
    });
    expect(screen.getByText(/2 of 6/i)).toBeInTheDocument();
  });
});
