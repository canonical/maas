import { Formik } from "formik";

import BridgeFormFields from "./BridgeFormFields";

import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("BridgeFormFields", () => {
  it("does not display the fd field if stp isn't on", async () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BridgeFormFields />
      </Formik>
    );
    expect(
      screen.queryByRole("textbox", { name: "Forward delay (ms)" })
    ).not.toBeInTheDocument();
  });

  it("displays the fd field if stp is on", async () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BridgeFormFields />
      </Formik>
    );

    await userEvent.click(screen.getByRole("checkbox", { name: "STP" }));
    expect(
      screen.getByRole("textbox", { name: "Forward delay (ms)" })
    ).toBeInTheDocument();
  });
});
