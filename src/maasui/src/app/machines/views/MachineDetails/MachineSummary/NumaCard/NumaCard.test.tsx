import NumaCard, { Labels as NumaCardLabels } from "./NumaCard";
import { Labels as NumaCardDetailsLabels } from "./NumaCardDetails/NumaCardDetails";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, within, renderWithProviders } from "@/testing/utils";

describe("NumaCard", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            numa_nodes: [factory.machineNumaNode()],
            system_id: "abc123",
          }),
        ],
      }),
    });
  });

  it("renders when there are no numa nodes", () => {
    state.machine.items = [
      factory.machineDetails({
        numa_nodes: [],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(<NumaCard id="abc123" />, {
      state,
    });

    const numa_card = screen.getByLabelText(NumaCardLabels.NumaCard);
    expect(within(numa_card).getByText("0 NUMA nodes")).toBeInTheDocument();
    expect(
      within(numa_card).queryByRole("list", { name: NumaCardLabels.NumaList })
    ).not.toBeInTheDocument();
  });

  it("renders with numa nodes", () => {
    renderWithProviders(<NumaCard id="abc123" />, {
      state,
    });
    expect(screen.getByText("1 NUMA node")).toBeInTheDocument();
    expect(screen.getByText("Node 2")).toBeInTheDocument();

    expect(
      screen.getByLabelText(NumaCardDetailsLabels.CpuCores)
    ).toHaveTextContent("0");
    expect(
      screen.getByLabelText(NumaCardDetailsLabels.Memory)
    ).toHaveTextContent("256 MiB");
    expect(
      screen.getByLabelText(NumaCardDetailsLabels.Storage)
    ).toHaveTextContent("0 B over 0 disks");
    expect(
      screen.getByLabelText(NumaCardDetailsLabels.Network)
    ).toHaveTextContent("0 interfaces");
  });
});
