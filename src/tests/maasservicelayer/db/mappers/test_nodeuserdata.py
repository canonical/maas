#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.db.mappers.nodeuserdata import (
    NodeUserDataDomainDataMapper,
)
from maasservicelayer.db.tables import NodeUserDataTable


class TestNodeUserDataDomainDataMapper:
    def test_build_resource(self):
        mapper = NodeUserDataDomainDataMapper(NodeUserDataTable)
        builder = NodeUserDataBuilder(
            node_id=1,
            data=b"\x00\xff\xfe",
            for_ephemeral_environment=True,
        )

        result = mapper.build_resource(builder)

        assert result["data"] == "AP/+"
        assert result["node_id"] == 1
        assert result["for_ephemeral_environment"] is True
