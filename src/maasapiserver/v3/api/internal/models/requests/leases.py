#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import IPvAnyAddress

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel


class LeaseInfoRequest(NamedBaseModel):
    action: str
    ip_family: str
    hostname: str
    mac: str
    ip: IPvAnyAddress
    timestamp: int
    lease_time: int  # seconds
