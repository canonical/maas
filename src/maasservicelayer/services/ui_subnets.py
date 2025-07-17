# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import UISubnetsRepository
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.services.base import ReadOnlyService


class UISubnetsService(ReadOnlyService[UISubnet, UISubnetsRepository]):
    def __init__(
        self,
        context: Context,
        ui_subnets_repository: UISubnetsRepository,
    ):
        super().__init__(context, ui_subnets_repository)
