import TypeColumn from "./TypeColumn";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("TypeColumn", () => {
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

  it("displays an icon when bond is over multiple numa nodes", () => {
    const interfaces = [factory.machineInterface({ numa_node: 1 })];
    const nic = factory.machineInterface({
      numa_node: 2,
      parents: [interfaces[0].id],
    });
    interfaces.push(nic);
    state.machine.items = [
      factory.machineDetails({
        interfaces,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <TypeColumn nic={nic} node={state.machine.items[0]} />,
      { state }
    );
    expect(screen.getByRole("button").children[0]).toHaveClass(
      "p-icon--warning"
    );
  });

  it("does not display an icon for single numa nodes", () => {
    const nic = factory.machineInterface({
      numa_node: 2,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <TypeColumn nic={nic} node={state.machine.items[0]} />,
      { state }
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("displays the full type for parent interfaces", () => {
    const interfaces = [
      factory.machineInterface({ type: NetworkInterfaceTypes.BOND }),
    ];
    const nic = factory.machineInterface({
      children: [interfaces[0].id],
    });
    interfaces.push(nic);
    state.machine.items = [
      factory.machineDetails({
        interfaces,
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <TypeColumn nic={nic} node={state.machine.items[0]} />,
      { state }
    );
    expect(screen.getByTestId("primary")).toHaveTextContent("Bonded physical");
  });
});
