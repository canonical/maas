import { Formik } from "formik";

import IPMIPowerFields, {
  NONE_WORKAROUND_VALUE,
  WORKAROUNDS_FIELD_NAME,
} from "./IPMIPowerFields";

import type { PowerField } from "@/app/store/general/types";
import { PowerFieldType } from "@/app/store/general/types";
import * as factory from "@/testing/factories";
import { screen, waitFor, renderWithProviders } from "@/testing/utils";

let workaroundsField: PowerField;
beforeEach(() => {
  workaroundsField = factory.powerField({
    field_type: PowerFieldType.MULTIPLE_CHOICE,
    label: "Workaround flags",
    name: WORKAROUNDS_FIELD_NAME,
    choices: [
      ["one", "One"],
      [NONE_WORKAROUND_VALUE, "None"],
    ],
  });
});

it("does not render the 'None' choice for the workaround flags field", async () => {
  renderWithProviders(
    <Formik
      initialValues={{
        power_parameters: { [WORKAROUNDS_FIELD_NAME]: [] },
      }}
      onSubmit={vi.fn()}
    >
      <IPMIPowerFields fields={[workaroundsField]} />
    </Formik>
  );

  await waitFor(() => {
    expect(
      screen.queryByRole("checkbox", { name: "None" })
    ).not.toBeInTheDocument();
  });
  expect(screen.getByRole("checkbox", { name: "One" })).toBeInTheDocument();
});
