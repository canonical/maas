import TagsColumn from "./TagsColumn";

import { screen, renderWithProviders } from "@/testing/utils";

describe("TagsColumn", () => {
  it("displays the pod's tags", () => {
    const tags = ["tag1", "tag2"];
    renderWithProviders(<TagsColumn tags={tags} />);
    expect(screen.getByTestId("pod-tags")).toHaveTextContent("tag1, tag2");
  });
});
