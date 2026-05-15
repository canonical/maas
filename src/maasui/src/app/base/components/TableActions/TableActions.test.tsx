import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TableActions from "./TableActions";

import { expectTooltipOnHover, renderWithProviders } from "@/testing/utils";

describe("TableActions ", () => {
  it("renders a copy button if copy value provided", () => {
    renderWithProviders(<TableActions copyValue="foo" />);
    expect(screen.getByText(/copy/i)).toBeInTheDocument();
  });

  it("renders an edit link if edit path provided", () => {
    renderWithProviders(<TableActions editPath="/bar" />);
    expect(screen.getByRole("link", { name: /edit/i })).toHaveAttribute(
      "href",
      "/bar"
    );
  });

  it("renders an edit button if edit on-click provided", async () => {
    const onEdit = vi.fn();
    renderWithProviders(<TableActions onEdit={onEdit} />);
    await userEvent.click(screen.getByText(/edit/i));
    expect(onEdit).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /edit/i })).toBeInTheDocument();
  });

  it("renders a delete button if delete function provided", async () => {
    const onDelete = vi.fn();
    renderWithProviders(<TableActions onDelete={onDelete} />);
    expect(screen.getByRole("button", { name: /delete/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /delete/i }));
    expect(onDelete).toHaveBeenCalled();
  });

  it("correctly renders tooltips", async () => {
    renderWithProviders(
      <TableActions
        deleteTooltip="delete tooltip"
        editPath="/bar"
        editTooltip="edit tooltip"
        onDelete={vi.fn()}
      />
    );
    await expectTooltipOnHover(
      screen.getByRole("link", { name: /edit/i }),
      /edit tooltip/i
    );
    await expectTooltipOnHover(
      screen.getByRole("button", { name: /delete/i }),
      /delete tooltip/i
    );
  });

  it("correctly disables buttons", () => {
    renderWithProviders(
      <TableActions
        deleteDisabled
        editDisabled
        editPath="/bar"
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByRole("link", { name: /edit/i })).toBeAriaDisabled();
    expect(screen.getByRole("button", { name: /delete/i })).toBeAriaDisabled();
  });
});
