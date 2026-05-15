import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Formik } from "formik";

import FormikField from "../FormikField";
import FormikForm from "../FormikForm";

import PrefixedIpInput from "./PrefixedIpInput";

import { renderWithProviders } from "@/testing/utils";

it("displays the correct range help text for an IPv4 subnet", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <PrefixedIpInput cidr="10.0.0.0/24" name="ip" />
    </Formik>
  );
  expect(
    screen.getByText(/The available range in this subnet is/i)
  ).toBeInTheDocument();
  expect(screen.getByText("10.0.0.[1-254]")).toBeInTheDocument();
});

it("displays the correct placeholder for an IPv4 subnet", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <PrefixedIpInput cidr="10.0.0.0/24" name="ip" />
    </Formik>
  );

  expect(screen.getByRole("textbox")).toHaveAttribute("placeholder", "[1-254]");
});

it("hides the range help text for an IPv6 subnet", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <PrefixedIpInput cidr="2001:db8::/32" name="ip" />
    </Formik>
  );

  expect(
    screen.queryByText(/The available range in this subnet is/i)
  ).not.toBeInTheDocument();
});

it("displays the correct placeholder for an IPv6 subnet", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <PrefixedIpInput cidr="2001:db8::/32" name="ip" />
    </Formik>
  );

  expect(screen.getByRole("textbox")).toHaveAttribute(
    "placeholder",
    "0000:0000:0000:0000:0000:0000"
  );
});

it("trims the immutable octets from a pasted IPv4 address", async () => {
  renderWithProviders(
    <FormikForm initialValues={{ ip: "" }} onSubmit={vi.fn()}>
      <FormikField cidr="10.0.0.0/24" component={PrefixedIpInput} name="ip" />
    </FormikForm>
  );

  await userEvent.click(screen.getByRole("textbox"));
  await userEvent.paste("10.0.0.1");

  expect(screen.getByRole("textbox")).toHaveValue("1");
});

it("trims the network address and subnet ID from a pasted IPv6 address", async () => {
  renderWithProviders(
    <FormikForm initialValues={{ ip: "" }} onSubmit={vi.fn()}>
      <FormikField cidr="2001:db8::/32" component={PrefixedIpInput} name="ip" />
    </FormikForm>
  );

  await userEvent.click(screen.getByRole("textbox"));
  await userEvent.paste("2001:db8::1");

  expect(screen.getByRole("textbox")).toHaveValue(":1");
});

it("displays provided help text instead of the IP address range", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <PrefixedIpInput
        cidr="10.0.0.0/24"
        help="A great song by the Beatles."
        name="ip"
      />
    </Formik>
  );

  expect(
    screen.queryByText(/The available range in this subnet is/i)
  ).not.toBeInTheDocument();
  expect(screen.queryByText("10.0.0.[1-254]")).not.toBeInTheDocument();

  expect(screen.getByText("A great song by the Beatles.")).toBeInTheDocument();
});
