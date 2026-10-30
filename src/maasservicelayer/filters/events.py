#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Iterable
from dataclasses import dataclass

from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.events import Event, EventType


@dataclass(frozen=True)
class EventsOfNodes(CustomFilter):
    """Events of the nodes with the given system ids, deleted ones included.

    Matches the system id stored on the event or the one of its linked node,
    so it is not a plain filter on `Event.node_system_id`.
    """

    model = Event
    system_ids: tuple[str, ...]


class EventFilters(FilterFactory):
    model = Event

    @classmethod
    def with_system_ids(cls, system_ids: Iterable[str]) -> EventsOfNodes:
        return EventsOfNodes(tuple(system_ids))


class EventTypeFilters(FilterFactory):
    model = EventType

    @classmethod
    def with_name(cls, name: str) -> FieldFilter:
        return cls._equals("name", name)
