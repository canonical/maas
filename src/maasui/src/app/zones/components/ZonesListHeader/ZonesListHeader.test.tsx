import ZonesListHeader from "./ZonesListHeader";

import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("ZonesListHeader", () => {
  it("displays the form when Add AZ is clicked", async () => {
    renderWithProviders(<ZonesListHeader />);

    await userEvent.click(screen.getByRole("button", { name: "Add AZ" }));

    expect(mockOpen).toHaveBeenCalled();
  });
});
