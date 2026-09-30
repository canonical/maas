# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maasservicelayer.builders.sshkeys import SshKeyBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sshkeys import SshKeysRepository
from maasservicelayer.exceptions.catalog import FIPSViolationException
from maasservicelayer.services.sshkeys import SshKeysService

TEST_ED25519_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBEqkw2AgmkjqNjCFuiKXeUgLNmRbgVr8"
    "W2TlAvFybJv ed255@bar"
)
TEST_RSA_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDdrzzDZNwyMVBvBTT6kBnrfPZv/AUbk"
    "xj7G5CaMTdw6xkKthV22EntD3lxaQxRKzQTfCc2d/CC1K4ushCcRs1S6SQ2zJ2jDq1UmO"
    "UkDMgvNh4JVhJYSKc6mu8i3s7oGSmBado5wvtlpSzMrscOpf8Qe/wmT5fH12KB9ipJqoF"
    "NQMVbVcVarE/v6wpn3GZC62YRb5iaz9/M+t92Qhu50W2u+KfouqtKB2lwIDDKZMww38Ex"
    "tdMouh2FZpxaoh4Uey5bRp3tM3JgnWcX6fyUOp2gxJRPIlD9rrZhX5IkEkZM8MQbdPTQL"
    "gIf98oFph5RG6w1t02BvI9nJKM7KkKEfBHt ubuntu@test_rsa0"
)
TEST_DSA_KEY = (
    "ssh-dss AAAAB3NzaC1kc3MAAACBALl8PCMaSa3pCCGJaJr4kH0QPlrgyG3Lka+/y4xx1"
    "dOuJhpsLe2V9+CKX7Sz1yphCs26KqMFe/ebYGAUDhTdVlE4/TgpAP4GiTjdO1FGXTYdgQ"
    "yJpfp50bTUW0zKIP/dwHs5dCLn4XYAxXzSsvORGVQGbM6P6vh3lieTkeVETGZDAAAAFQC"
    "AaBKUmPvRqI37VRj1PE9B2rnkfQAAAIEApWYMF0IU+BYUtFuwRRUE9wEGxDEjTtuoWYCW"
    "ML7Zn+cFOvK+C0x8YItQ3xIiI3a/0DCoDPIZPvImXDMrs0zUunegndS9g7J0gCHFY9dd+"
    "rgYShUHwCI+hy/D9Dp1ukNnGD0bb3x5vEoSK6whrJWBM6is7TW4R5fvz/xDhrtIcxgAAA"
    "CBAJbZsmuuWN2kb7lD27IzKcOgd07esoHPWZnv4qg7xhS1GdVr485v73OW1rfpWU6Pdoh"
    "ckXLg9ZaoWtVTwNKTfHxS3iug9/pseBWTHdpmxCM5ClsZJii6T4frR5NTOCGKLxOamTs/"
    "//OXopZr5u3vT20NFlzFE95J86tGtxYPPivx ubuntu@server-7476"
)
TEST_ECDSA_KEY = (
    "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAA"
    "ABBBEqp6hJ9qj6dD1Y1AfsbauzjAaoIQhvTCdg+otLRklg5ZWr8KoS98K50s0eVwcOD7i"
    "LltCeS7W0y8c7wlsADVh0= ec2@bar"
)


@pytest.mark.asyncio
class TestSshKeysServiceFIPSValidation:
    @pytest.fixture(autouse=True)
    def enable_fips(self, monkeypatch):
        monkeypatch.setattr(
            "maasservicelayer.services.sshkeys.is_fips_enabled",
            lambda: True,
        )

    async def test_fips_rejects_dsa_key(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock(
            return_value=TEST_DSA_KEY
        )
        with pytest.raises(FIPSViolationException):
            await sshkeys_service.pre_create_hook(
                SshKeyBuilder(key=TEST_DSA_KEY, user_id=1)
            )

    async def test_fips_rejects_ed25519_key(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock(
            return_value=TEST_ED25519_KEY
        )
        with pytest.raises(FIPSViolationException):
            await sshkeys_service.pre_create_hook(
                SshKeyBuilder(key=TEST_ED25519_KEY, user_id=1)
            )

    async def test_fips_rejects_small_rsa_key(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "maascommon.fips.rsa_ssh_key_bits",
            lambda _b64: 1024,
        )
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock(
            return_value=TEST_RSA_KEY
        )
        with pytest.raises(FIPSViolationException):
            await sshkeys_service.pre_create_hook(
                SshKeyBuilder(key=TEST_RSA_KEY, user_id=1)
            )

    async def test_fips_allows_large_rsa_key(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock(
            return_value=TEST_RSA_KEY
        )
        # TEST_RSA_KEY is a real 2048-bit key, so it must pass validation.
        await sshkeys_service.pre_create_hook(
            SshKeyBuilder(key=TEST_RSA_KEY, user_id=1)
        )

    async def test_fips_allows_ecdsa_key(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock(
            return_value=TEST_ECDSA_KEY
        )
        # Should not raise
        await sshkeys_service.pre_create_hook(
            SshKeyBuilder(key=TEST_ECDSA_KEY, user_id=1)
        )


@pytest.mark.asyncio
class TestSshKeysServiceNonFIPSValidation:
    async def test_non_fips_allows_dsa_key(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock(
            return_value=TEST_DSA_KEY
        )
        # Should not raise (FIPS is disabled by default in tests)
        await sshkeys_service.pre_create_hook(
            SshKeyBuilder(key=TEST_DSA_KEY, user_id=1)
        )
