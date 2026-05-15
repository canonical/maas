import tag, { TagSearchFilter } from "./selectors";

import * as factory from "@/testing/factories";
import { tagStateListFactory } from "@/testing/factories/state";

describe("tag selectors", () => {
  it("can get all items", () => {
    const items = [factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        items,
      }),
    });
    expect(tag.all(state)).toEqual(items);
  });

  it("can get items in a list", () => {
    const items = [factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        lists: {
          "mock-call-id": tagStateListFactory({
            items,
          }),
        },
      }),
    });
    expect(tag.list(state, "mock-call-id")).toStrictEqual(items);
  });

  it("can get the loading state for a list", () => {
    const items = [factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        lists: {
          "mock-call-id": tagStateListFactory({
            items,
            loading: true,
            loaded: false,
          }),
        },
      }),
    });
    expect(tag.listLoading(state, "mock-call-id")).toBe(true);
  });

  it("can get the loaded state for a list", () => {
    const items = [factory.tag(), factory.tag()];
    const state = factory.rootState({
      tag: factory.tagState({
        lists: {
          "mock-call-id": tagStateListFactory({
            items,
            loaded: true,
            loading: false,
          }),
        },
      }),
    });
    expect(tag.listLoaded(state, "mock-call-id")).toBe(true);
  });

  it("can get all manual tags", () => {
    const items = [
      factory.tag({ definition: "def1" }),
      factory.tag({ definition: "" }),
    ];
    const state = factory.rootState({
      tag: factory.tagState({
        items,
      }),
    });
    expect(tag.getManual(state)).toEqual([items[1]]);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      tag: factory.tagState({
        loading: true,
      }),
    });
    expect(tag.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      tag: factory.tagState({
        loaded: true,
      }),
    });
    expect(tag.loaded(state)).toEqual(true);
  });

  it("can get the errors state", () => {
    const state = factory.rootState({
      tag: factory.tagState({
        errors: "Data is incorrect",
      }),
    });
    expect(tag.errors(state)).toStrictEqual("Data is incorrect");
  });

  it("can get all automatic tags", () => {
    const items = [
      factory.tag({ definition: "def1" }),
      factory.tag({ definition: "" }),
    ];
    const state = factory.rootState({
      tag: factory.tagState({
        items,
      }),
    });
    expect(tag.getAutomatic(state)).toStrictEqual([items[0]]);
  });

  describe("getByIDs", () => {
    const tags = [
      factory.tag({ id: 1 }),
      factory.tag({ id: 2 }),
      factory.tag({ id: 3 }),
    ];

    it("handles the null case", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.getByIDs(state, null)).toStrictEqual([]);
    });

    it("returns a list of tags given their IDs", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.getByIDs(state, [1, 2])).toStrictEqual([tags[0], tags[1]]);
    });
  });

  describe("getByName", () => {
    const tags = [
      factory.tag({ name: "tag1" }),
      factory.tag({ name: "tag2" }),
      factory.tag({ name: "tag3" }),
    ];

    it("handles the null case", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.getByName(state, null)).toBe(null);
    });

    it("returns a list of tags given their IDs", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.getByName(state, "tag2")).toStrictEqual(tags[1]);
    });
  });

  describe("getAutomaticByIDs", () => {
    const tags = [
      factory.tag({ id: 1 }),
      factory.tag({ definition: "def1", id: 2 }),
      factory.tag({ id: 3 }),
    ];
    const state = factory.rootState({
      tag: factory.tagState({ items: tags }),
    });

    it("handles the null case", () => {
      expect(tag.getAutomaticByIDs(state, null)).toStrictEqual([]);
    });

    it("returns a list of tags given their IDs", () => {
      expect(tag.getAutomaticByIDs(state, [1, 2])).toStrictEqual([tags[1]]);
    });
  });

  describe("getManualByIDs", () => {
    const tags = [
      factory.tag({ id: 1 }),
      factory.tag({ definition: "def1", id: 2 }),
      factory.tag({ id: 3 }),
    ];
    const state = factory.rootState({
      tag: factory.tagState({ items: tags }),
    });

    it("handles the null case", () => {
      expect(tag.getManualByIDs(state, null)).toStrictEqual([]);
    });

    it("returns a list of tags given their IDs", () => {
      expect(tag.getManualByIDs(state, [1, 2])).toStrictEqual([tags[0]]);
    });
  });

  describe("search", () => {
    const tags = [
      factory.tag({ id: 1, definition: undefined, name: "jacket" }),
      factory.tag({ id: 2, definition: "denim", name: "jeans" }),
      factory.tag({ id: 3, definition: undefined, name: "shirt" }),
    ];

    it("returns all tags if no filters or search are provided", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.search(state, null, null)).toStrictEqual(tags);
    });

    it("returns all tags if the filter is set to 'All'", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.search(state, null, TagSearchFilter.All)).toStrictEqual(tags);
    });

    it("filters automatic tags", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.search(state, null, TagSearchFilter.Auto)).toStrictEqual([
        tags[1],
      ]);
    });

    it("filters manual tags", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.search(state, null, TagSearchFilter.Manual)).toStrictEqual([
        tags[0],
        tags[2],
      ]);
    });

    it("searches tags", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.search(state, "j", null)).toStrictEqual([tags[0], tags[1]]);
    });

    it("searches and filters tags", () => {
      const state = factory.rootState({
        tag: factory.tagState({ items: tags }),
      });
      expect(tag.search(state, "j", TagSearchFilter.Manual)).toStrictEqual([
        tags[0],
      ]);
    });
  });
});
