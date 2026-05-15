import { waitFor } from "@testing-library/react";

import NotificationGroupNotification from "./Notification";

import type { ConfigState } from "@/app/store/config/types";
import { ConfigNames } from "@/app/store/config/types";
import { NotificationIdent } from "@/app/store/notification/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

const mockServer = setupMockServer(authResolvers.getCurrentUser.handler());

describe("NotificationGroupNotification", () => {
  let config: ConfigState;

  beforeEach(() => {
    config = factory.configState({
      items: [
        factory.config({
          name: ConfigNames.RELEASE_NOTIFICATIONS,
          value: true,
        }),
      ],
    });
  });

  it("renders", () => {
    const notification = factory.notification({
      id: 1,
      message: "something important",
    });
    const state = factory.rootState({
      config,
      notification: factory.notificationState({
        items: [notification],
      }),
    });
    renderWithProviders(
      <NotificationGroupNotification
        id={notification.id}
        severity="negative"
      />,
      { initialEntries: ["/"], state }
    );
    expect(screen.getByTestId("notification-message")).toHaveTextContent(
      "something important"
    );
    expect(
      screen.getByRole("button", { name: "Close notification" })
    ).toBeInTheDocument();
  });

  it("can be dismissed", async () => {
    const notification = factory.notification();
    const state = factory.rootState({
      config,
      notification: factory.notificationState({
        items: [notification],
      }),
    });

    const { store } = renderWithProviders(
      <NotificationGroupNotification
        id={notification.id}
        severity="negative"
      />,
      { initialEntries: ["/"], state }
    );
    await userEvent.click(screen.getByTestId("notification-close-button"));
    expect(store.getActions().length).toEqual(1);
    expect(store.getActions()[0].type).toEqual("notification/dismiss");
  });

  it("does not show a dismiss action if notification is not dismissable", () => {
    const notification = factory.notification({ dismissable: false });
    const state = factory.rootState({
      config,
      notification: factory.notificationState({
        items: [notification],
      }),
    });
    renderWithProviders(
      <NotificationGroupNotification
        id={notification.id}
        severity="negative"
      />,
      { initialEntries: ["/"], state }
    );
    expect(
      screen.queryByTestId("notification-close-button")
    ).not.toBeInTheDocument();
  });

  it("shows the date for upgrade notifications", () => {
    const notification = factory.notification({
      created: factory.timestamp("Tue, 27 Apr. 2021 00:34:39"),
      ident: NotificationIdent.UPGRADE_STATUS,
    });
    const state = factory.rootState({
      config,
      notification: factory.notificationState({
        items: [notification],
      }),
    });
    renderWithProviders(
      <NotificationGroupNotification
        id={notification.id}
        severity="negative"
      />,
      { initialEntries: ["/settings"], state }
    );
    expect(screen.getByTestId("notification-timestamp")).toHaveTextContent(
      /Tue, 27 Apr. 2021 00:34:39/i
    );
  });

  it("shows a settings link for release notifications", async () => {
    const notification = factory.notification({
      ident: NotificationIdent.RELEASE,
    });
    const state = factory.rootState({
      config,
      notification: factory.notificationState({
        items: [notification],
      }),
    });
    renderWithProviders(
      <NotificationGroupNotification
        id={notification.id}
        severity="negative"
      />,
      { initialEntries: ["/settings"], state }
    );
    await waitFor(() => {
      expect(screen.getByTestId("notification-action")).toHaveTextContent(
        "See settings"
      );
    });
  });

  it("does not show the release notification menu to non-admins", () => {
    const notification = factory.notification({
      ident: NotificationIdent.RELEASE,
      message: "This is a release notification",
    });
    const state = factory.rootState({
      config,
      notification: factory.notificationState({
        items: [notification],
      }),
    });
    mockServer.use(
      authResolvers.getCurrentUser.handler(
        factory.user({ is_superuser: false })
      )
    );
    renderWithProviders(
      <NotificationGroupNotification
        id={notification.id}
        severity="negative"
      />,
      { initialEntries: ["/settings"], state }
    );
    expect(screen.queryByTestId("notification-action")).not.toBeInTheDocument();
  });
});
