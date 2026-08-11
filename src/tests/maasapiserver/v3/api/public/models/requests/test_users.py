# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.contrib.auth.hashers import PBKDF2PasswordHasher
from pydantic import ValidationError
import pytest

from maasapiserver.v3.api.public.models.requests.users import (
    BaseUserRequest,
    UserChangePasswordRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
import maascommon.hardening as _hardening
from maasservicelayer.models.base import UNSET


@pytest.fixture(autouse=True)
def reset_hardening():
    original = _hardening._hardening_active
    yield
    _hardening._hardening_active = original


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
            ("UPPER@EXAMPLE.COM", True),
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
            req = BaseUserRequest(
                username="test",
                is_superuser=False,
                first_name="test",
                last_name="test",
                email=email,
            )
            assert req.email == email.lower()


class TestUserCreateRequest:
    def test_password_length(self) -> None:
        _hardening._hardening_active = False
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
        _hardening._hardening_active = False
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

    def test_to_builder_with_password(self) -> None:
        _hardening._hardening_active = False
        u = UserUpdateRequest(
            username="test",
            password="test",
            is_superuser=False,
            first_name="test",
            last_name="test",
            email="email@example.com",
        )
        b = u.to_builder()
        assert PBKDF2PasswordHasher().verify("test", b.password)


_WEAK_PASSWORD = "weak"
_STRONG_PASSWORD = "Str0ng!Pass#12"


def _base_fields(**overrides):
    return {
        "username": "alice",
        "is_superuser": False,
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        **overrides,
    }


_REQUEST_BUILDERS = [
    pytest.param(
        lambda pw: UserCreateRequest(**_base_fields(password=pw)),
        id="UserCreateRequest",
    ),
    pytest.param(
        lambda pw: UserUpdateRequest(**_base_fields(password=pw)),
        id="UserUpdateRequest",
    ),
    pytest.param(
        lambda pw: UserChangePasswordRequest(password=pw),
        id="UserChangePasswordRequest",
    ),
]


class TestPasswordComplexityEnforcement:
    """_enforce_password_complexity is wired into every password field."""

    @pytest.mark.parametrize("build", _REQUEST_BUILDERS)
    def test_weak_password_rejected_when_hardening_active(self, build) -> None:
        _hardening._hardening_active = True
        with pytest.raises(ValidationError) as exc_info:
            build(_WEAK_PASSWORD)
        assert any(e["loc"] == ("password",) for e in exc_info.value.errors())

    @pytest.mark.parametrize("build", _REQUEST_BUILDERS)
    def test_strong_password_accepted_when_hardening_active(
        self, build
    ) -> None:
        _hardening._hardening_active = True
        req = build(_STRONG_PASSWORD)
        assert req.password == _STRONG_PASSWORD

    def test_weak_password_accepted_when_hardening_inactive(self) -> None:
        _hardening._hardening_active = False
        req = UserCreateRequest(**_base_fields(password=_WEAK_PASSWORD))
        assert req.password == _WEAK_PASSWORD

    def test_update_none_password_bypasses_complexity_check(self) -> None:
        # None is the "no-change" sentinel for UserUpdateRequest; the validator
        # short-circuits before reaching _enforce_password_complexity.
        _hardening._hardening_active = True
        req = UserUpdateRequest(**_base_fields(password=None))
        assert req.password is None
