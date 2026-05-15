import tlsCertificate from "./tlsCertificate";

import * as factory from "@/testing/factories";

describe("get", () => {
  it("returns tlsCertificate", () => {
    const data = factory.tlsCertificate();
    const state = factory.rootState({
      general: factory.generalState({
        tlsCertificate: factory.tlsCertificateState({
          data,
        }),
      }),
    });
    expect(tlsCertificate.get(state)).toStrictEqual(data);
  });
});

describe("loading", () => {
  it("returns tlsCertificate loading state", () => {
    const state = factory.rootState({
      general: factory.generalState({
        tlsCertificate: factory.tlsCertificateState({
          loading: true,
        }),
      }),
    });
    expect(tlsCertificate.loading(state)).toStrictEqual(true);
  });
});

describe("loaded", () => {
  it("returns tlsCertificate loaded state", () => {
    const state = factory.rootState({
      general: factory.generalState({
        tlsCertificate: factory.tlsCertificateState({
          loaded: true,
        }),
      }),
    });
    expect(tlsCertificate.loaded(state)).toStrictEqual(true);
  });
});

describe("errors", () => {
  it("returns tlsCertificate errors state", () => {
    const errors = "Cannot fetch TLS certificate";
    const state = factory.rootState({
      general: factory.generalState({
        tlsCertificate: factory.tlsCertificateState({
          errors,
        }),
      }),
    });
    expect(tlsCertificate.errors(state)).toStrictEqual(errors);
  });
});
