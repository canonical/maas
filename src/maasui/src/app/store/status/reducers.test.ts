import reducers from "./slice";

import * as factory from "@/testing/factories";

describe("status", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toStrictEqual(
      factory.statusState({
        authenticated: false,
        authenticating: true,
        authenticationError: null,
        connected: false,
        connecting: false,
        error: null,
        externalAuthURL: null,
        externalLoginURL: null,
        noUsers: false,
      })
    );
  });

  it("should correctly reduce status/websocketConnect", () => {
    expect(
      reducers(
        factory.statusState({
          connected: true,
          connecting: false,
          error: null,
        }),
        {
          type: "status/websocketConnect",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        connected: true,
        connecting: true,
        connectedCount: 0,
        error: null,
      })
    );
  });

  it("should correctly reduce status/websocketConnect on initial connection", () => {
    expect(
      reducers(
        factory.statusState({
          connected: false,
          connecting: false,
          error: null,
        }),
        {
          type: "status/websocketConnect",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        connected: false,
        connecting: true,
        error: null,
      })
    );
  });

  it("should correctly reduce status/websocketDisconnected", () => {
    expect(
      reducers(
        factory.statusState({
          connected: true,
        }),
        {
          type: "status/websocketDisconnected",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        connected: false,
      })
    );
  });

  it("should correctly reduce status/websocketConnected on initial connection", () => {
    expect(
      reducers(
        factory.statusState({
          connected: false,
          connecting: true,
        }),
        {
          type: "status/websocketConnected",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        connected: true,
        connecting: false,
        connectedCount: 1,
      })
    );
  });

  it("should correctly reduce status/websocketConnected on error", () => {
    expect(
      reducers(
        factory.statusState({
          authenticationError: null,
          connected: false,
          connecting: true,
          error: "Timeout",
        }),
        {
          type: "status/websocketConnected",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticationError: null,
        connected: true,
        connecting: false,
        connectedCount: 1,
        error: null,
      })
    );
  });

  it("status/websocketConnected should increment connectedCount on reconnect", () => {
    expect(
      reducers(
        factory.statusState({
          connected: true,
          connectedCount: 1,
        }),
        {
          type: "status/websocketConnected",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        connected: true,
        connecting: false,
        connectedCount: 2,
      })
    );
  });

  it("should correctly reduce status/websocketError", () => {
    expect(
      reducers(factory.statusState({ error: null }), {
        error: true,
        payload: "Error!",
        type: "status/websocketError",
      })
    ).toStrictEqual(
      factory.statusState({
        connected: false,
        connecting: false,
        error: "Error!",
      })
    );
  });

  it("should correctly reduce status/checkAuthenticatedStart", () => {
    expect(
      reducers(
        factory.statusState({
          authenticating: false,
        }),
        {
          type: "status/checkAuthenticatedStart",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticating: true,
      })
    );
  });

  it("should correctly reduce status/checkAuthenticatedSuccess", () => {
    expect(
      reducers(
        factory.statusState({
          authenticating: true,
          authenticated: false,
          noUsers: false,
        }),
        {
          type: "status/checkAuthenticatedSuccess",
          payload: {
            is_authenticated: true,
            external_legacy_login_url: "http://login.example.com",
            no_users: true,
          },
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticating: false,
        authenticated: true,
        externalAuthURL: "http://login.example.com",
        noUsers: true,
      })
    );
  });

  it("should correctly reduce status/loginStart", () => {
    expect(
      reducers(
        factory.statusState({
          authenticating: false,
        }),
        {
          type: "status/loginStart",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticating: true,
      })
    );
  });

  it("should correctly reduce status/loginSuccess", () => {
    expect(
      reducers(
        factory.statusState({
          authenticationError: null,
          authenticated: false,
          authenticating: true,
        }),
        {
          type: "status/loginSuccess",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticationError: null,
        authenticated: true,
        authenticating: false,
        error: null,
      })
    );
  });

  it("should correctly reduce status/externalLoginSuccess", () => {
    expect(
      reducers(
        factory.statusState({
          authenticationError: null,
          authenticated: false,
          authenticating: true,
        }),
        {
          type: "status/externalLoginSuccess",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticationError: null,
        authenticated: true,
        authenticating: false,
        error: null,
      })
    );
  });

  it("should correctly reduce status/loginError", () => {
    expect(
      reducers(
        factory.statusState({
          authenticationError: null,
          error: null,
        }),
        {
          error: true,
          payload: "Username not provided",
          type: "status/loginError",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticating: false,
        authenticationError: "Username not provided",
        error: null,
      })
    );
  });

  it("should correctly reduce status/externalLoginError", () => {
    expect(
      reducers(
        factory.statusState({
          error: null,
        }),
        {
          error: true,
          payload: "Username not provided",
          type: "status/externalLoginError",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticating: false,
        authenticationError: "Username not provided",
        error: null,
      })
    );
  });

  it("should correctly reduce status/checkAuthenticatedError", () => {
    expect(
      reducers(
        factory.statusState({
          authenticating: true,
          authenticated: true,
        }),
        {
          error: true,
          payload: "Gateway Timeout",
          type: "status/checkAuthenticatedError",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticating: false,
        authenticated: false,
        error: "Gateway Timeout",
      })
    );
  });

  it("should correctly reduce LOGOUT_SUCCESS", () => {
    expect(
      reducers(
        factory.statusState({
          authenticated: true,
        }),
        {
          type: "status/logoutSuccess",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        authenticated: false,
      })
    );
  });

  it("should correctly reduce status/externalLoginUrl", () => {
    expect(
      reducers(
        factory.statusState({
          externalLoginURL: null,
        }),
        {
          payload: { url: "http://login.example.com" },
          type: "status/externalLoginURL",
        }
      )
    ).toStrictEqual(
      factory.statusState({
        externalLoginURL: "http://login.example.com",
      })
    );
  });
});
