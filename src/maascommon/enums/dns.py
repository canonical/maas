#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum, StrEnum


class DnsUpdateAction(str, Enum):
    RELOAD = "RELOAD"
    INSERT = "INSERT"
    INSERT_DATA = "INSERT-DATA"
    INSERT_NAME = "INSERT-NAME"
    UPDATE_DATA = "UPDATE-DATA"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DELETE_IP = "DELETE-IP"
    DELETE_IFACE_IP = "DELETE-IFACE-IP"

    def __str__(self):
        return str(self.value)


class DNSSECEnumm(StrEnum):
    AUTO = "auto"
    YES = "yes"
    NO = "no"

    def __str__(self):
        return str(self.value)


class DNSResourceTypeEnum(StrEnum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    MX = "MX"
    NS = "NS"
    SRV = "SRV"
    SSHFP = "SSHFP"
    TXT = "TXT"
