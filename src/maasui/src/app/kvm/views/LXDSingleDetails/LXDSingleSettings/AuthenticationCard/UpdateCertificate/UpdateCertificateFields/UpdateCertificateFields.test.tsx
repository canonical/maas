import { Formik } from "formik";

import UpdateCertificateFields from "./UpdateCertificateFields";

import { Labels } from "@/app/base/components/CertificateFields/CertificateFields";
import * as factory from "@/testing/factories";
import { screen, waitFor, renderWithProviders } from "@/testing/utils";
describe("UpdateCertificateFields", () => {
  it("shows authentication fields if no certificate provided", async () => {
    renderWithProviders(
      <Formik
        initialValues={{ certificate: "", key: "", password: "" }}
        onSubmit={vi.fn()}
      >
        <UpdateCertificateFields
          generatedCertificate={null}
          setShouldGenerateCert={vi.fn()}
          shouldGenerateCert
        />
      </Formik>
    );
    await waitFor(() => {
      expect(screen.getByLabelText(Labels.Generate)).toBeInTheDocument();
    });
    expect(screen.queryByTestId("certificate-data")).not.toBeInTheDocument();
  });

  it("shows certificate data if certificate provided", () => {
    const generatedCertificate = factory.generatedCertificate();
    renderWithProviders(
      <Formik
        initialValues={{ certificate: "", key: "", password: "" }}
        onSubmit={vi.fn()}
      >
        <UpdateCertificateFields
          generatedCertificate={generatedCertificate}
          setShouldGenerateCert={vi.fn()}
          shouldGenerateCert
        />
      </Formik>
    );
    expect(screen.getByTestId("certificate-data")).toBeInTheDocument();
    expect(screen.queryByLabelText(Labels.Generate)).not.toBeInTheDocument();
  });
});
