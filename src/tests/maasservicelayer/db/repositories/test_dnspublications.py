#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
)
from tests.fixtures.factories.dnspublication import (
    create_test_dnspublication_entry,
)
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestDNSPublicationRepository:
    async def test_get_latest_serial(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        first_publication = await create_test_dnspublication_entry(fixture)
        second_publication = await create_test_dnspublication_entry(
            fixture, serial=first_publication.serial + 1
        )
        third_publication = await create_test_dnspublication_entry(
            fixture, serial=second_publication.serial + 1
        )
        dnspublication_repository = DNSPublicationRepository(
            Context(connection=db_connection)
        )

        serial = await dnspublication_repository.get_latest_serial()

        assert serial == third_publication.serial

    async def test_get_latest(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        first_publication = await create_test_dnspublication_entry(fixture)
        second_publication = await create_test_dnspublication_entry(
            fixture, serial=first_publication.serial + 1
        )
        third_publication = await create_test_dnspublication_entry(
            fixture, serial=second_publication.serial + 1
        )
        dnspublication_repository = DNSPublicationRepository(
            Context(connection=db_connection)
        )

        latest = await dnspublication_repository.get_latest()

        assert latest.id == third_publication.id

    async def test_get_publications_since_serial(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        first_publication = await create_test_dnspublication_entry(fixture)
        second_publication = await create_test_dnspublication_entry(
            fixture, serial=first_publication.serial + 1
        )

        dnspublication_repository = DNSPublicationRepository(
            Context(connection=db_connection)
        )

        result = await dnspublication_repository.get_publications_since_serial(
            first_publication.serial
        )

        assert result == [second_publication]
