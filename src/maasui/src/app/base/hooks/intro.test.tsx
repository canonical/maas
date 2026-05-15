import { renderHook, waitFor } from "@testing-library/react";
import { Provider } from "react-redux";
import configureStore from "redux-mock-store";
import type { Mock } from "vitest";

import { useCompletedIntro, useCompletedUserIntro } from "./intro";

import { ConfigNames } from "@/app/store/config/types";
import { getCookie } from "@/app/utils";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import { renderHookWithProviders, setupMockServer } from "@/testing/utils";

const mockStore = configureStore();
setupMockServer(
  authResolvers.getCurrentUser.handler(factory.user({ id: 1 })),
  authResolvers.getMeStatistics.handler(
    factory.userStatistics({ id: 1, completed_intro: true })
  )
);

vi.mock("@/app/utils", async () => {
  const actual: object = await vi.importActual("@/app/utils");
  return { ...actual, getCookie: vi.fn() };
});

describe("intro hooks", () => {
  describe("useCompletedIntro", () => {
    it("gets whether the intro has been completed", () => {
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.COMPLETED_INTRO, value: true }),
          ],
        }),
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCompletedIntro(), {
        wrapper: ({ children }) => (
          <Provider store={store}>{children}</Provider>
        ),
      });
      expect(result.current).toBe(true);
    });

    it("gets whether the intro has been skipped", () => {
      const getCookieMock = getCookie as Mock;
      getCookieMock.mockImplementation(() => "true");
      const state = factory.rootState({
        config: factory.configState({
          items: [
            factory.config({ name: ConfigNames.COMPLETED_INTRO, value: false }),
          ],
        }),
      });
      const store = mockStore(state);
      const { result } = renderHook(() => useCompletedIntro(), {
        wrapper: ({ children }) => (
          <Provider store={store}>{children}</Provider>
        ),
      });
      expect(result.current).toBe(true);
      getCookieMock.mockReset();
    });
  });

  describe("useCompletedUserIntro", () => {
    it("gets whether the user intro has been completed", async () => {
      const { result } = renderHookWithProviders(() => useCompletedUserIntro());
      await waitFor(() => {
        expect(result.current).toBe(true);
      });
    });

    it("gets whether the user intro has been skipped", () => {
      const getCookieMock = getCookie as Mock;
      getCookieMock.mockImplementation(() => "true");
      const { result } = renderHookWithProviders(() => useCompletedUserIntro());
      expect(result.current).toBe(true);
      getCookieMock.mockReset();
    });
  });
});
