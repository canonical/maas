#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.sshkeys import SshKey


class SshKeyFilters(FilterFactory):
    model = SshKey

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_user_id(cls, user_id: int) -> FieldFilter:
        return cls._equals("user_id", user_id)

    @classmethod
    def with_key(cls, key: str) -> FieldFilter:
        return cls._equals("key", key)

    @classmethod
    def with_protocol(
        cls, protocol: SshKeysProtocolType | None
    ) -> FieldFilter:
        return cls._equals("protocol", protocol)

    @classmethod
    def with_auth_id(cls, auth_id: str | None) -> FieldFilter:
        return cls._equals("auth_id", auth_id)
