import DoubleRow, { TestIds } from "./DoubleRow";

import { screen, renderWithProviders } from "@/testing/utils";

describe("DoubleRow ", () => {
  it("can render without a secondary row", () => {
    renderWithProviders(<DoubleRow primary="Top row" />);

    expect(screen.queryByTestId(TestIds.Secondary)).not.toBeInTheDocument();
  });

  it("can display an icon", () => {
    renderWithProviders(
      <DoubleRow
        icon={<i className="p-icon"></i>}
        primary="Top row"
        secondary="Bottom row"
      />
    );

    expect(screen.getByTestId(TestIds.Icon)).toBeInTheDocument();
    expect(screen.queryByTestId(TestIds.IconSpace)).not.toBeInTheDocument();
  });

  it("can display the space for an icon", () => {
    renderWithProviders(
      <DoubleRow iconSpace={true} primary="Top row" secondary="Bottom row" />
    );

    expect(screen.getByTestId(TestIds.Icon)).toBeInTheDocument();
    expect(screen.getByTestId(TestIds.IconSpace)).toBeInTheDocument();
  });

  it("can have a menu", () => {
    renderWithProviders(
      <DoubleRow
        menuLinks={[{ children: "Link1" }, { children: "Link2" }]}
        menuTitle="Take action:"
        primary="Top row"
        secondary="Bottom row"
      />
    );

    expect(
      screen.getByRole("button", { name: "Take action:" })
    ).toBeInTheDocument();
  });
});
