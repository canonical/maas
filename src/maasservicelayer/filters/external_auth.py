# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import Filter, FilterFactory
from maasservicelayer.models.external_auth import OAuthProvider


class ExternalOAuthFilters(FilterFactory):
    model = OAuthProvider

    @classmethod
    def with_enabled(cls, enabled: bool) -> Filter:
        return cls._equals("enabled", enabled)
