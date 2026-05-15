import machineActions from "./machineActions";

import { NodeActions } from "@/app/store/types/node";
import * as factory from "@/testing/factories";

describe("machineActions selectors", () => {
  describe("get", () => {
    it("returns machineActions", () => {
      const data = [factory.machineAction(), factory.machineAction()];
      const state = factory.rootState({
        general: factory.generalState({
          machineActions: factory.machineActionsState({
            data,
          }),
        }),
      });
      expect(machineActions.get(state)).toStrictEqual(data);
    });
  });

  describe("loading", () => {
    it("returns machineActions loading state", () => {
      const loading = true;
      const state = factory.rootState({
        general: factory.generalState({
          machineActions: factory.machineActionsState({
            loading,
          }),
        }),
      });
      expect(machineActions.loading(state)).toStrictEqual(loading);
    });
  });

  describe("loaded", () => {
    it("returns machineActions loaded state", () => {
      const loaded = true;
      const state = factory.rootState({
        general: factory.generalState({
          machineActions: factory.machineActionsState({
            loaded,
          }),
        }),
      });
      expect(machineActions.loaded(state)).toStrictEqual(loaded);
    });
  });

  describe("errors", () => {
    it("returns machineActions errors state", () => {
      const errors = "Cannot fetch machineActions.";
      const state = factory.rootState({
        general: factory.generalState({
          machineActions: factory.machineActionsState({
            errors,
          }),
        }),
      });
      expect(machineActions.errors(state)).toStrictEqual(errors);
    });
  });

  it("can return actions by name", () => {
    const data = [
      factory.machineAction({
        name: NodeActions.COMMISSION,
        title: "Commission...",
        sentence: "commissioned",
        type: "lifecycle",
      }),
      factory.machineAction({
        name: NodeActions.ACQUIRE,
        title: "Allocate...",
        sentence: "acquired",
        type: "lifecycle",
      }),
      factory.machineAction({
        name: NodeActions.DEPLOY,
        title: "Deploy...",
        sentence: "deployed",
        type: "lifecycle",
      }),
    ];
    const state = factory.rootState({
      general: factory.generalState({
        machineActions: factory.machineActionsState({
          data,
        }),
      }),
    });
    expect(machineActions.getByName(state, NodeActions.ACQUIRE)).toStrictEqual({
      name: NodeActions.ACQUIRE,
      title: "Allocate...",
      sentence: "acquired",
      type: "lifecycle",
    });
  });
});
