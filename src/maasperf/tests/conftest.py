# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pytest import fixture

from maasserver.models.user import get_auth_tokens
from maasserver.testing.factory import factory as maasserver_factory
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maastesting.perftest import perf
from maastesting.pytest import configure_seeds, random_seed

__all__ = [
    "admin_api_client",
    "api_client",
    "configure_seeds",
    "django_db_setup",
    "factory",
    "maas_user",
    "perf",
    "random_seed",
]


# override pytest-django's db setup
@fixture(scope="session")
def django_db_setup():
    pass


@fixture(scope="session")
def factory():
    return maasserver_factory


@fixture()
def admin(factory):
    return factory.make_admin()


@fixture()
def maas_user(factory):
    return factory.make_User()


@fixture()
def api_client(maas_user):
    return MAASSensibleOAuthClient(
        user=maas_user, token=get_auth_tokens(maas_user)[0]
    )


@fixture()
def admin_api_client(admin):
    return MAASSensibleOAuthClient(user=admin, token=get_auth_tokens(admin)[0])
