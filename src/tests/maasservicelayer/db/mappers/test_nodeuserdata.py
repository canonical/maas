#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from types import MappingProxyType

import pytest

from maasservicelayer.builders.nodeuserdata import NodeUserDataBuilder
from maasservicelayer.db.mappers.nodeuserdata import (
    NodeUserDataDomainDataMapper,
)
from maasservicelayer.db.tables import NodeUserDataTable
from maasservicelayer.models.nodeuserdata import NodeUserData


class TestNodeUserDataDomainDataMapper:
    def test_build_resource(self):
        mapper = NodeUserDataDomainDataMapper(NodeUserData, NodeUserDataTable)
        builder = NodeUserDataBuilder(
            node_id=1,
            data=b"\x00\xff\xfe",
            for_ephemeral_environment=True,
        )

        result = mapper.build_resource(builder)

        assert result["data"] == "AP/+"
        assert result["node_id"] == 1
        assert result["for_ephemeral_environment"] is True

    @pytest.mark.parametrize("data", [b"", b"\x00\xff\xfe", b"YWJj"])
    def test_roundtrip_preserves_bytes_and_input(self, data):
        mapper = NodeUserDataDomainDataMapper(NodeUserData, NodeUserDataTable)
        builder = NodeUserDataBuilder(data=data)
        values = mapper.build_resource(builder).get_values()
        row = MappingProxyType(
            dict(id=1, node_id=2, for_ephemeral_environment=False, **values)
        )
        original = dict(row)

        assert mapper.to_domain(row).data == data
        assert mapper.to_domain(row).data == data
        assert dict(row) == original
        assert builder.data == data

    def test_build_resource_without_data(self):
        mapper = NodeUserDataDomainDataMapper(NodeUserData, NodeUserDataTable)

        resource = mapper.build_resource(NodeUserDataBuilder(node_id=2))

        assert resource.get_values() == {"node_id": 2}
