#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from enum import Enum


class ExternalAuthType(Enum):
    CANDID = "CANDID"
    RBAC = "RBAC"


@dataclass
class ExternalAuthConfig:
    """Hold information about external authentication."""

    type: ExternalAuthType
    url: str
    domain: str = ""
    admin_group: str = ""
