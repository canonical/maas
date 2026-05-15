import ActionBar from "./ActionBar";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ActionBar", () => {
  it("displays provided actions", () => {
    const state = factory.rootState();

    renderWithProviders(
      <ActionBar
        actions={<span data-testid="actions">Actions</span>}
        currentPage={1}
        itemCount={10}
        onSearchChange={vi.fn()}
        searchFilter=""
        setCurrentPage={vi.fn()}
      />,
      { state }
    );
    expect(screen.getByTestId("actions")).toBeInTheDocument();
  });
});
