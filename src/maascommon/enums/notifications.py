# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from enum import StrEnum


class NotificationCategoryEnum(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    INFO = "info"
