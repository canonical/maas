import { Formik } from "formik";

import MinimumKernelSelect, { Labels } from "./MinimumKernelSelect";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("MinimumKernelSelect", () => {
  it("dispatches action to fetch hwe kernels on load", () => {
    const state = factory.rootState();

    const { store } = renderWithProviders(
      <Formik initialValues={{ minKernel: "" }} onSubmit={vi.fn()}>
        <MinimumKernelSelect name="minKernel" />
      </Formik>,
      { state }
    );

    expect(
      store
        .getActions()
        .some((action) => action.type === "general/fetchHweKernels")
    ).toBe(true);
  });

  it("disables select if hwe kernels have not loaded", () => {
    const state = factory.rootState({
      general: factory.generalState({
        hweKernels: factory.hweKernelsState({
          loaded: false,
        }),
      }),
    });

    renderWithProviders(
      <Formik initialValues={{ minKernel: "" }} onSubmit={vi.fn()}>
        <MinimumKernelSelect name="minKernel" />
      </Formik>,
      { state }
    );

    expect(
      screen.getByRole("combobox", { name: Labels.Select })
    ).toBeDisabled();
  });
});
