import notification from "./selectors";

import { ConfigNames } from "@/app/store/config/types";
import { NotificationIdent } from "@/app/store/notification/types";
import * as factory from "@/testing/factories";

describe("notification selectors", () => {
  it("can get all items", () => {
    const state = factory.rootState({
      notification: factory.notificationState({
        items: [factory.notification({ message: "Test message" })],
      }),
    });
    const items = notification.all(state);
    expect(items.length).toEqual(1);
    expect(items[0].message).toEqual("Test message");
  });

  it("can get all enabled items", () => {
    const state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({
            name: ConfigNames.RELEASE_NOTIFICATIONS,
            value: false,
          }),
        ],
      }),
      notification: factory.notificationState({
        items: [
          factory.notification({ message: "Test message" }),
          factory.notification({ ident: NotificationIdent.RELEASE }),
        ],
      }),
      router: factory.routerState({
        location: factory.locationState({
          pathname: "/kvm",
        }),
      }),
    });
    const items = notification.allEnabled(state);
    expect(items.length).toEqual(1);
    expect(items[0].message).toEqual("Test message");
  });

  it("does not include release notifications if the config is off", () => {
    const state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({
            name: ConfigNames.RELEASE_NOTIFICATIONS,
            value: false,
          }),
        ],
      }),
      notification: factory.notificationState({
        items: [
          factory.notification({ message: "Test message" }),
          factory.notification({ ident: NotificationIdent.RELEASE }),
        ],
      }),
      router: factory.routerState({
        location: factory.locationState({
          pathname: "/machines",
        }),
      }),
    });
    const items = notification.allEnabled(state);
    expect(items.length).toEqual(1);
    expect(items[0].message).toEqual("Test message");
  });

  it("does not include release notifications for some paths", () => {
    const state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({
            name: ConfigNames.RELEASE_NOTIFICATIONS,
            value: true,
          }),
        ],
      }),
      notification: factory.notificationState({
        items: [
          factory.notification({ message: "Test message" }),
          factory.notification({ ident: NotificationIdent.RELEASE }),
        ],
      }),
      router: factory.routerState({
        location: factory.locationState({
          pathname: "/kvm",
        }),
      }),
    });
    const items = notification.allEnabled(state);
    expect(items.length).toEqual(1);
    expect(items[0].message).toEqual("Test message");
  });

  it("can include release notifications", () => {
    const notifications = [
      factory.notification({ message: "Test message" }),
      factory.notification({ ident: NotificationIdent.RELEASE }),
    ];
    const state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({
            name: ConfigNames.RELEASE_NOTIFICATIONS,
            value: true,
          }),
        ],
      }),
      notification: factory.notificationState({
        items: notifications,
      }),
      router: factory.routerState({
        location: factory.locationState({
          pathname: "/machines",
        }),
      }),
    });
    const items = notification.allEnabled(state);
    expect(items.length).toEqual(2);
    expect(items).toStrictEqual(notifications);
  });

  it("can get the loading state", () => {
    const state = factory.rootState({
      notification: factory.notificationState({
        loading: true,
      }),
    });
    expect(notification.loading(state)).toEqual(true);
  });

  it("can get the loaded state", () => {
    const state = factory.rootState({
      notification: factory.notificationState({
        loaded: true,
      }),
    });
    expect(notification.loaded(state)).toEqual(true);
  });

  it("can get a notification by id", () => {
    const items = [
      factory.notification({ id: 808 }),
      factory.notification({ id: 909 }),
    ];
    const state = factory.rootState({
      notification: factory.notificationState({
        items,
      }),
    });
    expect(notification.getById(state, 909)).toStrictEqual(items[1]);
  });
});
