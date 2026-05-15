import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

it("should return the initial state", () => {
  expect(reducers(undefined, { type: "" })).toEqual(
    factory.reservedIpState({
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
  const initialState = factory.reservedIpState({
    errors: { key: "Key already exists" },
    saved: true,
    saving: true,
  });
  expect(reducers(initialState, actions.cleanup())).toEqual(
    factory.reservedIpState({
      errors: null,
      saved: false,
      saving: false,
    })
  );
});

describe("fetch reducers", () => {
  it("should correctly reduce fetchStart", () => {
    const initialState = factory.reservedIpState({ loading: false });
    expect(reducers(initialState, actions.fetchStart())).toEqual(
      factory.reservedIpState({
        loading: true,
      })
    );
  });

  it("should correctly reduce fetchSuccess", () => {
    const initialState = factory.reservedIpState({
      loading: true,
      loaded: false,
      items: [],
    });
    const items = [factory.reservedIp(), factory.reservedIp()];
    expect(reducers(initialState, actions.fetchSuccess(items))).toEqual(
      factory.reservedIpState({
        loading: false,
        loaded: true,
        items,
      })
    );
  });

  it("should correctly reduce fetchError", () => {
    const initialState = factory.reservedIpState({
      loading: true,
      loaded: false,
      items: [],
    });
    expect(reducers(initialState, actions.fetchError("Error"))).toEqual(
      factory.reservedIpState({
        loading: false,
        errors: "Error",
      })
    );
  });
});

describe("create reducers", () => {
  it("should correctly reduce createStart", () => {
    const initialState = factory.reservedIpState({ saving: false });
    expect(reducers(initialState, actions.createStart())).toEqual(
      factory.reservedIpState({
        saving: true,
      })
    );
  });

  it("should correctly reduce createSuccess", () => {
    const initialState = factory.reservedIpState({
      saving: true,
      saved: false,
    });

    const reservedIp = factory.reservedIp();
    expect(
      reducers(
        initialState,
        actions.createSuccess(factory.reservedIp(reservedIp))
      )
    ).toEqual(
      factory.reservedIpState({
        saving: false,
        saved: true,
        items: [reservedIp],
      })
    );
  });

  it("should correctly reduce createError", () => {
    const initialState = factory.reservedIpState({
      saving: true,
      saved: false,
    });
    expect(reducers(initialState, actions.createError("Error"))).toEqual(
      factory.reservedIpState({
        saving: false,
        errors: "Error",
      })
    );
  });

  it("should correctly reduce createNotify", () => {
    const items = [factory.reservedIp(), factory.reservedIp()];
    const initialState = factory.reservedIpState({
      items: [items[0]],
    });
    expect(reducers(initialState, actions.createNotify(items[1]))).toEqual(
      factory.reservedIpState({
        items,
      })
    );
  });
});

describe("update reducers", () => {
  it("should correctly reduce updateStart", () => {
    const initialState = factory.reservedIpState({ saving: false });
    expect(reducers(initialState, actions.updateStart())).toEqual(
      factory.reservedIpState({
        saving: true,
      })
    );
  });

  it("should correctly reduce updateSuccess", () => {
    const reservedIp = factory.reservedIp();
    const initialState = factory.reservedIpState({
      items: [reservedIp],
      saving: true,
      saved: false,
    });
    expect(reducers(initialState, actions.updateSuccess(reservedIp))).toEqual(
      factory.reservedIpState({
        saving: false,
        saved: true,
        items: [reservedIp],
      })
    );
  });

  it("should correctly reduce updateError", () => {
    const initialState = factory.reservedIpState({
      saving: true,
      saved: false,
    });
    expect(reducers(initialState, actions.updateError("Error"))).toEqual(
      factory.reservedIpState({
        saving: false,
        errors: "Error",
      })
    );
  });

  it("should correctly reduce updateNotify", () => {
    const items = [factory.reservedIp(), factory.reservedIp()];
    const initialState = factory.reservedIpState({
      items,
    });
    expect(
      reducers(initialState, actions.updateNotify(items[1])).items
    ).toEqual(items);
  });
});

describe("delete reducers", () => {
  it("should correctly reduce deleteStart", () => {
    const initialState = factory.reservedIpState({ saving: false });
    expect(reducers(initialState, actions.deleteStart())).toEqual(
      factory.reservedIpState({
        saving: true,
      })
    );
  });

  it("should correctly reduce deleteSuccess", () => {
    const initialState = factory.reservedIpState({
      saving: true,
      saved: false,
    });
    expect(
      reducers(initialState, actions.deleteSuccess({ id: 1, ip: "10.0.0.2" }))
    ).toEqual(
      factory.reservedIpState({
        saving: false,
        saved: true,
      })
    );
  });

  it("should correctly reduce deleteError", () => {
    const initialState = factory.reservedIpState({
      saving: true,
      saved: false,
    });
    expect(reducers(initialState, actions.deleteError("Error"))).toEqual(
      factory.reservedIpState({
        saving: false,
        errors: "Error",
      })
    );
  });

  it("should correctly reduce deleteNotify", () => {
    const items = [factory.reservedIp(), factory.reservedIp()];
    const initialState = factory.reservedIpState({
      items,
    });
    expect(
      reducers(initialState, actions.deleteNotify(items[0].id)).items
    ).toEqual([items[1]]);
  });
});

describe("get reducers", () => {
  it("should correctly reduce getStart", () => {
    const initialState = factory.reservedIpState({ items: [], loading: false });
    expect(reducers(initialState, actions.getStart())).toEqual(
      factory.reservedIpState({
        loading: true,
      })
    );
  });

  it("should correctly reduce getSuccess", () => {
    const newReservedIp = factory.reservedIp();
    const reservedIpState = factory.reservedIpState({
      items: [],
      loading: true,
    });
    expect(
      reducers(reservedIpState, actions.getSuccess(newReservedIp))
    ).toEqual(
      factory.reservedIpState({
        items: [newReservedIp],
        loading: false,
      })
    );
  });

  it("should correctly reduce getError", () => {
    const initialState = factory.reservedIpState({
      loading: true,
    });
    expect(reducers(initialState, actions.getError("Error"))).toEqual(
      factory.reservedIpState({
        loading: false,
        errors: "Error",
      })
    );
  });
});
