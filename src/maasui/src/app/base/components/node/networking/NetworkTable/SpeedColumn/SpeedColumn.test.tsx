import SpeedColumn from "./SpeedColumn";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("SpeedColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        loaded: true,
        statuses: {
          abc123: factory.machineStatus(),
        },
      }),
    });
  });

  it("can display a disconnected icon in the speed column", () => {
    const nic = factory.machineInterface({
      link_connected: false,
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<SpeedColumn nic={nic} node={machine} />, { state });

    expect(document.querySelector(".p-icon--disconnected")).toBeInTheDocument();
  });

  it("can display a slow icon in the speed column", () => {
    const nic = factory.machineInterface({
      interface_speed: 2,
      link_speed: 1,
      link_connected: true,
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<SpeedColumn nic={nic} node={machine} />, { state });

    expect(document.querySelector(".p-icon--warning")).toBeInTheDocument();
  });

  it("can display no icon in the speed column", () => {
    const nic = factory.machineInterface({
      link_connected: true,
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    const machine = factory.machineDetails({
      interfaces: [nic],
      system_id: "abc123",
    });
    state.machine.items = [machine];
    renderWithProviders(<SpeedColumn nic={nic} node={machine} />, { state });

    expect(
      document.querySelector("[class^='p-icon--']")
    ).not.toBeInTheDocument();
  });
});
