import SectionHeader from "./SectionHeader";

import { renderWithProviders, screen } from "@/testing/utils";

describe("SectionHeader", () => {
  it("can render title and subtitle", () => {
    renderWithProviders(<SectionHeader subtitle="Subtitle" title="Title" />);
    expect(screen.getByTestId("section-header-title")).toHaveTextContent(
      "Title"
    );
    expect(screen.getByTestId("section-header-subtitle")).toHaveTextContent(
      "Subtitle"
    );
  });

  it("displays the title as a h1 by default", () => {
    renderWithProviders(<SectionHeader title="Title" />);
    const title = screen.getByRole("heading", { level: 1, name: "Title" });
    expect(title).toBeInTheDocument();
    expect(title).toHaveClass("p-heading--4");
  });

  it("can change the title element", () => {
    renderWithProviders(<SectionHeader title="Title" titleElement="div" />);
    const title = screen.getByTestId("section-header-title");
    expect(
      screen.queryByRole("heading", { name: "Title" })
    ).not.toBeInTheDocument();
    expect(title).toBeInTheDocument();
    expect(title).toHaveTextContent("Title");
  });

  it("shows a spinner instead of title if loading", () => {
    renderWithProviders(
      <SectionHeader loading subtitle="Subtitle" title="Title" />
    );
    expect(
      screen.getByTestId("section-header-title-spinner")
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("section-header-title")
    ).not.toBeInTheDocument();
  });

  it("shows a spinner instead of subtitle if subtitle loading", () => {
    renderWithProviders(
      <SectionHeader subtitle="Subtitle" subtitleLoading title="Title" />
    );
    expect(screen.getByTestId("section-header-subtitle")).toHaveTextContent(
      "Loading"
    );
  });

  it("can render buttons", () => {
    const buttons = [
      <button key="button-1">Button 1</button>,
      <button key="button-2">Button 2</button>,
    ];
    renderWithProviders(<SectionHeader buttons={buttons} title="Title" />);
    expect(
      screen.getByRole("button", { name: "Button 1" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Button 2" })
    ).toBeInTheDocument();
  });

  it("can render tabs", () => {
    const tabLinks = [
      {
        active: true,
        label: "Tab 1",
        path: "/path1",
      },
      {
        active: false,
        label: "Tab 2",
        path: "/path2",
      },
    ];
    renderWithProviders(<SectionHeader tabLinks={tabLinks} title="Title" />);
    expect(screen.getByTestId("section-header-tabs")).toBeInTheDocument();
  });
});
