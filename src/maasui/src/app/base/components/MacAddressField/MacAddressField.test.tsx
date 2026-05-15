import { Formik } from "formik";

import MacAddressField from "./MacAddressField";

import * as factory from "@/testing/factories";
import { userEvent, screen, renderWithProviders } from "@/testing/utils";

describe("MacAddressField", () => {
  it("formats text as it is typed", async () => {
    const state = factory.rootState();
    renderWithProviders(
      <Formik initialValues={{ mac_address: "" }} onSubmit={vi.fn()}>
        <MacAddressField label="MAC address" name="mac_address" />
      </Formik>,
      { state }
    );
    const textbox = screen.getByRole("textbox", { name: "MAC address" });

    await userEvent.type(textbox, "1a2");

    expect(textbox).toHaveValue("1a:2");
  });
});
