import { DEFAULTS } from "../constants";

import PageSizeSelect from "./PageSizeSelect";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

const DEFAULT_PAGE_SIZE = DEFAULTS.pageSize;

describe("PageSizeSelect", () => {
  it("renders", () => {
    renderWithProviders(
      <PageSizeSelect
        pageSize={DEFAULT_PAGE_SIZE}
        paginate={vi.fn()}
        setPageSize={vi.fn()}
      />
    );
    expect(
      screen.getByRole("combobox", { name: "Items per page" })
    ).toBeInTheDocument();
  });

  it("calls a function to update the page size and reset to the first page", async () => {
    const setPageSize = vi.fn();
    const setCurrentPage = vi.fn();
    renderWithProviders(
      <PageSizeSelect
        pageSize={DEFAULT_PAGE_SIZE}
        paginate={setCurrentPage}
        setPageSize={setPageSize}
      />
    );

    const pageSizeSelect = screen.getByRole("combobox", {
      name: "Items per page",
    });
    await userEvent.selectOptions(pageSizeSelect, "100");

    expect(setPageSize).toHaveBeenCalledWith(100);
    expect(setCurrentPage).toHaveBeenCalledWith(1);
  });
});
