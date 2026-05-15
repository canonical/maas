import EditInterface from "./EditInterface";

import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import * as factory from "@/testing/factories";
import { renderWithProviders, screen } from "@/testing/utils";

describe("EditInterface", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            system_id: "abc123",
          }),
        ],
        statuses: factory.machineStatuses({
          abc123: factory.machineStatus(),
        }),
      }),
    });
  });

  it("displays a spinner when data is loading", () => {
    state.machine.items = [];
    renderWithProviders(
      <EditInterface selected={[]} setSelected={vi.fn()} systemId="abc123" />,
      {
        state,
      }
    );
    expect(screen.getByText(/Loading/i)).toBeInTheDocument();
  });

  it("displays a form for editing a physical interface", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces: [nic],
      }),
    ];
    renderWithProviders(
      <EditInterface
        nicId={nic.id}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      {
        state,
      }
    );
    expect(
      screen.getByRole("form", { name: "Edit physical" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save interface" })
    ).toBeInTheDocument();
  });

  it("displays a form for editing an alias", () => {
    const link = factory.networkLink();
    const nic = factory.machineInterface({
      links: [factory.networkLink(), link],
      type: NetworkInterfaceTypes.PHYSICAL,
    });
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces: [nic],
      }),
    ];
    renderWithProviders(
      <EditInterface
        linkId={link.id}
        nicId={nic.id}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      {
        state,
      }
    );
    expect(
      screen.getByRole("form", { name: "Edit alias" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save Alias" })
    ).toBeInTheDocument();
  });

  it("displays a form for editing a VLAN", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.VLAN,
    });
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces: [nic],
      }),
    ];
    renderWithProviders(
      <EditInterface
        nicId={nic.id}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      {
        state,
      }
    );
    expect(screen.getByRole("form", { name: "Edit VLAN" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save VLAN" })
    ).toBeInTheDocument();
  });

  it("displays a form for editing a bridge", () => {
    const nic = factory.machineInterface({
      type: NetworkInterfaceTypes.BRIDGE,
    });
    state.machine.items = [
      factory.machineDetails({
        system_id: "abc123",
        interfaces: [nic],
      }),
    ];
    renderWithProviders(
      <EditInterface
        nicId={nic.id}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      {
        state,
      }
    );
    expect(
      screen.getByRole("form", { name: "Edit bridge" })
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Save Bridge" })
    ).toBeInTheDocument();
  });
});
