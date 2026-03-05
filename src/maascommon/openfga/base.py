# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from enum import StrEnum
import os
from pathlib import Path
from typing import Any

from maascommon.path import get_maas_data_path


class OpenFGAEntitlementResourceType(StrEnum):
    """Resource types used in OpenFGA tuples."""

    POOL = "pool"
    MAAS = "maas"


class BaseOpenFGAClient:
    """Abstract base for sync/async OpenFGA clients."""

    HEADERS = {"User-Agent": "maas-openfga-client/1.0"}
    MAAS_GLOBAL_OBJ = f"{OpenFGAEntitlementResourceType.MAAS}:0"

    def __init__(self, unix_socket: str | None = None):
        self.socket_path = unix_socket or self._get_default_socket_path()

    def _get_default_socket_path(self) -> str:
        return str(
            Path(
                os.getenv(
                    "MAAS_OPENFGA_HTTP_SOCKET_PATH",
                    get_maas_data_path("openfga-http.sock"),
                )
            )
        )

    def _format_pool(self, pool_id: int) -> str:
        return f"{OpenFGAEntitlementResourceType.POOL}:{pool_id}"

    def _parse_list_objects(self, data: dict[str, Any]) -> list[int]:
        return [int(item.split(":")[1]) for item in data.get("objects", [])]
