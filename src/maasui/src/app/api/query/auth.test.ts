import { describe, it, expect, vi, beforeEach } from "vitest";

import {
  useActiveOauthProvider,
  useAuthenticate,
  useCompleteIntro,
  useCreateOauthProvider,
  useCreateSession,
  useDeleteOauthProvider,
  useExtendSession,
  useGetCallback,
  useGetCurrentUser,
  useGetIsSuperUser,
  useIsOIDCUser,
  usePreLogin,
  useUpdateOauthProvider,
} from "@/app/api/query/auth";
import { Labels } from "@/app/login/Login/Login";
import { setCookie } from "@/app/utils";
import { COOKIE_NAMES } from "@/app/utils/cookies";
import {
  authResolvers,
  mockAuth,
  mockOauthProvider,
} from "@/testing/resolvers/auth";
import {
  renderHookWithProviders,
  setupMockServer,
  waitFor,
} from "@/testing/utils";

vi.mock("@/app/utils", async () => {
  const actual = await vi.importActual("@/app/utils");
  return {
    ...actual,
    setCookie: vi.fn(),
  };
});

const mockServer = setupMockServer(
  authResolvers.authenticate.handler(),
  authResolvers.preLogin.handler(),
  authResolvers.createSession.handler(),
  authResolvers.isOidcUser.handler(),
  authResolvers.getCallback.handler(),
  authResolvers.extendSession.handler(),
  authResolvers.getCurrentUser.handler(),
  authResolvers.completeIntro.handler(),
  authResolvers.getActiveOauthProvider.handler(),
  authResolvers.createOauthProvider.handler(),
  authResolvers.updateOauthProvider.handler(),
  authResolvers.deleteOauthProvider.handler()
);

describe("usePreLogin", () => {
  it("should get pre-login data", async () => {
    const { result } = renderHookWithProviders(() => usePreLogin());
    result.current.mutate({});
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useAuthenticate", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("should authenticate the user and handle success flow", async () => {
    const { result, store } = renderHookWithProviders(() => useAuthenticate());

    result.current.mutate({
      body: {
        username: "username",
        password: "password",
      },
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(vi.mocked(setCookie)).toHaveBeenCalledWith(
      COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME,
      expect.any(String),
      {
        sameSite: "Strict",
        path: "/",
      }
    );
    expect(vi.mocked(setCookie)).toHaveBeenCalledWith(
      COOKIE_NAMES.LOCAL_REFRESH_TOKEN_NAME,
      expect.any(String),
      {
        sameSite: "Strict",
        path: "/",
      }
    );

    await waitFor(() => {
      const actions = store.getActions();
      expect(actions).toContainEqual(
        expect.objectContaining({ type: "status/loginSuccess" })
      );
    });
  });

  it("should handle 401 authentication errors", async () => {
    mockServer.use(
      authResolvers.authenticate.error({
        code: 401,
        message: "Unauthorized",
        kind: "Error",
      })
    );

    const { result, store } = renderHookWithProviders(() => useAuthenticate());

    result.current.mutate({
      body: {
        username: "invalid",
        password: "invalid",
      },
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    await waitFor(() => {
      const actions = store.getActions();
      expect(actions).toContainEqual(
        expect.objectContaining({
          type: "status/loginError",
          payload: Labels.IncorrectCredentials,
        })
      );
    });

    expect(vi.mocked(setCookie)).not.toHaveBeenCalled();
  });
});

describe("useIsOIDCUser", () => {
  it("should check if the user is an OIDC user and return the correct result", async () => {
    const { result } = renderHookWithProviders(() =>
      useIsOIDCUser(
        {
          query: {
            email: "username",
            redirect_target: "/machines",
          },
        },
        true
      )
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject({
      is_oidc: false,
    });
    expect(result.current.loginState).toMatchObject({
      step: "PASSWORD",
      oidcURL: "",
      providerName: "",
    });
  });

  it("should handle 409 conflict errors", async () => {
    mockServer.use(
      authResolvers.isOidcUser.error({
        code: 409,
        message: "Conflict",
        kind: "Error",
      })
    );

    const { result, store } = renderHookWithProviders(() =>
      useIsOIDCUser(
        {
          query: {
            email: "username",
            redirect_target: "/machines",
          },
        },
        true
      )
    );

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    await waitFor(() => {
      const actions = store.getActions();
      expect(actions).toContainEqual(
        expect.objectContaining({
          type: "status/loginError",
          payload: Labels.MissingProviderConfig,
        })
      );
    });
    expect(result.current.loginState).toMatchObject({
      step: "USERNAME",
      oidcURL: "",
      providerName: "",
    });
  });

  it("should change login step to OIDC when the user is an OIDC user", async () => {
    mockServer.use(
      authResolvers.isOidcUser.handler({
        is_oidc: true,
        auth_url: "https://oidc-provider.com/auth",
        provider_name: "Mock OIDC Provider",
      })
    );

    const { result } = renderHookWithProviders(() =>
      useIsOIDCUser(
        {
          query: {
            email: "username",
            redirect_target: "/machines",
          },
        },
        true
      )
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.loginState).toMatchObject({
      step: "OIDC",
      oidcURL: "https://oidc-provider.com/auth",
      providerName: "Mock OIDC Provider",
    });
  });
});

describe("useGetCallback", () => {
  it("should get the callback URL for OIDC authentication", async () => {
    const { result } = renderHookWithProviders(() =>
      useGetCallback(
        {
          query: {
            state: "mock_state",
            code: "mock_code",
          },
        },
        true
      )
    );

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data).toMatchObject({
      redirect_target: "/devices",
    });
  });
});

describe("useCreateSession", () => {
  it("should create a session", async () => {
    const { result } = renderHookWithProviders(() => useCreateSession());
    result.current.mutate({});
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useExtendSession", () => {
  it("should extend a session", async () => {
    const { result } = renderHookWithProviders(() => useExtendSession());
    result.current.mutate({});
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useGetCurrentUser", () => {
  it("should return the correct user", async () => {
    const expectedUser = mockAuth;
    const { result } = renderHookWithProviders(() => useGetCurrentUser());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedUser);
  });
});

describe("useGetIsSuperUser", () => {
  it("should return the correct authorization", async () => {
    const expectedUser = mockAuth;
    const { result } = renderHookWithProviders(() => useGetIsSuperUser());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toEqual(expectedUser.is_superuser);
  });
});

describe("useCompleteIntro", () => {
  it("should complete intro", async () => {
    const { result } = renderHookWithProviders(() => useCompleteIntro());
    result.current.mutate({});
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useActiveOauthProvider", () => {
  it("should return the active OAuth provider", async () => {
    const expectedProvider = mockOauthProvider;
    const { result } = renderHookWithProviders(() => useActiveOauthProvider());
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
    expect(result.current.data).toMatchObject(expectedProvider);
  });
});

describe("useCreateOauthProvider", () => {
  it("should create a new OAuth provider", async () => {
    const { result } = renderHookWithProviders(() => useCreateOauthProvider());
    result.current.mutate({ body: mockOauthProvider });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useUpdateOauthProvider", () => {
  it("should update an OAuth provider", async () => {
    const { result } = renderHookWithProviders(() => useUpdateOauthProvider());
    result.current.mutate({
      body: mockOauthProvider,
      path: { provider_id: 1 },
    });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});

describe("useDeleteOauthProvider", () => {
  it("should delete an OAuth provider", async () => {
    const { result } = renderHookWithProviders(() => useDeleteOauthProvider());
    result.current.mutate({ path: { provider_id: 1 } });
    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });
});
