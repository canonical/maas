# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.switches import (
    SwitchBuilder,
    SwitchInterfaceBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.switches import (
    SwitchesRepository,
    SwitchInterfacesRepository,
)
from maasservicelayer.models.switches import Switch, SwitchInterface
from maasservicelayer.services.base import BaseService


class SwitchesService(BaseService[Switch, SwitchesRepository, SwitchBuilder]):
    """Service for managing network switches.

    This service provides business logic for creating, reading, updating,
    and deleting network switches in MAAS. Switches represent network
    devices that can be monitored and managed.
    """

    def __init__(
        self,
        context: Context,
        switches_repository: SwitchesRepository,
    ):
        super().__init__(context, switches_repository)


class SwitchInterfacesService(
    BaseService[
        SwitchInterface, SwitchInterfacesRepository, SwitchInterfaceBuilder
    ]
):
    """Service for managing switch interfaces."""

    def __init__(
        self,
        context: Context,
        switchinterfaces_repository: SwitchInterfacesRepository,
    ):
        super().__init__(context, switchinterfaces_repository)
