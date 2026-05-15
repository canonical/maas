import { Formik } from "formik";

import UpdateTagFormFields from "./UpdateTagFormFields";

import type { RootState } from "@/app/store/root/types";
import { Label as DefinitionLabel } from "@/app/tags/components/DefinitionField";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

let state: RootState;

beforeEach(() => {
  state = factory.rootState({
    tag: factory.tagState({
      items: [
        factory.tag({
          id: 1,
          name: "rad",
        }),
      ],
    }),
  });
});

it("hides the definition field if it is a manual tag", async () => {
  state.tag.items[0].definition = "";
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <UpdateTagFormFields id={1} />
    </Formik>,
    { state }
  );
  expect(
    screen.queryByRole("textbox", { name: DefinitionLabel.Definition })
  ).not.toBeInTheDocument();
  expect(
    screen.getByText(/Definitions cannot be added to manual tags/i)
  ).toBeInTheDocument();
});

it("displays the definition field if it is an automatic tag", async () => {
  state.tag.items[0].definition = "def1";
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <UpdateTagFormFields id={1} />
    </Formik>,
    { state }
  );
  expect(
    screen.getByRole("textbox", { name: DefinitionLabel.Definition })
  ).toBeInTheDocument();
  expect(
    screen.queryByText(/Definitions cannot be added to manual tags/i)
  ).not.toBeInTheDocument();
});
