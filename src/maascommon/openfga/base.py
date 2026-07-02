# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager
import contextvars
from enum import StrEnum
import logging
import os
from pathlib import Path
from typing import Any, Iterator

from maascommon.path import get_maas_data_path

_suppress_httpx = contextvars.ContextVar("suppress_httpx", default=False)


class _HTTPXLogFilter(logging.Filter):
    """Drop httpx/httpcore INFO/DEBUG records when the `_suppress_httpx`
    ContextVar is set to True. Warnings and above always pass through.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno >= logging.WARNING:
            return True
        return not _suppress_httpx.get()


def _install_httpx_log_filter() -> None:
    """Attach the context-aware filter to the httpx/httpcore loggers.

    `addFilter` is idempotent, so repeated calls are harmless.
    """
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).addFilter(_HTTPX_LOG_FILTER)


_HTTPX_LOG_FILTER = _HTTPXLogFilter()
_install_httpx_log_filter()


class OpenFGAEntitlementResourceType(StrEnum):
    """Resource types used in OpenFGA tuples."""

    POOL = "pool"
    MAAS = "maas"


class MAASResourceEntitlement(StrEnum):
    """Entitlements for MAAS resources."""

    CAN_EDIT_MACHINES = "can_edit_machines"
    CAN_DEPLOY_MACHINES = "can_deploy_machines"
    CAN_VIEW_MACHINES = "can_view_machines"
    CAN_VIEW_AVAILABLE_MACHINES = "can_view_available_machines"
    CAN_EDIT_GLOBAL_ENTITIES = "can_edit_global_entities"
    CAN_VIEW_GLOBAL_ENTITIES = "can_view_global_entities"
    CAN_EDIT_CONTROLLERS = "can_edit_controllers"
    CAN_VIEW_CONTROLLERS = "can_view_controllers"
    CAN_EDIT_IDENTITIES = "can_edit_identities"
    CAN_VIEW_IDENTITIES = "can_view_identities"
    CAN_EDIT_CONFIGURATIONS = "can_edit_configurations"
    CAN_VIEW_CONFIGURATIONS = "can_view_configurations"
    CAN_EDIT_NOTIFICATIONS = "can_edit_notifications"
    CAN_VIEW_NOTIFICATIONS = "can_view_notifications"
    CAN_EDIT_BOOT_ENTITIES = "can_edit_boot_entities"
    CAN_VIEW_BOOT_ENTITIES = "can_view_boot_entities"
    CAN_EDIT_LICENSE_KEYS = "can_edit_license_keys"
    CAN_VIEW_LICENCE_KEYS = "can_view_license_keys"
    CAN_VIEW_DEVICES = "can_view_devices"
    CAN_VIEW_IPADDRESSES = "can_view_ipaddresses"
    CAN_VIEW_DNSRECORDS = "can_view_dnsrecords"
    CAN_EDIT_OPERATIONS = "can_edit_operations"
    CAN_VIEW_OPERATIONS = "can_view_operations"


class PoolResourceEntitlements(StrEnum):
    """Entitlements for pool resources."""

    CAN_EDIT_MACHINES = "can_edit_machines"
    CAN_DEPLOY_MACHINES = "can_deploy_machines"
    CAN_VIEW_MACHINES = "can_view_machines"
    CAN_VIEW_AVAILABLE_MACHINES = "can_view_available_machines"


class BaseOpenFGAClient:
    """Abstract base for sync/async OpenFGA clients."""

    HEADERS = {"User-Agent": "maas-openfga-client/1.0"}
    MAAS_GLOBAL_OBJ = f"{OpenFGAEntitlementResourceType.MAAS}:0"

    def __init__(self, unix_socket: str | None = None):
        self.socket_path = unix_socket or self._get_default_socket_path()

    @classmethod
    @contextmanager
    def _suppress_httpx_logging(cls) -> Iterator[None]:
        with _suppress_httpx.set(True):
            yield

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
