import RemoveControllers from "./RemoveControllers";

import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("RemoveControllers", () => {
  const testRackId = 1;

  it("runs closeForm function when the cancel button is clicked", async () => {
    renderWithProviders(<RemoveControllers id={testRackId} />);

    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  // TODO when endpoint is ready: https://warthogs.atlassian.net/browse/MAASENG-5529
  it.todo(
    "calls remove controllers API when remove controllers button is clicked"
  );
  // TODO when endpoint is ready: https://warthogs.atlassian.net/browse/MAASENG-5529
  it.todo("displays error message when remove controller fails");
});
