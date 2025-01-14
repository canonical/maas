#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasapiserver.v3.api.public.models.requests.sslkeys import SSLKeyRequest
from tests.fixtures import get_test_data_file


@pytest.mark.asyncio
class TestSSLKeyCreateRequest:
    async def test_valid_sslkey_request(self) -> None:
        SSLKeyRequest(
            key=get_test_data_file("test_x509_0.pem"),
        )

    async def test_invalid_sslkey_request(self) -> None:
        with pytest.raises(ValueError):
            SSLKeyRequest(
                key="Invalid SSL Key",
            )
