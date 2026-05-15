import { http, HttpResponse } from "msw";

import { notificationFactoryV3 } from "../factories/notification";
import { BASE_URL } from "../utils";

import type {
  DismissNotificationError,
  ListNotificationsError,
  ListNotificationsResponse,
} from "@/app/apiclient";

const mockNotifications: ListNotificationsResponse = {
  items: [
    notificationFactoryV3({
      id: 1,
      users: true,
      admins: true,
      message: "This is a success message",
      category: "success",
      context: {},
    }),
    notificationFactoryV3({
      id: 2,
      users: true,
      admins: true,
      message: "This is an info message",
      category: "info",
      context: {},
    }),
    notificationFactoryV3({
      id: 3,
      users: true,
      admins: true,
      message: "This is a warning message",
      category: "warning",
      context: {},
    }),
  ],
  total: 3,
};

const mockListNotificationsError: ListNotificationsError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // This will always be 'Error' for every error response
};

const mockDismissNotificationError: DismissNotificationError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const notificationResolvers = {
  listNotifications: {
    resolved: false,
    handler: (data: ListNotificationsResponse = mockNotifications) =>
      http.get(`${BASE_URL}MAAS/a/v3/notifications`, () => {
        notificationResolvers.listNotifications.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListNotificationsError = mockListNotificationsError) =>
      http.get(`${BASE_URL}MAAS/a/v3/notifications`, () => {
        notificationResolvers.listNotifications.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  dismissNotification: {
    resolved: false,
    handler: () => {
      return http.post(
        `${BASE_URL}MAAS/a/v3/notifications/:id\\:dismiss`,
        () => {
          notificationResolvers.dismissNotification.resolved = true;
          return HttpResponse.json({}, { status: 200 });
        }
      );
    },
    error: (error: DismissNotificationError = mockDismissNotificationError) =>
      http.post(`${BASE_URL}MAAS/a/v3/notifications/:id\\:dismiss`, () => {
        notificationResolvers.dismissNotification.resolved = true;
        return HttpResponse.json(error, { status: 404 });
      }),
  },
};

export { notificationResolvers, mockNotifications };
