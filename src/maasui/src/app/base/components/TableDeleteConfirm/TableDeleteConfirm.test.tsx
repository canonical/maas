import { screen } from "@testing-library/react";

import TableDeleteConfirm from "./TableDeleteConfirm";

import { renderWithProviders } from "@/testing/utils";

describe("TableDeleteConfirm", () => {
  it("renders", () => {
    renderWithProviders(
      <TableDeleteConfirm
        deleted={false}
        deleting={false}
        modelName="Cobba"
        modelType="user"
        onClose={vi.fn()}
        onConfirm={vi.fn()}
      />
    );
    expect(
      screen.getByText(/Are you sure you want to delete/i)
    ).toBeInTheDocument();
  });
});
