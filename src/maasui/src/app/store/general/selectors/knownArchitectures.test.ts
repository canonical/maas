import knownArchitectures from "./knownArchitectures";

import * as factory from "@/testing/factories";

describe("knownArchitectures selectors", () => {
  describe("get", () => {
    it("returns knownArchitectures", () => {
      const data = [factory.knownArchitecture(), factory.knownArchitecture()];
      const state = factory.rootState({
        general: factory.generalState({
          knownArchitectures: factory.knownArchitecturesState({
            data,
          }),
        }),
      });
      expect(knownArchitectures.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns knownArchitectures loading state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          knownArchitectures: factory.knownArchitecturesState({
            loading: true,
          }),
        }),
      });
      expect(knownArchitectures.loading(state)).toStrictEqual(true);
    });
  });

  describe("loaded", () => {
    it("returns knownArchitectures loaded state", () => {
      const state = factory.rootState({
        general: factory.generalState({
          knownArchitectures: factory.knownArchitecturesState({
            loaded: true,
          }),
        }),
      });
      expect(knownArchitectures.loaded(state)).toStrictEqual(true);
    });
  });

  describe("errors", () => {
    it("returns knownArchitectures errors state", () => {
      const errors = "Cannot fetch known architectures.";
      const state = factory.rootState({
        general: factory.generalState({
          knownArchitectures: factory.knownArchitecturesState({
            errors,
          }),
        }),
      });
      expect(knownArchitectures.errors(state)).toStrictEqual(errors);
    });
  });
});
