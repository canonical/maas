import LicenseKeyTable from "./LicenseKeyTable";

import {
  LicenseKeyAdd,
  LicenseKeyEdit,
} from "@/app/settings/views/LicenseKeys/components";
import LicenseKeyDelete from "@/app/settings/views/LicenseKeys/components/LicenseKeyDelete/LicenseKeyDelete";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

describe("LicenseKeyTable", () => {
  let initialState: RootState;

  beforeEach(() => {
    initialState = factory.rootState({
      general: factory.generalState({
        osInfo: factory.osInfoState({
          loaded: true,
          data: factory.osInfo({
            osystems: [
              ["ubuntu", "Ubuntu"],
              ["windows", "Windows"],
            ],
            releases: [
              ["ubuntu/bionic", "Ubuntu 18.04 LTS 'Bionic Beaver'"],
              ["windows/win2012*", "Windows Server 2012"],
            ],
          }),
        }),
      }),
      licensekeys: factory.licenseKeysState({
        loaded: true,
        items: [factory.licenseKeys()],
      }),
    });
  });

  describe("display", () => {
    it("displays a loading component if license keys are loading", async () => {
      const state = { ...initialState };
      state.licensekeys.loading = true;
      renderWithProviders(<LicenseKeyTable />, { state });

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      const state = { ...initialState };
      state.licensekeys.items = [];
      renderWithProviders(<LicenseKeyTable />, { state });

      await waitFor(() => {
        expect(
          screen.getByText("No license keys available.")
        ).toBeInTheDocument();
      });
    });

    // TODO: implement after v3
    it.skip("displays a message when an error is encountered", async () => {
      const state = { ...initialState };
      renderWithProviders(<LicenseKeyTable />, { state });
      await waitFor(() => {
        expect(
          screen.getByText(/Error while fetching package repositories/i)
        ).toBeInTheDocument();
      });
    });

    it("displays the columns corretly", async () => {
      const state = { ...initialState };
      renderWithProviders(<LicenseKeyTable />, { state });

      ["Operating System", "Distro Series", "Actions"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", { name: column })
        ).toBeInTheDocument();
      });
    });
  });

  describe("permissions", () => {
    it.todo(
      "enables the action buttons if the user has the correct permissions"
    );

    it.todo(
      "disables the action buttons if the user does not have the correct permissions"
    );
  });

  describe("actions", () => {
    it("opens the 'Add license key' side panel when the 'Add license key' button is clicked", async () => {
      const state = { ...initialState };
      renderWithProviders(<LicenseKeyTable />, { state });
      await userEvent.click(
        screen.getByRole("button", { name: "Add license key" })
      );
      expect(mockOpen).toHaveBeenCalledWith({
        component: LicenseKeyAdd,
        title: "Add license key",
      });
    });

    it("opens the 'Edit license key' side panel when the 'Edit' button is clicked", async () => {
      const state = { ...initialState };
      renderWithProviders(<LicenseKeyTable />, { state });
      await waitFor(() => {
        expect(screen.getAllByRole("button", { name: "Edit" }).length).toBe(1);
      });
      await userEvent.click(screen.getAllByRole("button", { name: "Edit" })[0]);

      expect(mockOpen).toHaveBeenCalledWith({
        component: LicenseKeyEdit,
        title: "Edit license key",
        props: {
          osystem: "windows",
          distro_series: "win2012",
        },
      });
    });

    it("opens the 'Delete license key' side panel when the 'Delete' button is clicked", async () => {
      const state = { ...initialState };
      renderWithProviders(<LicenseKeyTable />, { state });
      await waitFor(() => {
        expect(screen.getAllByRole("button", { name: "Delete" }).length).toBe(
          1
        );
      });
      await userEvent.click(
        screen.getAllByRole("button", { name: "Delete" })[0]
      );

      expect(mockOpen).toHaveBeenCalledWith({
        component: LicenseKeyDelete,
        title: "Delete license key",
        props: {
          licenseKey: state.licensekeys.items[0],
        },
      });
    });
  });
});
