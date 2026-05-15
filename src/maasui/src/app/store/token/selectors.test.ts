import token from "./selectors";

import * as factory from "@/testing/factories";

describe("token selectors", () => {
  describe("all", () => {
    it("returns list of all MAAS configs", () => {
      const items = [factory.token(), factory.token()];
      const state = factory.rootState({
        token: factory.tokenState({
          items,
        }),
      });
      expect(token.all(state)).toStrictEqual(items);
    });
  });

  describe("loading", () => {
    it("returns token loading state", () => {
      const state = factory.rootState({
        token: factory.tokenState({
          loading: false,
        }),
      });
      expect(token.loading(state)).toStrictEqual(false);
    });
  });

  describe("loaded", () => {
    it("returns token loaded state", () => {
      const state = factory.rootState({
        token: factory.tokenState({
          loaded: true,
        }),
      });
      expect(token.loaded(state)).toStrictEqual(true);
    });
  });

  describe("errors", () => {
    it("returns token error state", () => {
      const state = factory.rootState({
        token: factory.tokenState({
          errors: "Unable to list SSH keys.",
        }),
      });
      expect(token.errors(state)).toEqual("Unable to list SSH keys.");
    });
  });

  describe("saving", () => {
    it("returns token saving state", () => {
      const state = factory.rootState({
        token: factory.tokenState({
          saving: false,
        }),
      });
      expect(token.saving(state)).toStrictEqual(false);
    });
  });

  describe("saved", () => {
    it("returns token saved state", () => {
      const state = factory.rootState({
        token: factory.tokenState({
          saved: true,
        }),
      });
      expect(token.saved(state)).toStrictEqual(true);
    });
  });
});
