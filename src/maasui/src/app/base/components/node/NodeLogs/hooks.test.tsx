import type { ReactNode } from "react";

import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import type { MockStoreEnhanced } from "redux-mock-store";

import { useGetInstallationOutput } from "./hooks";

import type { RootState } from "@/app/store/root/types";
import {
  ScriptResultNames,
  ScriptResultType,
  ScriptResultStatus,
} from "@/app/store/scriptresult/types";
import * as factory from "@/testing/factories";

const mockStore = configureStore();

const generateWrapper =
  (store: MockStoreEnhanced<unknown>) =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

describe("machine utils", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      machine: factory.machineState({
        items: [factory.machineDetails({ system_id: "abc123" })],
      }),
      nodescriptresult: factory.nodeScriptResultState({
        items: { abc123: [1] },
      }),
      scriptresult: factory.scriptResultState({
        items: [
          factory.scriptResult({
            id: 1,
            name: ScriptResultNames.INSTALL_LOG,
            result_type: ScriptResultType.INSTALLATION,
            status: ScriptResultStatus.PASSED,
          }),
        ],
        logs: {
          1: factory.scriptResultData({
            combined: "Installation output",
          }),
        },
      }),
    });
  });

  describe("useGetInstallationOutput", () => {
    it("fetches the logs if they're not already loaded", () => {
      state.scriptresult.logs = {};
      const store = mockStore(state);
      renderHook(() => useGetInstallationOutput("abc123"), {
        wrapper: generateWrapper(store),
      });
      expect(
        store.getActions().some(({ type }) => type === "scriptresult/getLogs")
      ).toEqual(true);
    });

    it("retrieves the installation log", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useGetInstallationOutput("abc123"), {
        wrapper: generateWrapper(store),
      });
      expect(result.current.log).toBe("Installation output");
      expect(result.current.result).toStrictEqual(state.scriptresult.items[0]);
    });
  });
});
