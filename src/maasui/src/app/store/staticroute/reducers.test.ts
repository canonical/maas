import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

it("should return the initial state", () => {
  expect(reducers(undefined, { type: "" })).toEqual(
    factory.staticRouteState({
      errors: null,
      loading: false,
      loaded: false,
      items: [],
      saved: false,
      saving: false,
    })
  );
});

it("should correctly reduce cleanup", () => {
  const initialState = factory.staticRouteState({
    errors: { key: "Key already exists" },
    saved: true,
    saving: true,
  });
  expect(reducers(initialState, actions.cleanup())).toEqual(
    factory.staticRouteState({
      errors: null,
      saved: false,
      saving: false,
    })
  );
});

describe("fetch reducers", () => {
  it("should correctly reduce fetchStart", () => {
    const initialState = factory.staticRouteState({ loading: false });
    expect(reducers(initialState, actions.fetchStart())).toEqual(
      factory.staticRouteState({
        loading: true,
      })
    );
  });

  it("should correctly reduce fetchSuccess", () => {
    const initialState = factory.staticRouteState({
      loading: true,
      loaded: false,
      items: [],
    });
    const items = [factory.staticRoute(), factory.staticRoute()];
    expect(reducers(initialState, actions.fetchSuccess(items))).toEqual(
      factory.staticRouteState({
        loading: false,
        loaded: true,
        items,
      })
    );
  });

  it("should correctly reduce fetchError", () => {
    const initialState = factory.staticRouteState({
      errors: null,
      loading: true,
    });
    expect(
      reducers(initialState, actions.fetchError("Unable to list static routes"))
    ).toEqual(
      factory.staticRouteState({
        errors: "Unable to list static routes",
        loading: false,
      })
    );
  });
});

describe("create reducers", () => {
  it("should correctly reduce createStart", () => {
    const initialState = factory.staticRouteState({ saving: false });
    expect(reducers(initialState, actions.createStart())).toEqual(
      factory.staticRouteState({
        saving: true,
      })
    );
  });

  it("should correctly reduce createError", () => {
    const initialState = factory.staticRouteState({ saving: true });
    expect(
      reducers(initialState, actions.createError({ key: "Key already exists" }))
    ).toEqual(
      factory.staticRouteState({
        errors: { key: "Key already exists" },
        saving: false,
      })
    );
  });

  it("should correctly reduce createSuccess", () => {
    const initialState = factory.staticRouteState({
      saved: false,
      saving: true,
    });
    expect(reducers(initialState, actions.createSuccess())).toEqual(
      factory.staticRouteState({
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce createNotify", () => {
    const items = [factory.staticRoute(), factory.staticRoute()];
    const initialState = factory.staticRouteState({ items: [items[0]] });
    expect(reducers(initialState, actions.createNotify(items[1]))).toEqual(
      factory.staticRouteState({
        items,
      })
    );
  });
});

describe("delete reducers", () => {
  it("should correctly reduce deleteStart", () => {
    const initialState = factory.staticRouteState({
      saved: true,
      saving: false,
    });
    expect(reducers(initialState, actions.deleteStart())).toEqual(
      factory.staticRouteState({
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce deleteError", () => {
    const initialState = factory.staticRouteState({
      errors: null,
      saving: true,
    });
    expect(
      reducers(initialState, actions.deleteError("Could not delete"))
    ).toEqual(
      factory.staticRouteState({
        errors: "Could not delete",
        saving: false,
      })
    );
  });

  it("should correctly reduce deleteSuccess", () => {
    const initialState = factory.staticRouteState({ saved: false });
    expect(reducers(initialState, actions.deleteSuccess())).toEqual(
      factory.staticRouteState({
        saved: true,
      })
    );
  });

  it("should correctly reduce deleteNotify", () => {
    const items = [factory.staticRoute(), factory.staticRoute()];
    const initialState = factory.staticRouteState({ items });
    expect(reducers(initialState, actions.deleteNotify(items[0].id))).toEqual(
      factory.staticRouteState({
        items: [items[1]],
      })
    );
  });
});
