import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("space reducer", () => {
  it("should return the initial state", () => {
    const initialState = undefined;

    expect(reducers(initialState, { type: "" })).toEqual({
      ...factory.spaceState(),
      errors: null,
    });
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.spaceState({ loading: false });

      expect(reducers(initialState, actions.fetchStart())).toEqual(
        factory.spaceState({ loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.spaceState({
        items: [],
        loaded: false,
        loading: true,
      });
      const spaces = [factory.space(), factory.space()];

      expect(reducers(initialState, actions.fetchSuccess(spaces))).toEqual(
        factory.spaceState({ items: spaces, loaded: true, loading: false })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.spaceState({ errors: "", loading: true });

      expect(
        reducers(initialState, actions.fetchError("Could not fetch spaces"))
      ).toEqual(
        factory.spaceState({ errors: "Could not fetch spaces", loading: false })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.spaceState({ saving: false });

      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.spaceState({ saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.spaceState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.spaceState({ saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.spaceState({
        items: [factory.space()],
      });
      const newSpace = factory.space();

      expect(reducers(initialState, actions.createNotify(newSpace))).toEqual(
        factory.spaceState({ items: [...initialState.items, newSpace] })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.spaceState({ errors: "", saving: true });

      expect(
        reducers(initialState, actions.createError("Could not create space"))
      ).toEqual(
        factory.spaceState({
          errors: "Could not create space",
          saving: false,
        })
      );
    });
  });

  describe("update", () => {
    it("reduces updateStart", () => {
      const initialState = factory.spaceState({ saving: false });

      expect(reducers(initialState, actions.updateStart())).toEqual(
        factory.spaceState({ saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.spaceState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.updateSuccess())).toEqual(
        factory.spaceState({ saved: true, saving: false })
      );
    });

    it("reduces updateNotify", () => {
      const initialState = factory.spaceState({
        items: [factory.space()],
      });
      const updatedSpace = factory.space({
        id: initialState.items[0].id,
        name: "updated-reducers",
      });

      expect(
        reducers(initialState, actions.updateNotify(updatedSpace))
      ).toEqual(factory.spaceState({ items: [updatedSpace] }));
    });

    it("reduces updateError", () => {
      const initialState = factory.spaceState({ errors: "", saving: true });

      expect(
        reducers(initialState, actions.updateError("Could not update space"))
      ).toEqual(
        factory.spaceState({
          errors: "Could not update space",
          saving: false,
        })
      );
    });
  });

  describe("delete", () => {
    it("reduces deleteStart", () => {
      const initialState = factory.spaceState({ saving: false });

      expect(reducers(initialState, actions.deleteStart())).toEqual(
        factory.spaceState({ saving: true })
      );
    });

    it("reduces deleteSuccess", () => {
      const initialState = factory.spaceState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.deleteSuccess())).toEqual(
        factory.spaceState({ saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteSpace, keepSpace] = [factory.space(), factory.space()];
      const initialState = factory.spaceState({
        items: [deleteSpace, keepSpace],
      });

      expect(
        reducers(initialState, actions.deleteNotify(deleteSpace.id))
      ).toEqual(factory.spaceState({ items: [keepSpace] }));
    });

    it("reduces deleteError", () => {
      const initialState = factory.spaceState({ errors: "", saving: true });

      expect(
        reducers(initialState, actions.deleteError("Could not delete space"))
      ).toEqual(
        factory.spaceState({
          errors: "Could not delete space",
          saving: false,
        })
      );
    });
  });

  describe("get", () => {
    it("reduces getStart", () => {
      const initialState = factory.spaceState({ loading: false });

      expect(reducers(initialState, actions.getStart())).toEqual(
        factory.spaceState({ loading: true })
      );
    });

    it("reduces getError", () => {
      const initialState = factory.spaceState({ errors: null, loading: true });

      expect(
        reducers(initialState, actions.getError({ id: "id was not supplied" }))
      ).toEqual(
        factory.spaceState({
          errors: { id: "id was not supplied" },
          loading: false,
        })
      );
    });

    it("reduces getSuccess when space already exists in state", () => {
      const initialState = factory.spaceState({
        items: [factory.space({ id: 0, name: "space-1" })],
        loading: true,
      });
      const updatedSpace = factory.space({
        id: 0,
        name: "space-1-new",
      });

      expect(reducers(initialState, actions.getSuccess(updatedSpace))).toEqual(
        factory.spaceState({
          items: [updatedSpace],
          loading: false,
        })
      );
    });

    it("reduces getSuccess when space does not exist yet in state", () => {
      const initialState = factory.spaceState({
        items: [factory.space({ id: 0 })],
        loading: true,
      });
      const newSpace = factory.space({ id: 1 });

      expect(reducers(initialState, actions.getSuccess(newSpace))).toEqual(
        factory.spaceState({
          items: [...initialState.items, newSpace],
          loading: false,
        })
      );
    });
  });

  describe("setActive", () => {
    it("reduces setActiveSuccess", () => {
      const initialState = factory.spaceState({ active: null });

      expect(
        reducers(
          initialState,
          actions.setActiveSuccess(factory.space({ id: 0 }))
        )
      ).toEqual(factory.spaceState({ active: 0 }));
    });

    it("reduces setActiveError", () => {
      const initialState = factory.spaceState({
        active: 0,
        errors: null,
      });

      expect(
        reducers(initialState, actions.setActiveError("Space does not exist"))
      ).toEqual(
        factory.spaceState({
          active: null,
          errors: "Space does not exist",
        })
      );
    });
  });
});
