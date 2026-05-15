import { it, expect, vi, type Mock } from "vitest";

import { DEFAULT_HEADERS, fetchWithAuth, getFullApiUrl } from "./base";

import { getCookie } from "@/app/utils";

vi.mock("@/app/utils", () => ({ getCookie: vi.fn() }));

const mockCsrfToken = "mock-csrf-token";
const url = "https://example.com/api";

const originalFetch = global.fetch;

beforeEach(() => {
  (getCookie as Mock).mockReturnValue(mockCsrfToken);
});

afterAll(() => {
  global.fetch = originalFetch;
});

it("should call fetch with correct parameters", async () => {
  const mockResponse = {
    ok: true,
    json: vi.fn().mockResolvedValue({ data: "test" }),
  };
  global.fetch = vi.fn().mockResolvedValue(mockResponse);

  const options = { method: "POST", body: JSON.stringify({ test: true }) };
  const result = await fetchWithAuth(url, options);

  expect(fetch).toHaveBeenCalledWith(url, {
    ...options,
    headers: { ...DEFAULT_HEADERS, "X-CSRFToken": mockCsrfToken },
  });
  expect(result).toEqual({ data: "test" });
});

it("should handle errors", async () => {
  global.fetch = vi
    .fn()
    .mockResolvedValue({ ok: false, statusText: "Bad Request" });
  await expect(fetchWithAuth(url)).rejects.toThrow("Bad Request");
});

it("should handle invalid CSRF token", async () => {
  (getCookie as Mock).mockReturnValue(null);

  const mockResponse = {
    ok: false,
    status: 403,
    statusText: "Forbidden",
  };
  global.fetch = vi.fn().mockResolvedValue(mockResponse);

  await expect(fetchWithAuth(url)).rejects.toThrow("Forbidden");
  expect(fetch).toHaveBeenCalledWith(url, {
    headers: { ...DEFAULT_HEADERS, "X-CSRFToken": "" },
  });
});

it("should generate correct full API URL", () => {
  expect(getFullApiUrl("zones")).toBe("/MAAS/a/v2/zones");
});
