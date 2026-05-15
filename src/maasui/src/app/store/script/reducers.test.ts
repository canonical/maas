import reducers from "./slice";

import * as factory from "@/testing/factories";

describe("scripts reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(
      factory.scriptState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      })
    );
  });

  it("should correctly reduce script/fetchStart", () => {
    expect(
      reducers(undefined, {
        type: "script/fetchStart",
      })
    ).toEqual(
      factory.scriptState({
        errors: null,
        items: [],
        loaded: false,
        loading: true,
      })
    );
  });

  it("should correctly reduce script/fetchError", () => {
    expect(
      reducers(undefined, {
        payload: { error: "Unable to fetch scripts" },
        type: "script/fetchError",
      })
    ).toEqual(
      factory.scriptState({
        items: [],
        errors: { error: "Unable to fetch scripts" },
        loaded: false,
        loading: false,
      })
    );
  });

  it("should correctly reduce script/fetchSuccess", () => {
    const items = [
      factory.script({ name: "script 1" }),
      factory.script({ name: "script2" }),
    ];
    expect(
      reducers(
        factory.scriptState({
          items: [],
          loaded: false,
          loading: true,
        }),
        {
          type: "script/fetchSuccess",
          payload: items,
        }
      )
    ).toEqual(
      factory.scriptState({
        items,
        loaded: true,
        loading: false,
      })
    );
  });

  it("should correctly reduce script/deleteStart", () => {
    expect(
      reducers(
        {
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: true,
          saving: false,
        },
        {
          type: "script/deleteStart",
        }
      )
    ).toEqual(
      factory.scriptState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce script/deleteSuccess", () => {
    expect(
      reducers(
        factory.scriptState({
          errors: null,
          saved: false,
          saving: false,
        }),
        {
          type: "script/deleteSuccess",
          payload: null,
        }
      )
    ).toEqual(
      factory.scriptState({
        errors: null,
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce script/deleteError", () => {
    expect(
      reducers(
        {
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: false,
          saving: true,
        },
        {
          payload: { error: "Not found" },
          type: "script/deleteError",
        }
      )
    ).toEqual(
      factory.scriptState({
        errors: { error: "Not found" },
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      })
    );
  });
});
