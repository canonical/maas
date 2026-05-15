import ShowAdvanced, { Labels } from "./ShowAdvanced";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

it("displays additional content on press", async () => {
  renderWithProviders(<ShowAdvanced>additional content</ShowAdvanced>);

  expect(screen.getByText("additional content")).toHaveAttribute(
    "aria-hidden",
    "true"
  );
  await userEvent.click(
    screen.getByRole("button", { name: Labels.ShowAdvanced })
  );
  expect(screen.getByText("additional content")).toHaveAttribute(
    "aria-hidden",
    "false"
  );
});
