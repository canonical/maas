# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Final

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
)
from maastemporalworker.worker import REGION_TASK_QUEUE

SCHEDULES: Final[dict[str, Schedule]] = {
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME: Schedule(
        action=ScheduleActionStartWorkflow(
            FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
            id=FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
            task_queue=REGION_TASK_QUEUE,
        ),
        spec=ScheduleSpec(
            intervals=[ScheduleIntervalSpec(every=timedelta(minutes=10))]
        ),
    )
}


async def update_schedule(input: ScheduleUpdateInput) -> ScheduleUpdate:
    schedule_description = input.description
    schedule_definition = SCHEDULES.get(schedule_description.id)
    assert schedule_definition is not None, (
        "Tried to update a not defined Temporal schedule."
    )

    # Update the schedule with the last definition
    schedule_description.schedule = schedule_definition

    return ScheduleUpdate(schedule=input.description.schedule)


async def setup_schedules(client: Client):
    """Setup Temporal schedules.

    The schedules that must be registered in Temporal are defined in the `SCHEDULE`
    variable. This function will:
        - delete all the schedules that are registered but not defined (i.e. the
        ones we have defined in the past, but we later removed)
        - register all the new schedules (never registered)
        - update the already registered schedules
    """
    expected_schedules = set(SCHEDULES.keys())
    registered_schedules: set[str] = set()
    async for schedule in await client.list_schedules():
        registered_schedules.add(schedule.id)

    schedules_to_delete = registered_schedules - expected_schedules
    for schedule in schedules_to_delete:
        handle = client.get_schedule_handle(schedule)
        await handle.delete()

    schedules_to_add = expected_schedules - registered_schedules
    for schedule in schedules_to_add:
        await client.create_schedule(schedule, SCHEDULES[schedule])

    schedules_to_update = registered_schedules - schedules_to_delete
    for schedule in schedules_to_update:
        handle = client.get_schedule_handle(schedule)
        await handle.update(update_schedule)
