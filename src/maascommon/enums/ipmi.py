#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import StrEnum


class IPMICipherSuiteID(StrEnum):
    SUITE_17 = "17"
    SUITE_3 = "3"
    DEFAULT = ""
    SUITE_8 = "8"
    SUITE_12 = "12"

    def __str__(self):
        return str(self.value)


class IPMIPrivilegeLevel(StrEnum):
    USER = "USER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"

    def __str__(self):
        return str(self.value)


class IPMIWorkaroundFlags(StrEnum):
    OPENSESSPRIV = "opensesspriv"
    AUTHCAP = "authcap"
    IDZERO = "idzero"
    UNEXPECTEDAUTH = "unexpectedauth"
    FORCEPERMSG = "forcepermsg"
    ENDIANSEQ = "endianseq"
    INTEL20 = "intel20"
    SUPERMICRO20 = "supermicro20"
    SUN20 = "sun20"
    NOCHECKSUMCHECK = "nochecksumcheck"
    INTEGRITYCHECKVALUE = "integritycheckvalue"
    IPMIPING = "ipmiping"
    NONE = ""

    def __str__(self):
        return str(self.value)
