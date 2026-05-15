import { describe } from "vitest";

import DevicesTable from "./DevicesTable";

import urls from "@/app/base/urls";
import type { Device } from "@/app/store/device/types";
import { DeviceIpAssignment } from "@/app/store/device/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen, waitFor } from "@/testing/utils";

describe("DevicesTable", () => {
  let device: Device;
  let state: RootState;

  beforeEach(() => {
    device = factory.device({
      domain: { id: 1, name: "domain" },
      fqdn: "device.domain",
      hostname: "device",
      ip_address: "192.168.1.1",
      ip_assignment: DeviceIpAssignment.STATIC,
      owner: "owner",
      primary_mac: "11:22:33:44:55:66",
      system_id: "abc123",
      tags: [1, 2],
      zone: { id: 2, name: "zone" },
    });
    state = factory.rootState({
      device: factory.deviceState({ items: [device] }),
    });
  });

  describe("display", () => {
    it("displays a loading component if devices are loading", async () => {
      state.device.loading = true;
      renderWithProviders(
        <DevicesTable
          rowSelection={{}}
          searchFilter={""}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      await waitFor(() => {
        expect(screen.getByText("Loading...")).toBeInTheDocument();
      });
    });

    it("displays a message when rendering an empty list", async () => {
      state.device.items = [];
      renderWithProviders(
        <DevicesTable
          rowSelection={{}}
          searchFilter={""}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      await waitFor(() => {
        expect(screen.getByText("No devices available.")).toBeInTheDocument();
      });
    });

    it("displays the columns correctly", () => {
      renderWithProviders(
        <DevicesTable
          rowSelection={{}}
          searchFilter={""}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      ["FQDN", "IP assignment", "Zone", "Owner"].forEach((column) => {
        expect(
          screen.getByRole("columnheader", {
            name: new RegExp(`^${column}`, "i"),
          })
        ).toBeInTheDocument();
      });
    });

    it("links to a device's details page", () => {
      device.system_id = "def456";
      renderWithProviders(
        <DevicesTable
          rowSelection={{}}
          searchFilter={""}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      expect(screen.getAllByRole("link")[0]).toHaveAttribute(
        "href",
        urls.devices.device.index({ id: device.system_id })
      );
    });

    it("can show when a device has more than one mac address", () => {
      device.primary_mac = "11:11:11:11:11:11";
      device.extra_macs = ["22:22:22:22:22:22", "33:33:33:33:33:33"];
      renderWithProviders(
        <DevicesTable
          rowSelection={{}}
          searchFilter={""}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      expect(screen.getByText("11:11:11:11:11:11 (+2)")).toBeInTheDocument();
    });

    it("links to a device's zone's details page", () => {
      device.zone = { id: 101, name: "danger" };
      renderWithProviders(
        <DevicesTable
          rowSelection={{}}
          searchFilter={""}
          setRowSelection={vi.fn()}
        />,
        { state }
      );

      expect(screen.getAllByRole("link")[1]).toHaveAttribute(
        "href",
        urls.zones.index
      );
    });
  });
});
