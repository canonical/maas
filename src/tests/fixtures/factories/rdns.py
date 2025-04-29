# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from typing import Any

from maasservicelayer.models.rdns import RDNS
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_rdns_entry(
    fixture: Fixture,
    hostname: str,
    ip: str,
    observer_id: int,
    **extra_details: Any,
) -> RDNS:
    now = utcnow()
    rdns = {
        "hostname": hostname,
        "hostnames": [hostname],
        "ip": ip,
        "observer_id": observer_id,
        "created": now,
        "updated": now,
    }
    rdns.update(extra_details)

    [created_rdns] = await fixture.create("maasserver_rdns", [rdns])
    return RDNS(**created_rdns)
