# Overview of the v3 API

The v3 API is the next iteration of the MAAS API.
Its main goal is to fully replace the Django + Twisted application with a [SQLAlchemy](https://www.sqlalchemy.org/) + [FastAPI](https://fastapi.tiangolo.com/) one.
It follows a three-tier architecture, defined by the following layers:

- the repository layer: Data Layer
- the service layer: Application Layer
- the API layer: Presentation Layer

# Repository Layer

The repository layer acts as the Data Access Layer.
It is responsible for communicating with the database and to map the rows in the db to our [Pydantic](https://docs.pydantic.dev/1.10/) models (defined in `src/maasservicelayer/models`).

It heavily relies on [SQLAlchemy Core](https://docs.sqlalchemy.org/en/14/core/) for executing queries.
We prefer this approach in order to not hide implementation details behind an ORM, so we have full control on the query.

Usually, we have one repository for each entity in our data model (except rare cases such as users, see `src/maasservicelayer/db/repositories/users.py`).
The base classes for repositories are defined in `src/maasservicelayer/db/repositories/base.py`, in particular we have:

- `Repository`: abstract class which provides a method to execute the SQL statement based on the kind of db connection we have. More on this later.
- `ReadOnlyRepository`: defines all the common methods to access the entity. This class exists to deal with db views mainly.
- `BaseRepository`: extends `ReadOnlyRepository` and defines all the common methods to create, delete and update the entity.

Since this is part of the new v3 API, the ultimate objective will be to replace the old Django ORM with this implementation.
In order to do it progressively, we made it possible to access the repository layer in the v2 API (through the service layer).
This caused the following problem: since in the v2 API we are using Django in a synchronous way, we only have access to a db connection through a psycopg synchronous driver.
That means that we cannot use this implementation as is, since it's purely asynchronous.
To deal with this, we created an adapter to use the service layer with a synchronous connection, see `src/maasserver/sqlalchemy.py` for more details.

## Table Definitions

You can find all the definitions of the database tables in `src/maasservicelayer/db/tables.py`.
These have to be in sync with the current database status in order to make the generation of [Alembic](https://alembic.sqlalchemy.org/en/latest/) migrations work.
The Alembic migrations are stored in the `src/maasservicelayer/db/alembic/versions/` directory.

## Domain Query Specification

All repository and service query inputs use `QuerySpec` from `maasservicelayer.filters.query`.
It contains only domain filters and ordering; callers do not construct SQL clauses or refer to table columns.

### SQL compilation

The repository translates incoming queries through its mapper before executing statements.
The resulting `SQLQuerySpec`, `Clause`, and `OrderByClause` in `maasservicelayer.db.filters` are internal SQL representations, not accepted query inputs.

### Domain queries and filters

Domain filters and ordering live in `src/maasservicelayer/filters/`, without SQLAlchemy types or statement-building methods.

- A `FilterFactory` per entity exposes `with_<field>` methods, and `and_filters`, `or_filters` and `not_filter` to combine predicates.
- A `FieldFilter` compares one domain field with a value. The mapper finds the column with the same name, or the one declared in `field_mappings()` when the names differ (see `Event.owner`, stored in `username`).
- A `CustomFilter` covers conditions that are not a comparison on a single field, such as joins on other tables. The entity mapper translates it in `custom_filter_clause()` (see `EventsOfNodes`).
- The domain `QuerySpec` is a frozen value containing `where: Filter | None` and an immutable tuple of ordering values. It cannot contain a SQL `Clause` or `OrderByClause`.
- `OrderBy(Model, "field", descending=False)` checks that the field exists on the domain model. The mapper rejects ordering for another model or an unmapped field, and translates ordering through the same field mappings as filters.
- `CustomOrderBy` covers domain ordering rules, such as boot-resource release priority. The mapper translates these in `custom_order_by_clause()`; `OrderByFactory.asc()` and `.desc()` preserve the ordering rule while changing its direction.
- Ordering joins apply only to SELECT statements. Ordering is omitted from count queries and does not add restrictions to UPDATE or DELETE statements.

For example, ordering events by owner and then newest ID does not expose the `username` storage column:

```python
from maasservicelayer.filters.query import OrderBy, QuerySpec
from maasservicelayer.models.events import Event

query = QuerySpec(
    order_by=(OrderBy(Event, "owner"), OrderBy(Event, "id", descending=True))
)
```

The mapper's `to_query()` compiles domain queries; SQL statement enrichment remains inside `db`.
Repositories accept filters for their model or a genuine domain base class, such as `Node` filters applied to `Machine`; unrelated models are rejected before execution.
Field mappings may translate names or storage representations. For example, file content and node user data compare domain bytes against decoded base64 storage without exposing the encoding to callers.

#### Filter semantics

- An empty `And` matches every resource; an empty `Or` matches none.
- `Not` matches the complement of its operand, including resources whose nullable fields do not match that operand. This also applies to custom filters.
- `EQ None` matches null values. `IN` is equivalent to an `Or` of equality filters: it matches null values when `None` is included, and matches nothing when its collection is empty.
- Every operand is validated, even if another operand already determines the result. Filters for another model, unmapped fields, and unsupported custom filters raise `UnsupportedFilterError` before execution.



## Builders and Domain Data Mappers

Mappers own the translation between storage rows, domain models, and write values. Repositories retain query orchestration, pagination, aggregate queries, and grouping of already-hydrated models.

- `BaseDomainDataMapper[Model].to_domain(row)` hydrates the domain model without mutating its input. Generic repository reads and supported write-returning paths all use it.
- `select_statement()` owns representation-specific SELECTs, aliases, and joins. Repositories add filtering, ordering, and pagination to that statement; count-query behavior remains separate.
- `build_resource(builder)` maps the builder's populated fields to writable storage columns. Builders are generated from domain models by `make generate-builders`; omitted `UNSET` fields remain omitted for partial writes.

`field_mappings()` is shared by filtering, ordering, simple read renames, and write-column selection. A direct column on the mapper's table is writable by default. Computed expressions and related-table columns are not writable unless their `ColumnMapping` explicitly names an own-table `storage_column`.
For example, OpenFGA declares `user -> _user` once; both reads and writes use that metadata.
Nullable relationships must use outer joins so filters and count queries retain domain rows without a related row, such as unassigned machines when filtering on `owner`.

Custom codecs preprocess populated write values before calling `DefaultDomainDataMapper._build_resource()`, and override `to_domain()` for the inverse conversion. File content and node user data declare decoded SQL query expressions plus raw writable text columns; returned storage values are decoded before model construction, exactly once across get/list/upsert/delete paths.

The mapper's hydrated model and query model normally coincide. A read projection can set `query_model` explicitly: the machine-v2 mapper returns a typed `MachineRecord` while accepting filters and ordering on `Node`. Model-identity checks use the query model, not the projection's coincidentally named fields.

Aggregate and related-model results use named typed projection mappers. Existing non-Pydantic dataclasses and network ranges use dedicated typed mapping helpers rather than weakening the Pydantic mapper contract. Internal SQL-only DTOs may stay beside their queries.
Application grouping, permissions, status presentation, and discovered-address enrichment remain outside representation conversion.

## Testing

### Testing Repository

When testing repositories, we unit test them using a real database.
To access it, you can just require the fixture `db_connection`.

To be able to test common methods easier, some base test classes are provided in `src/tests/maasservicelayer/db/repositories/base.py`, which are  `ReadOnlyRepositoryCommonTests` and `RepositoryCommonTests`.

You can just inherit from them and provide the necessary fixtures to have all the tests already in place.
If for some reason a test doesn't apply to your repository, mark it with `@pytest.mark.skip(reason="your valid reason")`.

### Testing Domain Queries

Test filters, ordering, and hydration through repository results, including joins, nullable values, storage conversions, and write scoping.
Mapper edge tests should cover immutable input rows, renamed/projected fields, codecs, and explicit writable-column boundaries. Avoid pinning generated SQL text or repeating simple factory construction.

# Service layer

The service layer is the Business Logic Layer.
Repositories provide basic methods to interact with the db and the service layer defines the business logic through the use of the repository methods.
We can distinguish two kind of services:

- Entity Service
- Feature Service

While there's still no clear distinction between the two now in the code, in the future we might want to introduce substantial differences between them.

## Entity Service

An entity service is strictly tied to... an entity! It extends the `ReadOnlyService` or `BaseService` based on the underlying repository type (e.g. if the repository for that entity is a `ReadOnlyRepository` the service will be a `ReadOnlyService` as well).
Most of the methods it provides are pass-through methods to the repository.
Here is where you write your business logic and where you can interact with other entities: for example this is the place where you implement cascade deletion for entities (remember: **we don't use an ORM, so you have to manage relationships manually!**).

There might be cases where you don't want to provide all the methods that the `BaseService` exposes.
In such scenario, you will have to override the method and raise a `NotImplementedError`. See `src/maasservicelayer/services/sshkeys.py` for an example.

## Feature Service

A feature service can be defined as an aggregation of services that accomplish a specific purpose.
It's not tied to an underlying entity. 
It inherits from the `Service` class.

See `V3DNSResourceRecordSetsService` for an example of a feature service.

## ServiceCache

A `ServiceCache` is not a usual cache as you would think.
It's not meant to be used as a cache for db queries.
It's an utility to be able to re-use objects inside a service.
Think for example of an HTTP client: the best practice is to connect to one client and re-use it throughout the life cycle of the service instead of opening and closing one every time you make a request.
Here comes the `ServiceCache`.

To use it you must define a concrete cache for your service that inherits from `ServiceCache`.
Inside you have to define the attributes that will be cached.
Then, in your service you decorate the method responsible for creating the cached object with `@Service.from_cache_or_execute("attr_name")` where `attr_name` is the same name of the attribute that you defined in your own `ServiceCache`.

You can see an example of this in `src/maasservicelayer/services/external_auth.py`.

Also, the `ServiceCache` provides you a `close` method.
There you can define all the cleanup operations for your cached objects (e.g. closing the client for an HTTP client).
This is called for all the initialized service caches in the teardown of the FastAPI application.

## Using v3 services in maasserver

You can use all the v3 services, by using the `service_layer` object defined in `src/maasserver/sqlalchemy.py`.
In order to achieve this, we re-use the Django connection, **so the same rules that apply to Django ORM in maasserver are applied to the `service_layer`** (e.g. when to use `deferToDatabase`).

## Testing

When unit testing services, we usually mock the underlying repository and don't use a real database. 

As for repositories, services have their base test classes as well (`ReadOnlyServiceCommonTests`, `ServiceCommonTests`).
Follow the same process as for repositories.

# API Layer

The API layer is the Presentation Layer.
It's a FastAPI application that exposes a REST API to interact with MAAS entities.

To be precise, we currently have two different FastAPI applications, the REST API and an internal one that's mainly used by the agent to communicate with MAAS.

## Middlewares

We have different middlewares in place, which are:

- `PrometheusMiddleware` and `DatabaseMetricsMiddleware`: responsible for collecting metrics.
- `V3AuthenticationMiddleware`: manages authentication through different providers, more on this later.
- `ServicesMiddleware`: makes the v3 services available in the request context.
- `TransactionMiddleware`: makes the db connection available in the request context and manages the db transaction. **It opens a transaction for each request and commits that only if there weren't any exception**. Also, it executes the `post_commit` method of the `TemporalService`.
- `ExceptionMiddleware`: catches all the exceptions defined and returns the corresponding response.
- `ContextMiddleware`: add the context to each request.

## Authentication

Among all the middlewares above, this is probably the one that needs more attention.
Currently, the v3 API supports the following methods of authentication:

- using a Bearer token
- using a Django sessionid

After a successful authentication, the logged in user is available in the request context as an `AuthenticatedUser`.

### Bearer Token

This is the new way of authenticating.
When you login you get back a JWT token, to be later used in all the requests.
Currently, it's a short-lived token that lasts only 10 minutes.
Right now, there is no refresh token to be able to extend its lifetime.

The JWT authentication mechanism is built to support different providers.
As of now, only a `LocalAuthenticationProvider` is implemented, but we plan to add different providers when we'll add support for OIDC.

### Django sessionid

Back-compatible authentication mechanism that relies on Django.
Querying the v3 API is possible using the sessionid issued by Django.

## Authorization

Authorization checks are performed through the `check_permissions` function.

This is used as a dependency on each handler, which defines the user role required for accessing the endpoint.

Those requirements are checked against the `AuthenticatedUser`.

## Handlers

To define an handler, you create a class that extends `Handler` (from `src/maasapiserver/common/api/base.py`).
An endpoint is defined as a method of the handler class that you created.
You have to decorate every endpoint method with the `@handler` decorator, through which you can specify different properties, such as the path, methods and permissions needed to access that endpoint.
These properties will be used as keyword arguments to the `router.add_api_route` method, see FastAPI docs for the supported ones.

## Request and Response Models

We define request and response models as Pydantic models.
The main advantages we have are the automatic validation of types and the generation of the OpenAPI specification through FastAPI.

## OpenAPI

The OpenAPI spec is available at `http://<maas-ip>:5240/MAAS/a/openapi.json`.
This is a must for auto-generating clients.

Also you can access the Swagger UI at `http://<maas-ip>:5240/MAAS/a/docs` to directly interact with the v3 API.
Really useful for testing.

## Testing

When testing API endpoints, we usually mock the services.
And here as well we have a common class for all the API handlers `APICommonTests`.
Unlikely the others, this is only responsible for checking endpoint authorization.

To test API endpoints, we have different fixtures that comes in handy:

- `services_mock`: a mock of the entire `V3ServiceCollection` used by the FastAPI app being tested. Use this to mock the results of the services you are interacting with.
- `mocked_api_client`: unauthenticated client for querying the endpoint 
- `mocked_api_client_user`: client with a user authenticated
- `mocked_api_client_admin`: client with an admin authenticated
- `mocked_api_client_session_id`: client with a user authenticated with a sessionid
