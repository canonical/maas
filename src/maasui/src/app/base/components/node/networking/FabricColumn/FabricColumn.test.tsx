import { screen } from "@testing-library/react";

import FabricColumn from "./FabricColumn";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders } from "@/testing/utils";

describe("FabricColumn", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
      }),
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
        loaded: true,
        statuses: {
          abc123: factory.machineStatus(),
        },
      }),
    });
  });

  it("displays a spinner if the data is loading", () => {
    state.fabric.loaded = false;
    const nic = factory.machineInterface();
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];

    renderWithProviders(
      <FabricColumn nic={nic} node={state.machine.items[0]} />,
      { state }
    );
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("can display fabric and vlan details", () => {
    const fabric = factory.fabric({ name: "fabric-name" });
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id, vid: 2, name: "vlan-name" });
    state.vlan.items = [vlan];
    const nic = factory.machineInterface({
      vlan_id: vlan.id,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];

    renderWithProviders(
      <FabricColumn nic={nic} node={state.machine.items[0]} />,
      { state }
    );
    expect(screen.getByText("fabric-name")).toBeInTheDocument();
    expect(screen.getByText("2 (vlan-name)")).toBeInTheDocument();
  });
});
