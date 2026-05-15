/* eslint-disable testing-library/no-container */
import CoreResources from "./CoreResources";

import { render, screen, renderWithProviders } from "@/testing/utils";

describe("CoreResources", () => {
  it("renders correctly", () => {
    renderWithProviders(<CoreResources allocated={1} free={2} other={3} />);

    expect(
      screen.getByRole("heading", { name: /CPU cores/i })
    ).toBeInTheDocument();
  });

  it("can be made to have a dynamic layout", () => {
    const { container } = render(
      <CoreResources allocated={1} dynamicLayout free={2} />
    );

    expect(container.querySelector(".core-resources")).toHaveClass(
      "core-resources--dynamic-layout"
    );
  });

  it("renders the pinned core section if cores are provided as arrays", () => {
    renderWithProviders(<CoreResources allocated={[1]} free={[2]} />);

    expect(screen.getByText(/Pinned cores/)).toBeInTheDocument();
  });

  it("does not render the pinned core section if cores are provided as numbers", () => {
    renderWithProviders(<CoreResources allocated={1} free={2} />);

    expect(screen.queryByText(/Pinned cores/)).not.toBeInTheDocument();
  });
});
