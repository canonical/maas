import type { ReactNode } from "react";

import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import type { MockStoreEnhanced } from "redux-mock-store";

import { useIsAllNetworkingDisabled } from "./node-networking";

import type { Machine } from "@/app/store/machine/types";
import type { RootState } from "@/app/store/root/types";
import { NodeStatus } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

const mockStore = configureStore();

const generateWrapper =
  (store: MockStoreEnhanced<unknown>) =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

describe("machine hook utils", () => {
  let state: RootState;
  let machine: Machine | null;

  beforeEach(() => {
    machine = factory.machine({
      architecture: "amd64",
      locked: false,
      permissions: ["edit"],
      system_id: "abc123",
    });
    state = factory.rootState({
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [factory.powerType()],
        }),
      }),
      machine: factory.machineState({
        items: [machine],
      }),
    });
  });

  describe("useIsAllNetworkingDisabled", () => {
    it("is disabled when machine is not editable", () => {
      machine = factory.machine({
        permissions: [],
        system_id: "abc123",
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useIsAllNetworkingDisabled(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("is disabled when there is no machine", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useIsAllNetworkingDisabled(null), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("is disabled when the machine has the wrong status", () => {
      machine = factory.machine({
        status: NodeStatus.DEPLOYING,
        system_id: "abc123",
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useIsAllNetworkingDisabled(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(true);
    });

    it("can be not disabled", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useIsAllNetworkingDisabled(machine), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(false);
    });

    it("is enabled if the node is a device", () => {
      const store = mockStore(state);
      const { result } = renderHook(
        () => useIsAllNetworkingDisabled(factory.device()),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toBe(false);
    });

    it("is disabled if the node is a controller", () => {
      const store = mockStore(state);
      const { result } = renderHook(
        () => useIsAllNetworkingDisabled(factory.controller()),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toBe(true);
    });
  });
});
