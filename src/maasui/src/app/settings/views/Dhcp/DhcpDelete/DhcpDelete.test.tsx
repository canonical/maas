import DhcpDelete from "./DhcpDelete";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("DhcpDelete", () => {
  const snippet = factory.dhcpSnippet();

  const state = factory.rootState({
    dhcpsnippet: factory.dhcpSnippetState({
      items: [snippet],
    }),
  });

  it("should render the form", () => {
    renderWithProviders(<DhcpDelete id={1} />, { state });

    expect(
      screen.getByRole("form", { name: "Confirm DHCP deletion" })
    ).toBeInTheDocument();
  });

  it("should fire an action to delete a DHCP snippet", async () => {
    const { store } = renderWithProviders(<DhcpDelete id={1} />, { state });

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    expect(
      store.getActions().some((action) => action.type === "dhcpsnippet/delete")
    ).toBe(true);
  });
});
