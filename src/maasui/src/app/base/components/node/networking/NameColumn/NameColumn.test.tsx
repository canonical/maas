import NameColumn from "./NameColumn";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { screen, renderWithProviders } from "@/testing/utils";

describe("NameColumn", () => {
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

  it("disables the checkboxes when networking is disabled", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        status: NodeStatus.COMMISSIONING,
        system_id: "abc123",
      }),
    ];

    renderWithProviders(
      <NameColumn
        handleRowCheckbox={vi.fn()}
        nic={nic}
        node={state.machine.items[0]}
        selected={[]}
        showCheckbox={true}
      />,
      { state }
    );
    const checkbox: HTMLInputElement = screen.getByRole("checkbox");
    expect(checkbox.disabled).toBe(true);
  });

  it("can not show a checkbox", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        status: NodeStatus.COMMISSIONING,
        system_id: "abc123",
      }),
    ];

    renderWithProviders(
      <NameColumn
        handleRowCheckbox={vi.fn()}
        nic={nic}
        node={state.machine.items[0]}
        selected={[]}
        showCheckbox={false}
      />,
      { state }
    );
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.getByTestId("name")).toBeInTheDocument();
  });
});
