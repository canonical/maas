import type { ReactNode } from "react";

import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import type { MockStoreEnhanced } from "redux-mock-store";

import { useInitialPowerParameters } from "./hooks";

import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";

const mockStore = configureStore();

const generateWrapper =
  (store: MockStoreEnhanced<unknown>) =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

describe("general hook utils", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState({
      general: factory.generalState({
        powerTypes: factory.powerTypesState({
          data: [
            factory.powerType({
              can_probe: true,
              fields: [
                factory.powerField({
                  default: "",
                  name: "power_address",
                }),
                factory.powerField({
                  default: "",
                  name: "power_pass",
                }),
              ],
            }),
            factory.powerType({
              can_probe: false,
              fields: [
                factory.powerField({
                  default: "1",
                  name: "node_id",
                }),
                factory.powerField({
                  default: "",
                  name: "node_outlet",
                }),
              ],
            }),
          ],
        }),
      }),
    });
  });

  describe("useInitialPowerParameters", () => {
    it("can return the default power parameters for all power types", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useInitialPowerParameters(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toStrictEqual({
        node_id: "1",
        node_outlet: "",
        power_address: "",
        power_pass: "",
      });
    });

    it("can override default power parameters", () => {
      const store = mockStore(state);
      const { result } = renderHook(
        () =>
          useInitialPowerParameters({
            node_id: "2",
            power_address: "192.168.1.1",
          }),
        {
          wrapper: generateWrapper(store),
        }
      );
      expect(result.current).toStrictEqual({
        node_id: "2",
        node_outlet: "",
        power_address: "192.168.1.1",
        power_pass: "",
      });
    });

    it("can filter power parameters to those that are relevant for adding chassis", () => {
      const store = mockStore(state);
      const { result } = renderHook(() => useInitialPowerParameters({}, true), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toStrictEqual({
        power_address: "",
        power_pass: "",
      });
    });
  });
});
