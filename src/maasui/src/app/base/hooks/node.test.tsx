import type { ReactNode } from "react";

import { Button } from "@canonical/react-components";
import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import type { MockStoreEnhanced } from "redux-mock-store";
import configureStore from "redux-mock-store";

import type { MachineMenuAction } from "./node";
import {
  useCanEdit,
  useIsRackControllerConnected,
  useMachineActions,
} from "./node";

import { machineActions } from "@/app/store/machine";
import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { userEvent, render, screen } from "@/testing/utils";

const mockStore = configureStore();

const generateWrapper =
  (store: MockStoreEnhanced<unknown>) =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

describe("node hooks", () => {
  describe("useIsRackControllerConnected", () => {
    let state: RootState;

    beforeEach(() => {
      state = factory.rootState({
        general: factory.generalState({
          architectures: factory.architecturesState({
            data: ["amd64"],
          }),
          osInfo: factory.osInfoState({
            data: factory.osInfo(),
          }),
          powerTypes: factory.powerTypesState({
            data: [factory.powerType()],
          }),
        }),
      });
    });

    it("handles a connected state", () => {
      state.general.powerTypes = factory.powerTypesState({
        data: [factory.powerType()],
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useIsRackControllerConnected(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("handles a disconnected state", () => {
      state.general.powerTypes.data = [];
      const store = mockStore(state);
      const { result } = renderHook(() => useIsRackControllerConnected(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });
  });

  describe("useCanEdit", () => {
    let state: RootState;
    let machine: Machine | null;

    beforeEach(() => {
      machine = factory.machine({
        architecture: "amd64",
        events: [factory.machineEvent()],
        locked: false,
        permissions: ["edit"],
        system_id: "abc123",
      });
      state = factory.rootState({
        general: factory.generalState({
          architectures: factory.architecturesState({
            data: ["amd64"],
          }),
          osInfo: factory.osInfoState({
            data: factory.osInfo(),
          }),
          powerTypes: factory.powerTypesState({
            data: [factory.powerType()],
          }),
        }),
        machine: factory.machineState({
          items: [machine],
        }),
      });
    });

    it("handles an editable machine", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEdit(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("handles incorrect permissions", () => {
      state.machine.items[0].permissions = [];
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEdit(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("handles a locked machine", () => {
      state.machine.items[0].locked = true;
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEdit(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("handles a disconnected rack controller", () => {
      state.general.powerTypes.data = [];
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEdit(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("can ignore the rack controller state", () => {
      state.general.powerTypes.data = [];
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEdit(machine, true), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });
  });

  describe("useMachineActions", () => {
    let state: RootState;
    const HookWrapper = ({ action }: { action: MachineMenuAction }) => {
      const actions = useMachineActions("abc123", [action]);
      return (
        <>
          {actions.map((buttonProps, i) => (
            <Button {...buttonProps} key={i}>
              action
            </Button>
          ))}
        </>
      );
    };

    const dispatchAction = async (
      action: MachineMenuAction,
      expectedType: string
    ) => {
      state.general.machineActions.data[0].name = action;
      state.machine.items[0].actions = [action];
      const store = mockStore(state);
      render(
        <Provider store={store}>
          <HookWrapper action={action} />
        </Provider>
      );
      await userEvent.click(screen.getByRole("button"));
      return store.getActions().find((action) => action.type === expectedType);
    };

    beforeEach(() => {
      state = factory.rootState({
        general: factory.generalState({
          machineActions: factory.machineActionsState({
            data: [factory.machineAction()],
          }),
        }),
        machine: factory.machineState({
          items: [
            factory.machine({
              system_id: "abc123",
              actions: [],
            }),
          ],
        }),
      });
    });

    it("can dispatch an abort action", async () => {
      const action = NodeActions.ABORT;
      const expected = machineActions.abort({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch an acquire action", async () => {
      const action = NodeActions.ACQUIRE;
      const expected = machineActions.acquire({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a commission action", async () => {
      const action = NodeActions.COMMISSION;
      const expected = machineActions.commission({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a delete action", async () => {
      const action = NodeActions.DELETE;
      const expected = machineActions.delete({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a deploy action", async () => {
      const action = NodeActions.DEPLOY;
      const expected = machineActions.deploy({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch an exit-rescue-mode action", async () => {
      const action = NodeActions.EXIT_RESCUE_MODE;
      const expected = machineActions.exitRescueMode({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a lock action", async () => {
      const action = NodeActions.LOCK;
      const expected = machineActions.lock({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a mark-broken action", async () => {
      const action = NodeActions.MARK_BROKEN;
      const expected = machineActions.markBroken({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a mark-fixed action", async () => {
      const action = NodeActions.MARK_FIXED;
      const expected = machineActions.markFixed({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch an off action", async () => {
      const action = NodeActions.OFF;
      const expected = machineActions.off({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch an on action", async () => {
      const action = NodeActions.ON;
      const expected = machineActions.on({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch an override-failed-testing action", async () => {
      const action = NodeActions.OVERRIDE_FAILED_TESTING;
      const expected = machineActions.overrideFailedTesting({
        system_id: "abc123",
      });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a release action", async () => {
      const action = NodeActions.RELEASE;
      const expected = machineActions.release({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a rescue-mode action", async () => {
      const action = NodeActions.RESCUE_MODE;
      const expected = machineActions.rescueMode({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch a test action", async () => {
      const action = NodeActions.TEST;
      const expected = machineActions.test({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });

    it("can dispatch an unlock action", async () => {
      const action = NodeActions.UNLOCK;
      const expected = machineActions.unlock({ system_id: "abc123" });
      const dispatched = await dispatchAction(action, expected.type);
      expect(dispatched).toStrictEqual(expected);
    });
  });
});
