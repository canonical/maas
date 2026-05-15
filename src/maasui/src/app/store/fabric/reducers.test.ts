import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("fabric reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(factory.fabricState());
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.fabricState({ loading: false });

      expect(reducers(initialState, actions.fetchStart())).toEqual(
        factory.fabricState({ loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.fabricState({
        items: [],
        loaded: false,
        loading: true,
      });
      const fabrics = [factory.fabric(), factory.fabric()];

      expect(reducers(initialState, actions.fetchSuccess(fabrics))).toEqual(
        factory.fabricState({
          items: fabrics,
          loaded: true,
          loading: false,
        })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.fabricState({
        errors: null,
        loading: true,
      });

      expect(
        reducers(initialState, actions.fetchError("Could not fetch fabrics"))
      ).toEqual(
        factory.fabricState({
          errors: "Could not fetch fabrics",
          loading: false,
        })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.fabricState({ saving: false });

      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.fabricState({ saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.fabricState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.fabricState({ saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.fabricState({
        items: [factory.fabric()],
      });
      const newfabric = factory.fabric();

      expect(reducers(initialState, actions.createNotify(newfabric))).toEqual(
        factory.fabricState({
          items: [...initialState.items, newfabric],
        })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.fabricState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.createError("Could not create fabric"))
      ).toEqual(
        factory.fabricState({
          errors: "Could not create fabric",
          saving: false,
        })
      );
    });
  });

  describe("update", () => {
    it("reduces updateStart", () => {
      const initialState = factory.fabricState({ saving: false });

      expect(reducers(initialState, actions.updateStart())).toEqual(
        factory.fabricState({ saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.fabricState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.updateSuccess())).toEqual(
        factory.fabricState({ saved: true, saving: false })
      );
    });

    it("reduces updateNotify", () => {
      const initialState = factory.fabricState({
        items: [factory.fabric()],
      });
      const updatedFabric = factory.fabric({
        id: initialState.items[0].id,
        name: "updated-fabric",
      });

      expect(
        reducers(initialState, actions.updateNotify(updatedFabric))
      ).toEqual(factory.fabricState({ items: [updatedFabric] }));
    });

    it("reduces updateError", () => {
      const initialState = factory.fabricState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.updateError("Could not update fabric"))
      ).toEqual(
        factory.fabricState({
          errors: "Could not update fabric",
          saving: false,
        })
      );
    });
  });

  describe("delete", () => {
    it("reduces deleteStart", () => {
      const initialState = factory.fabricState({ saving: false });

      expect(reducers(initialState, actions.deleteStart())).toEqual(
        factory.fabricState({ saving: true })
      );
    });

    it("reduces deleteSuccess", () => {
      const initialState = factory.fabricState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.deleteSuccess())).toEqual(
        factory.fabricState({ saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteFabric, keepFabric] = [factory.fabric(), factory.fabric()];
      const initialState = factory.fabricState({
        items: [deleteFabric, keepFabric],
      });

      expect(
        reducers(initialState, actions.deleteNotify(deleteFabric.id))
      ).toEqual(factory.fabricState({ items: [keepFabric] }));
    });

    it("reduces deleteError", () => {
      const initialState = factory.fabricState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.deleteError("Could not delete fabric"))
      ).toEqual(
        factory.fabricState({
          errors: "Could not delete fabric",
          saving: false,
        })
      );
    });
  });

  describe("get", () => {
    it("reduces getStart", () => {
      const initialState = factory.fabricState({ loading: false });

      expect(reducers(initialState, actions.getStart())).toEqual(
        factory.fabricState({ loading: true })
      );
    });

    it("reduces getError", () => {
      const initialState = factory.fabricState({ errors: null, loading: true });

      expect(
        reducers(initialState, actions.getError({ id: "id was not supplied" }))
      ).toEqual(
        factory.fabricState({
          errors: { id: "id was not supplied" },
          loading: false,
        })
      );
    });

    it("reduces getSuccess when fabric already exists in state", () => {
      const initialState = factory.fabricState({
        items: [factory.fabric({ id: 0, name: "fabric-1" })],
        loading: true,
      });
      const updatedFabric = factory.fabric({
        id: 0,
        name: "fabric-1-new",
      });

      expect(reducers(initialState, actions.getSuccess(updatedFabric))).toEqual(
        factory.fabricState({
          items: [updatedFabric],
          loading: false,
        })
      );
    });

    it("reduces getSuccess when fabric does not exist yet in state", () => {
      const initialState = factory.fabricState({
        items: [factory.fabric({ id: 0 })],
        loading: true,
      });
      const newFabric = factory.fabric({ id: 1 });

      expect(reducers(initialState, actions.getSuccess(newFabric))).toEqual(
        factory.fabricState({
          items: [...initialState.items, newFabric],
          loading: false,
        })
      );
    });
  });

  describe("setActive", () => {
    it("reduces setActiveSuccess", () => {
      const initialState = factory.fabricState({ active: null });

      expect(
        reducers(
          initialState,
          actions.setActiveSuccess(factory.fabric({ id: 0 }))
        )
      ).toEqual(factory.fabricState({ active: 0 }));
    });

    it("reduces setActiveError", () => {
      const initialState = factory.fabricState({
        active: 0,
        errors: null,
      });

      expect(
        reducers(initialState, actions.setActiveError("Fabric does not exist"))
      ).toEqual(
        factory.fabricState({
          active: null,
          errors: "Fabric does not exist",
        })
      );
    });
  });
});
