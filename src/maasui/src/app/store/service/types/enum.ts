export enum ServiceMeta {
  MODEL = "service",
  PK = "id",
}

export enum ServiceName {
  AGENT = "agent",
  BIND9 = "bind9",
  DHCPD = "dhcpd",
  DHCPD6 = "dhcpd6",
  DNS_RACK = "dns_rack",
  HTTP = "http",
  NTP_RACK = "ntp_rack",
  NTP_REGION = "ntp_region",
  PROXY = "proxy",
  PROXY_RACK = "proxy_rack",
  RACKD = "rackd",
  REGIOND = "regiond",
  REVERSE_PROXY = "reverse_proxy",
  SYSLOG_RACK = "syslog_rack",
  SYSLOG_REGION = "syslog_region",
  TFTP = "tftp",
  TEMPORAL = "temporal",
}

export enum ServiceStatus {
  DEAD = "dead", // Service is dead. (Should be on but is off).
  DEGRADED = "degraded", // Service is running but is in a degraded state.
  OFF = "off", // Service is off. (Should be off and is off).
  RUNNING = "running", // Service is running and operational.
  UNKNOWN = "unknown", // Status of the service is not known.
}
