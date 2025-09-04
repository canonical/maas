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

## SQL Query Specification

While it's true that we don't use an ORM, we still want to make our life easier when writing queries.
That's why we implemented the class `QuerySpec` (see `src/maasservicelayer/db/filters.py`).
This is accepted by different methods in the repository classes and its main purpose is to apply some filtering on the query being made.
As of now, it implements "where" and "order by" clauses.

### What is a `Clause`?

A `Clause` is a simple representation of a database filter.
It's composed by a condition, a SQLAlchemy `ColumnElement` (like `eq(YourTable.c.your_column, "value")`) and a list of joins, a SQLAlchemy `Join`, so you can make it as complicated as you want.

### How do you specify a `Clause`?

The gold standard way to specify a `Clause` is by implementing a `ClauseFactory`.
Usually you'll end up with re-using most of the filters that you write, so a `ClauseFactory` serves this purpose.
It's strictly tied to an entity, and you must define it in the same module of the repository for that entity.
It defines method in the form of `with_<column>` where "column" is the column name of the table you're filtering on.

It also provides some utilities to put a list of `Clause`s in AND or OR, and one to negate a `Clause`.


## Builders and Domain Data Mappers

When creating or updating an entity, we heavily use builders.
Builders are Pydantic models generated starting from our entity models through the `make generate-builders` command (see `utilities/generate_builders.py`).
These models are a 1:1 representation of our standard models but with all the fields being `UNSET` (`UNSET` is just a sentinel and it just means that the field.. is not set!).
So when we have to create a model, we pass the builder to the repository method.
What happens next is that the builder will be processed by a `DomainDataMapper`:

- It will iterate over the fields that aren't `UNSET`
- It will return a `CreateOrUpdateResource` (basically a `dict`) which will map every field to the corresponding column in the db

If the domain model doesn't differ from the data model, it will use the `DefaultDomainDataMapper` which maps the builder to the table in a 1:1 representation.
Otherwise, you can specify your own custom mapper which fits your needs.
See `src/maasservicelayer/db/mappers/event.py` for an example of a custom mapper.

Having all the fields that default to `UNSET`, enable us to use the same builders both for updating and creating entities in the db.

Plus, having it auto-generated makes it possible to have them defined as Pydantic models with correct types and validation.

## Testing

### Testing Repository

When testing repositories, we unit test them using a real database.
To access it, you can just require the fixture `db_connection`.

To be able to test common methods easier, some base test classes are provided in `src/tests/maasservicelayer/db/repositories/base.py`, which are  `ReadOnlyRepositoryCommonTests` and `RepositoryCommonTests`.

You can just inherit from them and provide the necessary fixtures to have all the tests already in place.
If for some reason a test doesn't apply to your repository, mark it with `@pytest.mark.skip(reason="your valid reason")`.

### Testing Clause Factories

While testing a `ClauseFactory` the main thing we want to make sure is that the conditions we wrote, correctly maps to the db columns we have specified.
In order to do so we can compile the condition and the joins and compare the result with our expected values.
See for example `src/tests/maasservicelayer/db/repositories/test_ipranges.py`.

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
Currently, the v3 API supports three methods of authentication:

- using a Bearer token
- using a Django sessionid
- using a Macaroon

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

### Macaroons

MAAS supports Role Based Access Control through Candid and Canonical's RBAC.
To support it we have to deal with macaroons.
See `MacaroonAuthenticationProvider` for more details.

## Authorization

Authorization checks are performed through the `check_permissions` function.

This is used as a dependency on each handler, which defines the user role and, optionally, the RBAC permissions, required for accessing the endpoint.

Those requirements are checked against the `AuthenticatedUser`.
If RBAC is not enabled, the only check made is that the user role matches the required user role.
Otherwise, all the permissions the user has are retrieved from RBAC and checked if they meets the requirements.

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
- `mocked_api_client_user_rbac`: client with a user authenticated through RBAC
- `mocked_api_client_admin_rbac`: client with an admin authenticated through RBAC
