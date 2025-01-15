# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import BaseModel, Field

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.db.repositories.sshkeys import SshKeyResourceBuilder
from maasservicelayer.utils.date import utcnow


class SshKeyManualUploadRequest(BaseModel):
    key: str = Field(description="The SSH public key to be added.")

    def to_builder(self, user_id: int) -> SshKeyResourceBuilder:
        now = utcnow()
        return (
            SshKeyResourceBuilder()
            .with_key(self.key)
            .with_protocol(None)
            .with_auth_id(None)
            .with_user_id(user_id)
            .with_created(now)
            .with_updated(now)
        )


class SshKeyImportFromSourceRequest(BaseModel):
    protocol: SshKeysProtocolType = Field(
        description="The source from where to fetch the key."
    )
    auth_id: str = Field(description="The username related to the source.")
