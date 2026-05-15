import TagTable, { Label, TestId } from "./TagTable";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import { TagSearchFilter } from "@/app/store/tag/selectors";
import type { Tag } from "@/app/store/tag/types";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

vi.mock("../constants", () => ({
  __esModule: true,
  // Mock the number of items per page to allow testing pagination.
  TAGS_PER_PAGE: 2,
}));

let state: RootState;
let tags: Tag[];

beforeEach(() => {
  tags = [
    factory.tag({
      id: 1,
      name: "rad",
    }),
    factory.tag({
      id: 2,
      name: "cool",
    }),
  ];
  state = factory.rootState({
    tag: factory.tagState({
      items: tags,
    }),
  });
});

it("displays tags", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );

  expect(screen.getAllByRole("row")).toHaveLength(3);
  expect(screen.getByText("rad")).toBeInTheDocument();
  expect(screen.getByText("cool")).toBeInTheDocument();
});

it("displays the right columns", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />
  );
  [
    "Tag name ascending",
    "Last update",
    "Auto information",
    "Applied to",
    "Kernel options",
    "Actions",
  ].forEach((column) => {
    expect(
      screen.getByRole("columnheader", { name: new RegExp(`^${column}`, "i") })
    ).toBeInTheDocument();
  });
});

it("displays the tags in order", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />
  );
  expect(
    within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]
  ).toHaveTextContent("cool");
  expect(
    within(screen.getAllByRole("row")[2]).getAllByRole("cell")[0]
  ).toHaveTextContent("rad");
});

it("can change the sort order", async () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );

  expect(
    within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]
  ).toHaveTextContent("cool");
  expect(
    within(screen.getAllByRole("row")[2]).getAllByRole("cell")[0]
  ).toHaveTextContent("rad");
  await userEvent.click(
    screen.getByRole("button", { name: `${Label.Name} ascending` })
  );

  expect(
    within(screen.getAllByRole("row")[1]).getAllByRole("cell")[0]
  ).toHaveTextContent("rad");
  expect(
    within(screen.getAllByRole("row")[2]).getAllByRole("cell")[0]
  ).toHaveTextContent("cool");
});

it("shows an icon for automatic tags", () => {
  tags = [factory.tag({ definition: "automatic" })];
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );

  expect(
    within(screen.getAllByRole("row")[1]).getAllByRole("cell")[2].firstChild
  ).toHaveClass("p-icon--success-grey");
});

it("does not show an icon for manual tags", () => {
  tags = [factory.tag({ definition: undefined })];
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );

  expect(
    within(screen.getAllByRole("row")[1]).queryAllByRole("cell")[2].firstChild
  ).toBeNull();
});

it("shows an icon for kernel options", () => {
  tags = [factory.tag({ kernel_opts: "i'm a kernel option" })];
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );

  expect(
    within(screen.getAllByRole("row")[1]).getAllByRole("cell")[4].firstChild
  ).toHaveClass("p-icon--success-grey");
});

it("does not show an icon for tags without kernel options", () => {
  tags = [factory.tag({ kernel_opts: undefined })];
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );

  expect(
    within(screen.getAllByRole("row")[1]).queryAllByRole("cell")[4].firstChild
  ).toBeNull();
});

it("can link to nodes", () => {
  tags = [
    factory.tag({
      machine_count: 1,
      device_count: 2,
      controller_count: 3,
      name: "a-tag",
    }),
  ];
  state.tag.items = tags;
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );
  const row = screen.getByRole("row", { name: /a-tag/i });

  expect(within(row).getByRole("link", { name: "1 machine" })).toHaveAttribute(
    "href",
    `${urls.machines.index}?tags=%3Da-tag`
  );

  expect(within(row).getByRole("link", { name: "2 devices" })).toHaveAttribute(
    "href",
    `${urls.devices.index}?tags=%3Da-tag`
  );

  expect(
    within(row).getByRole("link", { name: "3 controllers" })
  ).toHaveAttribute("href", `${urls.controllers.index}?tags=%3Da-tag`);
});

it("does not display a message if there are tags", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={tags}
    />,
    { state }
  );
  expect(screen.queryByTestId(TestId.NoTags)).not.toBeInTheDocument();
});

it("displays a message if there are no automatic tags", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.Auto}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={[]}
    />,
    { state }
  );
  expect(screen.getByTestId(TestId.NoTags).textContent).toBe(
    "There are no automatic tags."
  );
});

it("displays a message if there are no manual tags", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.Manual}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText=""
      tags={[]}
    />,
    { state }
  );
  expect(screen.getByTestId(TestId.NoTags).textContent).toBe(
    "There are no manual tags."
  );
});

it("displays a message if none match the search terms", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText="nothing"
      tags={[]}
    />,
    { state }
  );
  expect(screen.getByTestId(TestId.NoTags).textContent).toBe(
    "No tags match the search criteria."
  );
});

it("displays a message if none match the filter and search terms", () => {
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.Auto}
      onDelete={vi.fn()}
      onUpdate={vi.fn()}
      searchText="nothing"
      tags={[]}
    />,
    { state }
  );
  expect(screen.getByTestId(TestId.NoTags).textContent).toBe(
    "No automatic tags match the search criteria."
  );
});

it("can trigger the tag edit sidepanel", async () => {
  const onUpdate = vi.fn();
  renderWithProviders(
    <TagTable
      filter={TagSearchFilter.All}
      onDelete={vi.fn()}
      onUpdate={onUpdate}
      searchText=""
      tags={tags}
    />,
    { state, initialEntries: [urls.tags.index] }
  );
  await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);
  expect(onUpdate).toHaveBeenCalled();
});
