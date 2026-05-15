import createRootReducer from "./root-reducer";

import * as factory from "@/testing/factories";

vi.mock("@/app/api/query/auth", () => ({
  useGetCurrentUser: vi.fn(() => ({
    data: null,
    isLoading: false,
    error: null,
  })),
}));

describe("rootReducer", () => {
  it(`should reset app to initial state on LOGOUT_SUCCESS, except status which
    resets to authenticating = false`, () => {
    const initialState = factory.rootState({
      status: factory.statusState({ authenticating: true }),
    });
    const newState = createRootReducer(
      vi.fn().mockReturnValue(factory.routerState())
    )(initialState, {
      type: "status/logoutSuccess",
    });

    const expectedState = createRootReducer(
      vi.fn().mockReturnValue(factory.routerState())
    )(factory.rootState(), { type: "status/logoutSuccess" });

    expect(newState.status.authenticating).toBe(false);
    expect(newState).toStrictEqual(expectedState);
  });

  it("it should clear the state on status/checkAuthenticatedError", () => {
    const initialState = factory.rootState({
      machine: factory.machineState({
        items: [factory.machine(), factory.machine(), factory.machine()],
      }),
      status: factory.statusState({ authenticating: true }),
    });
    const newState = createRootReducer(
      vi.fn().mockReturnValue(factory.routerState())
    )(initialState, {
      type: "status/checkAuthenticatedError",
    });

    expect(newState.machine.items.length).toBe(0);
    expect(newState.status.authenticating).toBe(false);
  });
});
