import { Formik } from "formik";

import ReleaseFormFields from "./ReleaseFormFields";

import { screen, renderWithProviders } from "@/testing/utils";

describe("ReleaseFormFields", () => {
  it("enables checkboxes for quick/secure erase if erasing is enabled", () => {
    renderWithProviders(
      <Formik
        initialValues={{
          enableErase: true,
          quickErase: false,
          secureErase: false,
        }}
        onSubmit={vi.fn()}
      >
        <ReleaseFormFields />
      </Formik>
    );

    expect(screen.getByLabelText(/Quick Erase/i)).toBeEnabled();
    expect(screen.getByLabelText(/Secure Erase/i)).toBeEnabled();
  });

  it("disables checkboxes for quick/secure erase if erasing is disabled", () => {
    renderWithProviders(
      <Formik
        initialValues={{
          enableErase: false,
          quickErase: false,
          secureErase: false,
        }}
        onSubmit={vi.fn()}
      >
        <ReleaseFormFields />
      </Formik>
    );

    expect(screen.getByLabelText(/Quick Erase/i)).toBeDisabled();
    expect(screen.getByLabelText(/Secure Erase/i)).toBeDisabled();
  });
});
