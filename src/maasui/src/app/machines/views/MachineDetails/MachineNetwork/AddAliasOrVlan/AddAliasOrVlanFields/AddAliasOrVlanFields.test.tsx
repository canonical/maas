import { Formik } from "formik";

import AddAliasOrVlanFields from "./AddAliasOrVlanFields";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("AddAliasOrVlanFields", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState();
  });

  it("displays a tag field for a VLAN", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <AddAliasOrVlanFields
          interfaceType={NetworkInterfaceTypes.VLAN}
          nic={factory.machineInterface()}
          systemId="abc123"
        />
      </Formik>,
      { state }
    );
    expect(screen.getByRole("textbox", { name: "Tags" })).toBeInTheDocument();
  });

  it("does not display a tag field for an ALIAS", () => {
    renderWithProviders(
      <Formik initialValues={{}} onSubmit={vi.fn()}>
        <AddAliasOrVlanFields
          interfaceType={NetworkInterfaceTypes.ALIAS}
          nic={factory.machineInterface()}
          systemId="abc123"
        />
      </Formik>,
      { state }
    );
    expect(
      screen.queryByRole("textbox", { name: "Tags" })
    ).not.toBeInTheDocument();
  });
});
