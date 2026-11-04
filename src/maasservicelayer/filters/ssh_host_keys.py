# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey


class TrustedSshHostKeyFilters(FilterFactory):
    model = TrustedSshHostKey

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_host(cls, host: str) -> FieldFilter:
        return cls._equals("host", host)

    @classmethod
    def with_key_type(cls, key_type: str) -> FieldFilter:
        return cls._equals("key_type", key_type)

    @classmethod
    def with_public_key(cls, public_key: str) -> FieldFilter:
        return cls._equals("public_key", public_key)
