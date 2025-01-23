#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.enums.sshkeys import (
    OPENSSH_PROTOCOL2_KEY_TYPES,
    SshKeysProtocolType,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.sshkeys import SshKeysRepository
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    ValidationException,
)
from maasservicelayer.models.sshkeys import SshKey, SshKeyBuilder
from maasservicelayer.services.sshkeys import SshKeysService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

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
TEST_ECDSA521_KEY = (
    "ecdsa-sha2-nistp521 AAAAE2VjZHNhLXNoYTItbmlzdHA1MjEAAAAIbmlzdHA1MjEAA"
    "ACFBAFid8WJ6720Z8xJ/Fnsz9eZmUxdbcVNzBeML380gMeBMP9zPXWz629cahQT0HncnK"
    "sLsbRB7MMxdaBdsAQ8pteGXQEHVdnr6IkOrVbCHtVaVbjN4gpRICseMnDHrryrOjsvBIU"
    "7GGpmmHZka9alvSZlbB1lCx1BxqZZj8AHjJq2KpUh+A== ec5@bar"
)
TEST_ECDSA384_KEY = (
    "ecdsa-sha2-nistp384 AAAAE2VjZHNhLXNoYTItbmlzdHAzODQAAAAIbmlzdHAzODQAA"
    "ABhBFnB+h79/2MeUR4FoDuKJDyjLEswi8I50NuwIoRbHOwPkPDSDXk6EKfBY0GEwAGyr7"
    "h9OjVlmA1KKWUE01KJKf4/iJOh+9zsaL4iQzP9Q9phiUAmxkvegefGwqEXeAvk1Q== "
    "ec3@bar"
)
TEST_ECDSA256_KEY = (
    "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAA"
    "ABBBEqp6hJ9qj6dD1Y1AfsbauzjAaoIQhvTCdg+otLRklg5ZWr8KoS98K50s0eVwcOD7i"
    "LltCeS7W0y8c7wlsADVh0= ec2@bar"
)


@pytest.mark.asyncio
class TestCommonSshKeysService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> SshKeysService:
        return SshKeysService(
            context=Context(), sshkeys_repository=Mock(SshKeysRepository)
        )

    @pytest.fixture
    def test_instance(self) -> SshKey:
        now = utcnow()
        return SshKey(
            id=1,
            created=now,
            updated=now,
            key=TEST_ED25519_KEY,
            protocol=SshKeysProtocolType.LP,
            auth_id="foo",
            user_id=1,
        )

    async def test_update_many(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_many(
                service_instance, test_instance
            )

    async def test_update_one(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one(
                service_instance, test_instance
            )

    async def test_update_one_not_found(self, service_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_not_found(service_instance)

    async def test_update_one_etag_match(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_match(
                service_instance, test_instance
            )

    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_one_etag_not_matching(
                service_instance, test_instance
            )

    async def test_update_by_id(self, service_instance, test_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id(
                service_instance, test_instance
            )

    async def test_update_by_id_not_found(self, service_instance):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_not_found(service_instance)

    async def test_update_by_id_etag_match(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_match(
                service_instance, test_instance
            )

    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance
    ):
        with pytest.raises(NotImplementedError):
            return await super().test_update_by_id_etag_not_matching(
                service_instance, test_instance
            )

    async def test_create(self, service_instance, test_instance):
        # pre_create_hook tested in the next tests
        service_instance.pre_create_hook = AsyncMock()
        return await super().test_create(service_instance, test_instance)


class TestSshKeysService:
    async def test_create_already_existing(self) -> None:
        repository = Mock(SshKeysRepository)
        repository.get_one.return_value = SshKey(
            id=1, key=TEST_ED25519_KEY, protocol=None, auth_id=None, user_id=1
        )
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )

        builder = SshKeyBuilder(
            key=TEST_ED25519_KEY, protocol=None, auth_id=None, user_id=1
        )

        with pytest.raises(AlreadyExistsException):
            await sshkeys_service.create(builder)

        repository.create.assert_not_called()

    async def test_create_normalize_key(self) -> None:
        repository = Mock(SshKeysRepository)
        repository.get_one.return_value = None
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service.normalize_openssh_public_key = AsyncMock()
        sshkeys_service.normalize_openssh_public_key.return_value = (
            "normalized_key"
        )

        builder = SshKeyBuilder(
            key=TEST_ED25519_KEY, protocol=None, auth_id=None, user_id=1
        )

        await sshkeys_service.create(builder)
        builder.key = "normalized_key"
        repository.create.assert_called_once_with(builder=builder)

    async def test_create_already_existing_imported_key(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )

        builder = SshKeyBuilder(
            key=TEST_ED25519_KEY,
            protocol=SshKeysProtocolType.LP,
            auth_id="foo",
            user_id=1,
        )

        await sshkeys_service.create(builder)

        repository.create.assert_called_once()

    @pytest.mark.parametrize(
        "protocol", [SshKeysProtocolType.LP, SshKeysProtocolType.GH]
    )
    async def test_import_keys_raise_error_with_no_keys(
        self, protocol: SshKeysProtocolType
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service._get_ssh_key_from_github = AsyncMock()
        sshkeys_service._get_ssh_key_from_github.return_value = []
        sshkeys_service._get_ssh_key_from_launchpad = AsyncMock()
        sshkeys_service._get_ssh_key_from_launchpad.return_value = []

        with pytest.raises(ValidationException) as e:
            await sshkeys_service.import_keys(protocol, "foo", 1)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "auth_id"
        assert (
            e.value.details[0].message
            == f"Unable to import SSH keys. There are no SSH keys for {protocol.value} user foo."
        )

    @pytest.mark.parametrize(
        "protocol", [SshKeysProtocolType.LP, SshKeysProtocolType.GH]
    )
    async def test_import_keys_not_created_if_existing(
        self, protocol: SshKeysProtocolType
    ) -> None:
        sshkey = SshKey(
            id=1,
            key=TEST_ED25519_KEY,
            protocol=protocol,
            auth_id="foo",
            user_id=1,
        )
        repository = Mock(SshKeysRepository)
        repository.get_many.return_value = [sshkey]
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service._get_ssh_key_from_github = AsyncMock()
        sshkeys_service._get_ssh_key_from_github.return_value = [
            TEST_ED25519_KEY
        ]
        sshkeys_service._get_ssh_key_from_launchpad = AsyncMock()
        sshkeys_service._get_ssh_key_from_launchpad.return_value = [
            TEST_ED25519_KEY
        ]

        keys = await sshkeys_service.import_keys(protocol, "foo", 1)
        assert keys == [sshkey]
        repository.create.assert_not_called()

    @pytest.mark.parametrize(
        "protocol", [SshKeysProtocolType.LP, SshKeysProtocolType.GH]
    )
    async def test_import_keys_only_missing_key_created(
        self, protocol: SshKeysProtocolType
    ) -> None:
        sshkey = SshKey(
            id=1,
            key=TEST_ED25519_KEY,
            protocol=protocol,
            auth_id="foo",
            user_id=1,
        )
        sshkey_created = SshKey(
            id=2, key=TEST_RSA_KEY, protocol=protocol, auth_id="foo", user_id=1
        )
        repository = Mock(SshKeysRepository)
        repository.get_many.return_value = [sshkey]
        repository.create.return_value = sshkey_created
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        sshkeys_service._get_ssh_key_from_github = AsyncMock()
        sshkeys_service._get_ssh_key_from_github.return_value = [
            TEST_ED25519_KEY,
            TEST_RSA_KEY,
        ]
        sshkeys_service._get_ssh_key_from_launchpad = AsyncMock()
        sshkeys_service._get_ssh_key_from_launchpad.return_value = [
            TEST_ED25519_KEY,
            TEST_RSA_KEY,
        ]

        builder = SshKeyBuilder(
            key=TEST_RSA_KEY, protocol=protocol, auth_id="foo", user_id=1
        )

        keys = await sshkeys_service.import_keys(protocol, "foo", 1)
        assert len(keys) == 2
        assert sshkey in keys
        assert sshkey_created in keys
        repository.create.assert_called_once_with(builder=builder)

    @pytest.mark.parametrize(
        "keys", [[], [TEST_ED25519_KEY], [TEST_ED25519_KEY, TEST_RSA_KEY]]
    )
    async def test_get_ssh_keys_from_launchpad(
        self,
        keys: list[str],
        mock_aioresponse,
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        auth_id = "foo"
        expected_response = "\n".join(keys)
        mock_aioresponse.get(
            f"https://launchpad.net/~{auth_id}/+sshkeys",
            body=expected_response,
        )
        fetched_keys = await sshkeys_service._get_ssh_key_from_launchpad(
            auth_id
        )

        assert set(fetched_keys) == set(keys)
        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"https://launchpad.net/~{auth_id}/+sshkeys",
        )

    @pytest.mark.parametrize("status", [404, 410])
    async def test_get_ssh_keys_from_launchpad_raise_exception(
        self,
        status: int,
        mock_aioresponse,
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        auth_id = "foo"
        mock_aioresponse.get(
            f"https://launchpad.net/~{auth_id}/+sshkeys",
            status=status,
        )
        with pytest.raises(ValidationException) as e:
            await sshkeys_service._get_ssh_key_from_launchpad(auth_id)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "auth_id"
        assert (
            e.value.details[0].message
            == "Unable to import SSH keys. Launchpad user foo doesn't exist."
        )

        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"https://launchpad.net/~{auth_id}/+sshkeys",
        )

    @pytest.mark.parametrize(
        "keys", [[], [TEST_ED25519_KEY], [TEST_ED25519_KEY, TEST_RSA_KEY]]
    )
    async def test_get_ssh_keys_from_github(
        self,
        keys: list[str],
        mock_aioresponse,
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        auth_id = "foo"
        expected_response = [{"key": key} for key in keys]
        mock_aioresponse.get(
            f"https://api.github.com/users/{auth_id}/keys",
            payload=expected_response,
        )
        fetched_keys = await sshkeys_service._get_ssh_key_from_github(auth_id)

        assert set(fetched_keys) == set(keys)
        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"https://api.github.com/users/{auth_id}/keys",
        )

    @pytest.mark.parametrize("status", [404, 410])
    async def test_get_ssh_keys_from_github_raise_exception(
        self,
        status: int,
        mock_aioresponse,
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        auth_id = "foo"
        mock_aioresponse.get(
            f"https://api.github.com/users/{auth_id}/keys",
            status=status,
        )
        with pytest.raises(ValidationException) as e:
            await sshkeys_service._get_ssh_key_from_github(auth_id)

        assert len(e.value.details) == 1
        assert e.value.details[0].field == "auth_id"
        assert (
            e.value.details[0].message
            == "Unable to import SSH keys. Github user foo doesn't exist."
        )

        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"https://api.github.com/users/{auth_id}/keys",
        )

    async def test_normalize_openssh_public_keys_less_than_2_parts(
        self,
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        with pytest.raises(ValidationException) as e:
            await sshkeys_service.normalize_openssh_public_key("testkey")
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "key"
        assert (
            e.value.details[0].message
            == "Key should contain 2 or more space separated parts (key type, base64-encoded key, optional comments), not 1)"
        )

    async def test_normalize_openssh_public_keys_wrong_keytype(self) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        # use a wrong keytype but a valid key
        key = "wrong-keytype " + " ".join(TEST_RSA_KEY.split()[1:])
        with pytest.raises(ValidationException) as e:
            await sshkeys_service.normalize_openssh_public_key(key)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "key"
        assert (
            e.value.details[0].message
            == f"Key type wrong-keytype not recognised; it should be one of: {" ".join(sorted(OPENSSH_PROTOCOL2_KEY_TYPES))}"
        )

    @pytest.mark.parametrize(
        "key",
        [
            TEST_RSA_KEY,
            TEST_DSA_KEY,
            TEST_ED25519_KEY,
            TEST_ECDSA256_KEY,
            TEST_ECDSA384_KEY,
            TEST_ECDSA521_KEY,
        ],
    )
    async def test_normalize_openssh_public_keys_valid_keys_with_comments(
        self, key: str
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        await sshkeys_service.normalize_openssh_public_key(key)

    @pytest.mark.parametrize(
        "key",
        [
            TEST_RSA_KEY,
            TEST_DSA_KEY,
            TEST_ED25519_KEY,
            TEST_ECDSA256_KEY,
            TEST_ECDSA384_KEY,
            TEST_ECDSA521_KEY,
        ],
    )
    async def test_normalize_openssh_public_keys_valid_keys_without_comments(
        self, key: str
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        # keep only the keytype and key
        key = " ".join(key.split()[:2])
        await sshkeys_service.normalize_openssh_public_key(key)

    async def test_normalize_openssh_public_keys_valid_keys_malformed_key(
        self,
    ) -> None:
        repository = Mock(SshKeysRepository)
        sshkeys_service = SshKeysService(
            context=Context(), sshkeys_repository=repository
        )
        key = TEST_RSA_KEY
        # remove the comment
        key = " ".join(key.split()[:2])
        # remove the last char of the key
        key = key[:-1]
        with pytest.raises(ValidationException) as e:
            await sshkeys_service.normalize_openssh_public_key(key)
        assert len(e.value.details) == 1
        assert e.value.details[0].field == "key"
        assert e.value.details[0].message.startswith(
            "Key could not be converted to RFC4716 form."
        )
