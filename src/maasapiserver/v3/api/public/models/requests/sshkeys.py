# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import BaseModel, Field

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.models.sshkeys import SshKeyBuilder


class SshKeyManualUploadRequest(BaseModel):
    key: str = Field(description="The SSH public key to be added.")

    def to_builder(self, user_id: int) -> SshKeyBuilder:
        return SshKeyBuilder(
            key=self.key, protocol=None, auth_id=None, user_id=user_id
        )


class SshKeyImportFromSourceRequest(BaseModel):
    protocol: SshKeysProtocolType = Field(
        description="The source from where to fetch the key."
    )
    auth_id: str = Field(description="The username related to the source.")
