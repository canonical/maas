#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from maasservicelayer.builders.tokens import ApiTokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.api_tokens import ApiTokenRepository
from maasservicelayer.models.tokens import ApiToken
from maasservicelayer.services.api_tokens import ApiTokenService
from maasservicelayer.utils.api_tokens import (
    floor_to_throttle_window,
    generate_api_token,
)
from maasservicelayer.utils.date import utcnow


def make_token(**overrides) -> ApiToken:
    generated = overrides.pop("generated", None) or generate_api_token()
    fields = {
        "id": 1,
        "name": "ci",
        "public_id": generated.public_id,
        "secret_hash": generated.secret_hash,
        "expires_at": utcnow() + timedelta(days=1),
        "user_id": 1,
    }
    fields.update(overrides)
    return ApiToken(**fields)


@pytest.mark.asyncio
class TestApiTokenService:
    @pytest.fixture
    def repository(self) -> Mock:
        return Mock(ApiTokenRepository)

    @pytest.fixture
    def service(self, repository: Mock) -> ApiTokenService:
        return ApiTokenService(context=Context(), repository=repository)

    async def test_create_token_stores_only_the_hash(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        repository.create.side_effect = lambda builder: make_token(
            public_id=builder.public_id, secret_hash=builder.secret_hash
        )
        expires_at = utcnow() + timedelta(days=1)

        token, raw_token = await service.create_token(1, "ci", expires_at)

        builder = repository.create.call_args.kwargs["builder"]
        assert raw_token == f"maas_pat_{token.public_id}_{raw_token[-43:]}"
        assert raw_token[-43:] not in builder.secret_hash
        assert builder.expires_at == expires_at
        assert builder.user_id == 1

    async def test_authenticate_updates_last_used_at_to_floored_window(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        generated = generate_api_token()
        token = make_token(generated=generated)
        repository.get_one.return_value = token
        repository.update_by_id.return_value = token

        result = await service.authenticate(generated.raw_token)

        assert result is token
        repository.update_by_id.assert_awaited_once()
        builder = repository.update_by_id.call_args.args[1]
        assert builder.last_used_at == floor_to_throttle_window(
            builder.last_used_at
        )
        assert builder.last_used_at <= utcnow()

    async def test_authenticate_skips_update_within_window(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        generated = generate_api_token()
        token = make_token(
            generated=generated,
            last_used_at=floor_to_throttle_window(utcnow()),
        )
        repository.get_one.return_value = token

        assert await service.authenticate(generated.raw_token) is token
        repository.update_by_id.assert_not_called()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"revoked_at": datetime(2020, 1, 1, tzinfo=timezone.utc)},
            {"expires_at": datetime(2020, 1, 1, tzinfo=timezone.utc)},
        ],
    )
    async def test_authenticate_rejects_revoked_or_expired(
        self, service: ApiTokenService, repository: Mock, overrides: dict
    ) -> None:
        generated = generate_api_token()
        repository.get_one.return_value = make_token(
            generated=generated, **overrides
        )

        assert await service.authenticate(generated.raw_token) is None
        repository.update_by_id.assert_not_called()

    async def test_authenticate_rejects_wrong_secret(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        generated = generate_api_token()
        repository.get_one.return_value = make_token(generated=generated)
        forged = generate_api_token()
        forged_raw = f"maas_pat_{generated.public_id}_{forged.raw_token[-43:]}"

        assert await service.authenticate(forged_raw) is None

    async def test_authenticate_rejects_malformed_token(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        assert await service.authenticate("maas_pat_nope") is None
        repository.get_one.assert_not_called()

    async def test_revoke_sets_revoked_at(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        token = make_token()
        repository.update_by_id = AsyncMock(return_value=token)

        await service.revoke(token)

        builder = repository.update_by_id.call_args.args[1]
        assert builder.revoked_at is not None

    async def test_revoke_is_noop_when_already_revoked(
        self, service: ApiTokenService, repository: Mock
    ) -> None:
        token = make_token(revoked_at=utcnow())

        assert await service.revoke(token) is token
        repository.update_by_id.assert_not_called()

    async def test_create_is_not_supported(
        self, service: ApiTokenService
    ) -> None:
        with pytest.raises(NotImplementedError):
            await service.create(ApiTokenBuilder())
