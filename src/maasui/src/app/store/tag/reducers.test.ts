import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";
import { tagStateListFactory } from "@/testing/factories/state";

describe("tag reducer", () => {
  it("returns the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      errors: null,
      items: [],
      lists: {},
      loaded: false,
      loading: false,
      saved: false,
      saving: false,
    });
  });

  it("reduces fetchStart", () => {
    expect(reducers(undefined, actions.fetchStart())).toEqual({
      errors: null,
      items: [],
      lists: {},
      loaded: false,
      loading: true,
      saved: false,
      saving: false,
    });
  });

  it("reduces fetchSuccess", () => {
    const state = factory.tagState();
    const tags = [factory.tag()];

    expect(reducers(state, actions.fetchSuccess(tags))).toEqual({
      errors: null,
      items: tags,
      lists: {},
      loading: false,
      loaded: true,
      saved: false,
      saving: false,
    });
  });

  it("ignores calls that don't exist when reducing fetchSuccess", () => {
    const initialState = factory.tagState({
      items: [],
      lists: {},
    });
    const fetchedTags = [
      factory.tag({ name: "tag1" }),
      factory.tag({ name: "tag2" }),
    ];

    expect(
      reducers(initialState, actions.fetchSuccess(fetchedTags, "123456"))
    ).toEqual(
      factory.tagState({
        items: [],
        lists: {},
      })
    );
  });

  it("can handle fetchSuccess with callId", () => {
    const initialState = factory.tagState({
      items: [],
      lists: { 123456: tagStateListFactory({ loading: true }) },
    });
    const fetchedTags = [
      factory.tag({ name: "tag1" }),
      factory.tag({ name: "tag2" }),
    ];

    expect(
      reducers(initialState, actions.fetchSuccess(fetchedTags, "123456"))
    ).toEqual(
      factory.tagState({
        items: [],
        loaded: false,
        loading: false,
        lists: {
          123456: tagStateListFactory({
            loading: false,
            loaded: true,
            items: fetchedTags,
          }),
        },
      })
    );
  });

  it("can handle fetchSuccess without callId", () => {
    const initialState = factory.tagState({
      items: [],
      loading: true,
      loaded: false,
      lists: {},
    });
    const fetchedTags = [
      factory.tag({ name: "tag1" }),
      factory.tag({ name: "tag2" }),
    ];

    expect(reducers(initialState, actions.fetchSuccess(fetchedTags))).toEqual(
      factory.tagState({
        items: fetchedTags,
        loading: false,
        loaded: true,
        lists: {},
      })
    );
  });

  it("reduces fetchError", () => {
    const state = factory.tagState();

    expect(reducers(state, actions.fetchError("Could not fetch tags"))).toEqual(
      {
        errors: "Could not fetch tags",
        items: [],
        lists: {},
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      }
    );
  });

  it("reduces removeRequest for a list request", () => {
    const initialState = factory.tagState({
      lists: { "mock-call-id": tagStateListFactory() },
    });

    expect(
      reducers(initialState, actions.removeRequest("mock-call-id"))
    ).toEqual(
      factory.tagState({
        lists: {},
      })
    );
  });

  describe("create reducers", () => {
    it("should correctly reduce createStart", () => {
      const initialState = factory.tagState({ saving: false });
      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.tagState({
          saving: true,
        })
      );
    });

    it("should correctly reduce createError", () => {
      const initialState = factory.tagState({ saving: true });
      expect(
        reducers(
          initialState,
          actions.createError({ key: "Key already exists" })
        )
      ).toEqual(
        factory.tagState({
          errors: { key: "Key already exists" },
          saving: false,
        })
      );
    });

    it("should correctly reduce createSuccess", () => {
      const initialState = factory.tagState({
        saved: false,
        saving: true,
      });
      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.tagState({
          saved: true,
          saving: false,
        })
      );
    });

    it("should correctly reduce createNotify", () => {
      const items = [factory.tag(), factory.tag()];
      const initialState = factory.tagState({ items: [items[0]] });
      expect(reducers(initialState, actions.createNotify(items[1]))).toEqual(
        factory.tagState({
          items,
        })
      );
    });
  });

  describe("update reducers", () => {
    it("reduces updateStart", () => {
      const tagState = factory.tagState({ saved: true });

      expect(reducers(tagState, actions.updateStart())).toEqual({
        errors: null,
        items: [],
        lists: {},
        loaded: false,
        loading: false,
        saved: false,
        saving: true,
      });
    });

    it("reduces updateSuccess", () => {
      const tagState = factory.tagState({
        saving: true,
      });

      expect(reducers(tagState, actions.updateSuccess())).toEqual({
        errors: null,
        items: [],
        lists: {},
        loaded: false,
        loading: false,
        saved: true,
        saving: false,
      });
    });

    it("reduces updateError", () => {
      const tagState = factory.tagState({
        saving: true,
      });

      expect(
        reducers(tagState, actions.updateError("Could not update tag"))
      ).toEqual({
        errors: "Could not update tag",
        items: [],
        lists: {},
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });

    it("reduces updateNotify", () => {
      const tags = [factory.tag({ id: 1 })];
      const updatedTag = factory.tag({
        comment: "updated comment",
        definition: "updated def",
        id: 1,
        kernel_opts: "updated opts",
        name: "updated tag",
      });

      const tagState = factory.tagState({
        items: tags,
      });

      expect(reducers(tagState, actions.updateNotify(updatedTag))).toEqual({
        errors: null,
        items: [updatedTag],
        lists: {},
        loaded: false,
        loading: false,
        saved: false,
        saving: false,
      });
    });
  });

  describe("delete reducers", () => {
    it("should correctly reduce deleteStart", () => {
      const initialState = factory.tagState({
        saved: true,
        saving: false,
      });
      expect(reducers(initialState, actions.deleteStart())).toEqual(
        factory.tagState({
          saved: false,
          saving: true,
        })
      );
    });

    it("should correctly reduce deleteError", () => {
      const initialState = factory.tagState({
        errors: null,
        saving: true,
      });
      expect(
        reducers(initialState, actions.deleteError("Could not delete"))
      ).toEqual(
        factory.tagState({
          errors: "Could not delete",
          saving: false,
        })
      );
    });

    it("should correctly reduce deleteSuccess", () => {
      const initialState = factory.tagState({ saved: false });
      expect(reducers(initialState, actions.deleteSuccess())).toEqual(
        factory.tagState({
          saved: true,
        })
      );
    });

    it("should correctly reduce deleteNotify", () => {
      const items = [factory.tag(), factory.tag()];
      const initialState = factory.tagState({ items });
      expect(reducers(initialState, actions.deleteNotify(items[0].id))).toEqual(
        factory.tagState({
          items: [items[1]],
        })
      );
    });
  });
});
