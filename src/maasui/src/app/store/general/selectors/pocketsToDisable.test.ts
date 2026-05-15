import pocketsToDisable from "./pocketsToDisable";

import * as factory from "@/testing/factories";

describe("pocketsToDisable selectors", () => {
  describe("get", () => {
    it("returns pocketsToDisable", () => {
      const data = [factory.pocketToDisable(), factory.pocketToDisable()];
      const state = factory.rootState({
        general: factory.generalState({
          pocketsToDisable: factory.pocketsToDisableState({
            data,
          }),
        }),
      });
      expect(pocketsToDisable.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns pocketsToDisable loading state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          pocketsToDisable: factory.pocketsToDisableState({
            loading: true,
          }),
        }),
      });
      expect(pocketsToDisable.loading(state)).toStrictEqual(true);
    });
  });

  describe("loaded", () => {
    it("returns pocketsToDisable loaded state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          pocketsToDisable: factory.pocketsToDisableState({
            loaded: true,
          }),
        }),
      });
      expect(pocketsToDisable.loaded(state)).toStrictEqual(true);
    });
  });

  describe("errors", () => {
    it("returns pocketsToDisable errors state", () => {
      const errors = "Cannot fetch pockets to disable.";
      const state = factory.rootState({
        general: factory.generalState({
          pocketsToDisable: factory.pocketsToDisableState({
            errors,
          }),
        }),
      });
      expect(pocketsToDisable.errors(state)).toStrictEqual(errors);
    });
  });
});
