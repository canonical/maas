import { Formik } from "formik";

import DomainSelect, { Labels } from "./DomainSelect";

import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DomainSelect", () => {
  it("dispatches action to fetch domains on load", () => {
    const state = factory.rootState();

    const { store } = renderWithProviders(
      <Formik initialValues={{ domain: "" }} onSubmit={vi.fn()}>
        <DomainSelect name="domain" />
      </Formik>,
      { state }
    );

    expect(
      store.getActions().some((action) => action.type === "domain/fetch")
    ).toBe(true);
  });

  it("disables select if domains have not loaded", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        loaded: false,
      }),
    });

    renderWithProviders(
      <Formik initialValues={{ domain: "" }} onSubmit={vi.fn()}>
        <DomainSelect name="domain" />
      </Formik>,
      { state }
    );

    expect(
      screen.getByRole("combobox", { name: Labels.DefaultLabel })
    ).toBeDisabled();
  });
});
