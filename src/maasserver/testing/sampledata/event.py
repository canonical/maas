from datetime import datetime
from itertools import cycle
from typing import Iterable

from maasserver.models import Event, EventType, Machine
from maasserver.models.eventtype import LOGGING_LEVELS

from .common import make_name, range_one


def make_event_types(count: int):
    levels = cycle(LOGGING_LEVELS)
    return [
        EventType.objects.create(
            name=f"event{n:02}", description=f"Event {n}", level=next(levels)
        )
        for n in range_one(count)
    ]


def make_events(
    counts: Iterable[int],
    event_types: Iterable[EventType],
    machines: Iterable[Machine],
):
    event_types = cycle(event_types)
    now = datetime.utcnow()
    for machine in machines:
        Event.objects.bulk_create(
            Event(
                type=next(event_types),
                node=machine,
                action=make_name(),
                description=make_name(),
                created=now,
                updated=now,
            )
            for _ in range(next(counts))
        )
