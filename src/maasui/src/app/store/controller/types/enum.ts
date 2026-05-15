export enum ControllerInstallType {
  UNKNOWN = "",
  SNAP = "snap",
  DEB = "deb",
}

export enum ControllerMeta {
  MODEL = "controller",
  PK = "system_id",
}

export enum ControllerVersionIssues {
  DIFFERENT_CHANNEL = "different-channel",
  DIFFERENT_COHORT = "different-cohort",
}

export enum ImageSyncStatus {
  OutOfSync = "Out Of Sync",
  RegionImporting = "Region Importing",
  Synced = "Synced",
  Syncing = "Syncing",
  Unknown = "Unknown",
}
