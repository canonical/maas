#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum


class ServiceName(str, Enum):
    """Service names"""

    AGENT = "agent"
    BIND9 = "bind9"
    DHCPD6 = "dhcpd6"
    DHCPD = "dhcpd"
    HTTP = "http"
    NTP_RACK = "ntp_rack"
    NTP_REGION = "ntp_region"
    PROXY = "proxy"
    PROXY_RACK = "proxy_rack"
    RACKD = "rackd"
    REGIOND = "regiond"
    REVERSE_PROXY = "reverse_proxy"
    SYSLOG_RACK = "syslog_rack"
    SYSLOG_REGION = "syslog_region"
    TEMPORAL = "temporal"
    TEMPORAL_WORKER = "temporal-worker"
    TFTP = "tftp"

    def __str__(self):
        return str(self.value)


class ServiceStatusEnum(str, Enum):
    """Service statuses"""

    # Status of the service is not known.
    UNKNOWN = "unknown"
    # Service is running and operational.
    RUNNING = "running"
    # Service is running but is in a degraded state.
    DEGRADED = "degraded"
    # Service is dead. (Should be on but is off).
    DEAD = "dead"
    # Service is off. (Should be off and is off).
    OFF = "off"

    def __str__(self):
        return str(self.value)
