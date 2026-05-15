import StorageResources from "./StorageResources";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("StorageResources", () => {
  it("displays as a meter if there is only one pool", () => {
    const storagePools = {
      "pool-0": factory.podStoragePoolResource({
        allocated_other: 1,
        allocated_tracked: 2,
        path: "/path/0",
        total: 7,
      }),
    };
    renderWithProviders(
      <StorageResources allocated={3} free={4} pools={storagePools} />
    );

    expect(screen.getByLabelText("storage meter")).toBeInTheDocument();
    expect(screen.queryByLabelText("storage cards")).not.toBeInTheDocument();
    expect(screen.queryByTestId("storage-summary")).not.toBeInTheDocument();
  });

  it("displays storage summary and pools as cards if there is more than one pool", () => {
    const storagePools = {
      "pool-0": factory.podStoragePoolResource({
        allocated_other: 0,
        allocated_tracked: 1,
        path: "/path/0",
        total: 2,
      }),
      "pool-1": factory.podStoragePoolResource({
        allocated_other: 1,
        allocated_tracked: 2,
        path: "/path/0",
        total: 4,
      }),
    };
    renderWithProviders(
      <StorageResources allocated={5} free={6} pools={storagePools} />
    );

    expect(screen.getByLabelText("storage cards")).toBeInTheDocument();
    expect(screen.getByTestId("storage-summary")).toBeInTheDocument();
    expect(screen.queryByLabelText("storage meter")).not.toBeInTheDocument();
  });
});
