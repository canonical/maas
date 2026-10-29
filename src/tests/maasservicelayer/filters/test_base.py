#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.filters.base import FieldFilter, Operator
from maasservicelayer.filters.query import OrderBy
from maasservicelayer.models.sshkeys import SshKey


class TestFieldFilter:
    def test_rejects_unknown_field(self) -> None:
        with pytest.raises(ValueError):
            FieldFilter(SshKey, "username", Operator.EQ, "admin")


class TestDomainQuery:
    def test_order_rejects_unknown_field(self):
        with pytest.raises(ValueError):
            OrderBy(SshKey, "username")
