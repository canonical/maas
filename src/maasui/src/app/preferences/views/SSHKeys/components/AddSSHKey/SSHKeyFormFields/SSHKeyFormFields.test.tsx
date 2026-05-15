import { Formik } from "formik";

import SSHKeyFormFields from "./SSHKeyFormFields";

import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("SSHKeyFormFields", () => {
  it("can render", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <SSHKeyFormFields />
      </Formik>
    );
    expect(
      screen.getByRole("combobox", { name: "Source" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Launchpad" })
    ).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "GitHub" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Upload" })).toBeInTheDocument();
    expect(screen.getByText("About SSH keys")).toBeInTheDocument();
  });

  it("can show id field", async () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <SSHKeyFormFields />
      </Formik>
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Source" }),
      "lp"
    );
    expect(
      screen.getByRole("textbox", { name: "Launchpad ID" })
    ).toBeInTheDocument();
  });

  it("can show key field", async () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <SSHKeyFormFields />
      </Formik>
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Source" }),
      "upload"
    );
    expect(
      screen.getByRole("textbox", { name: "Public key" })
    ).toBeInTheDocument();
  });
});
