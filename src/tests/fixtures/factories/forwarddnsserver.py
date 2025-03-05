#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Any, Optional

from maasservicelayer.models.domains import Domain
from maasservicelayer.models.forwarddnsserver import ForwardDNSServer
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_forwarddnsserver_entry(
    fixture: Fixture,
    domain: Optional[Domain] = None,
    **extra_details: dict[str, Any],
) -> ForwardDNSServer:
    created_at = datetime.now(timezone.utc).astimezone()
    updated_at = datetime.now(timezone.utc).astimezone()
    forwarddnsserver = {
        "created": created_at,
        "updated": updated_at,
        "ip_address": "10.0.0.1",
        "port": 53,
    }
    forwarddnsserver.update(extra_details)

    [created_forwarddnsserver] = await fixture.create(
        "maasserver_forwarddnsserver",
        [forwarddnsserver],
    )

    result = ForwardDNSServer(**created_forwarddnsserver)

    if domain:
        await fixture.create(
            "maasserver_forwarddnsserver_domains",
            [{"domain_id": domain.id, "forwarddnsserver_id": result.id}],
        )

    return result
