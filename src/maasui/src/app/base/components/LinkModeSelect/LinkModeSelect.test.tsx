import { Formik } from "formik";

import LinkModeSelect, { Label } from "./LinkModeSelect";

import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import { LINK_MODE_DISPLAY } from "@/app/store/utils";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("LinkModeSelect", () => {
  it("only displays LINK_UP if a subnet is not provided", () => {
    const state = factory.rootState();
    renderWithProviders(
      <Formik initialValues={{ mode: "" }} onSubmit={vi.fn()}>
        <LinkModeSelect
          defaultOption={null}
          interfaceType={NetworkInterfaceTypes.PHYSICAL}
          name="mode"
          subnet={null}
        />
      </Formik>,
      { state }
    );

    expect(screen.getAllByRole("option").length).toBe(1);
    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.LINK_UP],
      })
    ).toBeInTheDocument();
  });

  it("can display all options", () => {
    const state = factory.rootState();
    renderWithProviders(
      <Formik initialValues={{ mode: "" }} onSubmit={vi.fn()}>
        <LinkModeSelect
          defaultOption={null}
          interfaceType={NetworkInterfaceTypes.PHYSICAL}
          name="mode"
          subnet={1}
        />
      </Formik>,
      { state }
    );

    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.AUTO],
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.STATIC],
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.LINK_UP],
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.DHCP],
      })
    ).toBeInTheDocument();
  });

  it("only displays auto or static for an alias", () => {
    const state = factory.rootState();
    renderWithProviders(
      <Formik initialValues={{ mode: "" }} onSubmit={vi.fn()}>
        <LinkModeSelect
          defaultOption={null}
          interfaceType={NetworkInterfaceTypes.ALIAS}
          name="mode"
          subnet={1}
        />
      </Formik>,
      { state }
    );

    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.AUTO],
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.STATIC],
      })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.LINK_UP],
      })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("option", {
        name: LINK_MODE_DISPLAY[NetworkLinkMode.DHCP],
      })
    ).not.toBeInTheDocument();
  });

  it("can display a default option", () => {
    const state = factory.rootState();
    const defaultOption = {
      label: "Default",
      value: "99",
    };
    renderWithProviders(
      <Formik initialValues={{ mode: "" }} onSubmit={vi.fn()}>
        <LinkModeSelect
          defaultOption={defaultOption}
          interfaceType={NetworkInterfaceTypes.PHYSICAL}
          name="mode"
        />
      </Formik>,
      { state }
    );

    expect(screen.getByRole("option", { name: "Default" })).toBeInTheDocument();
  });

  it("can hide the default option", () => {
    const state = factory.rootState();
    renderWithProviders(
      <Formik initialValues={{ mode: "" }} onSubmit={vi.fn()}>
        <LinkModeSelect
          defaultOption={null}
          interfaceType={NetworkInterfaceTypes.PHYSICAL}
          name="mode"
        />
      </Formik>,
      { state }
    );

    expect(
      screen.queryByRole("option", { name: Label.DefaultOption })
    ).not.toBeInTheDocument();
  });
});
