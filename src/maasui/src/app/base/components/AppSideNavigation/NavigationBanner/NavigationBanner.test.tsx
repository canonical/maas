import NavigationBanner from "./NavigationBanner";

import { screen, renderWithProviders } from "@/testing/utils";

afterEach(() => {
  vi.resetModules();
  vi.resetAllMocks();
});

it("displays a link to the homepage", () => {
  renderWithProviders(<NavigationBanner />, {});

  expect(screen.getByRole("link", { name: /Homepage/ })).toBeInTheDocument();
});
