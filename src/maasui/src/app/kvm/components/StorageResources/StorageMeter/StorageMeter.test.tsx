import StorageMeter from "./StorageMeter";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

const pools = {
  "pool-1": factory.podStoragePoolResource({
    allocated_other: 1,
    allocated_tracked: 2,
    backend: "zfs",
    name: "pool-1",
    path: "/path1",
    total: 3,
  }),
};

describe("StorageMeter", () => {
  it("renders", () => {
    renderWithProviders(<StorageMeter pools={pools} />);

    expect(screen.getByText("Allocated")).toBeInTheDocument();
  });

  it("does not render if more than one pool present", () => {
    renderWithProviders(
      <StorageMeter
        pools={{ ...pools, "pool-2": factory.podStoragePoolResource() }}
      />
    );

    expect(screen.queryByText("Allocated")).not.toBeInTheDocument();
  });
});
