# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.users import UserRequest


class TestUserRequest:
    def test_mandatory_params(self) -> None:
        with pytest.raises(ValidationError) as e:
            UserRequest()
        assert len(e.value.errors()) == 7
        assert {
            "username",
            "password",
            "is_superuser",
            "is_staff",
            "is_active",
            "first_name",
            "last_name",
        } == set([f["loc"][0] for f in e.value.errors()])

    @pytest.mark.parametrize(
        "email, valid",
        [
            ("email@example.com", True),
            ("firstname.lastname@example.com", True),
            ("email@subdomain.example.com", True),
            ("firstname+lastname@example.com", True),
            ("Joe Smith <email@example.com>", False),
            ("email.example.com", False),
            ("email@example@example.com", False),
            (".email@example.com", False),
        ],
    )
    def test_check_email(self, email: str, valid: bool) -> None:
        if not valid:
            with pytest.raises(ValidationError):
                UserRequest(
                    username="test",
                    password="test",
                    is_superuser=False,
                    is_staff=False,
                    is_active=False,
                    first_name="test",
                    last_name="test",
                    email=email,
                )
        else:
            UserRequest(
                username="test",
                password="test",
                is_superuser=False,
                is_staff=False,
                is_active=False,
                first_name="test",
                last_name="test",
                email=email,
            )

    def test_password_length(self) -> None:
        with pytest.raises(ValidationError) as e:
            UserRequest(
                username="test",
                password="",
                is_superuser=False,
                is_staff=False,
                is_active=False,
                first_name="test",
                last_name="test",
                email="test@example.com",
            )
        assert len(e.value.errors()) == 1
        assert {"password"} == set([f["loc"][0] for f in e.value.errors()])

    def test_to_builder(self) -> None:
        u = UserRequest(
            username="test",
            password="test",
            is_superuser=False,
            is_staff=False,
            is_active=False,
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        b = u.to_builder()
        assert u.username == b.username
        assert u.is_superuser == b.is_superuser
        assert u.is_staff == b.is_staff
        assert u.is_active == b.is_active
        assert u.first_name == b.first_name
        assert u.last_name == b.last_name

        assert PBKDF2PasswordHasher().verify("test", b.password)
