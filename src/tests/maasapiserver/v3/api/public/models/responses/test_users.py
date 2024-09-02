import datetime

import pytest

from maasservicelayer.models.users import User


class TestUserResponse:
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
            date_joined=datetime.datetime.utcnow(),
        )
        assert expected_result == user.check_password(plaintext_password)
