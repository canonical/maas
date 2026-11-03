# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.mappers.ui_subnets import UISubnetDomainDataMapper
from maasservicelayer.db.repositories.base import ReadOnlyRepository
from maasservicelayer.db.tables import UISubnetView
from maasservicelayer.models.ui_subnets import UISubnet


class UISubnetsRepository(ReadOnlyRepository[UISubnet]):
    def get_repository_table(self) -> Table:
        return UISubnetView

    def get_model_factory(self) -> Type[UISubnet]:
        return UISubnet

    def get_mapper(self) -> UISubnetDomainDataMapper:
        return UISubnetDomainDataMapper(UISubnet, UISubnetView)
