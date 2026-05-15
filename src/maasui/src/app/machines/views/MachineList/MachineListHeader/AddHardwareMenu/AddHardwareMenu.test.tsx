import AddHardwareMenu from "./AddHardwareMenu";

import { screen, renderWithProviders } from "@/testing/utils";

describe("AddHardwareMenu", () => {
  it("can be enabled", () => {
    renderWithProviders(<AddHardwareMenu />);
    expect(screen.getByRole("button", { name: /Add hardware/i })).toBeEnabled();
  });
  it("can be disabled", () => {
    renderWithProviders(<AddHardwareMenu disabled />);
    expect(
      screen.getByRole("button", { name: /Add hardware/i })
    ).toBeAriaDisabled();
  });
});
