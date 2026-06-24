# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import patch

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
    def setup_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def teardown_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def test_password_length(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=False):
            with pytest.raises(ValidationError) as e:
                UserCreateRequest(
                    username="test",
                    password="",
                    is_superuser=False,
                    first_name="test",
                    last_name="test",
                    email="test@example.com",
                )
        with patch("maascommon.hardening.is_fips_enabled", return_value=False):
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
        with patch("maascommon.hardening.is_fips_enabled", return_value=False):
            u = UserCreateRequest(
                username="test",
                password="test",
                is_superuser=False,
                first_name="test",
                last_name="test",
                email="email@example.com",
            )
        with patch("maascommon.hardening.is_fips_enabled", return_value=False):
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


_WEAK_PASSWORD = "weak"
_STRONG_PASSWORD = "Str0ng!Pass#1"


def _base_fields(**overrides):
    return {
        "username": "alice",
        "is_superuser": False,
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        **overrides,
    }


class TestUserCreateRequestPasswordComplexity:
    """Hardening-on: weak passwords rejected; hardening-off: all accepted."""

    def setup_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def teardown_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def test_weak_password_rejected_when_hardening_active(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                UserCreateRequest(**_base_fields(password=_WEAK_PASSWORD))
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("password",) for e in errors)

    def test_strong_password_accepted_when_hardening_active(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            req = UserCreateRequest(**_base_fields(password=_STRONG_PASSWORD))
        assert req.password == _STRONG_PASSWORD

    def test_weak_password_accepted_when_hardening_inactive(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=False):
            req = UserCreateRequest(**_base_fields(password=_WEAK_PASSWORD))
        assert req.password == _WEAK_PASSWORD


class TestUserUpdateRequestPasswordComplexity:
    """Hardening-on: weak password rejected; None always accepted."""

    def setup_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def teardown_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def test_weak_password_rejected_when_hardening_active(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                UserUpdateRequest(**_base_fields(password=_WEAK_PASSWORD))
        assert any(e["loc"] == ("password",) for e in exc_info.value.errors())

    def test_none_password_always_accepted(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            req = UserUpdateRequest(**_base_fields(password=None))
        assert req.password is None

    def test_strong_password_accepted_when_hardening_active(self) -> None:
        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            req = UserUpdateRequest(**_base_fields(password=_STRONG_PASSWORD))
        assert req.password == _STRONG_PASSWORD


class TestUserChangePasswordRequestComplexity:
    """Hardening-on: weak password rejected."""

    def setup_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def teardown_method(self) -> None:
        from maascommon.hardening import get_hardening_config

        get_hardening_config.cache_clear()

    def test_weak_password_rejected_when_hardening_active(self) -> None:
        from maasapiserver.v3.api.public.models.requests.users import (
            UserChangePasswordRequest,
        )

        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            with pytest.raises(ValidationError) as exc_info:
                UserChangePasswordRequest(password=_WEAK_PASSWORD)
        assert any(e["loc"] == ("password",) for e in exc_info.value.errors())

    def test_strong_password_accepted(self) -> None:
        from maasapiserver.v3.api.public.models.requests.users import (
            UserChangePasswordRequest,
        )

        with patch("maascommon.hardening.is_fips_enabled", return_value=True):
            req = UserChangePasswordRequest(password=_STRONG_PASSWORD)
        assert req.password == _STRONG_PASSWORD
