import { Formik } from "formik";

import TagField from "./TagField";

import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("TagField", () => {
  it("sorts the tags by name", async () => {
    const initialValues = { tags: null };
    renderWithProviders(
      <Formik initialValues={initialValues} onSubmit={vi.fn()}>
        <TagField
          name="wombatTags"
          tags={[
            {
              name: "wallaby",
            },
            {
              name: "koala",
            },
          ]}
        />
      </Formik>
    );
    await userEvent.click(screen.getByRole("textbox", { name: "Tags" }));
    expect(screen.getAllByRole("option")).toHaveLength(2);
    expect(screen.getByRole("option", { name: "koala" })).toBeInTheDocument();

    expect(screen.getByRole("option", { name: "wallaby" })).toBeInTheDocument();
  });
});
