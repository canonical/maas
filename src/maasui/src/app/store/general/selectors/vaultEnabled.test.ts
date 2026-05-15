import vaultEnabled from "./vaultEnabled";

import * as factory from "@/testing/factories";

describe("get", () => {
  it("returns vaultEnabled", () => {
    const state = factory.rootState({
      general: factory.generalState({
        vaultEnabled: factory.vaultEnabledState({
          data: false,
        }),
      }),
    });
    expect(vaultEnabled.get(state)).toStrictEqual(false);
  });
});

describe("loading", () => {
  it("returns vaultEnabled loading state", () => {
    const state = factory.rootState({
      general: factory.generalState({
        vaultEnabled: factory.vaultEnabledState({
          loading: true,
        }),
      }),
    });
    expect(vaultEnabled.loading(state)).toStrictEqual(true);
  });
});

describe("loaded", () => {
  it("returns vaultEnabled loaded state", () => {
    const state = factory.rootState({
      general: factory.generalState({
        vaultEnabled: factory.vaultEnabledState({
          loaded: true,
        }),
      }),
    });
    expect(vaultEnabled.loaded(state)).toStrictEqual(true);
  });
});

describe("errors", () => {
  it("returns vaultEnabled errors state", () => {
    const errors = "Cannot fetch Vault status";
    const state = factory.rootState({
      general: factory.generalState({
        vaultEnabled: factory.vaultEnabledState({
          errors,
        }),
      }),
    });
    expect(vaultEnabled.errors(state)).toStrictEqual(errors);
  });
});
