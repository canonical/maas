# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.dhcpsnippets import DhcpSnippetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsRepository,
)
from maasservicelayer.models.dhcpsnippets import DhcpSnippet
from maasservicelayer.services.base import BaseService


class DhcpSnippetsService(
    BaseService[DhcpSnippet, DhcpSnippetsRepository, DhcpSnippetBuilder]
):
    def __init__(
        self, context: Context, dhcpsnippets_repository: DhcpSnippetsRepository
    ):
        super().__init__(context, dhcpsnippets_repository)
