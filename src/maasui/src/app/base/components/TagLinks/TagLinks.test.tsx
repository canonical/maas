import TagLinks from "./TagLinks";

import { screen, renderWithProviders } from "@/testing/utils";

describe("TagLinks", () => {
  it("displays tag links", () => {
    renderWithProviders(
      <TagLinks
        getLinkURL={(tag) => `www.tags.com/${tag}`}
        tags={["tag-1", "tag-2"]}
      />
    );

    expect(screen.getByRole("link", { name: "tag-1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "tag-2" })).toBeInTheDocument();
  });
});
