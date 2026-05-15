import { Formik } from "formik";

import TagNameField from "./TagNameField";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("FormikField", () => {
  it("maps the initial value to the tag format", () => {
    renderWithProviders(
      <Formik initialValues={{ tags: ["koala", "wallaby"] }} onSubmit={vi.fn()}>
        <TagNameField />
      </Formik>
    );
    expect(screen.getByRole("button", { name: "koala" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "wallaby" })).toBeInTheDocument();
  });

  it("can override the field name", () => {
    renderWithProviders(
      <Formik initialValues={{ tags: null }} onSubmit={vi.fn()}>
        <TagNameField name="wombatTags" />
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
        <TagNameField tagList={["koala", "wallaby"]} />
      </Formik>
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getByRole("option", { name: "koala" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "wallaby" })).toBeInTheDocument();
  });
});
