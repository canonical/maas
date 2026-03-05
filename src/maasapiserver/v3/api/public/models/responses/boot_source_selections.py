# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from typing import ClassVar

from pydantic import BaseModel


class BootSourceSelectionSyncResponse(BaseModel):
    kind: ClassVar[str] = "BootSourceSelectionSync"
    monitor_url: str
