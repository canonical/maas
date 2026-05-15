import ArrowPagination, { Labels, TestIds } from "./ArrowPagination";

import { screen, renderWithProviders } from "@/testing/utils";

describe("ArrowPagination", () => {
  it("disables both buttons when there are no items", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={1}
        itemCount={0}
        pageSize={25}
        setCurrentPage={() => null}
      />
    );

    expect(
      screen.getByRole("button", { name: Labels.GoBack })
    ).toBeAriaDisabled();
    expect(
      screen.getByRole("button", { name: Labels.GoForward })
    ).toBeAriaDisabled();
  });

  it("activates both buttons when between the start and end", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={2}
        itemCount={75}
        pageSize={25}
        setCurrentPage={() => null}
      />
    );

    expect(
      screen.getByRole("button", { name: Labels.GoBack })
    ).not.toBeAriaDisabled();
    expect(
      screen.getByRole("button", { name: Labels.GoForward })
    ).not.toBeAriaDisabled();
  });

  it("disables the back button when on the first page", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={1}
        itemCount={50}
        pageSize={25}
        setCurrentPage={() => null}
      />
    );

    expect(
      screen.getByRole("button", { name: Labels.GoBack })
    ).toBeAriaDisabled();
    expect(
      screen.getByRole("button", { name: Labels.GoForward })
    ).not.toBeAriaDisabled();
  });

  it("disables the forward button when on the last page", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={2}
        itemCount={50}
        pageSize={25}
        setCurrentPage={() => null}
      />
    );

    expect(
      screen.getByRole("button", { name: Labels.GoBack })
    ).not.toBeAriaDisabled();
    expect(
      screen.getByRole("button", { name: Labels.GoForward })
    ).toBeAriaDisabled();
  });

  it("can show the page bounds when there are no items", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={1}
        itemCount={0}
        pageSize={25}
        setCurrentPage={vi.fn()}
        showPageBounds
      />
    );

    expect(screen.getByTestId(TestIds.PageBounds).textContent).toBe(
      "0 - 0 of 0"
    );
  });

  it("can show the page bounds when there are more items than the current page shows", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={1}
        itemCount={26}
        pageSize={25}
        setCurrentPage={vi.fn()}
        showPageBounds
      />
    );

    expect(screen.getByTestId(TestIds.PageBounds).textContent).toBe(
      "1 - 25 of 26"
    );
  });

  it("can show the page bounds when there are less items than the current page shows", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={1}
        itemCount={24}
        pageSize={25}
        setCurrentPage={vi.fn()}
        showPageBounds
      />
    );

    expect(screen.getByTestId(TestIds.PageBounds).textContent).toBe(
      "1 - 24 of 24"
    );
  });

  it("shows a spinner in the page bound section if items are loading", () => {
    renderWithProviders(
      <ArrowPagination
        currentPage={1}
        itemCount={24}
        loading
        pageSize={25}
        setCurrentPage={vi.fn()}
        showPageBounds
      />
    );

    expect(
      screen.getByRole("alert", { name: Labels.LoadingPagination })
    ).toBeInTheDocument();
  });
});
