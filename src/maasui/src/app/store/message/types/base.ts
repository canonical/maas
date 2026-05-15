import type { NotificationProps } from "@canonical/react-components";

import type { Model } from "@/app/store/types/model";

export type Message = Model & {
  message: string;
  severity: NotificationProps["severity"];
  temporary: boolean;
  title?: NotificationProps["title"];
};

export type MessageState = {
  items: Message[];
};
