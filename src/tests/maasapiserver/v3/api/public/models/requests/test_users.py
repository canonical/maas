# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
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
        assert len(e.value.errors()) == 3
        assert {
            "username",
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
                    first_name="test",
                    last_name="test",
                    email=email,
                )
        else:
            BaseUserRequest(
                username="test",
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
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        b = u.to_builder()
        assert u.username == b.username
        assert u.first_name == b.first_name
        assert u.last_name == b.last_name
        assert b.is_superuser is False
        assert b.is_staff is False
        assert b.is_active is True

        assert PBKDF2PasswordHasher().verify("test", b.password)

    def test_groups_default_empty(self) -> None:
        u = UserCreateRequest(
            username="test",
            password="test",
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        assert u.groups == []

    def test_groups(self) -> None:
        u = UserCreateRequest(
            username="test",
            password="test",
            first_name="test",
            last_name="test",
            email="email@example.com",
            groups=[1, 2],
        )
        assert u.groups == [1, 2]


class TestUserUpdateRequest:
    def test_to_builder(self) -> None:
        u = UserUpdateRequest(
            username="test",
            password=None,
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        b = u.to_builder()
        assert u.username == b.username
        assert u.first_name == b.first_name
        assert u.last_name == b.last_name
        assert b.is_superuser == UNSET
        assert b.is_staff is False
        assert b.is_active is True
        assert b.password == UNSET

    def test_groups_default_empty(self) -> None:
        u = UserUpdateRequest(
            username="test",
            password=None,
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        assert u.groups == []

    def test_groups(self) -> None:
        u = UserUpdateRequest(
            username="test",
            password=None,
            first_name="test",
            last_name="test",
            email="email@example.com",
            groups=[1, 2],
        )
        assert u.groups == [1, 2]
