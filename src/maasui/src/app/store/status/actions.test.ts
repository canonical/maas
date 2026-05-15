import { actions } from "./slice";

describe("status actions", () => {
  it("should handle logging in", () => {
    const payload = {
      username: "koala",
      password: "gumtree",
    };
    expect(actions.login(payload)).toStrictEqual({
      type: "status/login",
      payload,
    });
  });

  it("should handle logging out", () => {
    expect(actions.logout()).toStrictEqual({
      type: "status/logout",
      payload: null,
    });
  });

  it("should handle checking if the user is authenticated", () => {
    expect(actions.checkAuthenticated()).toStrictEqual({
      type: "status/checkAuthenticated",
      payload: null,
    });
  });

  it("should handle external log in", () => {
    expect(actions.externalLogin()).toStrictEqual({
      type: "status/externalLogin",
      payload: null,
    });
  });

  it("should handle storing the external login URL", () => {
    const payload = {
      url: "http://login.example.com",
    };
    expect(actions.externalLoginURL(payload)).toStrictEqual({
      type: "status/externalLoginURL",
      payload,
    });
  });

  it("should handle connection to a WebSocket", () => {
    expect(actions.websocketConnect()).toEqual({
      type: "status/websocketConnect",
    });
  });
});
