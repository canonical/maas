import staticRoute from "./selectors";

import * as factory from "@/testing/factories";

describe("all", () => {
  it("returns list of all static routes", () => {
    const items = [factory.staticRoute(), factory.staticRoute()];
    const state = factory.rootState({
      staticroute: factory.staticRouteState({
        items,
      }),
    });
    expect(staticRoute.all(state)).toStrictEqual(items);
  });
});

describe("loading", () => {
  it("returns staticroute loading state", () => {
    const state = factory.rootState({
      staticroute: factory.staticRouteState({
        loading: false,
      }),
    });
    expect(staticRoute.loading(state)).toStrictEqual(false);
  });
});

describe("loaded", () => {
  it("returns staticroute loaded state", () => {
    const state = factory.rootState({
      staticroute: factory.staticRouteState({
        loaded: true,
      }),
    });
    expect(staticRoute.loaded(state)).toStrictEqual(true);
  });
});

describe("errors", () => {
  it("returns staticroute error state", () => {
    const state = factory.rootState({
      staticroute: factory.staticRouteState({
        errors: "Unable to list static routes.",
      }),
    });
    expect(staticRoute.errors(state)).toEqual("Unable to list static routes.");
  });
});

describe("saving", () => {
  it("returns staticroute saving state", () => {
    const state = factory.rootState({
      staticroute: factory.staticRouteState({
        saving: true,
      }),
    });
    expect(staticRoute.saving(state)).toStrictEqual(true);
  });
});

describe("saved", () => {
  it("returns staticroute saved state", () => {
    const state = factory.rootState({
      staticroute: factory.staticRouteState({
        saved: true,
      }),
    });
    expect(staticRoute.saved(state)).toStrictEqual(true);
  });
});
