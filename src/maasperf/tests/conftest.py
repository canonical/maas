# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pytest import fixture

__all__ = [
    "admin_api_client",
    "api_client",
    "django_db_setup",
    "factory",
    "maas_user",
]


pytest_plugins = "maastesting.pytest.perftest,maastesting.pytest.seeds"


# override pytest-django's db setup
@fixture(scope="session")
def django_db_setup():
    pass


@fixture(scope="session")
def factory():
    # Local imports from maasserver so that pytest --help works
    from maasserver.testing.factory import factory as maasserver_factory

    return maasserver_factory


@fixture()
def admin(factory):
    return factory.make_admin()


@fixture()
def maas_user(factory):
    return factory.make_User()


@fixture()
def api_client(maas_user):
    # Local imports from maasserver so that pytest --help works
    from maasserver.models.user import get_auth_tokens
    from maasserver.testing.testclient import MAASSensibleOAuthClient

    return MAASSensibleOAuthClient(
        user=maas_user, token=get_auth_tokens(maas_user)[0]
    )


@fixture()
def admin_api_client(admin):
    # Local imports from maasserver so that pytest --help works
    from maasserver.models.user import get_auth_tokens
    from maasserver.testing.testclient import MAASSensibleOAuthClient

    return MAASSensibleOAuthClient(user=admin, token=get_auth_tokens(admin)[0])
