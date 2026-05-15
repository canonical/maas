import NotificationGroup from "./NotificationGroup";

import * as factory from "@/testing/factories";
import { renderWithProviders, screen, userEvent } from "@/testing/utils";

describe("NotificationGroup", () => {
  it("renders", () => {
    const notifications = [factory.notification(), factory.notification()];

    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });
    renderWithProviders(
      <NotificationGroup notifications={notifications} severity="negative" />,
      { state }
    );

    expect(
      screen.getByRole("button", {
        name: "2 negative, click to open messages.",
      })
    ).toBeInTheDocument();
    expect(screen.getByTestId("notification-count")).toHaveTextContent(
      "2 Warnings"
    );
  });

  it("hides multiple notifications by default", () => {
    const notifications = [factory.notification(), factory.notification()];

    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });
    renderWithProviders(
      <NotificationGroup notifications={notifications} severity="negative" />,
      { state }
    );

    expect(
      screen.queryByTestId("notification-message")
    ).not.toBeInTheDocument();
  });

  it("displays a count for multiple notifications", () => {
    const notifications = [factory.notification(), factory.notification()];

    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });
    renderWithProviders(
      <NotificationGroup notifications={notifications} severity="negative" />,
      { state }
    );

    expect(screen.getByTestId("notification-count")).toHaveTextContent(
      "2 Warnings"
    );
  });

  it("does not display a dismiss all link if none can be dismissed", () => {
    const notifications = [
      factory.notification({ dismissable: false }),
      factory.notification({ dismissable: false }),
    ];
    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });
    renderWithProviders(
      <NotificationGroup notifications={notifications} severity="negative" />,
      { state }
    );

    expect(
      screen.queryByRole("button", { name: "Dismiss all" })
    ).not.toBeInTheDocument();
  });

  it("can dismiss multiple notifications", async () => {
    const notifications = [
      factory.notification({ dismissable: true }),
      factory.notification({ dismissable: true }),
    ];

    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });

    const { store } = renderWithProviders(
      <NotificationGroup notifications={notifications} severity="negative" />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Dismiss all" }));

    expect(store.getActions().length).toEqual(2);
    expect(store.getActions()[0].type).toEqual("notification/dismiss");
    expect(store.getActions()[1].type).toEqual("notification/dismiss");
  });

  it("does not dismiss undismissable notifications when dismissing a group", async () => {
    const notifications = [
      factory.notification({ dismissable: true }),
      factory.notification({ dismissable: false }),
    ];

    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });

    const { store } = renderWithProviders(
      <NotificationGroup notifications={notifications} severity="caution" />,
      { state }
    );

    await userEvent.click(screen.getByRole("button", { name: "Dismiss all" }));

    expect(store.getActions().length).toEqual(1);
    expect(store.getActions()[0].type).toEqual("notification/dismiss");
  });

  it("can toggle multiple notifications", async () => {
    const notifications = [
      factory.notification(),
      factory.notification(),
      factory.notification(),
    ];

    const state = factory.rootState({
      notification: factory.notificationState({
        items: notifications,
      }),
    });
    renderWithProviders(
      <NotificationGroup notifications={notifications} severity="negative" />,
      { state }
    );

    expect(
      screen.queryByTestId("notification-message")
    ).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", {
        name: "3 negative, click to open messages.",
      })
    );
    expect(screen.getAllByTestId("notification-message")).toHaveLength(3);
  });
});
