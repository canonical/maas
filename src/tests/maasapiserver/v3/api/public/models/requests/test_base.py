# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pydantic import BaseModel
import pytest

from maasapiserver.v3.api.public.models.requests.base import (
    FreeTextSearchQueryParam,
    NamedBaseModel,
    OptionalNamedBaseModel,
    OrderByQueryFilter,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.filters.base import FieldFilter, Filter, Operator
from maasservicelayer.filters.query import OrderBy

VALID_NAMES = [
    "ValidName",
    "Name With Spaces",
    "Name-With-Hyphens",
    "123ValidName",
    "name with trailing hyphens-",
]

INVALID_NAMES = [
    "Name_With_Special#Characters",
    "",
    " ",
    "-Name with leading hyphens",
]


class TestNamedBaseModel:
    @pytest.mark.parametrize(
        "name",
        VALID_NAMES,
    )
    def test_valid_names(self, name: str):
        assert NamedBaseModel(name=name).name == name

    @pytest.mark.parametrize(
        "name",
        INVALID_NAMES,
    )
    def test_invalid_names(self, name: str):
        with pytest.raises(ValueError, match="Invalid entity name."):
            NamedBaseModel(name=name)


class TestOptionalNamedBaseModel:
    @pytest.mark.parametrize("name", VALID_NAMES)
    def test_valid_names(self, name: str):
        assert OptionalNamedBaseModel(name=name).name == name

    @pytest.mark.parametrize("name", INVALID_NAMES)
    def test_invalid_names(self, name: str):
        with pytest.raises(ValueError, match="Invalid entity name."):
            OptionalNamedBaseModel(name=name)

    def test_none_name(self):
        model = OptionalNamedBaseModel()
        assert model.name is None


class DummyModel(BaseModel):
    id: int
    name: str


class OrderByQueryTestClass(OrderByQueryFilter):
    order_by_fields = {
        "id": OrderBy(DummyModel, "id"),
        "name": OrderBy(DummyModel, "name"),
    }


class TestOrderByQueryFilter:
    @pytest.mark.parametrize(
        "field,should_raise",
        [
            ("id", False),
            ("name", False),
            ("asc(id)", False),
            ("desc(id)", False),
            ("foo", True),
            ("asc(foo)", True),
            ("desc(foo)", True),
            ("wrong(foo)", True),
        ],
    )
    def test_allowed_fields(self, field: str, should_raise: bool) -> None:
        if should_raise:
            with pytest.raises(ValidationException):
                OrderByQueryTestClass(order_by=[field])

        else:
            OrderByQueryTestClass(order_by=[field])

    def test_duplicate_field(self) -> None:
        with pytest.raises(ValidationException):
            OrderByQueryTestClass(order_by=["desc(id)", "asc(id)"])

    def test_ordering_directions_and_precedence(self) -> None:
        query = OrderByQueryTestClass(order_by=["id", "asc(name)"])
        assert [
            (order.field, order.descending) for order in query.to_order_by()
        ] == [("id", True), ("name", False)]

    def test_ordering_requests_do_not_share_direction(self) -> None:
        descending = OrderByQueryTestClass(order_by=["desc(id)"])
        ascending = OrderByQueryTestClass(order_by=["asc(id)"])
        assert ascending.to_order_by()[0].descending is False
        assert descending.to_order_by()[0].descending is True

    def test_to_href_format(self) -> None:
        q = OrderByQueryTestClass(order_by=["desc(id)"])
        assert q.to_href_format() == "order_by=desc(id)"
        q = OrderByQueryTestClass(order_by=["desc(id)", "asc(name)"])
        assert q.to_href_format() == "order_by=desc(id)&order_by=asc(name)"


class FreeTextSearchQueryParamTestClass(FreeTextSearchQueryParam):
    def to_filter(self) -> Filter | None:
        if not self.q:
            return None
        return FieldFilter(DummyModel, "name", Operator.EQ, self.q)


class TestFreeTextSearchQueryParam:
    def test_to_href(self) -> None:
        freetext_query = FreeTextSearchQueryParamTestClass(q=None)
        assert freetext_query.to_href_format() == ""

        freetext_query = FreeTextSearchQueryParamTestClass(q="foo")
        assert freetext_query.to_href_format() == "q=foo"
