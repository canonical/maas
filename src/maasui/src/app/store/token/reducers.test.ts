import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("token reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(
      factory.tokenState({
        errors: null,
        loading: false,
        loaded: false,
        items: [],
        saved: false,
        saving: false,
      })
    );
  });

  it("should correctly reduce fetchStart", () => {
    const initialState = factory.tokenState({ loading: false });
    expect(reducers(initialState, actions.fetchStart())).toEqual(
      factory.tokenState({
        loading: true,
      })
    );
  });

  it("should correctly reduce fetchSuccess", () => {
    const initialState = factory.tokenState({
      loading: true,
      loaded: false,
      items: [],
    });
    const items = [factory.token(), factory.token()];
    expect(reducers(initialState, actions.fetchSuccess(items))).toEqual(
      factory.tokenState({
        loading: false,
        loaded: true,
        items,
      })
    );
  });

  it("should correctly reduce fetchError", () => {
    const initialState = factory.tokenState({
      errors: null,
      loading: true,
    });
    expect(
      reducers(initialState, actions.fetchError("Unable to list SSL keys"))
    ).toEqual(
      factory.tokenState({
        errors: "Unable to list SSL keys",
        loading: false,
      })
    );
  });

  it("should correctly reduce createStart", () => {
    const initialState = factory.tokenState({ saving: false });
    expect(reducers(initialState, actions.createStart())).toEqual(
      factory.tokenState({
        saving: true,
      })
    );
  });

  it("should correctly reduce createError", () => {
    const initialState = factory.tokenState({ saving: true });
    expect(
      reducers(initialState, actions.createError({ key: "Key already exists" }))
    ).toEqual(
      factory.tokenState({
        errors: { key: "Key already exists" },
        saving: false,
      })
    );
  });

  it("should correctly reduce createSuccess", () => {
    const initialState = factory.tokenState({
      saved: false,
      saving: true,
    });
    expect(reducers(initialState, actions.createSuccess())).toEqual(
      factory.tokenState({
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce deleteStart", () => {
    const initialState = factory.tokenState({
      saved: true,
      saving: false,
    });
    expect(reducers(initialState, actions.deleteStart())).toEqual(
      factory.tokenState({
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce deleteError", () => {
    const initialState = factory.tokenState({ errors: null, saving: true });
    expect(
      reducers(initialState, actions.deleteError("Could not delete"))
    ).toEqual(
      factory.tokenState({
        errors: "Could not delete",
        saving: false,
      })
    );
  });

  it("should correctly reduce deleteSuccess", () => {
    const initialState = factory.tokenState({ saved: false });
    expect(reducers(initialState, actions.deleteSuccess())).toEqual(
      factory.tokenState({
        saved: true,
      })
    );
  });

  it("should correctly reduce createNotify", () => {
    const items = [factory.token(), factory.token()];
    const initialState = factory.tokenState({ items: [items[0]] });
    expect(reducers(initialState, actions.createNotify(items[1]))).toEqual(
      factory.tokenState({
        items,
      })
    );
  });

  it("should correctly reduce deleteNotify", () => {
    const items = [factory.token(), factory.token()];
    const initialState = factory.tokenState({ items });
    expect(reducers(initialState, actions.deleteNotify(items[0].id))).toEqual(
      factory.tokenState({
        items: [items[1]],
      })
    );
  });

  it("should correctly reduce cleanup", () => {
    const initialState = factory.tokenState({
      errors: { key: "Key already exists" },
      saved: true,
      saving: true,
    });
    expect(reducers(initialState, actions.cleanup())).toEqual(
      factory.tokenState({
        errors: null,
        saved: false,
        saving: false,
      })
    );
  });
});
