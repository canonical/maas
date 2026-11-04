# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.mappers.base import ColumnMapping
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.models.openfga_tuple import OpenFGATuple


class OpenFGATuplesDataMapper(DefaultDomainDataMapper[OpenFGATuple]):
    def __init__(self):
        super().__init__(OpenFGATuple, OpenFGATupleTable)

    def field_mappings(self) -> dict[str, ColumnMapping]:
        return {"user": ColumnMapping(OpenFGATupleTable.c._user)}
