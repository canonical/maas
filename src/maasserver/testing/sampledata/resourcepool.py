# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasserver.models import ResourcePool


def make_resourcepools(num: int):
    return [
        ResourcePool.objects.create(name=f"ResourcePool-{i}")
        for i in range(num)
    ]
