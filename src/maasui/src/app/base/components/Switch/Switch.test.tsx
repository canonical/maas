import { screen } from "@testing-library/react";

import Switch from "./Switch";

import { renderWithProviders } from "@/testing/utils";

describe("Switch", () => {
  it("renders", () => {
    renderWithProviders(<Switch />);

    expect(screen.getByRole("checkbox")).toBeInTheDocument();
  });
});
