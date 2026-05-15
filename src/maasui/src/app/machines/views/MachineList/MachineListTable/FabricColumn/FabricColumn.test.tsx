import { FabricColumn } from "./FabricColumn";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("FabricColumn", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        loaded: true,
        items: [
          factory.machine({
            system_id: "abc123",
            network_test_status: factory.testStatus({
              status: 1,
            }),
            vlan: {
              id: 1,
              name: "Default VLAN",
              fabric_id: 0,
              fabric_name: "fabric-0",
            },
          }),
        ],
      }),
    });
  });

  it("displays the fabric name", () => {
    state.machine.items[0] = factory.machine({
      system_id: "abc123",
      network_test_status: factory.testStatus({
        status: 1,
      }),
      vlan: {
        id: 1,
        name: "Default VLAN",
        fabric_id: 0,
        fabric_name: "fabric-2",
      },
    });

    renderWithProviders(<FabricColumn systemId="abc123" />, {
      state,
    });
    expect(screen.getByLabelText("Fabric")).toHaveTextContent(/fabric-2/i);
  });

  it("displays '-' with no fabric present", () => {
    state.machine.items[0] = factory.machine({
      system_id: "abc123",
      network_test_status: factory.testStatus({
        status: 1,
      }),
      vlan: null,
    });

    renderWithProviders(<FabricColumn systemId="abc123" />, {
      state,
    });
    expect(screen.getByLabelText("Fabric")).toHaveTextContent("-");
  });

  it("displays VLAN name", () => {
    state.machine.items[0] = factory.machine({
      system_id: "abc123",
      network_test_status: factory.testStatus({
        status: 1,
      }),
      vlan: {
        id: 1,
        name: "Wombat",
        fabric_id: 0,
        fabric_name: "fabric-2",
      },
    });

    renderWithProviders(<FabricColumn systemId="abc123" />, {
      state,
    });
    expect(screen.getByTestId("vlan")).toHaveTextContent(/Wombat/i);
  });
});
