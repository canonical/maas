/* eslint-disable testing-library/no-container */

import TableHeader from "./TableHeader";

import { SortDirection } from "@/app/base/types";
import {
  render,
  screen,
  userEvent,
  renderWithProviders,
} from "@/testing/utils";

describe("TableHeader ", () => {
  it("renders a div if no onClick prop is present", () => {
    const { container } = render(<TableHeader>Text</TableHeader>);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(container.querySelector("div")).toBeInTheDocument();
  });

  it("renders a Button if onClick prop is present", async () => {
    const mockFn = vi.fn();
    renderWithProviders(<TableHeader onClick={mockFn}>Text</TableHeader>);
    expect(screen.getByRole("button")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button"));
    expect(mockFn).toHaveBeenCalled();
  });

  it("renders a contextual icon if currentSort.key matches sortKey", () => {
    const currentSort = {
      key: "key",
      direction: SortDirection.DESCENDING,
    };
    const { container } = render(
      <TableHeader currentSort={currentSort} onClick={vi.fn()} sortKey={"key"}>
        Text
      </TableHeader>
    );
    expect(
      container.querySelector(".p-icon--chevron-down")
    ).toBeInTheDocument();
  });

  it(`renders a flipped contextual icon if currentSort.key matches sortKey
    and direction is ascending`, () => {
    const currentSort = {
      key: "key",
      direction: SortDirection.ASCENDING,
    };
    const { container } = render(
      <TableHeader currentSort={currentSort} onClick={vi.fn()} sortKey={"key"}>
        Text
      </TableHeader>
    );
    expect(container.querySelector(".p-icon--chevron-up")).toBeInTheDocument();
  });
});
