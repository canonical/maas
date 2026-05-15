import { DhcpEdit } from "./DhcpEdit";

import { Labels as DhcpFormFieldsLabels } from "@/app/base/components/DhcpFormFields/DhcpFormFields";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("DhcpEdit", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items: [
          factory.dhcpSnippet({
            id: 1,
          }),
          factory.dhcpSnippet({
            id: 2,
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("displays a loading component if loading", () => {
    state.dhcpsnippet.loading = true;
    state.dhcpsnippet.loaded = false;
    renderWithProviders(<DhcpEdit id={1} />, { state });
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("handles dhcp snippet not found", () => {
    renderWithProviders(<DhcpEdit id={99999} />, { state });
    expect(screen.getByText("DHCP snippet not found")).toBeInTheDocument();
  });

  it("can display a dhcp snippet edit form", () => {
    renderWithProviders(<DhcpEdit id={1} />, { state });
    expect(
      screen.getByRole("form", { name: "Editing `test snippet`" })
    ).toBeInTheDocument();

    expect(
      screen.getByRole("textbox", { name: DhcpFormFieldsLabels.Name })
    ).toHaveValue("test snippet");

    expect(
      screen.getByRole("textbox", { name: DhcpFormFieldsLabels.Description })
    ).toHaveValue("test description");

    expect(
      screen.getByRole("checkbox", { name: DhcpFormFieldsLabels.Enabled })
    ).not.toBeChecked();

    expect(
      screen.getByRole("textbox", { name: DhcpFormFieldsLabels.Value })
    ).toHaveValue("test value");
  });
});
