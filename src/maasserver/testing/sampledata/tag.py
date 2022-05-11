from datetime import datetime
from typing import List

from maasserver.models import Tag

from .common import range_one


def make_tags(count: int, prefix: str) -> List[Tag]:
    now = datetime.utcnow()
    return Tag.objects.bulk_create(
        Tag(
            name=f"{prefix}{n:03}",
            created=now,
            updated=now,
        )
        for n in range_one(count)
    )
