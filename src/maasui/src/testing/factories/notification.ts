import { define, extend } from "cooky-cutter";

import { timestampedModel } from "./model";

import type { NotificationResponse } from "@/app/apiclient";
import { NotificationCategory } from "@/app/store/notification/types";
import type { Notification } from "@/app/store/notification/types";
import type { TimestampedModel } from "@/app/store/types/model";
import { user } from "@/testing/factories/user";

export const notification = extend<TimestampedModel, Notification>(
  timestampedModel,
  {
    ident: "default",
    user,
    users: true,
    admins: true,
    message: "Testing notification",
    category: NotificationCategory.WARNING,
    dismissable: true,
  }
);

export const notificationFactoryV3 = define<NotificationResponse>({
  id: (i: number) => i + 1,
  users: true,
  admins: true,
  message: "This is a test notification",
  context: {},
  category: NotificationCategory.INFO,
  dismissable: true,
});
