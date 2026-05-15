export enum NotificationCategory {
  ERROR = "error",
  WARNING = "warning",
  SUCCESS = "success",
  INFO = "info",
}

export enum NotificationIdent {
  RELEASE = "release_notification",
  UPGRADE_STATUS = "upgrade_status",
  UPGRADE_VERSION_ISSUE = "upgrade_version_issue",
}

export enum NotificationMeta {
  MODEL = "notification",
  PK = "id",
}

export enum ReleaseNotificationPaths {
  machines = "/machines",
  settings = "/settings",
}
