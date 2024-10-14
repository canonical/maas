from typing import List

from django.utils import timezone

from maasserver.models import Tag

from .common import range_one


def make_tags(count: int, prefix: str) -> List[Tag]:
    tags = []
    for n in range_one(count):
        now = timezone.now()
        tags.append(
            Tag(
                name=f"{prefix}{n:03}",
                created=now,
                updated=now,
            )
        )
    return Tag.objects.bulk_create(tags)
