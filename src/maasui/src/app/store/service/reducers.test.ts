import reducers, { actions } from "./slice";
import { ServiceName } from "./types";

import * as factory from "@/testing/factories";

describe("service reducer", () => {
  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual(factory.serviceState());
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.serviceState({ loading: false });

      expect(reducers(initialState, actions.fetchStart())).toEqual(
        factory.serviceState({ loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.serviceState({
        items: [],
        loaded: false,
        loading: true,
      });
      const services = [factory.service(), factory.service()];

      expect(reducers(initialState, actions.fetchSuccess(services))).toEqual(
        factory.serviceState({
          items: services,
          loaded: true,
          loading: false,
        })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.serviceState({
        errors: null,
        loading: true,
      });

      expect(
        reducers(initialState, actions.fetchError("Could not fetch services"))
      ).toEqual(
        factory.serviceState({
          errors: "Could not fetch services",
          loading: false,
        })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.serviceState({ saving: false });

      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.serviceState({ saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.serviceState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.serviceState({ saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.serviceState({
        items: [factory.service()],
      });
      const newService = factory.service();

      expect(reducers(initialState, actions.createNotify(newService))).toEqual(
        factory.serviceState({
          items: [...initialState.items, newService],
        })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.serviceState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.createError("Could not create service"))
      ).toEqual(
        factory.serviceState({
          errors: "Could not create service",
          saving: false,
        })
      );
    });
  });

  describe("update", () => {
    it("reduces updateStart", () => {
      const initialState = factory.serviceState({ saving: false });

      expect(reducers(initialState, actions.updateStart())).toEqual(
        factory.serviceState({ saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.serviceState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.updateSuccess())).toEqual(
        factory.serviceState({ saved: true, saving: false })
      );
    });

    it("reduces updateNotify", () => {
      const initialState = factory.serviceState({
        items: [factory.service()],
      });
      const updatedService = factory.service({
        id: initialState.items[0].id,
        name: ServiceName.PROXY,
      });

      expect(
        reducers(initialState, actions.updateNotify(updatedService))
      ).toEqual(factory.serviceState({ items: [updatedService] }));
    });

    it("reduces updateError", () => {
      const initialState = factory.serviceState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.updateError("Could not update service"))
      ).toEqual(
        factory.serviceState({
          errors: "Could not update service",
          saving: false,
        })
      );
    });
  });

  describe("delete", () => {
    it("reduces deleteStart", () => {
      const initialState = factory.serviceState({ saving: false });

      expect(reducers(initialState, actions.deleteStart())).toEqual(
        factory.serviceState({ saving: true })
      );
    });

    it("reduces deleteSuccess", () => {
      const initialState = factory.serviceState({
        saved: false,
        saving: true,
      });

      expect(reducers(initialState, actions.deleteSuccess())).toEqual(
        factory.serviceState({ saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteService, keepService] = [
        factory.service(),
        factory.service(),
      ];
      const initialState = factory.serviceState({
        items: [deleteService, keepService],
      });

      expect(
        reducers(initialState, actions.deleteNotify(deleteService.id))
      ).toEqual(factory.serviceState({ items: [keepService] }));
    });

    it("reduces deleteError", () => {
      const initialState = factory.serviceState({
        errors: null,
        saving: true,
      });

      expect(
        reducers(initialState, actions.deleteError("Could not delete service"))
      ).toEqual(
        factory.serviceState({
          errors: "Could not delete service",
          saving: false,
        })
      );
    });
  });
});
