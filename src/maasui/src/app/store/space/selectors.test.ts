import space from "./selectors";

import * as factory from "@/testing/factories";

describe("space selectors", () => {
  it("can get all items", () => {
    const items = [factory.space()];
    const state = factory.rootState({
      space: factory.spaceState({
        items,
      }),
    });
    expect(space.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      space: factory.spaceState({
        loading: true,
      }),
    });
    expect(space.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      space: factory.spaceState({
        loaded: true,
      }),
    });
    expect(space.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      space: factory.spaceState({
        saving: true,
      }),
    });
    expect(space.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      space: factory.spaceState({
        saved: true,
      }),
    });
    expect(space.saved(state)).toEqual(true);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      space: factory.spaceState({
        errors: "errors!",
      }),
    });
    expect(space.errors(state)).toEqual("errors!");
  });

  it("can get a space by id", () => {
    const items = [factory.space({ id: 10 }), factory.space({ id: 42 })];
    const state = factory.rootState({
      space: factory.spaceState({
        items,
      }),
    });
    expect(space.getById(state, 42)).toStrictEqual(items[1]);
  });

  it("can filter spaces by name", () => {
    const items = [
      factory.space({ name: "abc" }),
      factory.space({ name: "def" }),
    ];
    const state = factory.rootState({
      space: factory.spaceState({
        items,
      }),
    });
    expect(space.search(state, "d")).toStrictEqual([items[1]]);
  });

  it("can get the active space's id", () => {
    const state = factory.rootState({
      space: factory.spaceState({
        active: 0,
      }),
    });
    expect(space.activeID(state)).toEqual(0);
  });

  it("can get the active space", () => {
    const activeFabric = factory.space();
    const state = factory.rootState({
      space: factory.spaceState({
        active: activeFabric.id,
        items: [activeFabric],
      }),
    });
    expect(space.active(state)).toEqual(activeFabric);
  });
});
