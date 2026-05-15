import licensekeys from "./selectors";

import * as factory from "@/testing/factories";

describe("licensekeys selectors", () => {
  describe("all", () => {
    it("returns all license keys", () => {
      const items = [factory.licenseKeys(), factory.licenseKeys()];
      const state = factory.rootState({
        licensekeys: factory.licenseKeysState({
          items,
        }),
      });
      expect(licensekeys.all(state)).toStrictEqual(items);
    });
  });

  describe("loading", () => {
    it("returns licensekeys loading state", () => {
      const state = factory.rootState({
        licensekeys: factory.licenseKeysState({
          loading: true,
        }),
      });
      expect(licensekeys.loading(state)).toStrictEqual(true);
    });
  });

  describe("loaded", () => {
    it("returns license keys loaded state", () => {
      const state = factory.rootState({
        licensekeys: factory.licenseKeysState({
          loaded: true,
        }),
      });
      expect(licensekeys.loaded(state)).toStrictEqual(true);
    });
  });

  describe("saved", () => {
    it("returns license keys saved state", () => {
      const state = factory.rootState({
        licensekeys: factory.licenseKeysState({
          saved: true,
        }),
      });
      expect(licensekeys.saved(state)).toStrictEqual(true);
    });
  });

  describe("search", () => {
    it("filters license keys by term", () => {
      const items = [
        factory.licenseKeys(),
        factory.licenseKeys({
          distro_series: "2019",
        }),
      ];
      const state = factory.rootState({
        licensekeys: factory.licenseKeysState({
          items,
        }),
      });
      expect(licensekeys.search(state, "2019")).toStrictEqual([items[1]]);
    });
  });
});
