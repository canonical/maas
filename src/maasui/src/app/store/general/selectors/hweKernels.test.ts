import hweKernels from "./hweKernels";

import * as factory from "@/testing/factories";

describe("hweKernels selectors", () => {
  describe("get", () => {
    it("returns hweKernels", () => {
      const data = [factory.hweKernel(), factory.hweKernel()];
      const state = factory.rootState({
        general: factory.generalState({
          hweKernels: factory.hweKernelsState({
            data,
          }),
        }),
      });
      expect(hweKernels.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns hweKernels loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          hweKernels: factory.hweKernelsState({
            loading,
          }),
        }),
      });
      expect(hweKernels.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns hweKernels loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          hweKernels: factory.hweKernelsState({
            loaded,
          }),
        }),
      });
      expect(hweKernels.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns hweKernels errors state", () => {
      const errors = "Cannot fetch hweKernels.";
      const state = factory.rootState({
        general: factory.generalState({
          hweKernels: factory.hweKernelsState({
            errors,
          }),
        }),
      });
      expect(hweKernels.errors(state)).toStrictEqual(errors);
    });
  });
});
