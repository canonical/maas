import { actions } from "./slice";
import { NotificationCategory, NotificationIdent } from "./types";

describe("notification actions", () => {
  it("returns a fetch action", () => {
    expect(actions.fetch()).toEqual({
      type: "notification/fetch",
      meta: {
        model: "notification",
        method: "list",
      },
      payload: null,
    });
  });

  it("returns a create action", () => {
    expect(
      actions.create({
        message: "a notification",
        admins: true,
        category: NotificationCategory.ERROR,
        dismissable: true,
        ident: NotificationIdent.RELEASE,
        user: 9,
        users: true,
      })
    ).toEqual({
      type: "notification/create",
      meta: {
        model: "notification",
        method: "create",
      },
      payload: {
        params: {
          message: "a notification",
          admins: true,
          category: NotificationCategory.ERROR,
          dismissable: true,
          ident: NotificationIdent.RELEASE,
          user: 9,
          users: true,
        },
      },
    });
  });

  it("creates a dismiss action", () => {
    expect(actions.dismiss(2)).toEqual({
      type: "notification/dismiss",
      payload: {
        params: {
          id: 2,
        },
      },
      meta: {
        method: "dismiss",
        model: "notification",
      },
    });
  });

  it("returns a cleanup action", () => {
    expect(actions.cleanup()).toEqual({
      type: "notification/cleanup",
      payload: undefined,
    });
  });
});
