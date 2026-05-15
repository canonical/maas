import componentsToDisable from "./componentsToDisable";

import * as factory from "@/testing/factories";

describe("componentsToDisable selectors", () => {
  describe("get", () => {
    it("returns componentsToDisable", () => {
      const data = [factory.componentToDisable(), factory.componentToDisable()];
      const state = factory.rootState({
        general: factory.generalState({
          componentsToDisable: factory.componentsToDisableState({
            data,
          }),
        }),
      });
      expect(componentsToDisable.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns componentsToDisable loading state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          componentsToDisable: factory.componentsToDisableState({
            loading: true,
          }),
        }),
      });
      expect(componentsToDisable.loading(state)).toStrictEqual(true);
    });
  });

  describe("loaded", () => {
    it("returns componentsToDisable loaded state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          componentsToDisable: factory.componentsToDisableState({
            loaded: true,
          }),
        }),
      });
      expect(componentsToDisable.loaded(state)).toStrictEqual(true);
    });
  });

  describe("errors", () => {
    it("returns componentsToDisable errors state", () => {
      const errors = "Cannot fetch components to disable.";
      const state = factory.rootState({
        general: factory.generalState({
          componentsToDisable: factory.componentsToDisableState({
            errors,
          }),
        }),
      });
      expect(componentsToDisable.errors(state)).toStrictEqual(errors);
    });
  });
});
