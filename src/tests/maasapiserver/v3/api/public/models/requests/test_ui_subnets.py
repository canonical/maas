# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasapiserver.v3.api.public.models.requests.ui_subnets import (
    UISubnetFiltersParams,
    UISubnetOrderByQueryFilter,
    UISubnetsFreeTextSearchQueryParam,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.filters.ui_subnets import UISubnetsFilters


class TestUISubnetOrderByQueryFilter:
    @pytest.mark.parametrize(
        "field",
        [
            "cidr",
            "fabric",
            "space",
        ],
    )
    def test_allowed_fields(self, field: str) -> None:
        for fmt in ("asc({})", "desc({})", "{}"):
            UISubnetOrderByQueryFilter(order_by=[fmt.format(field)])

    @pytest.mark.parametrize(
        "field",
        [
            "non_existent",
            "asc(foo)",
            "desc(bar)",
            "wrong(cidr)",
        ],
    )
    def test_disallowed_fields(self, field: str) -> None:
        with pytest.raises(ValidationException):
            UISubnetOrderByQueryFilter(order_by=[field])

    def test_duplicate_field(self) -> None:
        with pytest.raises(ValidationException):
            UISubnetOrderByQueryFilter(order_by=["desc(cidr)", "asc(cidr)"])


class TestUISubnetFiltersParams:
    @pytest.mark.parametrize(
        "cidrs,vlan_ids,fabric_names,space_names,subnet_ids,expected_href",
        [
            ([], [], [], [], [], ""),
            (["10.0.0.0/24"], [], [], [], [], "cidr=10.0.0.0/24"),
            ([], [1], [], [], [], "vlan_id=1"),
            ([], [], ["fabric-0"], [], [], "fabric=fabric-0"),
            ([], [], [], ["space-0"], [], "space=space-0"),
            ([], [], [], [], [1], "subnet_id=1"),
            (
                ["10.10.0.0/24"],
                [1],
                ["fabric-0"],
                ["space-0"],
                [1],
                "cidr=10.10.0.0/24&vlan_id=1&fabric=fabric-0&space=space-0&subnet_id=1",
            ),
            (
                [],
                [],
                ["fabric-0", "fabric-1"],
                [],
                [],
                "fabric=fabric-0&fabric=fabric-1",
            ),
        ],
    )
    def test_to_href_format(
        self,
        cidrs: list[str],
        vlan_ids: list[int],
        fabric_names: list[str],
        space_names: list[str],
        subnet_ids: list[int],
        expected_href: str,
    ) -> None:
        f = UISubnetFiltersParams(
            cidrs=cidrs,
            vlan_ids=vlan_ids,
            fabric_names=fabric_names,
            space_names=space_names,
            subnet_ids=subnet_ids,
        )
        assert f.to_href_format() == expected_href


class TestUISubnetsFreeTextSearchQueryParam:
    def test_to_filter_empty_q(self) -> None:
        freetext_query = UISubnetsFreeTextSearchQueryParam(q=None)
        assert freetext_query.to_filter() is None

    def test_to_filter(self) -> None:
        freetext_query = UISubnetsFreeTextSearchQueryParam(q="foo")
        expected_filter = UISubnetsFilters.or_filters(
            [
                UISubnetsFilters.with_fabric_name_like("foo"),
                UISubnetsFilters.with_vlan_name_like("foo"),
                UISubnetsFilters.with_space_name_like("foo"),
                UISubnetsFilters.with_cidr_like("foo"),
            ]
        )

        assert freetext_query.to_filter() == expected_filter
