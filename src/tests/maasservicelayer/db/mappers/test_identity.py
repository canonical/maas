# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.db.mappers.base import UnsupportedFilterError
from maasservicelayer.db.mappers.openfga_tuples import OpenFGATuplesDataMapper
from maasservicelayer.db.mappers.usergroups import UserGroupsDataMapper
from maasservicelayer.db.mappers.users import UsersDataMapper
from maasservicelayer.filters.openfga_tuples import OpenFGATuplesFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.usergroups import UserGroupsFilters
from maasservicelayer.filters.users import UserFilters


@pytest.mark.parametrize(
    "mapper,foreign_filter",
    [
        (UsersDataMapper(), UserGroupsFilters.with_ids([1])),
        (UserGroupsDataMapper(), UserFilters.with_id(1)),
        (OpenFGATuplesDataMapper(), UserFilters.with_id(1)),
        (UsersDataMapper(), OpenFGATuplesFilters.with_user("user:1")),
    ],
)
def test_identity_mappers_reject_filters_for_unrelated_domain_models(
    mapper, foreign_filter
):
    with pytest.raises(UnsupportedFilterError):
        mapper.to_query(QuerySpec(where=foreign_filter))
