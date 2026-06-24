# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.enums.power_drivers import PowerTypeEnum


class MachineRequest(NamedBaseModel):
    # TODO
    pass


class PowerParametersRequest(BaseModel):
    """Request body for PUT /machines/{system_id}/power_parameters."""

    power_type: PowerTypeEnum
    power_parameters: dict
