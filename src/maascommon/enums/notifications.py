# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from enum import StrEnum


class NotificationCategoryEnum(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    INFO = "info"


class NotificationComponent(StrEnum):
    """Major moving parts of the application that may have failure states."""

    PSERV = "provisioning server"
    IMPORT_PXE_FILES = "maas-import-pxe-files script"
    RACK_CONTROLLERS = "clusters"
    REGION_IMAGE_IMPORT = "Image importer"
    REGION_IMAGE_SYNC = "Image synchronization"
    REGION_IMAGE_DB_EXPORT = "bootresources_export_from_db"
