#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from base64 import b64decode, b64encode

from maasservicelayer.models.nodeuserdata import NodeUserData
from tests.maasapiserver.fixtures.db import Fixture


async def create_test_nodeuserdata_entry(
    fixture: Fixture,
    node_id: int,
    data: bytes = b"user-data",
    for_ephemeral_environment: bool = True,
) -> NodeUserData:
    [created] = await fixture.create(
        "maasserver_nodeuserdata",
        [
            {
                "node_id": node_id,
                # `data` is `bytes` in the service layer, base64 `str` in db
                "data": b64encode(data).decode(),
                "for_ephemeral_environment": for_ephemeral_environment,
            }
        ],
    )
    created["data"] = b64decode(created["data"])
    return NodeUserData(**created)
