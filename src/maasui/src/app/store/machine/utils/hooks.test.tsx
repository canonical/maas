import type { ReactElement, ReactNode } from "react";

import * as reduxToolkit from "@reduxjs/toolkit";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import type { MockStoreEnhanced } from "redux-mock-store";

import { selectedToFilters } from "./common";
import type { UseFetchMachinesOptions, UseFetchQueryOptions } from "./hooks";
import {
  getCombinedActionStatus,
  useSelectedMachinesActionsDispatch,
  useMachineActionDispatch,
  useDispatchWithCallId,
  useFetchSelectedMachines,
  useHasSelection,
  useCanAddVLAN,
  useCanEditStorage,
  useFormattedOS,
  useHasInvalidArchitecture,
  useIsLimitedEditingAllowed,
  useFetchMachine,
  useFetchMachines,
  useFetchMachineCount,
  useFetchedCount,
} from "./hooks";

import { machineActions } from "@/app/store/machine";
import type {
  FetchFilters,
  FetchGroupKey,
  Machine,
  SelectedMachines,
} from "@/app/store/machine/types";
import * as query from "@/app/store/machine/utils/query";
import type { RootState } from "@/app/store/root/types";
import { NetworkInterfaceTypes } from "@/app/store/types/enum";
import type { FetchNodeStatus, TestParams } from "@/app/store/types/node";
import { NodeStatus, NodeStatusCode } from "@/app/store/types/node";
import * as factory from "@/testing/factories";
import { renderHook, cleanup, waitFor, screen, render } from "@/testing/utils";

const mockStore = configureStore();

vi.mock("@reduxjs/toolkit", async () => {
  const actual: object = await vi.importActual("@reduxjs/toolkit");
  return {
    ...actual,
    nanoid: vi.fn(),
  };
});

describe("machine hook utils", () => {
  let state: RootState;
  let machine: Machine | null;
  const mockCallId = "123456";

  beforeEach(() => {
    machine = factory.machine({
      architecture: "amd64",
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
    vi.spyOn(query, "generateCallId").mockReturnValue(mockCallId);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("useFetchMachineCount", () => {
    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode; filters?: FetchFilters }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("can dispatch machine count action", () => {
      const store = mockStore(state);
      renderHook(() => useFetchMachineCount(), {
        wrapper: generateWrapper(store),
      });
      const expected = machineActions.count(mockCallId);
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });

    it("does not fetch if isEnabled is false", async () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        (queryOptions: UseFetchQueryOptions) =>
          useFetchMachineCount({ hostname: "spotted-quoll" }, queryOptions),
        {
          initialProps: { isEnabled: false },
          wrapper: generateWrapper(store),
        }
      );
      const expectedActionType = machineActions.count(mockCallId).type;
      const getDispatches = () =>
        store
          .getActions()
          .filter((action) => action.type === expectedActionType);
      expect(getDispatches()).toHaveLength(0);
      rerender({ isEnabled: true });
      expect(getDispatches()).toHaveLength(1);
    });

    it("fetches if isEnabled changes back to true", async () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        (queryOptions: UseFetchQueryOptions) =>
          useFetchMachineCount({ hostname: "spotted-quoll" }, queryOptions),
        {
          initialProps: { isEnabled: true },
          wrapper: generateWrapper(store),
        }
      );
      const expectedActionType = machineActions.count(mockCallId).type;
      const getDispatches = () =>
        store
          .getActions()
          .filter((action) => action.type === expectedActionType);
      expect(getDispatches()).toHaveLength(1);
      rerender({ isEnabled: false });
      expect(getDispatches()).toHaveLength(1);
      rerender({ isEnabled: true });
      expect(getDispatches()).toHaveLength(2);
    });

    it("returns the machine count", async () => {
      vi.restoreAllMocks();
      vi.spyOn(query, "generateCallId").mockReturnValue("mocked-nanoid");
      const machineCount = 2;
      const counts = factory.machineStateCounts({
        "mocked-nanoid": factory.machineStateCount({
          count: machineCount,
          loaded: true,
          loading: false,
        }),
      });
      state.machine = factory.machineState({
        loaded: true,
        counts,
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useFetchMachineCount(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current.machineCountLoaded).toBe(true);
      expect(result.current.machineCount).toStrictEqual(machineCount);
    });

    it("does not fetch again with no params", () => {
      const store = mockStore(state);
      const { rerender } = renderHook(() => useFetchMachineCount(), {
        wrapper: generateWrapper(store),
      });
      rerender();
      const expected = machineActions.count(mockCallId);
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
    });

    it("does not fetch again if the filters haven't changed", () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        () => useFetchMachineCount({ hostname: "spotted-quoll" }),
        {
          wrapper: generateWrapper(store),
        }
      );
      rerender({ filters: { hostname: "spotted-quoll" } });
      const expected = machineActions.count(mockCallId);
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
    });

    it("fetches again if the filters change", () => {
      // clera all spies
      vi.restoreAllMocks();
      const store = mockStore(state);
      const { rerender } = renderHook(
        ({ filters }) => useFetchMachineCount(filters),
        {
          initialProps: {
            filters: {
              hostname: "spotted-quoll",
            },
          },
          wrapper: generateWrapper(store),
        }
      );
      rerender({ filters: { hostname: "eastern-quoll" } });
      const expected = machineActions.count(mockCallId);
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(2);
    });

    it("fetches again if the query has been marked as stale", async () => {
      state.machine.counts = {
        [mockCallId]: factory.machineStateCount({
          stale: true,
        }),
      };
      const store = mockStore(state);
      renderHook(() => useFetchMachineCount(), {
        wrapper: generateWrapper(store),
      });
      const expected = machineActions.count(mockCallId);
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
      const getDispatches = () =>
        store.getActions().filter((action) => action.type === expected.type);
      expect(getDispatches()).toHaveLength(2);
    });
  });

  describe("useFetchMachines", () => {
    beforeEach(() => {
      vi.spyOn(reduxToolkit, "nanoid")
        .mockReturnValueOnce(mockCallId)
        .mockReturnValueOnce("mocked-nanoid-2")
        .mockReturnValueOnce("mocked-nanoid-3");
      vi.spyOn(query, "generateCallId").mockReturnValueOnce(mockCallId);
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("can fetch machines", () => {
      const store = mockStore(state);
      renderHook(() => useFetchMachines(), {
        wrapper: generateWrapper(store),
      });
      const expected = machineActions.fetch(mockCallId);
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });

    it("fetches again if the query has been marked as stale", async () => {
      state.machine.lists = {
        [mockCallId]: factory.machineStateList({
          stale: true,
        }),
      };
      const store = mockStore(state);
      renderHook(() => useFetchMachines(), {
        wrapper: generateWrapper(store),
      });
      const expected = machineActions.fetch(mockCallId);
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
      const getDispatches = () =>
        store.getActions().filter((action) => action.type === expected.type);
      expect(getDispatches()).toHaveLength(2);
    });

    it("returns the fetched machines", () => {
      const machines = [
        factory.machine(),
        factory.machine(),
        factory.machine(),
      ];
      state.machine = factory.machineState({
        loaded: true,
        items: [...machines, factory.machine()],
        lists: {
          [mockCallId]: factory.machineStateList({
            loading: true,
            groups: [
              factory.machineStateListGroup({
                items: machines.map(({ system_id }) => system_id),
              }),
            ],
          }),
        },
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useFetchMachines(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current.machines).toStrictEqual(machines);
    });

    it("returns the loaded and loading states", () => {
      state.machine = factory.machineState({
        lists: {
          [mockCallId]: factory.machineStateList({
            loaded: false,
            loading: true,
          }),
        },
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useFetchMachines(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current.loaded).toBe(false);
      expect(result.current.loading).toBe(true);
    });

    it("does not fetch again with no params", () => {
      const store = mockStore(state);
      const { rerender } = renderHook(() => useFetchMachines(), {
        wrapper: generateWrapper(store),
      });
      rerender();
      const expected = machineActions.fetch(mockCallId);
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
    });

    it("does not fetch again if the options haven't changed", () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        (options: UseFetchMachinesOptions) => useFetchMachines(options),
        {
          initialProps: { filters: { hostname: "spotted-quoll" } },
          wrapper: generateWrapper(store),
        }
      );
      rerender({ filters: { hostname: "spotted-quoll" } });
      const expected = machineActions.fetch(mockCallId);
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
    });

    it("does not fetch if isEnabled is false", async () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        (queryOptions: UseFetchQueryOptions) =>
          useFetchMachines(
            { filters: { hostname: "spotted-quoll" } },
            queryOptions
          ),
        {
          initialProps: { isEnabled: false },
          wrapper: generateWrapper(store),
        }
      );
      const expectedActionType = machineActions.fetch(mockCallId).type;
      const getDispatches = () =>
        store
          .getActions()
          .filter((action) => action.type === expectedActionType);
      expect(getDispatches()).toHaveLength(0);
      rerender({ isEnabled: true });
      expect(getDispatches()).toHaveLength(1);
    });

    it("fetches again if isEnabled changes back to true", async () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        (queryOptions: UseFetchQueryOptions) =>
          useFetchMachines(undefined, queryOptions),
        {
          initialProps: { isEnabled: true },
          wrapper: generateWrapper(store),
        }
      );
      const expectedActionType = machineActions.fetch(mockCallId).type;
      const getDispatches = () =>
        store
          .getActions()
          .filter((action) => action.type === expectedActionType);
      expect(getDispatches()).toHaveLength(1);
      rerender({ isEnabled: false });
      expect(getDispatches()).toHaveLength(1);
      rerender({ isEnabled: true });
      expect(getDispatches()).toHaveLength(2);
    });

    it("does not fetch again if the options haven't changed including empty objects", () => {
      const store = mockStore(state);
      const { rerender } = renderHook(
        (options: UseFetchMachinesOptions | null) => useFetchMachines(options),
        {
          initialProps: {},
          wrapper: generateWrapper(store),
        }
      );
      rerender({});
      const expected = machineActions.fetch(mockCallId);
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
    });

    it("fetches again if the options change", () => {
      vi.restoreAllMocks();
      const store = mockStore(state);
      const { rerender } = renderHook(
        (options: UseFetchMachinesOptions) => useFetchMachines(options),
        {
          initialProps: {
            filters: {
              hostname: "spotted-quoll",
            },
          },
          wrapper: generateWrapper(store),
        }
      );
      const expected = machineActions.fetch(mockCallId);
      let getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
      rerender({ filters: { hostname: "eastern-quoll" } });
      getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(2);
    });

    it("resets the page number if the options change", () => {
      const store = mockStore(state);
      const handleSetCurrentPage = vi.fn();
      const initialProps = {
        filters: { hostname: "spotted-quoll" },
        pagination: {
          currentPage: 2,
          setCurrentPage: handleSetCurrentPage,
          pageSize: 10,
        },
      };
      const { rerender } = renderHook(
        (options: UseFetchMachinesOptions) => useFetchMachines(options),
        {
          initialProps,
          wrapper: generateWrapper(store),
        }
      );
      expect(handleSetCurrentPage).not.toHaveBeenCalled();
      rerender({ ...initialProps, filters: { hostname: "eastern-quoll" } });
      expect(handleSetCurrentPage).toHaveBeenCalledWith(1);
    });

    it("cleans up list request on unmount", async () => {
      const store = mockStore(state);
      vi.spyOn(query, "generateCallId").mockReturnValue(mockCallId);
      renderHook(() => useFetchMachines(), {
        wrapper: generateWrapper(store),
      });
      cleanup();
      const expected = machineActions.cleanupRequest(mockCallId);
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });
  });

  const generateWrapper =
    (store: MockStoreEnhanced<unknown>) =>
    ({ children }: { children?: ReactNode }) => (
      <Provider store={store}>{children}</Provider>
    );

  describe("useFetchSelectedMachines", () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("can fetch selected machines", async () => {
      vi.spyOn(query, "generateCallId").mockReturnValueOnce(mockCallId);
      const selected = { items: ["abc123", "def456"] };
      state.machine.selected = selected;
      const store = mockStore(state);
      renderHook(useFetchSelectedMachines, {
        wrapper: generateWrapper(store),
      });
      const expected = machineActions.fetch("mocked-nanoid");
      const actual = store
        .getActions()
        .find((action) => action.type === expected.type);
      expect(actual.payload.params.filter).toStrictEqual(
        selectedToFilters(selected)
      );
    });
  });

  describe("useDispatchWithCallId", () => {
    beforeEach(() => {
      vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");
    });
    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("adds a callId to redux dispatch function", async () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useDispatchWithCallId(), {
        wrapper: generateWrapper(store),
      });
      const testAction = { type: "test" };
      result.current.dispatch(testAction);
      const actual = store
        .getActions()
        .find((action) => action.type === testAction.type);
      await waitFor(() => {
        expect(actual).toStrictEqual({
          type: "test",
          meta: { callId: "mocked-nanoid" },
        });
      });
    });

    it("cleans up request on unmount", async () => {
      const store = mockStore(state);
      renderHook(() => useDispatchWithCallId(), {
        wrapper: generateWrapper(store),
      });
      cleanup();
      const expected = machineActions.removeRequest("mocked-nanoid");
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });
  });

  describe("useMachineActionDispatch", () => {
    beforeEach(() => {
      vi.spyOn(reduxToolkit, "nanoid").mockReturnValue("mocked-nanoid");
    });
    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("adds a callId to redux dispatch function and returns action state", async () => {
      state.machine.actions["mocked-nanoid"] = factory.machineActionState({
        status: "success",
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useMachineActionDispatch(), {
        wrapper: generateWrapper(store),
      });
      const testAction = { type: "test" };
      result.current.dispatch(testAction);

      await waitFor(() => {
        const actual = store
          .getActions()
          .find((action) => action.type === testAction.type);
        expect(actual).toStrictEqual({
          type: "test",
          meta: { callId: "mocked-nanoid" },
        });
      });
      expect(result.current.actionStatus).toEqual("success");
      expect(result.current.actionErrors).toEqual(null);
    });

    it("can return an error message", async () => {
      state.machine.actions["mocked-nanoid"] = factory.machineActionState({
        status: "success",
        failedSystemIds: ["abc123"],
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useMachineActionDispatch(), {
        wrapper: generateWrapper(store),
      });
      const testAction = { type: "test" };
      result.current.dispatch(testAction);

      await waitFor(() => {
        const actual = store
          .getActions()
          .find((action) => action.type === testAction.type);
        expect(actual).toStrictEqual({
          type: "test",
          meta: { callId: "mocked-nanoid" },
        });
      });
      expect(result.current.actionStatus).toEqual("success");
      render(result.current.actionErrors as ReactElement);
      expect(
        screen.getByText(/Action failed for 1 machine/)
      ).toBeInTheDocument();
    });
  });

  describe("useSelectedMachinesActionsDispatch", () => {
    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("dispatches separate calls when there are selected both groups and items", async () => {
      vi.spyOn(reduxToolkit, "nanoid")
        .mockReturnValueOnce("mocked-nanoid")
        .mockReturnValueOnce(mockCallId)
        .mockReturnValueOnce("mocked-nanoid-2");
      state.machine.actions["mocked-nanoid"] = factory.machineActionState({
        status: "success",
      });
      const store = mockStore(state);
      const selectedMachines: SelectedMachines = {
        groups: ["new", "broken"],
        grouping: "status" as FetchGroupKey,
        items: ["abcd123"],
      };
      const { result } = renderHook(
        () =>
          useSelectedMachinesActionsDispatch({
            selectedMachines,
            searchFilter: "",
          }),
        {
          wrapper: generateWrapper(store),
        }
      );
      result.current.dispatch(machineActions.test);
      const expectedGroupsDispatch = machineActions.test({
        filter: {
          status: ["=new" as FetchNodeStatus, "=broken" as FetchNodeStatus],
        },
      });
      const expectedItemsDispatch = machineActions.test({
        filter: { id: ["abcd123"] },
      });

      const actual = store
        .getActions()
        .filter(
          (action) => action.type === machineActions.test({} as TestParams).type
        );
      await waitFor(() => {
        expect(actual[0].payload).toStrictEqual(expectedGroupsDispatch.payload);
      });
      expect(actual[1].payload).toStrictEqual(expectedItemsDispatch.payload);
      expect(result.current.actionErrors).toEqual(null);
    });

    it("dispatches a single call when there are only items selected", async () => {
      vi.spyOn(reduxToolkit, "nanoid")
        .mockReturnValueOnce("mocked-nanoid")
        .mockReturnValueOnce(mockCallId)
        .mockReturnValueOnce("mocked-nanoid-2");
      state.machine.actions["mocked-nanoid"] = factory.machineActionState({
        status: "success",
      });
      const store = mockStore(state);
      const selectedMachines: SelectedMachines = {
        items: ["abcd123"],
      };
      const { result } = renderHook(
        () =>
          useSelectedMachinesActionsDispatch({
            selectedMachines,
            searchFilter: "",
          }),
        {
          wrapper: generateWrapper(store),
        }
      );
      result.current.dispatch(machineActions.test);
      const expectedItemsDispatch = machineActions.test({
        filter: { id: ["abcd123"] },
      });
      const actual = store
        .getActions()
        .filter(
          (action) => action.type === machineActions.test({} as TestParams).type
        );
      await waitFor(() => {
        expect(actual).toHaveLength(1);
      });
      expect(actual[0].payload).toStrictEqual(expectedItemsDispatch.payload);
    });

    it("dispatches a single call when there are only groups selected", async () => {
      vi.spyOn(reduxToolkit, "nanoid")
        .mockReturnValueOnce("mocked-nanoid")
        .mockReturnValueOnce(mockCallId)
        .mockReturnValueOnce("mocked-nanoid-2");
      state.machine.actions["mocked-nanoid"] = factory.machineActionState({
        status: "success",
      });
      const store = mockStore(state);
      const selectedMachines: SelectedMachines = {
        groups: ["new", "broken"],
        grouping: "status" as FetchGroupKey,
      };
      const { result } = renderHook(
        () =>
          useSelectedMachinesActionsDispatch({
            selectedMachines,
            searchFilter: "",
          }),
        {
          wrapper: generateWrapper(store),
        }
      );
      result.current.dispatch(machineActions.test);
      const expectedItemsDispatch = machineActions.test({
        filter: {
          status: ["=new" as FetchNodeStatus, "=broken" as FetchNodeStatus],
        },
      });
      const actual = store
        .getActions()
        .filter(
          (action) => action.type === machineActions.test({} as TestParams).type
        );
      await waitFor(() => {
        expect(actual).toHaveLength(1);
      });
      expect(actual[0].payload).toStrictEqual(expectedItemsDispatch.payload);
    });
  });

  describe("getCombinedActionStatus", () => {
    it("returns success when all actions are successful", () => {
      getCombinedActionStatus("success", "success", "success");
    });
    it("returns error when at least one action is in error", () => {
      getCombinedActionStatus("success", "error", "success");
    });
    it("returns loading when at least one action is loading", () => {
      getCombinedActionStatus("success", "error", "loading");
    });
    it("returns idle when there are no actions", () => {
      getCombinedActionStatus();
    });
  });

  describe("useFetchMachine", () => {
    beforeEach(() => {
      vi.spyOn(query, "generateCallId").mockReturnValueOnce(mockCallId);
    });
    afterEach(() => {
      vi.restoreAllMocks();
    });
    const generateWrapper =
      (store: MockStoreEnhanced<unknown>) =>
      ({ children }: { children?: ReactNode }) => (
        <Provider store={store}>{children}</Provider>
      );

    it("can get a machine", () => {
      vi.spyOn(reduxToolkit, "nanoid").mockReturnValueOnce("mocked-nanoid");
      const store = mockStore(state);
      renderHook(() => useFetchMachine("def456"), {
        wrapper: generateWrapper(store),
      });
      const expected = machineActions.get("def456", "mocked-nanoid");
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });

    it("does not fetch again if the id hasn't changed", () => {
      const store = mockStore(state);
      vi.spyOn(reduxToolkit, "nanoid").mockReturnValueOnce("mocked-nanoid");
      const { rerender } = renderHook(
        ({ id }: { children?: ReactNode; id: string }) => useFetchMachine(id),
        {
          initialProps: {
            id: "def456",
          },
          wrapper: generateWrapper(store),
        }
      );
      rerender({ id: "def456" });
      const expected = machineActions.get("def456", "mocked-nanoid");
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(1);
    });

    it("gets a machine if the id changes", () => {
      vi.spyOn(reduxToolkit, "nanoid")
        .mockReturnValueOnce(mockCallId)
        .mockReturnValueOnce("mocked-nanoid-2");
      const store = mockStore(state);
      const { rerender } = renderHook(
        ({ id }: { children?: ReactNode; id: string }) => useFetchMachine(id),
        {
          initialProps: {
            id: "def456",
          },
          wrapper: generateWrapper(store),
        }
      );
      rerender({ id: "ghi789" });
      const expected = machineActions.get("ghi789", "mocked-nanoid-2");
      const getDispatches = store
        .getActions()
        .filter((action) => action.type === expected.type);
      expect(getDispatches).toHaveLength(2);
      expect(getDispatches[1]).toStrictEqual(expected);
    });

    it("returns the machine and loading states", () => {
      vi.spyOn(reduxToolkit, "nanoid").mockReturnValue(mockCallId);
      const machine = factory.machine({
        system_id: "abc123",
      });
      state.machine = factory.machineState({
        items: [machine, factory.machine()],
        details: {
          [mockCallId]: factory.machineStateDetailsItem({
            loaded: true,
            loading: true,
            system_id: "abc123",
          }),
        },
      });
      const store = mockStore(state);
      const { result } = renderHook(
        ({ id }: { children?: ReactNode; id: string }) => useFetchMachine(id),
        {
          initialProps: {
            id: "abc123",
          },
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current.loaded).toBe(true);
      expect(result.current.loading).toBe(true);
      expect(result.current.machine).toStrictEqual(machine);
    });

    it("cleans up machine request on unmount", async () => {
      vi.spyOn(reduxToolkit, "nanoid").mockReturnValueOnce(mockCallId);
      const store = mockStore(state);
      renderHook(
        ({ id }: { children?: ReactNode; id: string }) => useFetchMachine(id),
        {
          initialProps: {
            id: "def456",
          },
          wrapper: generateWrapper(store),
        }
      );
      cleanup();
      const expected = machineActions.cleanupRequest(mockCallId);
      expect(
        store.getActions().find((action) => action.type === expected.type)
      ).toStrictEqual(expected);
    });

    it("cleans up machine requests when the id changes", async () => {
      vi.spyOn(reduxToolkit, "nanoid")
        .mockReturnValueOnce(mockCallId)
        .mockReturnValueOnce("mocked-nanoid-2");
      const store = mockStore(state);
      const { rerender } = renderHook(
        ({ id }: { children?: ReactNode; id: string }) => useFetchMachine(id),
        {
          initialProps: {
            id: "def123",
          },
          wrapper: generateWrapper(store),
        }
      );

      const expected1 = machineActions.cleanupRequest(mockCallId);
      const expected2 = machineActions.cleanupRequest("mocked-nanoid-2");
      const getCleanupActions = () =>
        store.getActions().filter((action) => action.type === expected1.type);

      rerender({ id: "def456" });
      expect(getCleanupActions()).toHaveLength(1);
      cleanup();
      expect(getCleanupActions()).toHaveLength(2);
      expect(getCleanupActions()[0]).toStrictEqual(expected1);
      expect(getCleanupActions()[1]).toStrictEqual(expected2);
    });
  });

  describe("useCanEditStorage", () => {
    it("handles a machine with editable storage", () => {
      const machine = factory.machineDetails({
        locked: false,
        status_code: NodeStatusCode.READY,
        permissions: ["edit"],
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEditStorage(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("handles a machine without editable storage", () => {
      const machine = factory.machineDetails({
        locked: false,
        status_code: NodeStatusCode.NEW,
        permissions: ["edit"],
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCanEditStorage(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });
  });

  describe("useFormattedOS", () => {
    it("handles null case", () => {
      const store = mockStore(state);

      const { result } = renderHook(() => useFormattedOS(null), {
        wrapper: generateWrapper(store),
      });

      expect(result.current).toBe("");
    });

    it("does not return anything if os info is loading", () => {
      state.machine.items[0].osystem = "ubuntu";
      state.machine.items[0].distro_series = "focal";
      state.general.osInfo.loading = true;
      const store = mockStore(state);
      const { result } = renderHook(() => useFormattedOS(machine), {
        wrapper: generateWrapper(store),
      });

      expect(result.current).toBe("");
    });

    it("can show the full Ubuntu release", () => {
      state.machine.items[0].osystem = "ubuntu";
      state.machine.items[0].distro_series = "focal";
      state.general.osInfo.data = factory.osInfo({
        releases: [["ubuntu/focal", 'Ubuntu 20.04 LTS "Focal Fossa"']],
      });
      const store = mockStore(state);

      const { result } = renderHook(() => useFormattedOS(machine), {
        wrapper: generateWrapper(store),
      });

      expect(result.current).toBe('Ubuntu 20.04 LTS "Focal Fossa"');
    });

    it("can show the short-form for Ubuntu releases", () => {
      state.machine.items[0].osystem = "ubuntu";
      state.machine.items[0].distro_series = "focal";
      state.general.osInfo.data = factory.osInfo({
        releases: [["ubuntu/focal", 'Ubuntu 20.04 LTS "Focal Fossa"']],
      });
      const store = mockStore(state);

      const { result } = renderHook(() => useFormattedOS(machine, true), {
        wrapper: generateWrapper(store),
      });

      expect(result.current).toBe("Ubuntu 20.04 LTS");
    });

    it("handles non-Ubuntu releases", () => {
      state.machine.items[0].osystem = "centos";
      state.machine.items[0].distro_series = "centos70";
      state.general.osInfo.data = factory.osInfo({
        releases: [["centos/centos70", "CentOS 7"]],
      });
      const store = mockStore(state);

      const { result } = renderHook(() => useFormattedOS(machine), {
        wrapper: generateWrapper(store),
      });

      expect(result.current).toBe("CentOS 7");
    });
  });

  describe("useHasInvalidArchitecture", () => {
    it("can return a valid result", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useHasInvalidArchitecture(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("handles a machine that has no architecture", () => {
      state.machine.items[0].architecture = "";
      const store = mockStore(state);
      const { result } = renderHook(() => useHasInvalidArchitecture(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("handles an architecture with no match", () => {
      state.machine.items[0].architecture = "unknown";
      const store = mockStore(state);
      const { result } = renderHook(() => useHasInvalidArchitecture(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });
  });

  describe("useIsLimitedEditingAllowed", () => {
    it("allows limited editing", () => {
      machine = factory.machineDetails({
        locked: false,
        permissions: ["edit"],
        status: NodeStatus.DEPLOYED,
        system_id: "abc123",
      });
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const store = mockStore(state);
      const { result } = renderHook(
        () => useIsLimitedEditingAllowed(nic, machine),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toBe(true);
    });

    it("does not allow limited editing when the machine is not editable", () => {
      machine = factory.machineDetails({
        locked: false,
        permissions: [],
        status: NodeStatus.DEPLOYED,
        system_id: "abc123",
      });
      const nic = factory.machineInterface();
      const store = mockStore(state);
      const { result } = renderHook(
        () => useIsLimitedEditingAllowed(nic, machine),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toBe(false);
    });

    it("does not allow limited editing when the machine is not deployed", () => {
      machine = factory.machineDetails({
        permissions: ["edit"],
        status: NodeStatus.NEW,
        system_id: "abc123",
      });
      const nic = factory.machineInterface();
      const store = mockStore(state);
      const { result } = renderHook(
        () => useIsLimitedEditingAllowed(nic, machine),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toBe(false);
    });

    it("does not allow limited editing when the nic is a VLAN", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const store = mockStore(state);
      const { result } = renderHook(
        () => useIsLimitedEditingAllowed(nic, machine),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toBe(false);
    });
  });

  describe("useCanAddVLAN", () => {
    it("can not add a VLAN if the nic is an alias", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.ALIAS,
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCanAddVLAN(machine, nic), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("can not add a VLAN if the nic is a VLAN", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.VLAN,
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCanAddVLAN(machine, nic), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("can not add a VLAN if there are no unused VLANS", () => {
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCanAddVLAN(machine, nic), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("can add a VLAN if there are unused VLANS", () => {
      const fabric = factory.fabric();
      state.fabric.items = [fabric];
      const vlan = factory.vlan({ fabric: fabric.id });
      state.vlan.items = [vlan];
      const nic = factory.machineInterface({
        type: NetworkInterfaceTypes.PHYSICAL,
        vlan_id: vlan.id,
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCanAddVLAN(machine, nic), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });
  });

  describe("useHasSelection", () => {
    it("can have no selected machines", () => {
      state.machine.selected = null;
      const store = mockStore(state);
      const { result } = renderHook(() => useHasSelection(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("is selected if there are filters", () => {
      state.machine.selected = {
        filter: { hostname: "wistful-wallaby" },
      };
      const store = mockStore(state);
      const { result } = renderHook(() => useHasSelection(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("is selected if there are empty filters", () => {
      state.machine.selected = { filter: {} };
      const store = mockStore(state);
      const { result } = renderHook(() => useHasSelection(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("is selected if there are groups", () => {
      state.machine.selected = { groups: ["Admin 2"] };
      const store = mockStore(state);
      const { result } = renderHook(() => useHasSelection(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("is selected if there are items", () => {
      state.machine.selected = { items: ["abc123"] };
      const store = mockStore(state);
      const { result } = renderHook(() => useHasSelection(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });
  });

  describe("useFetchedCount", () => {
    it("handles when no counts have loaded", () => {
      const { result } = renderHook(() => useFetchedCount(null, false));
      expect(result.current).toBe(0);
    });

    it("handles when the initial count is loading", () => {
      const { result } = renderHook(() => useFetchedCount(null, true));
      expect(result.current).toBe(0);
    });

    it("can display a count", () => {
      const { result } = renderHook(() => useFetchedCount(1, false));
      expect(result.current).toBe(1);
    });

    it("displays the previous count while loading a new one", () => {
      const { rerender, result } = renderHook(() => useFetchedCount(1, false));
      expect(result.current).toBe(1);
      rerender({ count: null, loading: true });
      expect(result.current).toBe(1);
    });

    it("displays the new count when it has loaded", () => {
      const { rerender, result } = renderHook<
        ReturnType<typeof useFetchedCount>,
        {
          count: number | null;
          loading?: boolean | null;
        }
      >(({ count, loading }) => useFetchedCount(count, loading), {
        initialProps: { count: 1, loading: false },
      });
      expect(result.current).toBe(1);
      rerender({ count: null, loading: true });
      expect(result.current).toBe(1);
      rerender({ count: 2, loading: false });
      expect(result.current).toBe(2);
    });
  });
});
