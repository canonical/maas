import { describe, it, expect, vi, beforeEach } from "vitest";

import { COOKIE_NAMES } from "../utils/cookies";

import { configureAuthInterceptor } from "./auth-interceptor";

import { client } from "@/app/apiclient/client.gen";
import { getCookie } from "@/app/utils";

vi.mock("@/app/apiclient/client.gen", () => ({
  client: {
    interceptors: {
      request: {
        use: vi.fn(),
      },
    },
  },
}));

vi.mock("@/app/utils", () => ({
  getCookie: vi.fn(),
}));

describe("configureAuthInterceptor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("adds Authorization header when token exists", async () => {
    vi.mocked(getCookie).mockReturnValue("test-token-123");
    const mockRequest = {
      headers: new Headers(),
    } as Request;

    configureAuthInterceptor();

    const interceptor = vi.mocked(client.interceptors.request.use).mock
      .calls[0][0];

    const result = await interceptor(mockRequest, { url: "" });

    expect(getCookie).toHaveBeenCalledWith(COOKIE_NAMES.LOCAL_JWT_TOKEN_NAME);
    expect(result.headers.get("Authorization")).toBe("Bearer test-token-123");
  });

  it("does not add Authorization header when token is null", async () => {
    vi.mocked(getCookie).mockReturnValue(null);

    const request = {
      headers: new Headers(),
    } as Request;

    configureAuthInterceptor();

    const interceptor = vi.mocked(client.interceptors.request.use).mock
      .calls[0][0];

    const result = await interceptor(request, { url: "" });

    expect(result.headers.get("Authorization")).toBeNull();
  });
});
