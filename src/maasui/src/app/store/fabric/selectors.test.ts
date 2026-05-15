import fabric from "./selectors";

import * as factory from "@/testing/factories";

describe("fabric selectors", () => {
  it("can get all items", () => {
    const items = [factory.fabric()];
    const state = factory.rootState({
      fabric: factory.fabricState({
        items,
      }),
    });
    expect(fabric.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        loading: true,
      }),
    });
    expect(fabric.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        loaded: true,
      }),
    });
    expect(fabric.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        saving: true,
      }),
    });
    expect(fabric.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        saved: true,
      }),
    });
    expect(fabric.saved(state)).toEqual(true);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        errors: "errors!",
      }),
    });
    expect(fabric.errors(state)).toEqual("errors!");
  });

  it("can get a fabric by id", () => {
    const items = [factory.fabric({ id: 10 }), factory.fabric({ id: 42 })];
    const state = factory.rootState({
      fabric: factory.fabricState({
        items,
      }),
    });
    expect(fabric.getById(state, 42)).toStrictEqual(items[1]);
  });

  it("can filter fabrics by name", () => {
    const items = [
      factory.fabric({ name: "abc" }),
      factory.fabric({ name: "def" }),
    ];
    const state = factory.rootState({
      fabric: factory.fabricState({
        items,
      }),
    });
    expect(fabric.search(state, "d")).toStrictEqual([items[1]]);
  });

  it("can get the active fabric's id", () => {
    const state = factory.rootState({
      fabric: factory.fabricState({
        active: 0,
      }),
    });
    expect(fabric.activeID(state)).toEqual(0);
  });

  it("can get the active fabric", () => {
    const activeFabric = factory.fabric();
    const state = factory.rootState({
      fabric: factory.fabricState({
        active: activeFabric.id,
        items: [activeFabric],
      }),
    });
    expect(fabric.active(state)).toEqual(activeFabric);
  });
});
