#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import datetime

import pytest

from maasservicelayer.models.users import User


@pytest.mark.asyncio
class TestUserModel:
    async def test_etag(self) -> None:
        test_date = datetime.datetime(2024, 11, 1)
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
            "f66ac35f42647ee07da439699deea437f62b9875228d6852528da01bc144419a"
        )
        assert test_user.etag() == expected_etag

    @pytest.mark.parametrize(
        "hashed_password, plaintext_password, expected_result",
        [
            (
                "pbkdf2_sha256$260000$f1nMJPH4Z5Wc8QxkTsZ1p6$ylZBpgGE3FNlP2zOU21cYiLtvxwtkglsPKUETtXhzDw=",  # hash('test')
                "test",
                True,
            ),
            (
                "pbkdf2_sha256$260000$f1nMJPH4Z5Wc8QxkTsZ1p6$ylZBpgGE3FNlP2zOU21cYiLtvxwtkglsPKUETtXhzDw=",  # hash('test')
                "wrong",
                False,
            ),
            (
                "pbkdf2_sha256$260000$f1nMJPH4Z5Wc8QxkTsZ1p6$ylZBpgGE3FNlP2zOU21cYiLtvxwtkglsPKUETtXhzDw=",  # hash('test')
                "",
                False,
            ),
        ],
    )
    def test_check_password(
        self,
        hashed_password: str,
        plaintext_password: str,
        expected_result: bool,
    ) -> None:
        user = User(
            id=1,
            username="myusername",
            password=hashed_password,
            is_superuser=False,
            first_name="first",
            last_name="last",
            is_staff=False,
            is_active=False,
            date_joined=datetime.datetime.now(datetime.timezone.utc),
        )
        assert expected_result == user.check_password(plaintext_password)
