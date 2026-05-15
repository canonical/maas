import type { Notification } from "./base";

import type { UserResponse } from "@/app/apiclient";

export type CreateParams = {
  admins: Notification["admins"];
  category: Notification["category"];
  context?: string;
  dismissable: Notification["dismissable"];
  ident: Notification["ident"];
  message: Notification["message"];
  user: UserResponse["id"];
  users: Notification["users"];
};
