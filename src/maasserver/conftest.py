# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pytest import fixture

from maasserver.testing.factory import factory as maasserver_factory


@fixture(scope="session")
def factory():
    return maasserver_factory
