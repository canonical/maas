import reducers, { actions } from "./slice";

import * as factory from "@/testing/factories";

describe("dhcpSnippet reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(
      factory.dhcpSnippetState()
    );
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.dhcpSnippetState({ loading: false });

      expect(reducers(initialState, actions.fetchStart())).toEqual(
        factory.dhcpSnippetState({ loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.dhcpSnippetState({
        items: [],
        loaded: false,
        loading: true,
      });
      const dhcpSnippets = [factory.dhcpSnippet(), factory.dhcpSnippet()];

      expect(
        reducers(initialState, actions.fetchSuccess(dhcpSnippets))
      ).toEqual(
        factory.dhcpSnippetState({
          items: dhcpSnippets,
          loaded: true,
          loading: false,
        })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.dhcpSnippetState({
        errors: "",
        loading: true,
      });

      expect(
        reducers(
          initialState,
          actions.fetchError("Could not fetch dhcpSnippets")
        )
      ).toEqual(
        factory.dhcpSnippetState({
          errors: "Could not fetch dhcpSnippets",
          loading: false,
        })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.dhcpSnippetState({ saving: false });

      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.dhcpSnippetState({ saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.dhcpSnippetState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.dhcpSnippetState({ saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.dhcpSnippetState({
        items: [factory.dhcpSnippet()],
      });
      const newDHCPSnippet = factory.dhcpSnippet();

      expect(
        reducers(initialState, actions.createNotify(newDHCPSnippet))
      ).toEqual(
        factory.dhcpSnippetState({
          items: [...initialState.items, newDHCPSnippet],
        })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.dhcpSnippetState({
        errors: "",
        saving: true,
      });

      expect(
        reducers(
          initialState,
          actions.createError("Could not create dhcpSnippet")
        )
      ).toEqual(
        factory.dhcpSnippetState({
          errors: "Could not create dhcpSnippet",
          saving: false,
        })
      );
    });
  });

  describe("update", () => {
    it("reduces updateStart", () => {
      const initialState = factory.dhcpSnippetState({ saving: false });

      expect(reducers(initialState, actions.updateStart())).toEqual(
        factory.dhcpSnippetState({ saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.dhcpSnippetState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.updateSuccess())).toEqual(
        factory.dhcpSnippetState({ saved: true, saving: false })
      );
    });

    it("reduces updateNotify", () => {
      const initialState = factory.dhcpSnippetState({
        items: [factory.dhcpSnippet()],
      });
      const updatedDHCPSnippet = factory.dhcpSnippet({
        id: initialState.items[0].id,
        name: "updated-reducers",
      });

      expect(
        reducers(initialState, actions.updateNotify(updatedDHCPSnippet))
      ).toEqual(factory.dhcpSnippetState({ items: [updatedDHCPSnippet] }));
    });

    it("reduces updateError", () => {
      const initialState = factory.dhcpSnippetState({
        errors: "",
        saving: true,
      });

      expect(
        reducers(
          initialState,
          actions.updateError("Could not update dhcpSnippet")
        )
      ).toEqual(
        factory.dhcpSnippetState({
          errors: "Could not update dhcpSnippet",
          saving: false,
        })
      );
    });
  });

  describe("delete", () => {
    it("reduces deleteStart", () => {
      const initialState = factory.dhcpSnippetState({ saving: false });

      expect(reducers(initialState, actions.deleteStart())).toEqual(
        factory.dhcpSnippetState({ saving: true })
      );
    });

    it("reduces deleteSuccess", () => {
      const initialState = factory.dhcpSnippetState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.deleteSuccess())).toEqual(
        factory.dhcpSnippetState({ saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteDHCPSnippet, keepDHCPSnippet] = [
        factory.dhcpSnippet(),
        factory.dhcpSnippet(),
      ];
      const initialState = factory.dhcpSnippetState({
        items: [deleteDHCPSnippet, keepDHCPSnippet],
      });

      expect(
        reducers(initialState, actions.deleteNotify(deleteDHCPSnippet.id))
      ).toEqual(factory.dhcpSnippetState({ items: [keepDHCPSnippet] }));
    });

    it("reduces deleteError", () => {
      const initialState = factory.dhcpSnippetState({
        errors: "",
        saving: true,
      });

      expect(
        reducers(
          initialState,
          actions.deleteError("Could not delete dhcpSnippet")
        )
      ).toEqual(
        factory.dhcpSnippetState({
          errors: "Could not delete dhcpSnippet",
          saving: false,
        })
      );
    });
  });
});
