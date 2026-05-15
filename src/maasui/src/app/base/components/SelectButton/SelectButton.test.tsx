import SelectButton from "./SelectButton";

import { screen, renderWithProviders } from "@/testing/utils";

it("displays a button", () => {
  renderWithProviders(<SelectButton>Test</SelectButton>);

  expect(screen.getByRole("button", { name: "Test" })).toBeInTheDocument();
});
