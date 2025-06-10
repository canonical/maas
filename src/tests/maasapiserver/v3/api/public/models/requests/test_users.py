# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.users import (
    BaseUserRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from maasservicelayer.models.base import UNSET


class TestUserRequest:
    def test_mandatory_params(self) -> None:
        with pytest.raises(ValidationError) as e:
            BaseUserRequest()
        assert len(e.value.errors()) == 4
        assert {
            "username",
            "is_superuser",
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
                BaseUserRequest(
                    username="test",
                    is_superuser=False,
                    first_name="test",
                    last_name="test",
                    email=email,
                )
        else:
            BaseUserRequest(
                username="test",
                is_superuser=False,
                first_name="test",
                last_name="test",
                email=email,
            )


class TestUserCreateRequest:
    def test_password_length(self) -> None:
        with pytest.raises(ValidationError) as e:
            UserCreateRequest(
                username="test",
                password="",
                is_superuser=False,
                first_name="test",
                last_name="test",
                email="test@example.com",
            )
        assert len(e.value.errors()) == 1
        assert {"password"} == set([f["loc"][0] for f in e.value.errors()])

    def test_to_builder(self) -> None:
        u = UserCreateRequest(
            username="test",
            password="test",
            is_superuser=False,
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        b = u.to_builder()
        assert u.username == b.username
        assert u.is_superuser == b.is_superuser
        assert u.first_name == b.first_name
        assert u.last_name == b.last_name
        assert b.is_staff is False
        assert b.is_active is True

        assert PBKDF2PasswordHasher().verify("test", b.password)


class TestUserUpdateRequest:
    def test_to_builder(self) -> None:
        u = UserUpdateRequest(
            username="test",
            password=None,
            is_superuser=False,
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        b = u.to_builder()
        assert u.username == b.username
        assert u.is_superuser == b.is_superuser
        assert u.first_name == b.first_name
        assert u.last_name == b.last_name
        assert b.is_staff is False
        assert b.is_active is True
        assert b.password is UNSET
