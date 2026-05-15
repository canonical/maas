import TitledSection from "./TitledSection";

import { screen, within, renderWithProviders } from "@/testing/utils";

it("displays the provided title and content", () => {
  const title = "echidna says";
  const content = "G'day";
  renderWithProviders(<TitledSection title={title}>{content}</TitledSection>);
  expect(screen.getByText(content)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: title })).toBeInTheDocument();
});

it("displays a section correctly labelled with the provided title", () => {
  const title = "echidna says";
  const content = "G'day";
  renderWithProviders(
    <TitledSection title={title}>
      <p>{content}</p>
    </TitledSection>
  );
  const section = screen.getByRole("region", { name: title });
  expect(within(section).getByText(content)).toBeInTheDocument();
});

it("sets the labelledby ids", () => {
  renderWithProviders(
    <TitledSection title="echidna says">G'day</TitledSection>
  );
  const sectionId = screen.getByRole("heading").id;
  expect(sectionId).toBeTruthy();
  expect(screen.getByTestId("titled-section")).toHaveAttribute(
    "aria-labelledby",
    sectionId
  );
});

it("can display buttons", () => {
  renderWithProviders(
    <TitledSection
      buttons={
        <>
          <button>Button</button>
          <button>Button</button>
        </>
      }
      title="echidna says"
    >
      G'day
    </TitledSection>
  );
  expect(screen.getAllByRole("button").length).toBe(2);
});

it("displays a custom heading level", () => {
  renderWithProviders(
    <TitledSection
      headingElement="h4"
      headingVisuallyHidden={true}
      title="echidna says"
    ></TitledSection>
  );

  expect(
    screen.getByRole("heading", { name: "echidna says", level: 4 })
  ).toBeInTheDocument();
});

it("adds a custom heading className", () => {
  renderWithProviders(
    <TitledSection headingClassName="u-no-margin--bottom" title="echidna says">
      G'day
    </TitledSection>
  );
  expect(screen.getByRole("heading")).toHaveAttribute(
    "class",
    "u-no-margin--bottom"
  );
});

it("can display a full span title", () => {
  renderWithProviders(<TitledSection hasSidebarTitle={false} title="Title" />);

  expect(screen.getByTestId("has-fullspan-title")).toBeInTheDocument();
  expect(screen.queryByTestId("has-sidebar-title")).not.toBeInTheDocument();
});

it("can display the title in a sidebar", () => {
  renderWithProviders(<TitledSection hasSidebarTitle title="Title" />);

  expect(screen.getByTestId("has-sidebar-title")).toBeInTheDocument();
  expect(screen.queryByTestId("has-fullspan-title")).not.toBeInTheDocument();
});
