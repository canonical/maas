import EditInterface from "../../EditInterface";

import NetworkTableActions from "./NetworkTableActions";

import MarkConnectedForm from "@/app/machines/views/MachineDetails/MachineNetwork/MarkConnectedForm";
import type { MachineDetails } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes, NetworkLinkMode } from "@/app/store/types/enum";
import type { NetworkInterface } from "@/app/store/types/node";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import {
  expectTooltipOnHover,
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
  waitFor,
  within,
} from "@/testing/utils";

const { mockOpen } = await mockSidePanel();

const openMenu = async () => {
  await userEvent.click(screen.getByRole("button", { name: "Take action:" }));
};

describe("NetworkTableActions", () => {
  let nic: NetworkInterface;
  let state: RootState;
  beforeEach(() => {
    nic = factory.machineInterface();
    state = factory.rootState({
      machine: factory.machineState({
        items: [
          factory.machineDetails({
            interfaces: [nic],
            system_id: "abc123",
          }),
        ] as MachineDetails[],
        loaded: true,
      }),
    });
  });

  it("can display the menu", () => {
    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    expect(
      screen.getByRole("button", { name: "Take action:" })
    ).toBeInTheDocument();
  });

  it("disables menu when networking is disabled and limited editing is not allowed", () => {
    state.machine.items[0].permissions = [];
    state.machine.items[0].status = NodeStatus.NEW;
    nic.type = NetworkInterfaceTypes.VLAN;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    expect(
      screen.getByRole("button", { name: "Take action:" })
    ).toBeAriaDisabled();
  });

  it("can display an item to mark an interface as connected", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.link_connected = false;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();

    expect(
      screen.getByRole("button", { name: /Mark as connected/ })
    ).toBeInTheDocument();
  });

  it("can display an item to mark an interface as disconnected", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.link_connected = true;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();

    expect(
      screen.getByRole("button", { name: /Mark as disconnected/ })
    ).toBeInTheDocument();
  });

  it("does not display an item to mark an alias as connected", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.link_connected = false;
    const link = factory.networkLink();
    nic.links = [factory.networkLink(), link];

    renderWithProviders(
      <NetworkTableActions link={link} nic={nic} systemId="abc123" />,
      { state }
    );
    // Open the menu:
    await openMenu();
    expect(
      screen.queryByRole("button", { name: "Mark as connected" })
    ).not.toBeInTheDocument();
  });

  it("does not display an item to mark an alias as disconnected", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.link_connected = true;
    const link = factory.networkLink();
    nic.links = [factory.networkLink(), link];

    renderWithProviders(
      <NetworkTableActions link={link} nic={nic} systemId="abc123" />,
      { state }
    );
    // Open the menu:
    await openMenu();
    expect(
      screen.queryByRole("button", { name: "Mark as disconnected" })
    ).not.toBeInTheDocument();
  });

  it("can display an item to remove the interface", async () => {
    nic.type = NetworkInterfaceTypes.BOND;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    expect(
      screen.getByRole("button", { name: "Remove Bond..." })
    ).toBeInTheDocument();
  });

  it("can display an item to edit the interface", async () => {
    nic.type = NetworkInterfaceTypes.BOND;

    renderWithProviders(
      <NetworkTableActions
        nic={nic}
        selected={[]}
        setSelected={vi.fn()}
        systemId="abc123"
      />,
      {
        state,
      }
    );
    // Open the menu:
    await openMenu();
    const editBondButton = screen.getByRole("button", {
      name: /Edit Bond/,
    });
    expect(editBondButton).toBeInTheDocument();
    await userEvent.click(editBondButton);
    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: EditInterface,
      })
    );
  });

  it("can display a warning when trying to edit a disconnected interface", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.link_connected = false;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    const editPhysicalButton = screen.getByRole("button", {
      name: /Edit Physical/,
    });
    expect(editPhysicalButton).toBeInTheDocument();
    await userEvent.click(editPhysicalButton);
    expect(mockOpen).toHaveBeenCalledWith(
      expect.objectContaining({
        component: MarkConnectedForm,
      })
    );
  });

  it("can display an action to add an alias", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.links = [factory.networkLink()];

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    const addAlias = screen.getByRole("button", {
      name: /Add alias/i,
    });
    expect(addAlias).toBeInTheDocument();
    expect(addAlias).not.toBeAriaDisabled();
    await userEvent.hover(addAlias);
    expect(
      screen.queryByRole("tooltip", {
        name: "IP mode needs to be configured for this interface.",
      })
    ).not.toBeInTheDocument();
  });

  it("can display a disabled action to add an alias", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    nic.links = [factory.networkLink({ mode: NetworkLinkMode.LINK_UP })];

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    const addAlias = screen.getByRole("button", {
      name: /Add alias/i,
    });
    expect(addAlias).toBeInTheDocument();
    expect(addAlias).toBeAriaDisabled();
    await expectTooltipOnHover(
      addAlias,
      "IP mode needs to be configured for this interface."
    );
  });

  it("can display an action to add a VLAN", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    const fabric = factory.fabric();
    state.fabric.items = [fabric];
    const vlan = factory.vlan({ fabric: fabric.id });
    state.vlan.items = [vlan];
    nic.vlan_id = vlan.id;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    const addVLAN = screen.getByRole("button", { name: /Add VLAN/i });
    expect(addVLAN).toBeInTheDocument();
    expect(addVLAN).not.toBeAriaDisabled();
    expect(
      screen.queryByRole("tooltip", {
        name: "There are no unused VLANS for this interface.",
      })
    ).not.toBeInTheDocument();
  });

  it("can display a disabled action to add a VLAN", async () => {
    nic.type = NetworkInterfaceTypes.PHYSICAL;
    state.vlan.items = [];

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    const addVLAN = screen.getByRole("button", { name: /Add VLAN/i });
    expect(addVLAN).toBeInTheDocument();
    expect(addVLAN).toBeAriaDisabled();
    await expectTooltipOnHover(
      addVLAN,
      "There are no unused VLANS for this interface."
    );
    await userEvent.hover(within(addVLAN).getByLabelText("help"));
    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent(
        "There are no unused VLANS for this interface."
      );
    });
  });

  it("can not display an action to add an alias or vlan", async () => {
    state.machine.items[0].permissions = [];
    state.machine.items[0].status = NodeStatus.NEW;

    renderWithProviders(<NetworkTableActions nic={nic} systemId="abc123" />, {
      state,
    });
    // Open the menu:
    await openMenu();
    expect(
      screen.queryByRole("button", { name: /Add alias/i })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Add VLAN/i })
    ).not.toBeInTheDocument();
  });
});
