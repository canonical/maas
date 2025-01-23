#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasBaseModel, make_builder


class FileStorage(MaasBaseModel):
    filename: str
    content: str
    key: str
    owner_id: Optional[int]

    def etag(self) -> str:
        pass


FileStorageBuilder = make_builder(FileStorage)
