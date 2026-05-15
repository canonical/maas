import domain from "./selectors";

import * as factory from "@/testing/factories";

describe("domain selectors", () => {
  it("can get all items", () => {
    const items = [factory.domain()];
    const state = factory.rootState({
      domain: factory.domainState({
        items,
      }),
    });
    expect(domain.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        loading: true,
      }),
    });
    expect(domain.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      domain: factory.domainState({
        loaded: true,
      }),
    });
    expect(domain.loaded(state)).toEqual(true);
  });

  it("can get a domain by name", () => {
    const items = [
      factory.domain({ name: "koala" }),
      factory.domain({ name: "kangaroo" }),
    ];
    const state = factory.rootState({
      domain: factory.domainState({
        items,
      }),
    });
    expect(domain.getByName(state, "kangaroo")).toEqual(items[1]);
  });

  it("can get the default domain", () => {
    const items = [
      factory.domain({ is_default: true }),
      factory.domain({ is_default: false }),
    ];
    const state = factory.rootState({
      domain: factory.domainState({
        items,
      }),
    });
    expect(domain.getDefault(state)).toEqual(items[0]);
  });
});
