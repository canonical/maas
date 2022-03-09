# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pytest import fixture


@fixture(scope="session")
def django_db_setup():
    pass
