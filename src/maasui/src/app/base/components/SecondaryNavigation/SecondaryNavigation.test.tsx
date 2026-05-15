import SecondaryNavigation from "./SecondaryNavigation";
import type { NavItem } from "./SecondaryNavigation";

import { renderWithProviders, screen } from "@/testing/utils";

describe("SecondaryNavigation", () => {
  const navItems: NavItem[] = [
    {
      label: "Item 1",
      path: "/item1",
    },
    {
      label: "Item 2",
      path: "/item2",
    },
  ];
  const title = "Test";

  it("renders correctly", () => {
    renderWithProviders(
      <SecondaryNavigation isOpen items={navItems} title={title} />
    );

    expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Item 1" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Item 2" })).toBeInTheDocument();
  });

  it("can set an active item", () => {
    renderWithProviders(
      <SecondaryNavigation isOpen items={navItems} title={title} />,
      { initialEntries: ["/item1"] }
    );

    expect(screen.getByRole("link", { name: "Item 1" })).toHaveClass(
      "is-active"
    );

    expect(screen.getByRole("link", { name: "Item 2" })).not.toHaveClass(
      "is-active"
    );
  });
});
