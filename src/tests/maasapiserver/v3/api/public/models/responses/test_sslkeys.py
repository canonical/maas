#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.sslkey import SSLKeyResponse
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.utils.date import utcnow
from tests.fixtures import get_test_data_file


class TestSSLKeyResponse:
    def test_from_model_valid(self) -> None:
        now = utcnow()
        key = get_test_data_file("test_x509_0.pem")
        sslkey = SSLKey(
            id=1,
            key=key,
            created=now,
            updated=now,
            user_id=1,
        )
        response = SSLKeyResponse.from_model(sslkey=sslkey)

        assert sslkey.id == response.id
        assert sslkey.key == response.key
