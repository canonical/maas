import MachineActionMenuBar from "./MachineActionMenuBar";

import type { RootState } from "@/app/store/root/types";
import { NodeActions, NodeStatus } from "@/app/store/types/node";
import { getNodeActionTitle } from "@/app/store/utils";
import * as factory from "@/testing/factories";
import {
  renderWithProviders,
  screen,
  userEvent,
  within,
} from "@/testing/utils";

describe("MachineActionMenuBar", () => {
  let state: RootState;

  const openMenu = async (name: string) => {
    await userEvent.click(screen.getByRole("button", { name: name }));
  };

  const getSubMenu = (name: string) => screen.getByLabelText(`${name} submenu`);

  const getActionButton = (submenu: HTMLElement, name: NodeActions) =>
    within(submenu).getByRole("button", {
      name: RegExp(getNodeActionTitle(name)),
    });

  const queryActionButton = (submenu: HTMLElement, name: NodeActions) =>
    within(submenu).queryByRole("button", {
      name: RegExp(getNodeActionTitle(name)),
    });

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machine({ system_id: "abc123" })],
      }),
    });
  });

  it("only shows actions that a given machine can perform when provided a system id", async () => {
    const machine = factory.machine({
      actions: [NodeActions.COMMISSION, NodeActions.DEPLOY],
    });
    state.machine.items = [machine];
    renderWithProviders(
      <MachineActionMenuBar isViewingDetails systemId={machine.system_id} />,
      { state }
    );

    await openMenu("Actions");

    const actionsMenu = getSubMenu("Actions");

    expect(
      getActionButton(actionsMenu, NodeActions.COMMISSION)
    ).toBeInTheDocument();
    expect(
      getActionButton(actionsMenu, NodeActions.DEPLOY)
    ).toBeInTheDocument();
    expect(
      queryActionButton(actionsMenu, NodeActions.ACQUIRE)
    ).not.toBeInTheDocument();
  });

  it("can show disabled actions, even if a machine cannot perform them", async () => {
    const machine = factory.machine({
      actions: [NodeActions.DEPLOY],
    });
    renderWithProviders(
      <MachineActionMenuBar
        disabledActions={[NodeActions.RELEASE]}
        systemId={machine.system_id}
      />,
      { state }
    );

    await openMenu("Actions");

    const actionsMenu = getSubMenu("Actions");

    expect(
      getActionButton(actionsMenu, NodeActions.DEPLOY)
    ).toBeInTheDocument();
    expect(
      queryActionButton(actionsMenu, NodeActions.DEPLOY)
    ).not.toBeAriaDisabled();
    expect(
      getActionButton(actionsMenu, NodeActions.RELEASE)
    ).toBeInTheDocument();
    expect(
      getActionButton(actionsMenu, NodeActions.RELEASE)
    ).toBeAriaDisabled();
  });

  it("disables actions even when a machine can peform them", async () => {
    const machine = factory.machine({
      actions: [NodeActions.DEPLOY],
    });
    renderWithProviders(
      <MachineActionMenuBar
        disabledActions={[NodeActions.DEPLOY]}
        isViewingDetails
        systemId={machine.system_id}
      />,
      { state }
    );

    await openMenu("Actions");

    const actionsMenu = getSubMenu("Actions");

    expect(
      getActionButton(actionsMenu, NodeActions.DEPLOY)
    ).toBeInTheDocument();
    expect(getActionButton(actionsMenu, NodeActions.DEPLOY)).toBeAriaDisabled();
  });

  it("can exclude actions", async () => {
    renderWithProviders(
      <MachineActionMenuBar excludeActions={[NodeActions.DEPLOY]} />,
      { state }
    );

    await openMenu("Actions");

    const actionsMenu = getSubMenu("Actions");

    expect(
      queryActionButton(actionsMenu, NodeActions.DEPLOY)
    ).not.toBeInTheDocument();
  });

  it("shows all actions that can be performed when machines are not provided", async () => {
    renderWithProviders(<MachineActionMenuBar />, { state });

    await openMenu("Actions");

    const actionsMenu = getSubMenu("Actions");

    [
      NodeActions.ABORT,
      NodeActions.ACQUIRE,
      NodeActions.CLONE,
      NodeActions.COMMISSION,
      NodeActions.DEPLOY,
      NodeActions.RELEASE,
    ].forEach((action) => {
      expect(getActionButton(actionsMenu, action)).toBeInTheDocument();
    });
  });

  it("shows 'Check power' only when viewing machine details and a system id is provided", async () => {
    renderWithProviders(
      <MachineActionMenuBar isViewingDetails systemId="abc123" />,
      { state }
    );
    await openMenu("Power");

    const powerMenu = getSubMenu("Power");

    expect(
      getActionButton(powerMenu, NodeActions.CHECK_POWER)
    ).toBeInTheDocument();
  });

  it("renders a button instead of a contextual menu for 'Delete'", () => {
    renderWithProviders(<MachineActionMenuBar />, { state });

    expect(screen.getByRole("button", { name: "Delete" })).not.toHaveClass(
      "p-contextual-menu__toggle"
    );
  });

  it("renders an icon for buttons that have one", () => {
    renderWithProviders(<MachineActionMenuBar />, { state });

    expect(
      screen.getByRole("button", { name: "Delete" }).firstElementChild
    ).toHaveClass("p-icon--delete");
  });

  it("renders a switch for locking instead of a contexual menu when viewing details and the machine can be locked", () => {
    const machine = factory.machine({
      system_id: "abc123",
      status: NodeStatus.DEPLOYED,
      actions: [NodeActions.LOCK],
    });
    state.machine.items = [machine];
    const { rerender } = renderWithProviders(
      <MachineActionMenuBar isViewingDetails systemId="abc123" />,
      { state }
    );

    expect(screen.getByRole("switch", { name: "Lock" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Lock" })
    ).not.toBeInTheDocument();

    rerender(<MachineActionMenuBar />);

    expect(screen.getByRole("button", { name: "Lock" })).toBeInTheDocument();
    expect(
      screen.queryByRole("switch", { name: "Lock" })
    ).not.toBeInTheDocument();
  });

  it("renders a switch for locking instead of a contexual menu when viewing details and the machine can be unlocked", () => {
    const machine = factory.machine({
      system_id: "abc123",
      status: NodeStatus.DEPLOYED,
      actions: [NodeActions.LOCK],
    });
    state.machine.items = [machine];
    renderWithProviders(
      <MachineActionMenuBar isViewingDetails systemId="abc123" />,
      { state }
    );

    expect(screen.getByRole("switch", { name: "Lock" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Lock" })
    ).not.toBeInTheDocument();
  });

  it("does not render a switch for locking when viewing details if the machine cannot be locked or unlocked", () => {
    const machine = factory.machine({
      system_id: "abc123",
      status: NodeStatus.DEPLOYED,
      actions: [],
    });
    state.machine.items = [machine];
    renderWithProviders(
      <MachineActionMenuBar isViewingDetails systemId="abc123" />,
      { state }
    );

    expect(
      screen.queryByRole("switch", { name: "Lock" })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Lock" })
    ).not.toBeInTheDocument();
  });
});
