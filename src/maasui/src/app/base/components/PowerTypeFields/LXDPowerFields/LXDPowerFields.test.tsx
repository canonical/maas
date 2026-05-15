import { Formik } from "formik";

import LXDPowerFields from "./LXDPowerFields";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("LXDPowerFields", () => {
  it("can be given a custom power parameters name", () => {
    const field = factory.powerField({ name: "field", label: "custom field" });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <LXDPowerFields
          fields={[field]}
          powerParametersValueName="custom-power-parameters"
        />
      </Formik>
    );
    expect(screen.getByLabelText("custom field")).toHaveAttribute(
      "name",
      "custom-power-parameters.field"
    );
  });

  it("renders certificate fields if the user can edit them", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <LXDPowerFields canEditCertificate fields={[]} />
      </Formik>
    );

    expect(
      screen.getByLabelText(/Generate new certificate/i)
    ).toBeInTheDocument();
  });

  it("does not render certificate fields if the user cannot edit them", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <LXDPowerFields canEditCertificate={false} fields={[]} />
      </Formik>
    );

    expect(
      screen.queryByLabelText(/Generate new certificate/i)
    ).not.toBeInTheDocument();
  });
});
