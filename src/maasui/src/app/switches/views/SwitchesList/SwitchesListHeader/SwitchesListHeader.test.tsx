import { waitFor } from "@testing-library/react";

import SwitchesListHeader from "./SwitchesListHeader";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("SwitchesListHeader", () => {
  it("changes the search text when the filters change", () => {
    const { rerender } = renderWithProviders(
      <SwitchesListHeader searchFilter={""} setSearchFilter={vi.fn()} />
    );
    expect(screen.getByRole("searchbox")).toHaveValue("");

    rerender(
      <SwitchesListHeader
        searchFilter={"free-text"}
        setSearchFilter={vi.fn()}
      />
    );

    expect(screen.getByRole("searchbox")).toHaveValue("free-text");
  });

  it("calls setSearchFilter when text is entered", async () => {
    const mockSetSearchFilter = vi.fn();
    renderWithProviders(
      <SwitchesListHeader
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
