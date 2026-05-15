import { screen } from "@testing-library/react";

import Placeholder from "./Placeholder";

import { renderWithProviders } from "@/testing/utils";

describe("Placeholder", () => {
  beforeEach(() => {
    vi.spyOn(Math, "floor").mockReturnValue(0);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders", () => {
    renderWithProviders(<Placeholder>Placeholder text</Placeholder>);
    expect(screen.getByTestId("placeholder")).toBeInTheDocument();
  });

  it("does not return placeholder styling if loading is false", () => {
    renderWithProviders(
      <Placeholder loading={false}>Placeholder text</Placeholder>
    );
    expect(screen.queryByTestId("placeholder")).not.toBeInTheDocument();
  });
});
