import architectures from "./architectures";

import * as factory from "@/testing/factories";

describe("architectures selectors", () => {
  describe("get", () => {
    it("returns architectures", () => {
      const data = ["amd64/generic"];
      const state = factory.rootState({
        general: factory.generalState({
          architectures: factory.architecturesState({
            data,
          }),
        }),
      });
      expect(architectures.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns architectures loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          architectures: factory.architecturesState({
            loading,
          }),
        }),
      });
      expect(architectures.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns architectures loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          architectures: factory.architecturesState({
            loaded,
          }),
        }),
      });
      expect(architectures.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns architectures errors state", () => {
      const errors = "Cannot fetch architectures.";
      const state = factory.rootState({
        general: factory.generalState({
          architectures: factory.architecturesState({
            errors,
          }),
        }),
      });
      expect(architectures.errors(state)).toStrictEqual(errors);
    });
  });
});
