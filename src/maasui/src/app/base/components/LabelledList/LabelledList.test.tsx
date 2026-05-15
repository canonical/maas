import LabelledList from "./LabelledList";

import { screen, renderWithProviders } from "@/testing/utils";

describe("LabelledList ", () => {
  it("can add additional classes", () => {
    renderWithProviders(<LabelledList className="extra-class" items={[]} />);

    expect(screen.getByRole("list")).toHaveClass("p-list--labelled");
    expect(screen.getByRole("list")).toHaveClass("extra-class");
  });
});
