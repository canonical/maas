import VisuallyHidden from "./VisuallyHidden";

import { screen, renderWithProviders } from "@/testing/utils";

it("renders children correctly", () => {
  renderWithProviders(<VisuallyHidden>test content</VisuallyHidden>);
  expect(screen.getByText("test content")).toBeInTheDocument();
});
