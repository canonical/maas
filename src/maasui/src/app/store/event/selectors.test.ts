import eventSelectors from "./selectors";

import * as factory from "@/testing/factories";

describe("eventSelectors selectors", () => {
  it("can get all items", () => {
    const items = [factory.eventRecord(), factory.eventRecord()];
    const state = factory.rootState({
      event: factory.eventState({
        items,
      }),
    });
    expect(eventSelectors.all(state)).toEqual(items);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      event: factory.eventState({
        loading: true,
      }),
    });
    expect(eventSelectors.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      event: factory.eventState({
        loaded: true,
      }),
    });
    expect(eventSelectors.loaded(state)).toEqual(true);
  });

  it("can get the saving state", () => {
    const state = factory.rootState({
      event: factory.eventState({
        saving: true,
      }),
    });
    expect(eventSelectors.saving(state)).toEqual(true);
  });

  it("can get the saved state", () => {
    const state = factory.rootState({
      event: factory.eventState({
        saved: true,
      }),
    });
    expect(eventSelectors.saved(state)).toEqual(true);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      event: factory.eventState({
        errors: "Unable to get events",
      }),
    });
    expect(eventSelectors.errors(state)).toStrictEqual("Unable to get events");
  });

  it("can get an event by id", () => {
    const items = [
      factory.eventRecord({ id: 101 }),
      factory.eventRecord({ id: 123 }),
    ];
    const state = factory.rootState({
      event: factory.eventState({
        items,
      }),
    });
    expect(eventSelectors.getById(state, 101)).toStrictEqual(items[0]);
  });

  it("can get events for a node", () => {
    const items = [
      factory.eventRecord({ id: 101, node_id: 1 }),
      factory.eventRecord({ id: 123, node_id: 2 }),
      factory.eventRecord({ id: 124, node_id: 1 }),
    ];
    const state = factory.rootState({
      event: factory.eventState({
        items,
      }),
    });
    expect(eventSelectors.getByNodeId(state, 1)).toStrictEqual([
      items[0],
      items[2],
    ]);
  });
});
