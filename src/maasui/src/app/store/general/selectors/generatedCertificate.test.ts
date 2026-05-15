import generatedCertificate from "./generatedCertificate";

import * as factory from "@/testing/factories";

describe("generatedCertificate selectors", () => {
  describe("get", () => {
    it("returns generatedCertificate", () => {
      const data = factory.generatedCertificate();
      const state = factory.rootState({
        general: factory.generalState({
          generatedCertificate: factory.generatedCertificateState({
            data,
          }),
        }),
      });
      expect(generatedCertificate.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns generatedCertificate loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          generatedCertificate: factory.generatedCertificateState({
            loading,
          }),
        }),
      });
      expect(generatedCertificate.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns generatedCertificate loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          generatedCertificate: factory.generatedCertificateState({
            loaded,
          }),
        }),
      });
      expect(generatedCertificate.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns generatedCertificate errors state", () => {
      const errors = "Cannot fetch generatedCertificate.";
      const state = factory.rootState({
        general: factory.generalState({
          generatedCertificate: factory.generatedCertificateState({
            errors,
          }),
        }),
      });
      expect(generatedCertificate.errors(state)).toStrictEqual(errors);
    });
  });
});
