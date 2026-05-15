import MachineActionMenu from "./MachineActionMenu";

import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import { getNodeActionTitle } from "@/app/store/utils";
import * as factory from "@/testing/factories";
import {
  mockSidePanel,
  renderWithProviders,
  screen,
  userEvent,
} from "@/testing/utils";

describe("MachineActionMenu", async () => {
  let state: RootState;

  const { mockOpen } = await mockSidePanel();

  const machineActions = Object.values(NodeActions).filter(
    (action) =>
      ![NodeActions.IMPORT_IMAGES, NodeActions.UNTAG].some(
        (filterAction) => filterAction === action
      )
  );

  const openMenu = async () => {
    await userEvent.click(screen.getByRole("button", { name: "Menu" }));
  };

  const getActionButton = (action: NodeActions) =>
    screen.getByRole("button", {
      name: new RegExp(getNodeActionTitle(action)),
    });

  const queryActionButton = (action: NodeActions) =>
    screen.queryByRole("button", {
      name: new RegExp(getNodeActionTitle(action)),
    });

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machine({ system_id: "abc123" })],
      }),
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  describe("display", () => {
    it("only shows actions that a given machine can perform when provided a system id", async () => {
      const machine = factory.machine({
        actions: [NodeActions.DELETE, NodeActions.SET_ZONE],
      });
      state.machine.items = [machine];
      renderWithProviders(
        <MachineActionMenu isViewingDetails systemId={machine.system_id} />,
        { state }
      );

      await openMenu();

      expect(getActionButton(NodeActions.DELETE)).toBeInTheDocument();
      expect(getActionButton(NodeActions.SET_ZONE)).toBeInTheDocument();
      expect(queryActionButton(NodeActions.TEST)).not.toBeInTheDocument();
    });

    it("can show disabled actions, even if a machine cannot perform them", async () => {
      const machine = factory.machine({
        actions: [NodeActions.DEPLOY],
      });
      renderWithProviders(
        <MachineActionMenu
          disabledActions={[NodeActions.RELEASE]}
          systemId={machine.system_id}
        />,
        { state }
      );

      await openMenu();

      expect(getActionButton(NodeActions.DEPLOY)).toBeInTheDocument();
      expect(queryActionButton(NodeActions.DEPLOY)).not.toBeAriaDisabled();
      expect(getActionButton(NodeActions.RELEASE)).toBeInTheDocument();
      expect(getActionButton(NodeActions.RELEASE)).toBeAriaDisabled();
    });

    it("disables actions even when a machine can peform them", async () => {
      const machine = factory.machine({
        actions: [NodeActions.DEPLOY],
      });
      renderWithProviders(
        <MachineActionMenu
          disabledActions={[NodeActions.DEPLOY]}
          isViewingDetails
          systemId={machine.system_id}
        />,
        { state }
      );

      await openMenu();

      expect(getActionButton(NodeActions.DEPLOY)).toBeInTheDocument();
      expect(getActionButton(NodeActions.DEPLOY)).toBeAriaDisabled();
    });

    it("can exclude actions from being shown", async () => {
      renderWithProviders(
        <MachineActionMenu excludeActions={[NodeActions.DELETE]} />,
        { state }
      );

      await openMenu();

      expect(queryActionButton(NodeActions.DELETE)).not.toBeInTheDocument();
    });

    it("shows all actions that can be performed when machines are not provided", async () => {
      renderWithProviders(<MachineActionMenu />, { state });

      await openMenu();

      expect(getActionButton(NodeActions.DELETE)).toBeInTheDocument();
      expect(getActionButton(NodeActions.SET_ZONE)).toBeInTheDocument();
      expect(getActionButton(NodeActions.TEST)).toBeInTheDocument();
    });

    it("shows 'Check power' only when viewing machine details and a system id is provided", async () => {
      renderWithProviders(
        <MachineActionMenu isViewingDetails systemId="abc123" />,
        { state }
      );
      await openMenu();

      expect(getActionButton(NodeActions.CHECK_POWER)).toBeInTheDocument();
    });

    it("can be disabled", () => {
      renderWithProviders(<MachineActionMenu disabled={true} />, { state });

      expect(screen.getByRole("button", { name: "Menu" })).toBeAriaDisabled();
    });

    it("can display a custom label", () => {
      renderWithProviders(
        <MachineActionMenu label="A fun label or something" />,
        { state }
      );

      expect(
        screen.getByRole("button", { name: "A fun label or something" })
      ).toBeInTheDocument();
    });

    it("can use different button appearances", () => {
      renderWithProviders(<MachineActionMenu appearance="positive" />, {
        state,
      });

      expect(screen.getByRole("button", { name: "Menu" })).toHaveClass(
        "p-button--positive"
      );
    });
  });

  describe("actions", () => {
    machineActions
      .filter(
        (action) =>
          ![NodeActions.CHECK_POWER, NodeActions.SOFT_OFF].some(
            (filterAction) => action === filterAction
          )
      )
      .forEach((action) => {
        const actionTitle = getNodeActionTitle(action);
        it(`opens the ${actionTitle} form when the ${actionTitle} button is clicked`, async () => {
          // TODO: Remove when DPU feature flag is removed https://warthogs.atlassian.net/browse/MAASENG-4186
          vi.stubEnv("VITE_APP_DPU_PROVISIONING", "true");
          renderWithProviders(<MachineActionMenu />, { state });

          await openMenu();

          await userEvent.click(getActionButton(action));

          expect(mockOpen).toHaveBeenCalledWith(
            expect.objectContaining({ title: actionTitle })
          );
        });
      });

    it("opens the 'Power off' form with props for 'Soft power off' when 'Soft power off' is clicked", async () => {
      renderWithProviders(<MachineActionMenu />, { state });

      await openMenu();

      await userEvent.click(getActionButton(NodeActions.SOFT_OFF));

      expect(mockOpen).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Soft power off" })
      );
    });

    it("imediately dispatches an action to check power when clicked", async () => {
      const { store } = renderWithProviders(
        <MachineActionMenu isViewingDetails systemId="abc123" />,
        { state }
      );

      await openMenu();

      await userEvent.click(getActionButton(NodeActions.CHECK_POWER));

      expect(
        store
          .getActions()
          .find((action) => action.type === "machine/checkPower")
      ).toStrictEqual({
        meta: {
          method: "check_power",
          model: "machine",
        },
        payload: {
          params: {
            system_id: "abc123",
          },
        },
        type: "machine/checkPower",
      });
    });
  });
});
