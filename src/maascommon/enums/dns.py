#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum


class DnsUpdateAction(str, Enum):
    RELOAD = "RELOAD"
    INSERT = "INSERT"
    INSERT_DATA = "INSERT-DATA"
    UPDATE_DATA = "UPDATE-DATA"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    DELETE_IP = "DELETE-IP"
    DELETE_IFACE_IP = "DELETE-IFACE-IP"

    def __str__(self):
        return str(self.value)
