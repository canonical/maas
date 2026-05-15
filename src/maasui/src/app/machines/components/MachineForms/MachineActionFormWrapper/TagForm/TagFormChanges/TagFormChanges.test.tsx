import * as reduxToolkit from "@reduxjs/toolkit";
import { Formik } from "formik";

import TagFormChanges, { Label, RowType } from "./TagFormChanges";

import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import type { Tag } from "@/app/store/tag/types";
import * as factory from "@/testing/factories";
import { tagStateListFactory } from "@/testing/factories/state";
import {
  userEvent,
  screen,
  waitFor,
  within,
  renderWithProviders,
} from "@/testing/utils";

let state: RootState;
let tags: Tag[];
const commonProps = {
  selectedCount: 0,
  toggleTagDetails: vi.fn(),
};

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

beforeEach(() => {
  vi.spyOn(query, "generateCallId").mockReturnValue("mocked-nanoid");
  vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");
  tags = [
    factory.tag({ id: 1, name: "tag1" }),
    factory.tag({ id: 2, name: "tag2" }),
  ];

  state = factory.rootState({
    machine: factory.machineState({
      items: [
        factory.machine({ tags: [1] }),
        factory.machine({ tags: [1, 2] }),
      ],
    }),
    tag: factory.tagState({
      items: tags,
      lists: {
        "mocked-nanoid": tagStateListFactory({
          items: [
            factory.tag({ id: 1, name: "tag1" }),
            factory.tag({ id: 2, name: "tag2" }),
          ],
          loaded: true,
        }),
      },
    }),
  });
});

it("displays manual tags", () => {
  tags[0].definition = "";
  tags[1].definition = "";

  renderWithProviders(
    <Formik initialValues={{ added: [], removed: [] }} onSubmit={vi.fn()}>
      <TagFormChanges {...commonProps} newTags={[]} tags={tags} />
    </Formik>,
    { state }
  );
  const labelCell = screen.getByRole("cell", { name: Label.Manual });
  expect(labelCell).toBeInTheDocument();
  expect(labelCell).toHaveAttribute("rowSpan", "2");
  expect(screen.getByRole("row", { name: "tag1" })).toHaveAttribute(
    "data-testid",
    RowType.Manual
  );
  expect(screen.getByRole("row", { name: "tag2" })).toHaveAttribute(
    "data-testid",
    RowType.Manual
  );
});

it("displays automatic tags", () => {
  tags[0].definition = "def1";
  tags[1].definition = "def2";

  renderWithProviders(
    <Formik initialValues={{ added: [], removed: [] }} onSubmit={vi.fn()}>
      <TagFormChanges {...commonProps} newTags={[]} tags={tags} />
    </Formik>,
    { state }
  );
  const labelCell = screen.getByRole("cell", {
    name: new RegExp(Label.Automatic),
  });
  expect(labelCell).toBeInTheDocument();
  expect(labelCell).toHaveAttribute("rowSpan", "2");
  expect(screen.getByRole("row", { name: "tag1" })).toHaveAttribute(
    "data-testid",
    RowType.Auto
  );
  expect(screen.getByRole("row", { name: "tag2" })).toHaveAttribute(
    "data-testid",
    RowType.Auto
  );
});

it("displays added tags, with a 'NEW' prefix for newly created tags", () => {
  renderWithProviders(
    <Formik
      initialValues={{ added: [tags[0].id, tags[1].id], removed: [] }}
      onSubmit={vi.fn()}
    >
      <TagFormChanges {...commonProps} newTags={[tags[1].id]} tags={tags} />
    </Formik>,
    { state }
  );
  const labelCell = screen.getByRole("cell", {
    name: new RegExp(Label.Added),
  });
  const existingTagRow = screen.getByRole("row", { name: "tag1" });
  const newTagRow = screen.getByRole("row", { name: "tag2" });
  expect(labelCell).toBeInTheDocument();
  expect(labelCell).toHaveAttribute("rowSpan", "2");
  expect(existingTagRow).toHaveAttribute("data-testid", RowType.Added);
  expect(within(existingTagRow).queryByText("New")).not.toBeInTheDocument();
  expect(newTagRow).toHaveAttribute("data-testid", RowType.Added);
  expect(within(newTagRow).getByText("NEW")).toBeInTheDocument();
});

it("discards added tags", async () => {
  renderWithProviders(
    <Formik
      initialValues={{ added: [tags[0].id, tags[1].id], removed: [] }}
      onSubmit={vi.fn()}
    >
      <TagFormChanges {...commonProps} newTags={[]} tags={[]} />
    </Formik>,
    { state }
  );
  const row = screen.getByRole("row", { name: "tag1" });
  expect(row).toHaveAttribute("data-testid", RowType.Added);
  await userEvent.click(
    within(row).getByRole("button", { name: Label.Discard })
  );
  await waitFor(() => {
    expect(screen.queryByRole("row", { name: "tag1" })).not.toBeInTheDocument();
  });
});

it("displays a tag details modal when chips are clicked", async () => {
  const expectedTag = tags[0];
  expectedTag.name = "tag1";
  expectedTag.machine_count = 2;

  const handleToggleTagDetails = vi.fn();
  renderWithProviders(
    <Formik initialValues={{ added: [], removed: [] }} onSubmit={vi.fn()}>
      <TagFormChanges
        newTags={[]}
        selectedCount={2}
        tags={tags}
        toggleTagDetails={handleToggleTagDetails}
      />
    </Formik>,
    { state }
  );
  await userEvent.click(
    screen.getByRole("button", { name: `${expectedTag.name} (2/2)` })
  );
  expect(handleToggleTagDetails).toHaveBeenCalledWith(expectedTag);
});

it("can remove manual tags", async () => {
  renderWithProviders(
    <Formik initialValues={{ added: [], removed: [] }} onSubmit={vi.fn()}>
      <TagFormChanges {...commonProps} newTags={[]} tags={tags} />
    </Formik>,
    { state }
  );
  const tagName = "tag1";
  const manualRow = screen.getByRole("row", { name: tagName });
  expect(manualRow).toHaveAttribute("data-testid", RowType.Manual);
  await userEvent.click(
    within(manualRow).getByRole("button", { name: Label.Remove })
  );
  // Get the tag's new row.
  const updatedRow = screen.getByRole("row", { name: tagName });
  await waitFor(() => {
    expect(updatedRow).toHaveAttribute("data-testid", RowType.Removed);
  });
});

it("displays removed tags", () => {
  const tags = state.tag.items;

  renderWithProviders(
    <Formik
      initialValues={{ added: [], removed: [tags[0].id, tags[1].id] }}
      onSubmit={vi.fn()}
    >
      <TagFormChanges {...commonProps} newTags={[]} tags={[]} />
    </Formik>,
    { state }
  );
  const labelCell = screen.getByRole("cell", {
    name: new RegExp(Label.Removed),
  });
  expect(labelCell).toBeInTheDocument();
  expect(labelCell).toHaveAttribute("rowSpan", "2");
  expect(screen.getByRole("row", { name: "tag1" })).toHaveAttribute(
    "data-testid",
    RowType.Removed
  );
  expect(screen.getByRole("row", { name: "tag2" })).toHaveAttribute(
    "data-testid",
    RowType.Removed
  );
});

it("discards removed tags", async () => {
  renderWithProviders(
    <Formik
      initialValues={{ added: [], removed: [tags[0].id, tags[1].id] }}
      onSubmit={vi.fn()}
    >
      <TagFormChanges {...commonProps} newTags={[]} tags={tags} />
    </Formik>,
    { state }
  );
  const row = screen.getByRole("row", { name: "tag1" });
  expect(row).toHaveAttribute("data-testid", RowType.Removed);
  await userEvent.click(
    within(row).getByRole("button", { name: Label.Discard })
  );
  await waitFor(() => {
    expect(screen.queryByRole("row", { name: "tag1" })).toHaveAttribute(
      "data-testid",
      RowType.Manual
    );
  });
});

it("shows a message if no tags are assigned to the selected machines", () => {
  const state = factory.rootState({
    machine: factory.machineState({
      items: [factory.machine({ tags: [] }), factory.machine({ tags: [] })],
      loaded: true,
      loading: false,
    }),
    tag: factory.tagState({
      items: [factory.tag(), factory.tag()],
      loaded: true,
      loading: false,
    }),
  });

  renderWithProviders(
    <Formik initialValues={{ added: [], removed: [] }} onSubmit={vi.fn()}>
      <TagFormChanges {...commonProps} newTags={[]} tags={tags} />
    </Formik>,
    { state }
  );

  expect(screen.getByText(Label.NoTags)).toBeInTheDocument();
});
