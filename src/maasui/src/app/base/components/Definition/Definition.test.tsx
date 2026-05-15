import Definition from "./Definition";

import { screen, renderWithProviders } from "@/testing/utils";

it("renders term and description correctly", () => {
  renderWithProviders(
    <Definition description="description text" label="Term" />
  );
  expect(screen.getByText("description text")).toBeInTheDocument();
  expect(screen.getByText("Term")).toBeInTheDocument();
  expect(screen.getByText("description text")).toHaveAccessibleName("Term");
});

it("renders description provided as children correctly", () => {
  renderWithProviders(
    <Definition label="Term">description child text</Definition>
  );
  expect(screen.getByText("description child text")).toBeInTheDocument();
  expect(screen.getByText("Term")).toBeInTheDocument();
  expect(screen.getByText("description child text")).toHaveAccessibleName(
    "Term"
  );
});

it("renders multiple children correctly", () => {
  renderWithProviders(
    <Definition label="Term">
      <a href="#1">link1</a>
      <a href="#2">link2</a>
    </Definition>
  );
  expect(screen.getByRole("link", { name: "link1" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "link2" })).toBeInTheDocument();
  expect(screen.getByText("Term")).toBeInTheDocument();
});

it("displays alternative text with no description provided", () => {
  renderWithProviders(
    <Definition label="Term">
      {undefined}
      {null}
    </Definition>
  );
  expect(screen.getByText("Term")).toBeInTheDocument();
  expect(screen.getByText("—")).toBeInTheDocument();
});

it("displays alternative text for empty string as description", () => {
  renderWithProviders(<Definition label="Term">{""}</Definition>);
  expect(screen.getByText("Term")).toBeInTheDocument();
  expect(screen.getByText("—")).toBeInTheDocument();
});
