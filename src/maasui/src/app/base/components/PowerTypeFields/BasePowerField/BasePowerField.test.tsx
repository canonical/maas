import { Formik } from "formik";

import BasePowerField from "./BasePowerField";

import { PowerFieldType } from "@/app/store/general/types";
import * as factory from "@/testing/factories";
import { screen, userEvent, renderWithProviders } from "@/testing/utils";

describe("BasePowerField", () => {
  it("can be given a custom power parameters name", () => {
    const field = factory.powerField({ name: "field-name" });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField
          field={field}
          powerParametersValueName="custom-power-parameters"
        />
      </Formik>
    );
    expect(
      screen.getByRole("textbox", { name: "test-powerfield-label-1" })
    ).toHaveAttribute("name", "custom-power-parameters.field-name");
  });

  it("correctly renders a string field type", () => {
    const field = factory.powerField({ field_type: PowerFieldType.STRING });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).not.toHaveAttribute("type", "password");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("correctly renders a IP address field type", () => {
    const field = factory.powerField({ field_type: PowerFieldType.IP_ADDRESS });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).not.toHaveAttribute("type", "password");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("correctly renders a Virsh address field type", () => {
    const field = factory.powerField({
      field_type: PowerFieldType.VIRSH_ADDRESS,
    });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).not.toHaveAttribute("type", "password");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("correctly renders a LXD address field type", () => {
    const field = factory.powerField({
      field_type: PowerFieldType.LXD_ADDRESS,
    });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.getByRole("textbox")).toBeInTheDocument();
    expect(screen.getByRole("textbox")).not.toHaveAttribute("type", "password");
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("correctly renders a password field type", () => {
    const field = factory.powerField({
      field_type: PowerFieldType.PASSWORD,
      label: "Password",
    });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "type",
      "password"
    );
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("correctly renders a choice field type", () => {
    const field = factory.powerField({ field_type: PowerFieldType.CHOICE });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });

  it("correctly handles a multiple choice field type", async () => {
    const field = factory.powerField({
      choices: [
        ["value1", "label1"],
        ["value2", "label2"],
      ],
      field_type: PowerFieldType.MULTIPLE_CHOICE,
      label: "label",
      name: "field",
    });
    renderWithProviders(
      <Formik
        initialValues={{ power_parameters: { field: ["value1"] } }}
        onSubmit={vi.fn()}
      >
        <BasePowerField field={field} />
      </Formik>
    );
    expect(screen.getByTestId("field-label")).toHaveTextContent("label");
    expect(screen.getAllByRole("checkbox")[0]).toBeChecked();
    expect(screen.getAllByRole("checkbox")[1]).not.toBeChecked();

    await userEvent.click(screen.getAllByRole("checkbox")[0]);
    await userEvent.click(screen.getAllByRole("checkbox")[1]);

    expect(screen.getAllByRole("checkbox")[0]).not.toBeChecked();
    expect(screen.getAllByRole("checkbox")[1]).toBeChecked();
  });
});
