import NotFound from "./NotFound";

import { renderWithProviders, screen } from "@/testing/utils";

describe("NotFound ", () => {
  it("can render", () => {
    renderWithProviders(<NotFound />, {});
    expect(screen.getByText(/Page not found/i)).toBeInTheDocument();

    expect(screen.queryByRole("section")).not.toBeInTheDocument();
  });

  it("can render in a row", () => {
    renderWithProviders(<NotFound includeSection />, {});
    expect(
      screen.getByRole("banner", { name: "main content" })
    ).toBeInTheDocument();
  });
});
