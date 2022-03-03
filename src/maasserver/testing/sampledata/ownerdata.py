from typing import List

from maasserver.enum import NODE_STATUS
from maasserver.models import Machine, OwnerData

from .common import make_name, range_one


def make_ownerdata(count: int, prefix: str, machines: List[Machine]):
    ownerdata = []
    for machine in machines:
        if machine.status != NODE_STATUS.DEPLOYED:
            continue
        for n in range_one(count):
            ownerdata.append(
                OwnerData(
                    key=f"{prefix}{n:03}", value=make_name(), node=machine
                )
            )

    OwnerData.objects.bulk_create(ownerdata)
