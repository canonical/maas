import { waitFor } from "@testing-library/react";

import RacksListHeader from "./RacksListHeader";

import {
  userEvent,
  screen,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("RacksListHeader", () => {
  it("displays the form when Add Rack is clicked", async () => {
    renderWithProviders(
      <RacksListHeader searchFilter={""} setSearchFilter={vi.fn()} />
    );

    await userEvent.click(screen.getByRole("button", { name: "Add rack" }));

    expect(mockOpen).toHaveBeenCalled();
  });

  it("changes the search text when the filters change", () => {
    const { rerender } = renderWithProviders(
      <RacksListHeader searchFilter={""} setSearchFilter={vi.fn()} />,
      { initialEntries: ["/racks"] }
    );
    expect(screen.getByRole("searchbox")).toHaveValue("");

    rerender(
      <RacksListHeader searchFilter={"free-text"} setSearchFilter={vi.fn()} />
    );

    expect(screen.getByRole("searchbox")).toHaveValue("free-text");
  });

  it("calls setSearchFilter when text is entered", async () => {
    const mockSetSearchFilter = vi.fn();
    renderWithProviders(
      <RacksListHeader
        searchFilter={""}
        setSearchFilter={mockSetSearchFilter}
      />
    );

    await userEvent.type(screen.getByRole("searchbox"), "test");

    await waitFor(() => {
      expect(mockSetSearchFilter).toHaveBeenCalledWith("test");
    });
  });
});
