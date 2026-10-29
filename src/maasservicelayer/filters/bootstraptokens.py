# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.bootstraptokens import BootstrapToken


class BootstrapTokensFilters(FilterFactory):
    model = BootstrapToken

    @classmethod
    def with_rack_id(cls, rack_id: int) -> FieldFilter:
        return cls._equals("rack_id", rack_id)

    @classmethod
    def with_rack_id_in(cls, rack_id_list: list[int]) -> FieldFilter:
        return cls._is_in("rack_id", rack_id_list)

    @classmethod
    def with_secret(cls, secret: str) -> FieldFilter:
        return cls._equals("secret", secret)
