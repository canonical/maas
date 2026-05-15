import reducers from "./slice";

import * as factory from "@/testing/factories";

describe("licenseKeys reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      })
    );
  });

  it("should correctly reduce licensekeys/createStart", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: true,
          saving: false,
        }),
        {
          type: "licensekeys/createStart",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce licensekeys/createSuccess", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: false,
          saving: true,
        }),
        {
          type: "licensekeys/createSuccess",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce licensekeys/createError", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: false,
          saving: true,
        }),
        {
          errors: true,
          payload: { error: "Invalid license key." },
          type: "licensekeys/createError",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: { error: "Invalid license key." },
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      })
    );
  });

  it("should correctly reduce licensekeys/fetchStart", () => {
    expect(
      reducers(undefined, {
        type: "licensekeys/fetchStart",
      })
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [],
        loaded: false,
        loading: true,
      })
    );
  });

  it("should correctly reduce licensekeys/fetchError", () => {
    expect(
      reducers(undefined, {
        errors: true,
        payload: { error: "Unable to fetch license keys" },
        type: "licensekeys/fetchError",
      })
    ).toEqual(
      factory.licenseKeysState({
        items: [],
        errors: { error: "Unable to fetch license keys" },
        loaded: false,
        loading: false,
      })
    );
  });

  it("should correctly reduce licensekeys/fetchSuccess", () => {
    const items = [
      factory.licenseKeys({ osystem: "windows", license_key: "foo" }),
      factory.licenseKeys({ osystem: "redhat", license_key: "bar" }),
    ];
    expect(
      reducers(
        factory.licenseKeysState({
          items: [],
          loaded: false,
          loading: true,
        }),
        {
          type: "licensekeys/fetchSuccess",
          payload: items,
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        items,
        loaded: true,
        loading: false,
      })
    );
  });

  it("should correctly reduce licensekeys/updateStart", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: true,
          saving: false,
        }),
        {
          type: "licensekeys/updateStart",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce licensekeys/updateSuccess", () => {
    const items = [
      factory.licenseKeys({
        osystem: "windows",
        distro_series: "2012",
        license_key: "foo",
      }),
      factory.licenseKeys({
        id: 1,
        osystem: "windows",
        distro_series: "2019",
        license_key: "bar",
      }),
    ];
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items,
          loaded: false,
          loading: false,
          saved: false,
          saving: false,
        }),
        {
          type: "licensekeys/updateSuccess",
          payload: {
            ...items[1],
            osystem: "windows",
            distro_series: "2019",
            license_key: "baz",
          },
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [
          items[0],
          factory.licenseKeys({
            ...items[1],
            osystem: "windows",
            distro_series: "2019",
            license_key: "baz",
          }),
        ],
        loaded: false,
        loading: false,
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce licensekeys/updateError", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: false,
          saving: true,
        }),
        {
          errors: true,
          payload: { error: "Not found" },
          type: "licensekeys/updateError",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: { error: "Not found" },
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      })
    );
  });

  it("should correctly reduce licensekeys/deleteStart", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: true,
          saving: false,
        }),
        {
          type: "licensekeys/deleteStart",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      })
    );
  });

  it("should correctly reduce licensekeys/deleteSuccess", () => {
    const items = [
      factory.licenseKeys({
        osystem: "windows",
        distro_series: "2012",
        license_key: "foo",
      }),
      factory.licenseKeys({
        osystem: "windows",
        distro_series: "2019",
        license_key: "bar",
      }),
    ];
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items,
          loaded: false,
          loading: false,
          saved: false,
          saving: false,
        }),
        {
          type: "licensekeys/deleteSuccess",
          payload: {
            osystem: "windows",
            distro_series: "2019",
            license_key: "bar",
          },
        }
      )
    ).toEqual(
      factory.licenseKeysState({
        errors: null,
        items: [items[0]],
        loaded: false,
        loading: false,
        saved: true,
        saving: false,
      })
    );
  });

  it("should correctly reduce licensekeys/deleteError", () => {
    expect(
      reducers(
        factory.licenseKeysState({
          errors: null,
          items: [],
          loaded: false,
          loading: false,
          saved: false,
          saving: true,
        }),
        {
          errors: true,
          payload: { error: "Not found" },
          type: "licensekeys/deleteError",
        }
      )
    ).toEqual(
      factory.licenseKeysState({
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
