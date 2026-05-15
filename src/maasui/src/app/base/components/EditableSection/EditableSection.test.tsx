import EditableSection, { Labels } from "./EditableSection";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

it("can toggle showing content depending on editing state", async () => {
  renderWithProviders(
    <EditableSection
      canEdit
      renderContent={(editing) => (editing ? <div>Is editing</div> : null)}
      title="Title"
    />
  );

  expect(
    screen.getByRole("button", { name: Labels.EditButton })
  ).toBeInTheDocument();
  expect(screen.queryByText("Is editing")).not.toBeInTheDocument();

  await userEvent.click(
    screen.getByRole("button", { name: Labels.EditButton })
  );

  expect(
    screen.queryByRole("button", { name: Labels.EditButton })
  ).not.toBeInTheDocument();
  expect(screen.getByText("Is editing")).toBeInTheDocument();
});

it("does not show an edit button if content cannot be edited", () => {
  renderWithProviders(
    <EditableSection canEdit={false} renderContent={() => null} title="Title" />
  );

  expect(
    screen.queryByRole("button", { name: Labels.EditButton })
  ).not.toBeInTheDocument();
});
