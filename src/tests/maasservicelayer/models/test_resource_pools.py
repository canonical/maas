#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.models.resource_pools import ResourcePool


class TestResourcePool:
    @pytest.mark.parametrize(
        "id, is_default", [(-1, False), (0, True), (1, False)]
    )
    def test_is_default(self, id: int, is_default: bool):
        r = ResourcePool(id=id, name="", description="")
        assert r.is_default() is is_default
