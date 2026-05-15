import type { Tag } from "./TagSelector";
import TagSelector from "./TagSelector";

import {
  screen,
  userEvent,
  within,
  renderWithProviders,
} from "@/testing/utils";

describe("TagSelector", () => {
  let tags: Tag[];
  beforeEach(() => {
    tags = [
      { displayName: "tag one", name: "tag1" },
      { displayName: "tag two", name: "tag2" },
    ];
  });

  it("doesn't show tags when closed", () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    expect(screen.getByRole("textbox", { name: "Tags" })).toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "tag one" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", { name: "tag two" })
    ).not.toBeInTheDocument();
  });

  it("shows tags when opened", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getByRole("option", { name: "tag one" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "tag two" })).toBeInTheDocument();
  });

  it("shows tag descriptions if present", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={[
          { ...tags[0], description: "description one" },
          { ...tags[1], description: "description two" },
        ]}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(
      within(screen.getByRole("option", { name: "tag one" })).getByText(
        "description one"
      )
    ).toBeInTheDocument();
    expect(
      within(screen.getByRole("option", { name: "tag two" })).getByText(
        "description two"
      )
    ).toBeInTheDocument();
  });

  it("can have some tags preselected", () => {
    renderWithProviders(
      <TagSelector
        initialSelected={[tags[0]]}
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    expect(screen.getByTestId("selected-tag")).toHaveTextContent("tag1");
  });

  it("opens the dropdown when input is focused", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
  });

  it("can select existing tags from dropdown", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    await userEvent.click(screen.getAllByTestId("existing-tag")[0]);
    expect(screen.getByTestId("selected-tag")).toHaveTextContent("tag1");
  });

  it("can hide the tags that have been selected", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        showSelectedTags={false}
        tags={tags}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    await userEvent.click(screen.getAllByTestId("existing-tag")[0]);
    expect(screen.queryByTestId("selected-tag")).not.toBeInTheDocument();
  });

  it("can remove tags that have been selected", async () => {
    renderWithProviders(
      <TagSelector
        initialSelected={tags}
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    expect(screen.getAllByTestId("selected-tag")).toHaveLength(2);
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    await userEvent.click(screen.getAllByTestId("selected-tag")[0]);
    expect(screen.getAllByTestId("selected-tag")).toHaveLength(1);
    expect(screen.getAllByTestId("selected-tag")[0]).toHaveTextContent("tag2");
  });

  it("can create and select a new tag", async () => {
    renderWithProviders(
      <TagSelector
        allowNewTags
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Tags" }),
      "new-tag"
    );
    await userEvent.click(screen.getByTestId("new-tag"));
    expect(screen.getAllByTestId("selected-tag")[0]).toHaveTextContent(
      "new-tag"
    );
  });

  it("can call a provide function to create a new tag", async () => {
    const onAddNewTag = vi.fn();
    renderWithProviders(
      <TagSelector
        allowNewTags
        label="Tags"
        onAddNewTag={onAddNewTag}
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Tags" }),
      "new-tag"
    );
    await userEvent.click(screen.getByTestId("new-tag"));
    expect(onAddNewTag).toHaveBeenCalledWith("new-tag");
    // The input should get cleared.
    expect(screen.getByRole("textbox", { name: "Tags" })).toHaveValue("");
  });

  it("sanitises text when creating new tag", async () => {
    renderWithProviders(
      <TagSelector
        allowNewTags
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={tags}
      />
    );
    await userEvent.type(
      screen.getByRole("textbox", { name: "Tags" }),
      "Tag with spaces"
    );
    await userEvent.click(screen.getByTestId("new-tag"));
    expect(screen.getByTestId("selected-tag")).toHaveTextContent(
      "Tag-with-spaces"
    );
  });

  it("can filter tag list", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={[...tags, { displayName: "other", name: "other" }]}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getAllByTestId("existing-tag")).toHaveLength(3);
    await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "tag");
    expect(screen.getAllByTestId("existing-tag")).toHaveLength(2);
  });

  it("can highlight what matches the filter in existing tags", async () => {
    renderWithProviders(
      <TagSelector
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        tags={[
          { displayName: "there", name: "there" },
          { displayName: "other", name: "other" },
        ]}
      />
    );
    await userEvent.type(screen.getByRole("textbox", { name: "Tags" }), "the");
    expect(screen.getAllByTestId("existing-tag")[0]).toHaveTextContent("there");
    // This child is the <strong> element that highlights the text
    expect(
      screen.getAllByTestId("existing-tag")[0].firstChild?.firstChild
    ).toHaveTextContent("the");

    expect(screen.getAllByTestId("existing-tag")[1]).toHaveTextContent("other");
    // This child is the <strong> element that highlights the text
    expect(
      screen.getAllByTestId("existing-tag")[1].firstChild?.firstChild
    ).toHaveTextContent("the");
  });

  it("can disable tags", () => {
    const tags = [
      { id: 1, name: "enabledTag" },
      { id: 2, name: "disabledTag" },
    ];
    renderWithProviders(
      <TagSelector
        disabledTags={[{ id: 2, name: "disabledTag" }]}
        initialSelected={tags}
        tags={tags}
      />
    );

    expect(screen.getAllByTestId("selected-tag")[0]).not.toBeAriaDisabled();
    expect(screen.getAllByTestId("selected-tag")[1]).toBeAriaDisabled();
  });

  it("can display a dropdown header", async () => {
    renderWithProviders(
      <TagSelector
        header={<span data-testid="dropdown-header">A header</span>}
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        showSelectedTags={false}
        tags={tags}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getByTestId("dropdown-header")).toHaveTextContent("A header");
    expect(screen.getByTestId("dropdown-header").parentElement).toHaveClass(
      "tag-selector__dropdown-header"
    );
  });

  it("can customise the dropdown items", async () => {
    renderWithProviders(
      <TagSelector
        generateDropdownEntry={() => (
          <span data-testid="dropdown-item">An item</span>
        )}
        label="Tags"
        onTagsUpdate={vi.fn()}
        placeholder="Select or create tags"
        showSelectedTags={false}
        tags={tags}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getAllByTestId("dropdown-item")[0]).toHaveTextContent(
      "An item"
    );
  });

  it("can use an external list of selected tags", () => {
    renderWithProviders(
      <TagSelector
        externalSelectedTags={[tags[0]]}
        label="Tags"
        onTagsUpdate={vi.fn()}
        tags={tags}
      />
    );
    expect(screen.getAllByTestId("selected-tag")[0]).toHaveTextContent("tag1");
  });

  it("handles selecting external tags", async () => {
    const onTagsUpdate = vi.fn();
    renderWithProviders(
      <TagSelector
        externalSelectedTags={[tags[0]]}
        label="Tags"
        onTagsUpdate={onTagsUpdate}
        tags={tags}
      />
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    await userEvent.click(screen.getAllByTestId("existing-tag")[0]);
    expect(onTagsUpdate).toHaveBeenCalledWith([tags[0], tags[1]]);
  });
});
