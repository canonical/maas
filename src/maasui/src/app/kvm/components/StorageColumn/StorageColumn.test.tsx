import StorageColumn from "./StorageColumn";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("StorageColumn", () => {
  it("displays correct storage information for a pod", () => {
    const pod = factory.pod({
      id: 1,
      name: "pod-1",
      resources: factory.podResources({
        storage: factory.podResource({
          allocated_other: 30000000000,
          allocated_tracked: 70000000000,
          free: 900000000000,
        }),
      }),
    });
    const state = factory.rootState({
      pod: factory.podState({
        items: [pod],
      }),
    });
    renderWithProviders(
      <StorageColumn
        defaultPoolId={pod.default_storage_pool}
        pools={{}}
        storage={pod.resources.storage}
      />,
      { state }
    );
    expect(screen.getByText(/0.1 of 1TB allocated/i)).toBeInTheDocument();
    const segmentWidths = [
      "width: 7.000000000000001%",
      "width: 3%",
      "width: 90%;",
    ];
    const segments = screen.getAllByTestId("meter-filled");
    expect(segments[0]).toHaveStyle(segmentWidths[0]);
    expect(segments[1]).toHaveStyle(segmentWidths[1]);
    expect(segments[2]).toHaveStyle(segmentWidths[2]);
  });

  it("displays correct storage information for a vmcluster", () => {
    const resources = factory.vmClusterResource({
      allocated_other: 1,
      allocated_tracked: 2,
      free: 3,
    });

    renderWithProviders(<StorageColumn pools={{}} storage={resources} />);
    expect(screen.getByText(/2 of 6B allocated/i)).toBeInTheDocument();

    const segmentWidths = [
      "width: 33.33333333333333%",
      "width: 16.666666666666664%",
      "width: 50%;",
    ];
    const segments = screen.getAllByTestId("meter-filled");
    expect(segments[0]).toHaveStyle(segmentWidths[0]);
    expect(segments[1]).toHaveStyle(segmentWidths[1]);
    expect(segments[2]).toHaveStyle(segmentWidths[2]);
  });
});
