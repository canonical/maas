import knownBootArchitectures from "./knownBootArchitectures";

import * as factory from "@/testing/factories";

describe("get", () => {
  it("returns knownBootArchitectures", () => {
    const data = [
      factory.knownBootArchitecture(),
      factory.knownBootArchitecture(),
    ];
    const state = factory.rootState({
      general: factory.generalState({
        knownBootArchitectures: factory.knownBootArchitecturesState({
          data,
        }),
      }),
    });
    expect(knownBootArchitectures.get(state)).toStrictEqual(data);
  });
});

describe("loading", () => {
  it("returns knownBootArchitectures loading state", () => {
    const state = factory.rootState({
      general: factory.generalState({
        knownBootArchitectures: factory.knownBootArchitecturesState({
          loading: true,
        }),
      }),
    });
    expect(knownBootArchitectures.loading(state)).toStrictEqual(true);
  });
});

describe("loaded", () => {
  it("returns knownBootArchitectures loaded state", () => {
    const state = factory.rootState({
      general: factory.generalState({
        knownBootArchitectures: factory.knownBootArchitecturesState({
          loaded: true,
        }),
      }),
    });
    expect(knownBootArchitectures.loaded(state)).toStrictEqual(true);
  });
});

describe("errors", () => {
  it("returns knownBootArchitectures errors state", () => {
    const errors = "Cannot fetch known architectures.";
    const state = factory.rootState({
      general: factory.generalState({
        knownBootArchitectures: factory.knownBootArchitecturesState({
          errors,
        }),
      }),
    });
    expect(knownBootArchitectures.errors(state)).toStrictEqual(errors);
  });
});
