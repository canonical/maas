import type { NotificationCategory, NotificationIdent } from "./enum";

import type { UserResponse } from "@/app/apiclient";
import type { APIError } from "@/app/base/types";
import type { TimestampedModel } from "@/app/store/types/model";
import type { GenericState } from "@/app/store/types/state";

export type Notification = TimestampedModel & {
  ident: NotificationIdent | string;
  user: UserResponse;
  users: boolean;
  admins: boolean;
  message: string;
  category: NotificationCategory;
  dismissable: boolean;
};

export type NotificationState = GenericState<Notification, APIError>;
