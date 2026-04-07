# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import BaseModel, Field


class BootSourceSelectionSyncResponse(BaseModel):
    kind: str = Field(default="BootSourceSelectionSync")
    monitor_url: str
