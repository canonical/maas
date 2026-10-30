# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from ipaddress import ip_address
from types import MappingProxyType

import pytest

from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.mappers.domains import (
    ForwardDNSServerProjectionDataMapper,
)
from maasservicelayer.db.tables import DomainTable, ForwardDNSServerTable
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.forwarddnsserver import ForwardDNSServer


@pytest.mark.parametrize("server_ip", ["192.0.2.1", "2001:db8::1"])
def test_forwarded_domain_row_keeps_domain_and_server_fields_separate(
    server_ip,
):
    domain_created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    server_created = datetime(2026, 2, 1, tzinfo=timezone.utc)
    server_updated = datetime(2026, 3, 1, tzinfo=timezone.utc)
    row = MappingProxyType(
        {
            "id": 11,
            "created": domain_created,
            "updated": domain_created,
            "name": "forwarded.example",
            "authoritative": False,
            "ttl": None,
            "fdns_id": 22,
            "fdns_created": server_created,
            "fdns_updated": server_updated,
            "fdns_ip_address": server_ip,
            "fdns_port": 5353,
        }
    )
    domain_mapper = DefaultDomainDataMapper(Domain, DomainTable)
    server_mapper = ForwardDNSServerProjectionDataMapper(
        ForwardDNSServer, ForwardDNSServerTable
    )

    domain = domain_mapper.to_domain(row)
    server = server_mapper.to_domain(row)

    assert domain.id == 11
    assert domain.created == domain_created
    assert domain.name == "forwarded.example"
    assert domain.authoritative is False
    assert server.id == 22
    assert server.created == server_created
    assert server.updated == server_updated
    assert server.ip_address == ip_address(server_ip)
    assert server.port == 5353
