export enum ScriptResultDataType {
  COMBINED = "combined",
  RESULT = "result",
  STDERR = "stderr",
  STDOUT = "stdout",
}

export enum ScriptResultEstimated {
  UNKNOWN = "Unknown",
}

export enum ScriptResultMeta {
  MODEL = "scriptresult",
  PK = "id",
}

export enum ScriptResultNames {
  CURTIN_LOG = "/tmp/curtin-logs.tar",
  INSTALL_LOG = "/tmp/install.log",
}

export enum ScriptResultParamType {
  INTERFACE = "interface",
  RUNTIME = "runtime",
  STORAGE = "storage",
  URL = "url",
}

export enum ScriptResultStatus {
  NONE = -1,
  PENDING = 0,
  RUNNING = 1,
  PASSED = 2,
  FAILED = 3,
  TIMEDOUT = 4,
  ABORTED = 5,
  DEGRADED = 6,
  INSTALLING = 7,
  FAILED_INSTALLING = 8,
  SKIPPED = 9,
  APPLYING_NETCONF = 10,
  FAILED_APPLYING_NETCONF = 11,
}

export enum ScriptResultType {
  COMMISSIONING = 0,
  INSTALLATION = 1,
  TESTING = 2,
  RELEASE = 3,
  DEPLOYMENT = 4,
}
