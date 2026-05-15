import NonBreakingSpace from "./NonBreakingSpace";

import {
  screen,
  getDefaultNormalizer,
  renderWithProviders,
} from "@/testing/utils";

it("renders a non breaking space correctly", () => {
  renderWithProviders(
    <>
      1<NonBreakingSpace />2
    </>
  );
  expect(
    screen.getByText("1 2", {
      normalizer: getDefaultNormalizer({ collapseWhitespace: false }),
    })
  ).toBeInTheDocument();
  expect(screen.getByText("1 2")).toBeInTheDocument();
});
