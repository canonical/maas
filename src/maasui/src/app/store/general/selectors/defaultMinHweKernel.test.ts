import defaultMinHweKernel from "./defaultMinHweKernel";

import * as factory from "@/testing/factories";

describe("defaultMinHweKernel selectors", () => {
  describe("get", () => {
    it("returns defaultMinHweKernel", () => {
      const data = "ga-18.04";
      const state = factory.rootState({
        general: factory.generalState({
          defaultMinHweKernel: factory.defaultMinHweKernelState({
            data,
          }),
        }),
      });
      expect(defaultMinHweKernel.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns defaultMinHweKernel loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          defaultMinHweKernel: factory.defaultMinHweKernelState({
            loading,
          }),
        }),
      });
      expect(defaultMinHweKernel.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns defaultMinHweKernel loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          defaultMinHweKernel: factory.defaultMinHweKernelState({
            loaded,
          }),
        }),
      });
      expect(defaultMinHweKernel.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns defaultMinHweKernel errors state", () => {
      const errors = "Cannot fetch defaultMinHweKernel.";
      const state = factory.rootState({
        general: factory.generalState({
          defaultMinHweKernel: factory.defaultMinHweKernelState({
            errors,
          }),
        }),
      });
      expect(defaultMinHweKernel.errors(state)).toStrictEqual(errors);
    });
  });
});
