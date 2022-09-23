# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maastesting.factory import factory as maastesting_factory


@pytest.fixture(scope="session")
def factory():
    return maastesting_factory
