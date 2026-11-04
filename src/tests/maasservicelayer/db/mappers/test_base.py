#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

from pydantic import BaseModel
import pytest
from sqlalchemy import (
    case,
    Column,
    create_engine,
    delete,
    func,
    Integer,
    MetaData,
    select,
    String,
    Table,
    update,
)

from maasservicelayer.db.mappers.base import (
    ColumnMapping,
    UnsupportedFilterError,
)
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import EventTable, SshKeyTable
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    Filter,
    Operator,
)
from maasservicelayer.filters.events import EventFilters
from maasservicelayer.filters.query import (
    CustomOrderBy,
    OrderBy,
    OrderByFactory,
    QuerySpec,
)
from maasservicelayer.filters.sshkeys import SshKeyFilters
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.events import Event
from maasservicelayer.models.sshkeys import SshKey


@dataclass(frozen=True)
class UnknownSshKeyFilter(CustomFilter):
    model = SshKey


class TestBaseDomainDataMapperToClause:
    @pytest.fixture
    def mapper(self) -> DefaultDomainDataMapper:
        return DefaultDomainDataMapper(SshKey, SshKeyTable)

    @pytest.mark.parametrize(
        "filter",
        [
            FieldFilter(Event, "id", Operator.EQ, 1),
            EventFilters.with_system_ids(["abc"]),
            SshKeyFilters.and_filters(
                [
                    SshKeyFilters.or_filters([]),
                    FieldFilter(Event, "id", Operator.EQ, 1),
                ]
            ),
            SshKeyFilters.or_filters(
                [
                    SshKeyFilters.and_filters([]),
                    EventFilters.with_system_ids(["abc"]),
                ]
            ),
        ],
    )
    def test_rejects_filter_of_another_model(
        self, mapper: DefaultDomainDataMapper, filter: Filter
    ) -> None:
        with pytest.raises(UnsupportedFilterError):
            mapper.to_clause(filter)

    def test_rejects_unknown_custom_filter(
        self, mapper: DefaultDomainDataMapper
    ) -> None:
        with pytest.raises(UnsupportedFilterError):
            mapper.to_clause(UnknownSshKeyFilter())

    def test_rejects_field_without_column(self) -> None:
        mapper = DefaultDomainDataMapper(Event, EventTable)
        with pytest.raises(UnsupportedFilterError):
            mapper.to_clause(FieldFilter(Event, "type", Operator.EQ, 1))


class TestBaseDomainDataMapperToQuery:
    @pytest.mark.parametrize(
        "order", [OrderBy(Event, "id"), OrderBy(Event, "type")]
    )
    def test_rejects_wrong_model_or_unmapped_order(self, order):
        mapper = DefaultDomainDataMapper(
            SshKey if order.field == "id" else Event,
            SshKeyTable if order.field == "id" else EventTable,
        )
        with pytest.raises(UnsupportedFilterError):
            mapper.to_query(QuerySpec(order_by=(order,)))

    @pytest.mark.parametrize("descending", [False, True])
    def test_ordering_join_selects_rows_but_does_not_restrict_mutations(
        self, descending
    ):
        metadata = MetaData()
        keys = Table(
            "keys",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("key", String),
        )
        owners = Table(
            "owners",
            metadata,
            Column("id", Integer, primary_key=True),
            Column("name", String),
        )

        class JoinedMapper(DefaultDomainDataMapper):
            def field_mappings(self):
                return {
                    "auth_id": ColumnMapping(
                        owners.c.name,
                        (keys.join(owners, keys.c.id == owners.c.id),),
                    )
                }

        mapper = JoinedMapper(SshKey, keys)
        query = mapper.to_query(
            QuerySpec(order_by=(OrderBy(SshKey, "auth_id", descending),))
        )
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                metadata.create_all(connection)
                connection.execute(
                    keys.insert(), [{"id": i, "key": "old"} for i in [1, 2, 3]]
                )
                connection.execute(
                    owners.insert(),
                    [{"id": 1, "name": "z"}, {"id": 2, "name": "a"}],
                )
                assert list(
                    connection.execute(
                        query.enrich_stmt(select(keys.c.id))
                    ).scalars()
                ) == ([1, 2] if descending else [2, 1])
                connection.execute(
                    query.enrich_stmt(update(keys).values(key="new"))
                )
                assert (
                    list(connection.execute(select(keys.c.key)).scalars())
                    == ["new"] * 3
                )
                connection.execute(query.enrich_stmt(delete(keys)))
                assert (
                    list(connection.execute(select(keys.c.id)).scalars()) == []
                )
        finally:
            engine.dispose()

    def test_base_model_query_applies_only_to_subtypes(self):
        class Parent(BaseModel):
            id: int

        class Child(Parent):
            pass

        table = Table(
            "items", MetaData(), Column("id", Integer, primary_key=True)
        )
        mapper = DefaultDomainDataMapper(Child, table)
        query = mapper.to_query(
            QuerySpec(
                where=FieldFilter(Parent, "id", Operator.EQ, 2),
                order_by=(OrderBy(Parent, "id"),),
            )
        )
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                table.create(connection)
                connection.execute(table.insert(), [{"id": 1}, {"id": 2}])
                assert list(
                    connection.execute(
                        query.enrich_stmt(select(table.c.id))
                    ).scalars()
                ) == [2]
        finally:
            engine.dispose()

        with pytest.raises(UnsupportedFilterError):
            DefaultDomainDataMapper(Parent, table).to_query(
                QuerySpec(where=FieldFilter(Child, "id", Operator.EQ, 2))
            )

    @pytest.mark.parametrize("descending", [False, True])
    def test_custom_ordering_preserves_priorities_and_direction(
        self, descending
    ):
        table = Table(
            "keys",
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("key", String),
        )

        @dataclass(frozen=True)
        class PriorityOrder(CustomOrderBy):
            model = SshKey
            names: tuple[str, ...]

        class PriorityMapper(DefaultDomainDataMapper):
            def custom_order_by_clause(self, order):
                from maasservicelayer.db.filters import OrderByClause

                return OrderByClause(
                    case(
                        {
                            name: index
                            for index, name in enumerate(order.names)
                        },
                        value=table.c.key,
                        else_=len(order.names),
                    )
                )

        order = PriorityOrder(("b", "a"))
        order = (
            OrderByFactory.desc(order)
            if descending
            else OrderByFactory.asc(order)
        )
        query = PriorityMapper(SshKey, table).to_query(
            QuerySpec(order_by=(order,))
        )
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                table.create(connection)
                connection.execute(
                    table.insert(),
                    [
                        {"id": 1, "key": "a"},
                        {"id": 2, "key": "b"},
                        {"id": 3, "key": "c"},
                    ],
                )
                assert list(
                    connection.execute(
                        query.enrich_stmt(select(table.c.key))
                    ).scalars()
                ) == (["c", "a", "b"] if descending else ["b", "a", "c"])
        finally:
            engine.dispose()


class TestDomainDataMapperHydration:
    @pytest.mark.parametrize("projected", [False, True])
    def test_storage_rename_round_trips_without_mutating_rows(self, projected):
        class Record(BaseModel):
            id: int
            name: str

        class Builder(ResourceBuilder):
            name: str

        table = Table(
            "records",
            MetaData(),
            Column("id", Integer, primary_key=True),
            Column("stored_name", String),
        )

        class Mapper(DefaultDomainDataMapper[Record]):
            def field_mappings(self):
                return {"name": ColumnMapping(table.c.stored_name)}

        mapper = Mapper(Record, table)
        resource = mapper.build_resource(Builder(name="alpha"))
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                table.create(connection)
                connection.execute(table.insert(), {"id": 1, **resource})
                statement = (
                    select(table.c.id, table.c.stored_name.label("name"))
                    if projected
                    else mapper.select_statement()
                )
                query = mapper.to_query(
                    QuerySpec(
                        where=FieldFilter(Record, "name", Operator.EQ, "alpha")
                    )
                )
                row = connection.execute(query.enrich_stmt(statement)).one()
                values = dict(row._mapping)
                assert mapper.to_domain(values) == Record(id=1, name="alpha")
                assert values == dict(row._mapping)
        finally:
            engine.dispose()

    @pytest.mark.parametrize("related", [False, True])
    def test_computed_and_related_fields_are_not_implicitly_writable(
        self, related
    ):
        class Record(BaseModel):
            name: str

        class Builder(ResourceBuilder):
            name: str

        metadata = MetaData()
        table = Table("records", metadata, Column("name", String))
        other = Table("other", metadata, Column("name", String))

        class Mapper(DefaultDomainDataMapper[Record]):
            def field_mappings(self):
                return {
                    "name": ColumnMapping(
                        other.c.name if related else func.upper(table.c.name)
                    )
                }

        with pytest.raises(ValueError):
            Mapper(Record, table).build_resource(Builder(name="alpha"))

    def test_query_model_is_distinct_from_hydrated_projection(self):
        class Source(BaseModel):
            id: int

        class Projection(BaseModel):
            id: int

        table = Table("records", MetaData(), Column("id", Integer))
        mapper = DefaultDomainDataMapper(Projection, table, query_model=Source)
        query = mapper.to_query(
            QuerySpec(where=FieldFilter(Source, "id", Operator.EQ, 1))
        )
        engine = create_engine("sqlite://")
        try:
            with engine.begin() as connection:
                table.create(connection)
                connection.execute(table.insert(), [{"id": 1}, {"id": 2}])
                rows = connection.execute(
                    query.enrich_stmt(mapper.select_statement())
                ).all()
                assert [mapper.to_domain(row._mapping) for row in rows] == [
                    Projection(id=1)
                ]
        finally:
            engine.dispose()
        with pytest.raises(UnsupportedFilterError):
            mapper.to_query(
                QuerySpec(where=FieldFilter(Projection, "id", Operator.EQ, 1))
            )
