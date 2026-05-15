import type { ReactNode } from "react";

import { renderHook } from "@testing-library/react";
import { Provider } from "react-redux";
import type { MockStoreEnhanced } from "redux-mock-store";
import configureStore from "redux-mock-store";

import { useExitURL } from "./hooks";

import urls from "@/app/base/urls";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { user } from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { setupMockServer } from "@/testing/utils";

const mockStore = configureStore();
const mockServer = setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

const generateWrapper =
  (store: MockStoreEnhanced<unknown>) =>
  ({ children }: { children: ReactNode }) => (
    <Provider store={store}>{children}</Provider>
  );

describe("hooks", () => {
  let state: RootState;

  beforeEach(() => {
    state = factory.rootState();
  });

  describe("useExitURL", () => {
    it("gets the exit URL for an admin", () => {
      mockServer.use(
        authResolvers.getCurrentUser.handler(user({ is_superuser: true }))
      );
      const store = mockStore(state);
      const { result } = renderHook(() => useExitURL(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(urls.machines.index);
    });

    it("gets the exit URL for a non-admin", () => {
      mockServer.use(
        authResolvers.getCurrentUser.handler(user({ is_superuser: false }))
      );
      const store = mockStore(state);
      const { result } = renderHook(() => useExitURL(), {
        wrapper: generateWrapper(store),
      });
      expect(result.current).toBe(urls.machines.index);
    });
  });
});
