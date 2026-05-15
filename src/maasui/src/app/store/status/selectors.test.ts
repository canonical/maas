import status from "./selectors";

import * as factory from "@/testing/factories";

describe("status", () => {
  it("can get the connected status", () => {
    const state = factory.rootState({
      status: factory.statusState({
        connected: true,
      }),
    });
    expect(status.connected(state)).toBe(true);
  });

  it("can get the error status", () => {
    const state = factory.rootState({
      status: factory.statusState({
        error: "Timeout",
      }),
    });
    expect(status.error(state)).toBe("Timeout");
  });

  it("can get the authenticated status", () => {
    const state = factory.rootState({
      status: factory.statusState({
        authenticated: false,
      }),
    });
    expect(status.authenticated(state)).toBe(false);
  });

  it("can get the authenticating status", () => {
    const state = factory.rootState({
      status: factory.statusState({
        authenticating: false,
      }),
    });
    expect(status.authenticating(state)).toBe(false);
  });

  it("can get the connecting status", () => {
    const state = factory.rootState({
      status: factory.statusState({
        connecting: false,
      }),
    });
    expect(status.connecting(state)).toBe(false);
  });

  it("can get the external auth url", () => {
    const state = factory.rootState({
      status: factory.statusState({
        externalAuthURL: "http://login.example.com",
      }),
    });
    expect(status.externalAuthURL(state)).toEqual("http://login.example.com");
  });

  it("can get the external login url", () => {
    const state = factory.rootState({
      status: factory.statusState({
        externalLoginURL: "http://login.example.com",
      }),
    });
    expect(status.externalLoginURL(state)).toEqual("http://login.example.com");
  });

  it("can get the noUsers status", () => {
    const state = factory.rootState({
      status: factory.statusState({
        noUsers: true,
      }),
    });
    expect(status.noUsers(state)).toEqual(true);
  });
});
