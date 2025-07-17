# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import and_, asc, desc

from maasapiserver.v3.api.public.models.requests.ui_subnets import (
    UISubnetFiltersParams,
    UISubnetOrderByQueryFilter,
)
from maasservicelayer.db.filters import Clause, OrderByClause
from maasservicelayer.db.tables import UISubnetView
from maasservicelayer.exceptions.catalog import ValidationException


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

    def test_to_clauses(self) -> None:
        q = UISubnetOrderByQueryFilter(order_by=["asc(cidr)"])
        assert q.to_clauses() == [
            OrderByClause(column=asc(UISubnetView.c.cidr))
        ]

        q = UISubnetOrderByQueryFilter(order_by=["desc(cidr)"])
        assert q.to_clauses() == [
            OrderByClause(column=desc(UISubnetView.c.cidr))
        ]

        q = UISubnetOrderByQueryFilter(order_by=["asc(cidr)", "desc(fabric)"])
        assert q.to_clauses() == [
            OrderByClause(column=asc(UISubnetView.c.cidr)),
            OrderByClause(column=desc(UISubnetView.c.fabric_name)),
        ]


class TestUISubnetFiltersParams:
    @pytest.mark.parametrize(
        "cidrs,vlan_ids,fabric_names,space_names,expected_clause",
        [
            ([], [], [], [], None),
            (
                ["10.0.0.0/24"],
                [],
                [],
                [],
                Clause(condition=UISubnetView.c.cidr.in_(["10.0.0.0/24"])),
            ),
            (
                [],
                [1],
                [],
                [],
                Clause(condition=UISubnetView.c.vlan_id.in_([1])),
            ),
            (
                [],
                [],
                ["fabric-0"],
                [],
                Clause(condition=UISubnetView.c.fabric_name.in_(["fabric-0"])),
            ),
            (
                [],
                [],
                [],
                ["space-0"],
                Clause(condition=UISubnetView.c.space_name.in_(["space-0"])),
            ),
            (
                ["10.0.0.0/24"],
                [1],
                ["fabric-0"],
                ["space-0"],
                Clause(
                    condition=and_(
                        *[
                            UISubnetView.c.cidr.in_(["10.0.0.0/24"]),
                            UISubnetView.c.vlan_id.in_([1]),
                            UISubnetView.c.fabric_name.in_(["fabric-0"]),
                            UISubnetView.c.space_name.in_(["space-0"]),
                        ]
                    )
                ),
            ),
        ],
    )
    def test_to_clause(
        self,
        cidrs: list[str],
        vlan_ids: list[int],
        fabric_names: list[str],
        space_names: list[str],
        expected_clause: Clause,
    ) -> None:
        f = UISubnetFiltersParams(
            cidrs=cidrs,
            vlan_ids=vlan_ids,
            fabric_names=fabric_names,
            space_names=space_names,
        )
        assert f.to_clause() == expected_clause

    @pytest.mark.parametrize(
        "cidrs,vlan_ids,fabric_names,space_names,expected_clause",
        [
            ([], [], [], [], ""),
            (["10.0.0.0/24"], [], [], [], "cidr=10.0.0.0/24"),
            ([], [1], [], [], "vlan_id=1"),
            ([], [], ["fabric-0"], [], "fabric=fabric-0"),
            ([], [], [], ["space-0"], "space=space-0"),
            (
                ["name"],
                [1],
                ["fabric-0"],
                ["space-0"],
                "subnet=name&vlan_id=1&fabric=fabric-0&space=space-0",
            ),
            (
                [],
                [],
                ["fabric-0", "fabric-1"],
                [],
                "fabric=fabric-0&fabric=fabric-1",
            ),
        ],
    )
    def to_href_format(
        self,
        cidrs: list[str],
        vlan_ids: list[int],
        fabric_names: list[str],
        space_names: list[str],
        expected_href: str,
    ) -> None:
        f = UISubnetFiltersParams(
            cidrs=cidrs,
            vlan_ids=vlan_ids,
            fabric_names=fabric_names,
            space_names=space_names,
        )
        assert f.to_href_format() == expected_href
