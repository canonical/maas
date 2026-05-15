import powerTypes from "./powerTypes";

import * as factory from "@/testing/factories";

describe("powerTypes selectors", () => {
  describe("get", () => {
    it("returns powerTypes", () => {
      const data = [factory.powerType()];
      const state = factory.rootState({
        general: factory.generalState({
          powerTypes: factory.powerTypesState({
            data,
          }),
        }),
      });
      expect(powerTypes.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns powerTypes loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          powerTypes: factory.powerTypesState({
            loading,
          }),
        }),
      });
      expect(powerTypes.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns powerTypes loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          powerTypes: factory.powerTypesState({
            loaded,
          }),
        }),
      });
      expect(powerTypes.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns powerTypes errors state", () => {
      const errors = "Cannot fetch powerTypes.";
      const state = factory.rootState({
        general: factory.generalState({
          powerTypes: factory.powerTypesState({
            errors,
          }),
        }),
      });
      expect(powerTypes.errors(state)).toStrictEqual(errors);
    });
  });

  describe("canProbe", () => {
    it("returns powerTypes that can be used with add_chassis", () => {
      const probePowerTypes = [
        factory.powerType({ can_probe: true }),
        factory.powerType({ can_probe: true }),
      ];
      const nonProbePowerType = factory.powerType({ can_probe: false });
      const state = factory.rootState({
        general: factory.generalState({
          powerTypes: factory.powerTypesState({
            data: [...probePowerTypes, nonProbePowerType],
          }),
        }),
      });
      expect(powerTypes.canProbe(state)).toStrictEqual(probePowerTypes);
    });
  });
});
