import SearchBox from "./SearchBox";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

it("focuses on the search box when pressing '/' key", async () => {
  renderWithProviders(<SearchBox />);
  const searchBox = screen.getByRole("searchbox");
  expect(searchBox).not.toHaveFocus();
  await userEvent.type(document.body, "/");
  expect(searchBox).toHaveFocus();
});
