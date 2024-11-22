#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

import pytest

from maasservicelayer.models.users import User


@pytest.mark.asyncio
class TestUserModel:
    async def test_etag(self) -> None:
        test_date = datetime(2024, 11, 1)
        test_user = User(
            id=1,
            username="test_username",
            password="test_password",
            is_superuser=False,
            first_name="test_first_name",
            last_name="test_last_name",
            is_staff=False,
            is_active=False,
            date_joined=test_date,
            email="email@example.com",
            last_login=test_date,
        )

        expected_etag = (
            "4eec78f604a4adf4bea0077c807645856ad9d211c5bdc4d9e4748c0c81c81bcd"
        )
        assert test_user.etag() == expected_etag
