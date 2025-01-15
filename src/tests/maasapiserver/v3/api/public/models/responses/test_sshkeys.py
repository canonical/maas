#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasapiserver.v3.api.public.models.responses.sshkeys import SshKeyResponse
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.sshkeys import SshKey
from maasservicelayer.utils.date import utcnow


class TestSshKeyResponse:
    def test_from_model(self) -> None:
        now = utcnow()
        sshkey = SshKey(
            id=1,
            created=now,
            updated=now,
            key="ssh-rsa randomkey comment",
            protocol=SshKeysProtocolType.LP,
            auth_id="foo",
            user_id=1,
        )
        sshkey_response = SshKeyResponse.from_model(
            sshkey, self_base_hyperlink=f"{V3_API_PREFIX}/users/me/sshkeys"
        )
        assert sshkey_response.id == sshkey.id
        assert sshkey_response.key == sshkey.key
        assert sshkey_response.protocol == sshkey.protocol
        assert sshkey_response.auth_id == sshkey.auth_id
        assert sshkey_response.user_id == sshkey.user_id
        assert sshkey_response.hal_links is not None
        assert (
            sshkey_response.hal_links.self.href
            == f"{V3_API_PREFIX}/users/me/sshkeys/{sshkey.id}"
        )
