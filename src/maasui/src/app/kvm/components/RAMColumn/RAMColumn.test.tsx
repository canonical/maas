import RAMColumn from "./RAMColumn";

import type { Pod } from "@/app/store/pod/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("RAMColumn", () => {
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

  it("can display correct memory information without overcommit", () => {
    pod.memory_over_commit_ratio = 1;
    pod.resources = factory.podResources({
      memory: factory.podMemoryResource({
        general: factory.podResource({
          allocated_other: 1,
          allocated_tracked: 2,
          free: 3,
        }),
        hugepages: factory.podResource({
          allocated_other: 4,
          allocated_tracked: 5,
          free: 6,
        }),
      }),
    });

    renderWithProviders(
      <RAMColumn
        memory={pod.resources.memory}
        overCommit={pod.memory_over_commit_ratio}
      />,
      { state }
    );
    // Allocated tracked = 2 + 5 = 7
    // Total = (1 + 2 + 3) + (4 + 5 + 6) = 6 + 15 = 21
    expect(screen.getByText(/7 of 21B allocated/i)).toBeInTheDocument();
  });

  it("can display correct memory information with overcommit", () => {
    pod.memory_over_commit_ratio = 2;
    pod.resources = factory.podResources({
      memory: factory.podMemoryResource({
        general: factory.podResource({
          allocated_other: 1,
          allocated_tracked: 2,
          free: 3,
        }),
        hugepages: factory.podResource({
          allocated_other: 4,
          allocated_tracked: 5,
          free: 6,
        }),
      }),
    });

    renderWithProviders(
      <RAMColumn
        memory={pod.resources.memory}
        overCommit={pod.memory_over_commit_ratio}
      />,
      { state }
    );
    // Allocated tracked = 2 + 5 = 7
    // Hugepages do not take overcommit into account, so
    // Total = ((1 + 2 + 3) * 2) + (4 + 5 + 6) = 12 + 15 = 27
    expect(screen.getByText(/7 of 27B allocated/i)).toBeInTheDocument();
  });

  it("can display when memory has been overcommitted", () => {
    pod.memory_over_commit_ratio = 1;
    pod.resources = factory.podResources({
      memory: factory.podMemoryResource({
        general: factory.podResource({
          allocated_other: 0,
          allocated_tracked: 2,
          free: -1,
        }),
        hugepages: factory.podResource({
          allocated_other: 0,
          allocated_tracked: 5,
          free: -1,
        }),
      }),
    });

    renderWithProviders(
      <RAMColumn
        memory={pod.resources.memory}
        overCommit={pod.memory_over_commit_ratio}
      />,
      { state }
    );
    expect(screen.getByTestId("meter-overflow")).toBeInTheDocument();
    expect(screen.getByText(/7 of 5B allocated/i)).toBeInTheDocument();
  });

  it("can display correct memory for a vmcluster", () => {
    const memory = factory.vmClusterResourcesMemory({
      general: factory.vmClusterResource({
        allocated_other: 1,
        allocated_tracked: 2,
        free: 3,
      }),
      hugepages: factory.vmClusterResource({
        allocated_other: 4,
        allocated_tracked: 5,
        free: 6,
      }),
    });

    renderWithProviders(<RAMColumn memory={memory} />, {
      state,
    });
    expect(screen.getByText(/7 of 21B allocated/i)).toBeInTheDocument();
  });
});
