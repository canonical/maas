#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from typing import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.services import CacheForServices, ServiceCollectionV3


@pytest.fixture
async def services(
    db_connection: AsyncConnection,
) -> AsyncIterator[AsyncConnection]:
    """The service layer."""
    yield await ServiceCollectionV3.produce(
        Context(connection=db_connection), cache=CacheForServices()
    )
