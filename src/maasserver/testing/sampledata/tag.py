from maasserver.models import Tag

from .common import range_one


def make_tags(count: int, prefix: str):
    return [
        Tag.objects.create(name=f"{prefix}{n:03}") for n in range_one(count)
    ]
