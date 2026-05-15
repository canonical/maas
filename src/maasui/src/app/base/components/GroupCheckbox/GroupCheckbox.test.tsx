import GroupCheckbox from "./GroupCheckbox";

import { screen, renderWithProviders } from "@/testing/utils";

describe("GroupCheckbox", () => {
  it("shows as mixed when some items are checked", () => {
    renderWithProviders(
      <GroupCheckbox
        handleGroupCheckbox={vi.fn()}
        items={[1, 2, 3]}
        selectedItems={[2]}
      />
    );

    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByRole("checkbox")).toBePartiallyChecked();
  });

  it("can show a label", () => {
    renderWithProviders(
      <GroupCheckbox
        handleGroupCheckbox={vi.fn()}
        inputLabel="Check all"
        items={[]}
        selectedItems={[]}
      />
    );

    expect(
      screen.getByRole("checkbox", { name: "Check all" })
    ).toBeInTheDocument();
  });

  it("can be disabled even if items exist", () => {
    renderWithProviders(
      <GroupCheckbox
        disabled
        handleGroupCheckbox={vi.fn()}
        inputLabel="Check all"
        items={[1, 2, 3]}
        selectedItems={[2]}
      />
    );

    expect(screen.getByRole("checkbox")).toBeDisabled();
  });

  it("can check if it should be selected via a function", () => {
    renderWithProviders(
      <GroupCheckbox
        checkSelected={() => true}
        handleGroupCheckbox={vi.fn()}
        items={[]}
        selectedItems={[]}
      />
    );

    expect(screen.getByRole("checkbox")).toBeChecked();
  });

  it("can check if it should display as mixed via a function", () => {
    renderWithProviders(
      <GroupCheckbox
        checkAllSelected={() => false}
        handleGroupCheckbox={vi.fn()}
        items={[1, 2, 3]}
        selectedItems={[2]}
      />
    );

    expect(screen.getByRole("checkbox")).toBeChecked();
    expect(screen.getByRole("checkbox")).toBePartiallyChecked();
  });
});
