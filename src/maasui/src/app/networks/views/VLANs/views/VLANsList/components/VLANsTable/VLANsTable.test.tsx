import VLANsTable from "./VLANsTable";

import { DeleteVLAN, EditVLAN } from "@/app/networks/views/VLANs/components";
import type { RootState } from "@/app/store/root/types";
import {
  rootState as rootStateFactory,
  vlan as vlanFactory,
  vlanState as vlanStateFactory,
} from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("VLANsTable", () => {
  let state: RootState;
  beforeEach(() => {
    state = rootStateFactory({
      vlan: vlanStateFactory({
        loading: false,
        loaded: true,
        items: [vlanFactory()],
      }),
    });
  });

  describe("display", () => {
    it("displays a spinner while loading", () => {
      state.vlan.loading = true;
      renderWithProviders(<VLANsTable />, { state });

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });

    it("displays an appropriate message when there are no VLANs", () => {
      state.vlan.items = [];
      renderWithProviders(<VLANsTable />, { state });

      expect(screen.getByText("No VLANs found.")).toBeInTheDocument();
    });

    it("displays DHCP status correctly", () => {
      // maas-provided
      state.vlan.items = [vlanFactory({ dhcp_on: true })];
      const { rerender } = renderWithProviders(<VLANsTable />, { state });
      expect(screen.getByText("MAAS-provided")).toBeInTheDocument();

      // external
      state.vlan.items = [vlanFactory({ external_dhcp: "somewhere" })];
      rerender(<VLANsTable />, { state });
      expect(screen.getByText("External (somewhere)")).toBeInTheDocument();

      // relayed
      state.vlan.items = [vlanFactory({ relay_vlan: 1 })];
      rerender(<VLANsTable />, { state });
      expect(screen.getByText("Relayed")).toBeInTheDocument();

      // disabled
      state.vlan.items = [vlanFactory({ dhcp_on: false })];
      rerender(<VLANsTable />, { state });
      expect(screen.getByText("Disabled")).toBeInTheDocument();
    });
  });

  describe("actions", () => {
    it("opens the Edit VLAN form when the Edit button is clicked", async () => {
      renderWithProviders(<VLANsTable />, { state });

      await userEvent.click(screen.getByRole("button", { name: "Edit" }));

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: EditVLAN,
          title: "Edit VLAN",
          props: {
            id: state.vlan.items[0].id,
          },
        });
      });
    });

    it("opens the Delete VLAN form when the Delete button is clicked", async () => {
      renderWithProviders(<VLANsTable />, { state });

      await userEvent.click(screen.getByRole("button", { name: "Delete" }));

      await waitFor(() => {
        expect(mockOpen).toHaveBeenCalledWith({
          component: DeleteVLAN,
          title: "Delete VLAN",
          props: {
            id: state.vlan.items[0].id,
          },
        });
      });
    });
  });
});
