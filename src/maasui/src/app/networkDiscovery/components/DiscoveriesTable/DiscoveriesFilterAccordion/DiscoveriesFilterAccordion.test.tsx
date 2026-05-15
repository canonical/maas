import DiscoveriesFilterAccordion, {
  Labels as DiscoveriesFilterAccordionLabels,
} from "./DiscoveriesFilterAccordion";

import { screen, renderWithProviders } from "@/testing/utils";

describe("DiscoveriesFilterAccordion", () => {
  it("button is disabled when loading discoveries", () => {
    renderWithProviders(
      <DiscoveriesFilterAccordion searchText="" setSearchText={vi.fn()} />
    );
    expect(screen.getByRole("button", { name: "Filters" })).toBeAriaDisabled();
  });

  it("displays a filter accordion", () => {
    renderWithProviders(
      <DiscoveriesFilterAccordion searchText="" setSearchText={vi.fn()} />
    );
    expect(
      screen.getByLabelText(DiscoveriesFilterAccordionLabels.FilterDiscoveries)
    ).toBeInTheDocument();
  });
});
