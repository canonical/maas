import DiskNumaNodes from "./DiskNumaNodes";

import * as factory from "@/testing/factories";
import {
  expectTooltipOnHover,
  screen,
  renderWithProviders,
} from "@/testing/utils";

describe("DiskNumaNodes", () => {
  it("can show a single numa node", () => {
    const disk = factory.nodeDisk({
      numa_node: 5,
      numa_nodes: undefined,
    });
    renderWithProviders(<DiskNumaNodes disk={disk} />);
    expect(screen.getByTestId("numa-nodes")).toHaveTextContent("5");
  });

  it("can show multiple numa nodes with a warning", async () => {
    const disk = factory.nodeDisk({
      numa_node: undefined,
      numa_nodes: [0, 1],
    });
    renderWithProviders(<DiskNumaNodes disk={disk} />);
    const numaNodes = screen.getByTestId("numa-nodes");
    expect(numaNodes).toHaveTextContent("0, 1");
    await expectTooltipOnHover(
      screen.getByRole("button", { name: /warning/i }),
      /This volume is spread over multiple NUMA nodes/
    );
  });
});
