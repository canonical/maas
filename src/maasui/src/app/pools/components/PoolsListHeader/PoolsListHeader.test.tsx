import PoolsListHeader from "@/app/pools/components/PoolsListHeader/PoolsListHeader";
import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("PoolsListHeader", () => {
  it("displays the form when Add AZ is clicked", async () => {
    renderWithProviders(<PoolsListHeader />);

    await userEvent.click(screen.getByRole("button", { name: "Add pool" }));

    expect(mockOpen).toHaveBeenCalled();
  });
});
