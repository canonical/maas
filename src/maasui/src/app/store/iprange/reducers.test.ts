import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

it("should return the initial state", () => {
  expect(reducers(undefined, { type: "" })).toEqual(
    factory.ipRangeState({
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
  const initialState = factory.ipRangeState({
    errors: { key: "Key already exists" },
    saved: true,
    saving: true,
  });
  expect(reducers(initialState, actions.cleanup())).toEqual(
    factory.ipRangeState({
      errors: null,
      saved: false,
      saving: false,
    })
  );
});

describe("fetch reducers", () => {
  it("should correctly reduce fetchStart", () => {
    const initialState = factory.ipRangeState({ loading: false });
    expect(reducers(initialState, actions.fetchStart())).toEqual(
      factory.ipRangeState({
        loading: true,
      })
    );
  });

  it("should correctly reduce fetchSuccess", () => {
    const initialState = factory.ipRangeState({
      loading: true,
      loaded: false,
      items: [],
    });
    const items = [factory.ipRange(), factory.ipRange()];
    expect(reducers(initialState, actions.fetchSuccess(items))).toEqual(
      factory.ipRangeState({
        loading: false,
        loaded: true,
        items,
      })
    );
  });

  it("should correctly reduce fetchError", () => {
    const initialState = factory.ipRangeState({
      errors: null,
      loading: true,
    });
    expect(
      reducers(initialState, actions.fetchError("Unable to list IP ranges"))
    ).toEqual(
      factory.ipRangeState({
        errors: "Unable to list IP ranges",
        loading: false,
      })
    );
  });
});

describe("create reducers", () => {
  it("should correctly reduce createStart", () => {
    const initialState = factory.ipRangeState({ saving: false });
    expect(reducers(initialState, actions.createStart())).toEqual(
      factory.ipRangeState({
        saving: true,
      })
    );
  });

  it("should correctly reduce createError", () => {
    const initialState = factory.ipRangeState({ saving: true });
    expect(
      reducers(initialState, actions.createError({ key: "Key already exists" }))
    ).toEqual(
      factory.ipRangeState({
        errors: { key: "Key already exists" },
        saving: false,
      })
    );
  });

  it("should correctly reduce createSuccess", () => {
    const initialState = factory.ipRangeState({
      saved: false,
      saving: true,
    });
    expect(reducers(initialState, actions.createSuccess())).toEqual(
      factory.ipRangeState({
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce createNotify", () => {
    const items = [factory.ipRange(), factory.ipRange()];
    const initialState = factory.ipRangeState({ items: [items[0]] });
    expect(reducers(initialState, actions.createNotify(items[1]))).toEqual(
      factory.ipRangeState({
        items,
      })
    );
  });
});

describe("delete reducers", () => {
  it("should correctly reduce deleteStart", () => {
    const initialState = factory.ipRangeState({
      saved: true,
      saving: false,
    });
    expect(reducers(initialState, actions.deleteStart())).toEqual(
      factory.ipRangeState({
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce deleteError", () => {
    const initialState = factory.ipRangeState({
      errors: null,
      saving: true,
    });
    expect(
      reducers(initialState, actions.deleteError("Could not delete"))
    ).toEqual(
      factory.ipRangeState({
        errors: "Could not delete",
        saving: false,
      })
    );
  });

  it("should correctly reduce deleteSuccess", () => {
    const initialState = factory.ipRangeState({ saved: false });
    expect(reducers(initialState, actions.deleteSuccess())).toEqual(
      factory.ipRangeState({
        saved: true,
      })
    );
  });

  it("should correctly reduce deleteNotify", () => {
    const items = [factory.ipRange(), factory.ipRange()];
    const initialState = factory.ipRangeState({ items });
    expect(reducers(initialState, actions.deleteNotify(items[0].id))).toEqual(
      factory.ipRangeState({
        items: [items[1]],
      })
    );
  });
});

describe("get reducers", () => {
  it("reduces getStart", () => {
    const ipRangeState = factory.ipRangeState({ items: [], loading: false });

    expect(reducers(ipRangeState, actions.getStart())).toEqual(
      factory.ipRangeState({ loading: true })
    );
  });

  it("reduces getSuccess", () => {
    const newIPRange = factory.ipRange();
    const ipRangeState = factory.ipRangeState({
      items: [],
      loading: true,
    });

    expect(reducers(ipRangeState, actions.getSuccess(newIPRange))).toEqual(
      factory.ipRangeState({
        items: [newIPRange],
        loading: false,
      })
    );
  });

  it("reduces getError", () => {
    const ipRangeState = factory.ipRangeState({ loading: true });

    expect(
      reducers(ipRangeState, actions.getError("Could not get ipRange"))
    ).toEqual(
      factory.ipRangeState({
        errors: "Could not get ipRange",
        loading: false,
      })
    );
  });
});
