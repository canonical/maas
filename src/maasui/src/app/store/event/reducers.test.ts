import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("eventRecord reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      errors: null,
      items: [],
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
    });
  });

  describe("fetch", () => {
    it("reduces fetch", () => {
      expect(reducers(undefined, actions.fetchStart())).toEqual({
        errors: null,
        items: [],
        loaded: false,
        loading: true,
        saved: false,
        saving: false,
      });
    });

    it("reduces fetchSuccess", () => {
      const eventState = factory.eventState({
        items: [],
        loading: true,
      });
      const eventRecords = [factory.eventRecord()];
      expect(reducers(eventState, actions.fetchSuccess(eventRecords))).toEqual({
        errors: null,
        items: eventRecords,
        loading: false,
        loaded: true,
        saved: false,
        saving: false,
      });
    });

    it("appends new items when reducing fetchSuccess", () => {
      const items = [factory.eventRecord()];
      const eventState = factory.eventState({
        items,
        loading: true,
      });
      const eventRecords = [factory.eventRecord()];
      expect(reducers(eventState, actions.fetchSuccess(eventRecords))).toEqual({
        errors: null,
        items: items.concat(eventRecords),
        loading: false,
        loaded: true,
        saved: false,
        saving: false,
      });
    });

    it("deduplicates when reducing fetchSuccess", () => {
      const items = [factory.eventRecord(), factory.eventRecord()];
      const eventState = factory.eventState({
        items,
        loading: true,
      });
      const eventRecords = [items[0], factory.eventRecord()];
      expect(reducers(eventState, actions.fetchSuccess(eventRecords))).toEqual({
        errors: null,
        items: [...items, eventRecords[1]],
        loading: false,
        loaded: true,
        saved: false,
        saving: false,
      });
    });

    it("reduces fetchError", () => {
      const eventState = factory.eventState();
      expect(
        reducers(eventState, actions.fetchError("Could not fetch events"))
      ).toEqual({
        errors: "Could not fetch events",
        items: [],
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });
  });
});
