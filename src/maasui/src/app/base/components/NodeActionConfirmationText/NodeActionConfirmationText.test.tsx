import NodeActionConfirmationText from "./NodeActionConfirmationText";

import { NodeActions } from "@/app/store/types/node";
import { screen, renderWithProviders } from "@/testing/utils";

it("displays correct confirmation text for deleting a single node", () => {
  renderWithProviders(
    <NodeActionConfirmationText
      action={NodeActions.DELETE}
      modelName="machine"
      selectedCount={1}
    />
  );
  expect(
    screen.getByText("Are you sure you want to delete a machine?")
  ).toBeInTheDocument();
});

it("displays correct confirmation text for deleting multiple nodes", () => {
  renderWithProviders(
    <NodeActionConfirmationText
      action={NodeActions.DELETE}
      modelName="machine"
      selectedCount={2}
    />
  );
  expect(
    screen.getByText(/Are you sure you want to delete 2 machines?/)
  ).toBeInTheDocument();
});
