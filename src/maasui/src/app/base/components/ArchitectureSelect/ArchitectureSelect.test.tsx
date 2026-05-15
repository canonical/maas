import { Formik } from "formik";

import ArchitectureSelect, { Labels } from "./ArchitectureSelect";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("ArchitectureSelect", () => {
  it("dispatches action to fetch architectures on load", () => {
    const state = factory.rootState();

    const { store } = renderWithProviders(
      <Formik initialValues={{ architecture: "" }} onSubmit={vi.fn()}>
        <ArchitectureSelect name="architecture" />
      </Formik>,
      { state }
    );

    expect(
      store
        .getActions()
        .some((action) => action.type === "general/fetchArchitectures")
    ).toBe(true);
  });

  it("disables select if architectures have not loaded", () => {
    const state = factory.rootState({
      general: factory.generalState({
        architectures: factory.architecturesState({
          loaded: false,
        }),
      }),
    });

    renderWithProviders(
      <Formik initialValues={{ architecture: "" }} onSubmit={vi.fn()}>
        <ArchitectureSelect name="architecture" />
      </Formik>,
      { state }
    );

    expect(
      screen.getByRole("combobox", { name: Labels.DefaultLabel })
    ).toBeDisabled();
  });
});
