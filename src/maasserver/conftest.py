# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

from pytest import fixture

from maasserver.testing.factory import factory as maasserver_factory


@fixture(scope="session")
def factory():
    return maasserver_factory


@fixture(autouse=True)
def setup_testenv(monkeypatch):
    curdir = os.getcwd()
    monkeypatch.setenv("MAAS_ROOT", os.path.join(curdir, ".run"))
    monkeypatch.setenv("MAAS_DATA", os.path.join(curdir, ".run/maas"))
    yield
