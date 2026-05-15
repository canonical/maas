import { getCookie, setCookie, clearCookie } from "@/app/utils";

describe("cookies", () => {
  let cookieStore = "";

  beforeAll(() => {
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get: () => cookieStore,
      set: (value: string) => {
        cookieStore = value;
      },
    });
  });
  beforeEach(() => {
    cookieStore = "";
  });
  describe("getCookie", () => {
    it("returns null if a cookie is not found", () => {
      expect(getCookie("foo")).toBeNull();
    });

    it("returns the value of a cookie by name", () => {
      cookieStore = "a=foo; b=bar; c=baz";
      expect(getCookie("b")).toBe("bar");
    });
  });
  describe("setCookie", () => {
    it("sets a cookie with the right options", () => {
      const expires = new Date("2030-01-01T00:00:00Z");
      setCookie("testKey", "testValue", {
        expires,
        domain: "example.com",
        secure: true,
        sameSite: "Lax",
      });
      expect(document.cookie).toBe(
        "testKey=testValue; Expires=Tue, 01 Jan 2030 00:00:00 GMT; Domain=example.com; SameSite=Lax; Secure"
      );
    });
  });
  describe("clearCookie", () => {
    it("clears a cookie by setting its expiration date to the past", () => {
      clearCookie("testKey", { path: "/", domain: "example.com" });
      expect(document.cookie).toBe(
        "testKey=; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/; Domain=example.com"
      );
    });
  });
});
