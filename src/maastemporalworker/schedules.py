# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from typing import Final

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)

from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
    MASTER_IMAGE_SYNC_WORKFLOW_NAME,
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
    ),
    MASTER_IMAGE_SYNC_WORKFLOW_NAME: Schedule(
        action=ScheduleActionStartWorkflow(
            MASTER_IMAGE_SYNC_WORKFLOW_NAME,
            id=MASTER_IMAGE_SYNC_WORKFLOW_NAME,
            task_queue=REGION_TASK_QUEUE,
        ),
        spec=ScheduleSpec(
            # Will be updated at startup with the value from the db
            intervals=[ScheduleIntervalSpec(every=timedelta(minutes=60))]
        ),
        # Will be updated at startup with the value from the db
        state=ScheduleState(paused=True),
        policy=SchedulePolicy(overlap=ScheduleOverlapPolicy.CANCEL_OTHER),
    ),
}


def _master_image_sync_updater(
    sync_interval_minutes: int, auto_import_enabled_config: bool | None = None
):
    async def do_update(input: ScheduleUpdateInput) -> ScheduleUpdate:
        master_image_sync_schedule = SCHEDULES[MASTER_IMAGE_SYNC_WORKFLOW_NAME]
        master_image_sync_schedule.spec = ScheduleSpec(
            intervals=[
                ScheduleIntervalSpec(
                    every=timedelta(minutes=sync_interval_minutes)
                )
            ]
        )
        schedule_description = input.description
        # When updating a schedule ALL the options must be specified again.
        # Here we save the current state in order to avoid un-pausing the schedule
        # when only changing the sync interval
        current_state = schedule_description.schedule.state
        if auto_import_enabled_config is not None:
            # On startup, set the state based on the config
            current_state.paused = not auto_import_enabled_config
        schedule_description.schedule = master_image_sync_schedule
        schedule_description.schedule.state = current_state
        return ScheduleUpdate(schedule=schedule_description.schedule)

    return do_update


async def update_master_image_sync_schedule(
    client: Client,
    sync_interval_minutes_config: int,
    auto_import_enabled_config: bool | None = None,
):
    handle = client.get_schedule_handle(MASTER_IMAGE_SYNC_WORKFLOW_NAME)
    await handle.update(
        _master_image_sync_updater(
            sync_interval_minutes_config, auto_import_enabled_config
        )
    )


async def pause_or_unpause_master_image_sync_schedule(
    client: Client, auto_import_enabled_config: bool | None
):
    handle = client.get_schedule_handle(MASTER_IMAGE_SYNC_WORKFLOW_NAME)
    if auto_import_enabled_config:
        await handle.unpause()
    else:
        await handle.pause()


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
        await client.create_schedule(
            id=schedule, schedule=SCHEDULES[schedule], trigger_immediately=True
        )

    schedules_to_update = registered_schedules - schedules_to_delete
    for schedule in schedules_to_update:
        handle = client.get_schedule_handle(schedule)
        # Handled with `update_master_image_sync_schedule` above
        if schedule != MASTER_IMAGE_SYNC_WORKFLOW_NAME:
            await handle.update(update_schedule)

        await handle.trigger()
