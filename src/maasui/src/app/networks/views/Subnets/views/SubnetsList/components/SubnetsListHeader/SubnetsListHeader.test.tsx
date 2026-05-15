import SubnetsListHeader from "./SubnetsListHeader";

import { renderWithProviders } from "@/testing/utils";

describe("SubnetListHeader", () => {
  it("sets the grouping parameter in the url to 'fabric' if one is not provided", async () => {
    const { router } = renderWithProviders(
      <SubnetsListHeader grouping="" searchText="" setSearchText={vi.fn()} />,
      {
        initialEntries: ["/networks/subnets"],
      }
    );

    expect(router.state.location.search).toBe("?by=fabric&q=");
  });

  it("includes the search text in the URL query parameters", async () => {
    const { router } = renderWithProviders(
      <SubnetsListHeader
        grouping=""
        searchText="test-search"
        setSearchText={vi.fn()}
      />,
      {
        initialEntries: ["/networks/subnets"],
      }
    );

    expect(router.state.location.search).toBe("?by=fabric&q=test-search");
  });
});
