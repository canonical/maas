#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.auth.external_auth import ExternalAuthType
from maasapiserver.v3.services import SecretsService
from maasapiserver.v3.services.external_auth import ExternalAuthService


@pytest.mark.asyncio
class TestExternalAuthService:
    async def test_get_external_auth_candid(self):
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "http://10.0.1.23:8081/",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "",
                "admin-group": "admin",
            }
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default={}
        )
        assert external_auth.url == "http://10.0.1.23:8081"
        assert external_auth.type == ExternalAuthType.CANDID
        assert external_auth.domain == ""
        assert external_auth.admin_group == "admin"

    async def test_get_external_auth_rbac(self):
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(
            return_value={
                "key": "mykey",
                "url": "",
                "user": "admin@candid",
                "domain": "",
                "rbac-url": "http://10.0.1.23:5000",
                "admin-group": "admin",
            }
        )
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default={}
        )
        assert external_auth.url == "http://10.0.1.23:5000/auth"
        assert external_auth.type == ExternalAuthType.RBAC
        assert external_auth.domain == ""
        assert external_auth.admin_group == ""

    async def test_get_external_auth_not_enabled(self):
        secrets_service_mock = Mock(SecretsService)
        secrets_service_mock.get_composite_secret = AsyncMock(return_value={})
        external_auth_service = ExternalAuthService(
            Mock(AsyncConnection),
            secrets_service=secrets_service_mock,
        )
        external_auth = await external_auth_service.get_external_auth()
        secrets_service_mock.get_composite_secret.assert_called_once_with(
            path="global/external-auth", default={}
        )
        assert external_auth is None
