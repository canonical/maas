import { Formik } from "formik";

import RecordFields, { Labels as RecordFieldsLabels } from "./RecordFields";

import { RecordType } from "@/app/store/domain/types";
import { screen, renderWithProviders } from "@/testing/utils";

describe("RecordFields", () => {
  it("disables record type field if in editing state", () => {
    renderWithProviders(
      <Formik initialValues={{ rrtype: RecordType.TXT }} onSubmit={vi.fn()}>
        <RecordFields editing />
      </Formik>
    );
    expect(
      screen.getByRole("combobox", { name: RecordFieldsLabels.Type })
    ).toBeDisabled();
  });
});
