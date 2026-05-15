import ThemedRadioButton from "./ThemedRadioButton";

import { renderWithProviders, screen } from "@/testing/utils";

describe("ThemedRadioButton", () => {
  it("displays a radio button", () => {
    renderWithProviders(
      <ThemedRadioButton label="Test button" name="test-button" />
    );

    expect(screen.getByRole("radio", { name: "Test button" }));
  });
});
