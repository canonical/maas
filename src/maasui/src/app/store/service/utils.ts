import { ServiceName } from "./types";

export const getServiceDisplayName = (name: ServiceName): string => {
  switch (name) {
    case ServiceName.DNS_RACK:
      return "dns";
    case ServiceName.NTP_RACK:
    case ServiceName.NTP_REGION:
      return "ntp";
    case ServiceName.PROXY:
    case ServiceName.PROXY_RACK:
      return "proxy";
    case ServiceName.REVERSE_PROXY:
      return "reverse-proxy";
    case ServiceName.SYSLOG_RACK:
    case ServiceName.SYSLOG_REGION:
      return "syslog";
    default:
      return name;
  }
};
