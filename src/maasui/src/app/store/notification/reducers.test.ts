import reducers, { actions } from "./slice";
import type { NotificationState } from "./types";

import * as factory from "@/testing/factories";

describe("notifications reducer", () => {
  let state: Pick<NotificationState, "items">;
  beforeEach(() => {
    // Reset the state to not contain any data.
    state = { items: [] };
  });

  it("should return the initial state", () => {
    expect(reducers(undefined, { type: "" })).toEqual({
      ...factory.notificationState(state),
      errors: null,
    });
  });

  describe("fetch", () => {
    it("reduces fetchStart", () => {
      const initialState = factory.notificationState({
        ...state,
        loading: false,
      });
      expect(reducers(initialState, actions.fetchStart())).toEqual(
        factory.notificationState({ ...state, loading: true })
      );
    });

    it("reduces fetchSuccess", () => {
      const initialState = factory.notificationState({
        ...state,
        items: [],
        loaded: false,
        loading: true,
      });
      const notifications = [factory.notification(), factory.notification()];

      expect(
        reducers(initialState, actions.fetchSuccess(notifications))
      ).toEqual(
        factory.notificationState({
          ...state,
          items: notifications,
          loaded: true,
          loading: false,
        })
      );
    });

    it("reduces fetchError", () => {
      const initialState = factory.notificationState({
        ...state,
        errors: "",
        loading: true,
      });
      expect(
        reducers(
          initialState,
          actions.fetchError("Could not fetch notifications")
        )
      ).toEqual(
        factory.notificationState({
          ...state,
          errors: "Could not fetch notifications",
          loading: false,
        })
      );
    });
  });

  describe("create", () => {
    it("reduces createStart", () => {
      const initialState = factory.notificationState({
        ...state,
        saving: false,
      });
      expect(reducers(initialState, actions.createStart())).toEqual(
        factory.notificationState({ ...state, saving: true })
      );
    });

    it("reduces createSuccess", () => {
      const initialState = factory.notificationState({
        ...state,
        saved: false,
        saving: true,
      });
      expect(reducers(initialState, actions.createSuccess())).toEqual(
        factory.notificationState({ ...state, saved: true, saving: false })
      );
    });

    it("reduces createNotify", () => {
      const initialState = factory.notificationState({
        ...state,
        items: [factory.notification()],
      });
      const newNotification = factory.notification();
      expect(
        reducers(initialState, actions.createNotify(newNotification))
      ).toEqual(
        factory.notificationState({
          ...state,
          items: [...initialState.items, newNotification],
        })
      );
    });

    it("reduces createError", () => {
      const initialState = factory.notificationState({
        ...state,
        errors: "",
        saving: true,
      });
      expect(
        reducers(
          initialState,
          actions.createError("Could not create notification")
        )
      ).toEqual(
        factory.notificationState({
          ...state,
          errors: "Could not create notification",
          saving: false,
        })
      );
    });
  });

  describe("update", () => {
    it("reduces updateStart", () => {
      const initialState = factory.notificationState({
        ...state,
        saving: false,
      });
      expect(reducers(initialState, actions.updateStart())).toEqual(
        factory.notificationState({ ...state, saving: true })
      );
    });

    it("reduces updateSuccess", () => {
      const initialState = factory.notificationState({
        ...state,
        saved: false,
        saving: true,
      });
      expect(reducers(initialState, actions.updateSuccess())).toEqual(
        factory.notificationState({ ...state, saved: true, saving: false })
      );
    });

    it("reduces updateNotify", () => {
      const initialState = factory.notificationState({
        ...state,
        items: [factory.notification()],
      });
      const updatedNotification = factory.notification({
        id: initialState.items[0].id,
        message: "updated-reducers",
      });
      expect(
        reducers(initialState, actions.updateNotify(updatedNotification))
      ).toEqual(
        factory.notificationState({ ...state, items: [updatedNotification] })
      );
    });

    it("reduces updateError", () => {
      const initialState = factory.notificationState({
        ...state,
        errors: "",
        saving: true,
      });
      expect(
        reducers(
          initialState,
          actions.updateError("Could not update notification")
        )
      ).toEqual(
        factory.notificationState({
          ...state,
          errors: "Could not update notification",
          saving: false,
        })
      );
    });
  });

  describe("dismiss", () => {
    it("reduces dismissStart", () => {
      const initialState = factory.notificationState({
        ...state,
        saving: false,
      });
      expect(reducers(initialState, actions.dismissStart())).toEqual(
        factory.notificationState({ ...state, saving: true })
      );
    });

    it("reduces dismissSuccess", () => {
      const initialState = factory.notificationState({
        ...state,
        saved: false,
        saving: true,
      });
      expect(reducers(initialState, actions.dismissSuccess())).toEqual(
        factory.notificationState({ ...state, saved: true, saving: false })
      );
    });

    it("reduces deleteNotify", () => {
      const [deleteNotification, keepNotification] = [
        factory.notification(),
        factory.notification(),
      ];
      const initialState = factory.notificationState({
        ...state,
        items: [deleteNotification, keepNotification],
      });
      expect(
        reducers(initialState, actions.deleteNotify(deleteNotification.id))
      ).toEqual(
        factory.notificationState({ ...state, items: [keepNotification] })
      );
    });

    it("reduces dismissError", () => {
      const initialState = factory.notificationState({
        ...state,
        errors: "",
        saving: true,
      });
      expect(
        reducers(
          initialState,
          actions.dismissError("Could not dismiss notification")
        )
      ).toEqual(
        factory.notificationState({
          ...state,
          errors: "Could not dismiss notification",
          saving: false,
        })
      );
    });
  });
});
