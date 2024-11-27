# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import MaasTimestampedBaseModel


class ReservedIP(MaasTimestampedBaseModel):
    ip: IPvAnyAddress
    # TODO: validate
    mac_address: str
    comment: Optional[str] = None
    subnet_id: int
