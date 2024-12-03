#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.events import EventsRepository
from maasservicelayer.models.events import Event
from maasservicelayer.services._base import BaseService


class EventsService(BaseService[Event, EventsRepository]):
    def __init__(
        self,
        context: Context,
        events_repository: EventsRepository,
    ):
        super().__init__(context, events_repository)
