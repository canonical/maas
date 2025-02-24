#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from enum import StrEnum


class StorageLayoutEnum(StrEnum):
    BACACHE = "bcache"
    BLANK = "blank"
    CUSTOM = "custom"
    FLAT = "flat"
    LVM = "lvm"
    VMFS6 = "vmfs6"
    VMFS7 = "vmfs7"

    def __str__(self):
        return str(self.value)
