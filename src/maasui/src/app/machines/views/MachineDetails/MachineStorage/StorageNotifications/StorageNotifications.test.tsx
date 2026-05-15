import StorageNotifications from "./StorageNotifications";

import urls from "@/app/base/urls";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

const machineRoutePattern = `${urls.machines.machine.index(null)}/*`;
const storageUrl = urls.machines.machine.storage({ id: "abc123" });

describe("StorageNotifications", () => {
  let state: RootState;
  let machine: MachineDetails;

  beforeEach(() => {
    machine = factory.machineDetails({
      disks: [factory.nodeDisk()],
      locked: false,
      osystem: "ubuntu",
      permissions: ["edit"],
      status_code: NodeStatusCode.READY,
      storage_layout_issues: [],
      system_id: "abc123",
    });
    state = factory.rootState({
      machine: factory.machineState({
        items: [machine],
      }),
    });
  });

  it("handles no notifications", () => {
    renderWithProviders(<StorageNotifications />, {
      initialEntries: [storageUrl],
      pattern: machineRoutePattern,
      state,
    });

    expect(
      screen.getByTestId("machine-notifications-list")
    ).toBeEmptyDOMElement();
  });

  it("can display a commissioning error", () => {
    machine.disks = [];
    renderWithProviders(<StorageNotifications />, {
      initialEntries: [storageUrl],
      pattern: machineRoutePattern,
      state,
    });

    expect(
      screen.getByText(
        "No storage information. Commission this machine to gather storage information."
      )
    ).toBeInTheDocument();
  });

  it("can display a machine state error", () => {
    machine.status_code = NodeStatusCode.NEW;
    renderWithProviders(<StorageNotifications />, {
      initialEntries: [storageUrl],
      pattern: machineRoutePattern,
      state,
    });

    expect(
      screen.getByText(
        "Storage configuration cannot be modified unless the machine is Ready."
      )
    ).toBeInTheDocument();
  });

  it("can display an OS storage configuration notification", () => {
    machine.osystem = "windows";
    renderWithProviders(<StorageNotifications />, {
      initialEntries: [storageUrl],
      pattern: machineRoutePattern,
      state,
    });

    expect(
      screen.getByText(
        /Custom storage configuration is only supported on Ubuntu, CentOS, and RHEL./i
      )
    ).toBeInTheDocument();
  });

  it("can display a bcache ZFS error", () => {
    machine.osystem = "centos";
    renderWithProviders(<StorageNotifications />, {
      initialEntries: [storageUrl],
      pattern: machineRoutePattern,
      state,
    });

    expect(
      screen.getByText(/Bcache and ZFS are only supported on Ubuntu./i)
    ).toBeInTheDocument();
  });

  it("can display a list of storage layout issues", () => {
    machine.storage_layout_issues = ["it's bad", "it won't work"];
    renderWithProviders(<StorageNotifications />, {
      initialEntries: [storageUrl],
      pattern: machineRoutePattern,
      state,
    });

    expect(screen.getByText("it's bad")).toBeInTheDocument();
    expect(screen.getByText("it won't work")).toBeInTheDocument();
  });
});
