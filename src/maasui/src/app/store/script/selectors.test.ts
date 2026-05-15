import script from "./selectors";

import { ScriptType } from "@/app/store/script/types";
import * as factory from "@/testing/factories";

describe("script selectors", () => {
  describe("all", () => {
    it("returns all script", () => {
      const items = [factory.script(), factory.script()];
      const state = factory.rootState({
        script: factory.scriptState({
          items,
        }),
      });

      expect(script.all(state)).toStrictEqual(items);
    });
  });

  describe("loading", () => {
    it("returns script loading state", () => {
      const state = factory.rootState({
        script: factory.scriptState({
          loading: true,
        }),
      });
      expect(script.loading(state)).toStrictEqual(true);
    });
  });

  describe("hasErrors", () => {
    it("can identify errors from a string", () => {
      const state = factory.rootState({
        script: factory.scriptState({
          errors: "Uh oh!",
        }),
      });
      expect(script.hasErrors(state)).toStrictEqual(true);
    });

    it("can identify errors from an object", () => {
      const state = factory.rootState({
        script: factory.scriptState({
          errors: { name: "Name is required" },
        }),
      });
      expect(script.hasErrors(state)).toStrictEqual(true);
    });

    it("does not identify errors from an empty object", () => {
      const state = factory.rootState({
        script: factory.scriptState({
          errors: {},
        }),
      });
      expect(script.hasErrors(state)).toStrictEqual(false);
    });
  });

  describe("loaded", () => {
    it("returns script loaded state", () => {
      const state = factory.rootState({
        script: factory.scriptState({
          loaded: true,
        }),
      });
      expect(script.loaded(state)).toStrictEqual(true);
    });
  });

  describe("commissioning", () => {
    it("returns all commissioning script", () => {
      const items = [
        factory.script({ script_type: ScriptType.COMMISSIONING }),
        factory.script({ script_type: ScriptType.TESTING }),
        factory.script({ script_type: ScriptType.COMMISSIONING }),
      ];
      const state = factory.rootState({
        script: factory.scriptState({
          items,
        }),
      });

      expect(script.commissioning(state)).toEqual([items[0], items[2]]);
    });
  });

  describe("preselected", () => {
    it("returns all preselected commissioning script", () => {
      const preselectedItems = [
        factory.script({
          script_type: ScriptType.COMMISSIONING,
          default: true,
        }),
        factory.script({
          script_type: ScriptType.COMMISSIONING,
          default: false,
        }),
      ];
      const nonPreselectedItems = [
        factory.script({
          script_type: ScriptType.COMMISSIONING,
          tags: ["noauto"],
        }),
      ];
      const state = factory.rootState({
        script: factory.scriptState({
          items: [...preselectedItems, ...nonPreselectedItems],
        }),
      });

      expect(script.preselectedCommissioning(state)).toEqual(preselectedItems);
    });
  });

  describe("testing", () => {
    it("returns all testing script", () => {
      const items = [
        factory.script({ script_type: ScriptType.COMMISSIONING }),
        factory.script({ script_type: ScriptType.TESTING }),
        factory.script({ script_type: ScriptType.TESTING }),
      ];
      const state = factory.rootState({
        script: factory.scriptState({
          items,
        }),
      });

      expect(script.testing(state)).toEqual([items[1], items[2]]);
    });
  });

  describe("defaultTesting", () => {
    it("returns all default testing script", () => {
      const items = [
        factory.script({ script_type: ScriptType.TESTING, default: true }),
        factory.script({ script_type: ScriptType.TESTING, default: false }),
        factory.script({ script_type: ScriptType.TESTING, tags: ["noauto"] }),
      ];
      const state = factory.rootState({
        script: factory.scriptState({
          items,
        }),
      });

      expect(script.defaultTesting(state)).toEqual([items[0]]);
    });
  });

  describe("testingWithUrl", () => {
    it("returns testing script that contain a url parameter", () => {
      const items = [
        factory.script(),
        factory.script(),
        factory.script({
          parameters: {
            url: {
              default: "www.website.come",
              description: "url description",
            },
          },
          script_type: ScriptType.TESTING,
        }),
      ];
      const state = factory.rootState({
        script: factory.scriptState({
          items,
        }),
      });

      expect(script.testingWithUrl(state)).toEqual([items[2]]);
    });
  });
});
