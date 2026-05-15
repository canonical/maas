import { Formik } from "formik";

import FabricSelect, { Label } from "./FabricSelect";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, within, renderWithProviders } from "@/testing/utils";

describe("FabricSelect", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        items: [],
        loaded: true,
      }),
    });
  });

  it("is disabled if the fabrics haven't loaded", () => {
    state.fabric.loaded = false;

    renderWithProviders(
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <FabricSelect name="fabric" />
      </Formik>,
      { state }
    );

    expect(screen.getByRole("combobox", { name: Label.Select })).toBeDisabled();
  });

  it("displays the fabric options", () => {
    const items = [
      factory.fabric({ id: 1, name: "FABric1" }),
      factory.fabric({ id: 2, name: "FABric2" }),
    ];
    state.fabric.items = items;

    renderWithProviders(
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <FabricSelect name="fabric" />
      </Formik>,
      { state }
    );
    const options = screen.getAllByRole("option");

    expect(options[0]).toBeDisabled();
    expect(options[0]).toHaveValue("");
    expect(
      within(options[0]).getByText(Label.DefaultOption)
    ).toBeInTheDocument();
    expect(options[1]).toHaveValue(items[0].id.toString());
    expect(within(options[1]).getByText(items[0].name)).toBeInTheDocument();
    expect(options[2]).toHaveValue(items[1].id.toString());
    expect(within(options[2]).getByText(items[1].name)).toBeInTheDocument();
  });

  it("can display a default option", () => {
    const defaultOption = {
      label: "Default",
      value: "99",
    };
    renderWithProviders(
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <FabricSelect defaultOption={defaultOption} name="fabric" />
      </Formik>,
      { state }
    );
    const options = screen.getAllByRole("option");

    expect(options[0]).toHaveValue(defaultOption.value);
    expect(
      within(options[0]).getByText(defaultOption.label)
    ).toBeInTheDocument();
  });

  it("can hide the default option", () => {
    state.fabric.items = [];

    renderWithProviders(
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <FabricSelect defaultOption={null} name="fabric" />
      </Formik>,
      { state }
    );
    const options = screen.queryAllByRole("option");

    expect(options.length).toBe(0);
  });

  it("orders the fabrics by name", () => {
    const items = [
      factory.fabric({ id: 1, name: "FABric2" }),
      factory.fabric({ id: 2, name: "FABric1" }),
    ];
    state.fabric.items = items;

    renderWithProviders(
      <Formik initialValues={{ fabric: "" }} onSubmit={vi.fn()}>
        <FabricSelect name="fabric" />
      </Formik>,
      { state }
    );
    const options = screen.getAllByRole("option");

    expect(within(options[1]).getByText(items[1].name)).toBeInTheDocument();
    expect(within(options[2]).getByText(items[0].name)).toBeInTheDocument();
  });
});
