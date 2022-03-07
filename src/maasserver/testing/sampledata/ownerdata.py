from typing import List

from maasserver.enum import NODE_STATUS
from maasserver.models import Machine, OwnerData

from .common import make_name, range_one


def make_ownerdata(count: int, prefix: str, machines: List[Machine]):
    for machine in machines:
        if machine.status != NODE_STATUS.DEPLOYED:
            continue
        OwnerData.objects.bulk_create(
            OwnerData(key=f"{prefix}{n:03}", value=make_name(), node=machine)
            for n in range_one(count)
        )
