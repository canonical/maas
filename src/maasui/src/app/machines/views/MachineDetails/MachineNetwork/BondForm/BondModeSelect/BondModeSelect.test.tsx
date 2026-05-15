import { Formik } from "formik";

import BondModeSelect from "./BondModeSelect";

import { BondMode } from "@/app/store/general/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, within, renderWithProviders } from "@/testing/utils";

describe("BondModeSelect", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        bondOptions: factory.bondOptionsState({
          data: factory.bondOptions({
            modes: [
              [BondMode.BALANCE_RR, BondMode.BALANCE_RR],
              [BondMode.ACTIVE_BACKUP, BondMode.ACTIVE_BACKUP],
              [BondMode.BALANCE_XOR, BondMode.BALANCE_XOR],
              [BondMode.BROADCAST, BondMode.BROADCAST],
              [BondMode.LINK_AGGREGATION, BondMode.LINK_AGGREGATION],
              [BondMode.BALANCE_TLB, BondMode.BALANCE_TLB],
              [BondMode.BALANCE_ALB, BondMode.BALANCE_ALB],
            ],
          }),
          loaded: true,
        }),
      }),
    });
  });

  it("shows a spinner if the bond options haven't loaded", () => {
    state.general.bondOptions.loaded = false;
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BondModeSelect name="mode" />
      </Formik>,
      { state }
    );
    expect(screen.getByText("Loading")).toBeInTheDocument();
  });

  it("displays the options", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BondModeSelect name="mode" />
      </Formik>,
      { state }
    );

    const bondModeSelect = screen.getByRole("combobox", { name: "Bond mode" });
    const bondModeOptions = within(bondModeSelect).getAllByRole("option");
    const expectedOptions = [
      { label: "Select bond mode", value: "" },
      {
        label: BondMode.BALANCE_RR,
        value: BondMode.BALANCE_RR,
      },
      {
        label: BondMode.ACTIVE_BACKUP,
        value: BondMode.ACTIVE_BACKUP,
      },
      {
        label: BondMode.BALANCE_XOR,
        value: BondMode.BALANCE_XOR,
      },
      {
        label: BondMode.BROADCAST,
        value: BondMode.BROADCAST,
      },
      {
        label: BondMode.LINK_AGGREGATION,
        value: BondMode.LINK_AGGREGATION,
      },
      {
        label: BondMode.BALANCE_TLB,
        value: BondMode.BALANCE_TLB,
      },
      {
        label: BondMode.BALANCE_ALB,
        value: BondMode.BALANCE_ALB,
      },
    ];

    for (let i = 0; i < expectedOptions.length; i++) {
      expect(bondModeOptions[i]).toHaveValue(expectedOptions[i].value);
      expect(bondModeOptions[i]).toHaveTextContent(expectedOptions[i].label);
    }
  });

  it("can display a default option", () => {
    const defaultOption = {
      label: "Default",
      value: "99",
    };
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BondModeSelect defaultOption={defaultOption} name="mode" />
      </Formik>,
      { state }
    );

    const bondModeSelect = screen.getByRole("combobox", { name: "Bond mode" });
    const bondModeOptions = within(bondModeSelect).getAllByRole("option");

    expect(bondModeOptions[0]).toHaveValue(defaultOption.value);
    expect(bondModeOptions[0]).toHaveTextContent(defaultOption.label);
  });

  it("can hide the default option", () => {
    state.general.bondOptions = factory.bondOptionsState({
      data: undefined,
      loaded: true,
    });
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <BondModeSelect defaultOption={null} name="mode" />
      </Formik>,
      { state }
    );
    const bondModeSelect = screen.getByRole("combobox", { name: "Bond mode" });
    const bondModeOptions = within(bondModeSelect).queryAllByRole("option");

    expect(bondModeOptions).toHaveLength(0);
  });
});
