import reducers from "./slice";

import { ConfigNames } from "@/app/store/config/types";
import * as factory from "@/testing/factories";

describe("config reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(
      factory.configState({
        errors: null,
        loading: false,
        loaded: false,
        saving: false,
        saved: false,
        items: [],
      })
    );
  });

  it("should correctly reduce config/fetchStart", () => {
    expect(
      reducers(undefined, {
        type: "config/fetchStart",
      })
    ).toEqual(
      factory.configState({
        loading: true,
        loaded: false,
        saving: false,
        saved: false,
        items: [],
      })
    );
  });

  it("should correctly reduce config/fetchSuccess", () => {
    expect(
      reducers(
        factory.configState({
          loading: true,
          loaded: false,
          saving: false,
          items: [],
        }),
        {
          type: "config/fetchSuccess",
          payload: [
            factory.config({
              name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
              value: "bcache",
            }),
            factory.config({
              name: ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
              value: "foo",
            }),
          ],
        }
      )
    ).toEqual(
      factory.configState({
        loading: false,
        loaded: true,
        saving: false,
        items: [
          factory.config({
            name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
            value: "bcache",
          }),
          factory.config({
            name: ConfigNames.ENABLE_DISK_ERASING_ON_RELEASE,
            value: "foo",
          }),
        ],
      })
    );
  });

  it("should correctly reduce config/updateStart", () => {
    expect(
      reducers(
        factory.configState({
          loading: false,
          loaded: false,
          saving: false,
          saved: false,
          items: [],
        }),
        {
          type: "config/updateStart",
        }
      )
    ).toEqual(
      factory.configState({
        loading: false,
        loaded: false,
        saving: true,
        saved: false,
        items: [],
      })
    );
  });

  it("should correctly reduce config/updateSuccess, without a store update", () => {
    expect(
      reducers(
        factory.configState({
          loading: false,
          loaded: false,
          saving: true,
          saved: false,
          items: [
            factory.config({
              name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
              value: "bcache",
            }),
          ],
        }),
        {
          type: "config/updateSuccess",
          payload: { name: ConfigNames.DEFAULT_STORAGE_LAYOUT, value: "flat" },
        }
      )
    ).toEqual(
      factory.configState({
        loading: false,
        loaded: false,
        saving: false,
        saved: true,
        items: [
          factory.config({
            name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
            value: "bcache",
          }),
        ],
      })
    );
  });

  it("should correctly reduce config/updateNotify, updating the store", () => {
    expect(
      reducers(
        factory.configState({
          loading: false,
          loaded: false,
          saving: false,
          saved: true,
          items: [
            factory.config({ name: ConfigNames.MAAS_NAME, value: "my-maas" }),
            factory.config({
              name: ConfigNames.DEFAULT_STORAGE_LAYOUT,
              value: "bcache",
            }),
          ],
        }),
        {
          type: "config/updateNotify",
          payload: { name: ConfigNames.DEFAULT_STORAGE_LAYOUT, value: "flat" },
        }
      )
    ).toEqual(
      factory.configState({
        loading: false,
        loaded: false,
        saving: false,
        saved: true,
        items: [
          { name: ConfigNames.MAAS_NAME, value: "my-maas" },
          { name: ConfigNames.DEFAULT_STORAGE_LAYOUT, value: "flat" },
        ],
      })
    );
  });
});
