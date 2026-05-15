import RowCheckbox from "./RowCheckbox";

import { screen, renderWithProviders } from "@/testing/utils";

describe("RowCheckbox", () => {
  it("can show a label", () => {
    renderWithProviders(
      <RowCheckbox
        handleRowCheckbox={vi.fn()}
        item={null}
        items={[]}
        label="Check row"
      />
    );
    expect(
      screen.getByRole("checkbox", { name: /Check row/i })
    ).toBeInTheDocument();
  });

  it("can check if it should be selected via a function", () => {
    renderWithProviders(
      <RowCheckbox
        checkSelected={() => true}
        handleRowCheckbox={vi.fn()}
        item={null}
        items={[]}
        label="Check row"
      />
    );
    expect(screen.getByRole("checkbox", { name: /Check row/i })).toBeChecked();
  });
});
