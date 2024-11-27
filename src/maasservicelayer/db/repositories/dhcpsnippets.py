# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DHCPSnippetTable
from maasservicelayer.models.dhcpsnippets import DhcpSnippet


class DhcpSnippetsRepository(BaseRepository[DhcpSnippet]):
    def get_repository_table(self) -> Table:
        return DHCPSnippetTable

    def get_model_factory(self) -> Type[DhcpSnippet]:
        return DhcpSnippet
