import InterfaceFormTable from "./InterfaceFormTable";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("InterfaceFormTable", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [],
        loaded: true,
        statuses: {
          abc123: factory.machineStatus(),
        },
      }),
    });
  });

  it("displays a spinner when loading", () => {
    state.machine.items = [];
    renderWithProviders(
      <InterfaceFormTable interfaces={[]} systemId="abc123" />,
      { state }
    );

    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays a table when loaded", () => {
    const nic = factory.machineInterface();
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <InterfaceFormTable interfaces={[{ nicId: nic.id }]} systemId="abc123" />,
      { state }
    );

    expect(screen.getByRole("grid")).toBeInTheDocument();
  });

  it("displays a PXE column by default", () => {
    const nic = factory.machineInterface();
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <InterfaceFormTable interfaces={[{ nicId: nic.id }]} systemId="abc123" />,
      { state }
    );

    expect(
      screen.getByRole("columnheader", { name: "PXE" })
    ).toBeInTheDocument();
  });

  it("can show checkboxes to update the selection", () => {
    const nic = factory.machineInterface();
    state.machine.items = [
      factory.machineDetails({
        interfaces: [nic],
        system_id: "abc123",
      }),
    ];
    renderWithProviders(
      <InterfaceFormTable
        interfaces={[{ nicId: nic.id }]}
        selectedEditable
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      { state }
    );

    expect(
      screen.getByRole("checkbox", { name: `select ${nic.name}` })
    ).toBeInTheDocument();
  });
});
