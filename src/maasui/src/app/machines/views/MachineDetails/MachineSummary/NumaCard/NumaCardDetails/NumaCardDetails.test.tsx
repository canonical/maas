import NumaCardDetails, {
  Labels as NumaCardDetailsLabels,
} from "./NumaCardDetails";

import type { RootState } from "@/app/store/root/types";
import type { NodeNumaNode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("NumaCardDetails", () => {
  let state: RootState;
  let numaNode: NodeNumaNode;
  beforeEach(() => {
    numaNode = factory.machineNumaNode();
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            numa_nodes: [numaNode],
            system_id: "abc123",
          }),
        ],
      }),
    });
  });

  it("can display as expanded", () => {
    renderWithProviders(
      <NumaCardDetails machineId="abc123" numaNode={numaNode} showExpanded />,
      { state }
    );

    expect(
      screen.queryByRole("button", { name: "Node 1" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText(NumaCardDetailsLabels.Details)
    ).not.toBeInTheDocument();

    expect(screen.getByText("Node 1")).toBeInTheDocument();

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

  it("can display as collapsed", () => {
    renderWithProviders(
      <NumaCardDetails machineId="abc123" numaNode={numaNode} />,
      { state }
    );

    expect(screen.getByRole("button", { name: "Node 2" })).toBeInTheDocument();
    expect(
      screen.getByLabelText(NumaCardDetailsLabels.Details)
    ).toBeInTheDocument();
  });

  it("can be expanded", async () => {
    renderWithProviders(
      <NumaCardDetails machineId="abc123" numaNode={numaNode} />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Node 3" }));

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

    expect(
      screen.queryByLabelText(NumaCardDetailsLabels.Details)
    ).not.toBeInTheDocument();
  });
});
