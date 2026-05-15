import { DhcpForm } from "./DhcpForm";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  screen,
  renderWithProviders,
  mockSidePanel,
  userEvent,
} from "@/testing/utils";

const { mockClose } = await mockSidePanel();

describe("DhcpForm", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      dhcpsnippet: factory.dhcpSnippetState({
        items: [
          factory.dhcpSnippet({
            id: 1,
            name: "lease",
            value: "lease 10",
          }),
          factory.dhcpSnippet({
            id: 2,
            name: "class",
          }),
        ],
        loaded: true,
      }),
    });
  });

  it("can render", () => {
    renderWithProviders(<DhcpForm />, { state });
    expect(
      screen.getByRole("form", { name: "Add DHCP snippet" })
    ).toBeInTheDocument();
  });

  it("runs closeSidePanel function when snippet is saved", async () => {
    state.dhcpsnippet.saved = true;
    renderWithProviders(<DhcpForm />, { state });
    await userEvent.click(screen.getByRole("button", { name: /Cancel/i }));
    expect(mockClose).toHaveBeenCalled();
  });

  it("shows the snippet name in the title when editing", () => {
    renderWithProviders(<DhcpForm dhcpSnippet={state.dhcpsnippet.items[0]} />, {
      state,
    });

    expect(
      screen.getByRole("form", { name: "Editing `lease`" })
    ).toBeInTheDocument();
  });
});
