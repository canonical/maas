import DhcpDelete from "../DhcpDelete";
import DhcpEdit from "../DhcpEdit";

import DhcpList from "./DhcpList";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  userEvent,
  screen,
  within,
  renderWithProviders,
  mockSidePanel,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("DhcpList", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      controller: factory.controllerState({
        loaded: true,
      }),
      device: factory.deviceState({
        loaded: true,
      }),
      dhcpsnippet: factory.dhcpSnippetState({
        loaded: true,
        items: [
          factory.dhcpSnippet({ id: 1, name: "class", description: "" }),
          factory.dhcpSnippet({
            id: 2,
            name: "lease",
            subnet: 2,
            description: "",
          }),
          factory.dhcpSnippet({
            id: 3,
            name: "boot",
            node: "xyz",
            description: "",
          }),
        ],
      }),
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "xyz",
            hostname: "machine1",
            domain: factory.modelRef({ name: "test" }),
          }),
        ],
      }),
      subnet: factory.subnetState({
        loaded: true,
        items: [
          factory.subnet({ id: 1, name: "10.0.0.99" }),
          factory.subnet({ id: 2, name: "test.maas" }),
        ],
      }),
    });
  });

  describe("display", () => {
    it("displays a loading component if snippets are loading", () => {
      state.dhcpsnippet.loading = true;
      renderWithProviders(<DhcpList />, { state });

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("displays a message when rendering an empty list", () => {
      state.dhcpsnippet.items = [];
      renderWithProviders(<DhcpList />, { state });

      expect(
        screen.getByText("No DHCP snippets available.")
      ).toBeInTheDocument();
    });

    it("displays the columns correctly", () => {
      renderWithProviders(<DhcpList />, { state });

      [
        "Snippet name",
        "Type",
        "Applies to",
        "description",
        "enabled",
        "Last edited",
        "Actions",
      ].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });
  });

  describe("table actions", () => {
    it("can show a delete side panel", async () => {
      renderWithProviders(<DhcpList />, { state });
      await userEvent.click(
        screen.getAllByRole("button", { name: "Delete" })[0]
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Delete DHCP snippet",
          component: DhcpDelete,
          props: {
            id: state.dhcpsnippet.items[2].id,
          },
        })
      );
    });

    it("can show an edit side panel to edit and view details", async () => {
      renderWithProviders(<DhcpList />, { state });
      await userEvent.click(
        within(screen.getAllByRole("row")[1]).getByRole("button", {
          name: "Edit",
        })
      );

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Edit DHCP snippet",
          component: DhcpEdit,
          props: {
            id: state.dhcpsnippet.items[2].id,
          },
        })
      );
    });
  });
});
