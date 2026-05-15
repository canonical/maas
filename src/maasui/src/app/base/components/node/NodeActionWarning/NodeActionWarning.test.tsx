import NodeActionWarning from "./NodeActionWarning";

import { NodeActions } from "@/app/store/types/node";
import { screen, renderWithProviders } from "@/testing/utils";

it("displays a warning for selectedCount of 0", () => {
  renderWithProviders(
    <NodeActionWarning
      action={NodeActions.ABORT}
      nodeType="machine"
      onUpdateSelected={vi.fn()}
      selectedCount={0}
    />
  );
  expect(
    screen.getByText(/No machines have been selected/)
  ).toBeInTheDocument();
});

it("displays a warning for an action with a selected count", () => {
  renderWithProviders(
    <NodeActionWarning
      action={NodeActions.COMMISSION}
      nodeType="node"
      onUpdateSelected={vi.fn()}
      selectedCount={2}
    />
  );
  expect(
    screen.getByText(/2 nodes cannot be commissioned/)
  ).toBeInTheDocument();
});
