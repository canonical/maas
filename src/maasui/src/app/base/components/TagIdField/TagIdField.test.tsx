import { Formik } from "formik";

import TagIdField from "./TagIdField";

import type { Tag } from "@/app/store/tag/types";
import * as factory from "@/testing/factories";
import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("TagIdField", () => {
  let tags: Tag[];

  beforeEach(() => {
    tags = [
      factory.tag({ id: 1, name: "tag1" }),
      factory.tag({ id: 2, name: "tag2" }),
    ];
  });

  it("maps the initial value to the tag format", () => {
    renderWithProviders(
      <Formik initialValues={{ tags: [2] }} onSubmit={vi.fn()}>
        <TagIdField tagList={tags} />
      </Formik>
    );

    expect(screen.getByRole("button", { name: "tag2" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "tag1" })
    ).not.toBeInTheDocument();
  });

  it("can override the field name", () => {
    renderWithProviders(
      <Formik initialValues={{ tags: null }} onSubmit={vi.fn()}>
        <TagIdField name="wombatTags" tagList={tags} />
      </Formik>
    );

    // The first element with this text is the div where the name is affected
    expect(screen.getAllByLabelText("Tags")[0]).toHaveAttribute(
      "name",
      "wombatTags"
    );
  });

  it("can populate the list of tags", async () => {
    renderWithProviders(
      <Formik initialValues={{ tags: null }} onSubmit={vi.fn()}>
        <TagIdField tagList={tags} />
      </Formik>
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getByRole("option", { name: "tag1" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "tag2" })).toBeInTheDocument();
  });
});
