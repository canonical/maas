import { Formik } from "formik";

import FormikFormButtons from "./FormikFormButtons";

import {
  userEvent,
  screen,
  waitFor,
  renderWithProviders,
} from "@/testing/utils";

it("can display a cancel button", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons onCancel={vi.fn()} submitLabel="Save user" />
    </Formik>
  );
  expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
});

it("can perform a secondary submit action if function and label provided", async () => {
  const secondarySubmit = vi.fn();
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons
        secondarySubmit={secondarySubmit}
        secondarySubmitLabel="Save and add another"
        submitLabel="Save user"
      />
    </Formik>
  );
  expect(screen.getByTestId("secondary-submit")).toHaveTextContent(
    "Save and add another"
  );
  await userEvent.click(
    screen.getByRole("button", { name: "Save and add another" })
  );
  expect(secondarySubmit).toHaveBeenCalled();
});

it("can generate a secondary submit label via a function", async () => {
  const secondarySubmit = vi.fn();
  renderWithProviders(
    <Formik initialValues={{ name: "Koala" }} onSubmit={vi.fn()}>
      <FormikFormButtons
        secondarySubmit={secondarySubmit}
        secondarySubmitLabel={({ name }) => `Kool ${name}`}
        submitLabel="Save user"
      />
    </Formik>
  );
  expect(screen.getByTestId("secondary-submit")).toHaveTextContent(
    "Kool Koala"
  );
  await userEvent.click(screen.getByRole("button", { name: "Kool Koala" }));
  expect(secondarySubmit).toHaveBeenCalled();
});

it("can display a tooltip for the secondary submit action", async () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons
        secondarySubmit={vi.fn()}
        secondarySubmitLabel="Save and add another"
        secondarySubmitTooltip="Will add another"
        submitLabel="Save user"
      />
    </Formik>
  );
  await userEvent.hover(
    screen.getByRole("button", { name: "Save and add another" })
  );

  await waitFor(() => {
    expect(
      screen.getByRole("button", { name: "Save and add another" })
    ).toHaveAccessibleDescription("Will add another");
  });

  await waitFor(() => {
    expect(
      screen.getByRole("tooltip", { name: "Will add another" })
    ).toBeInTheDocument();
  });
});

it("displays inline if inline is true", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons inline submitLabel="Save" />
    </Formik>
  );
  expect(screen.getByTestId("buttons-wrapper")).toHaveClass("is-inline");
});

it("displays help text if provided", () => {
  const buttonsHelp = <p>Help!</p>;
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons buttonsHelp={buttonsHelp} submitLabel="Save" />
    </Formik>
  );
  expect(screen.getByTestId("buttons-help")).toBeInTheDocument();
  expect(screen.getByTestId("buttons-help")).toHaveTextContent("Help!");
});

it("can fire custom onCancel function", async () => {
  const onCancel = vi.fn();
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons onCancel={onCancel} submitLabel="Save" />
    </Formik>
  );
  await userEvent.click(screen.getByTestId("cancel-action"));
  expect(onCancel).toHaveBeenCalled();
});

it("can display a saving label", () => {
  renderWithProviders(
    <Formik initialValues={{}} onSubmit={vi.fn()}>
      <FormikFormButtons saving savingLabel="Be patient!" submitLabel="Save" />
    </Formik>
  );
  expect(screen.getByTestId("saving-label")).toHaveTextContent("Be patient!");
});
