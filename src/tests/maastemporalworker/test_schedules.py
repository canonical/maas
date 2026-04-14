# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from temporalio.client import Client, ScheduleListDescription

from maascommon.workflows.bootresource import MASTER_IMAGE_SYNC_WORKFLOW_NAME
from maastemporalworker.schedules import (
    _master_image_sync_updater,
    pause_or_unpause_master_image_sync_schedule,
    SCHEDULES,
    setup_schedules,
    update_master_image_sync_schedule_interval,
    update_schedule,
)
from tests.fixtures import AsyncIteratorMock


@pytest.fixture
def mock_client():
    client = Mock(Client)
    return client


@pytest.mark.asyncio
class TestSetupSchedules:
    def mock_schedule_info(self, schedule_id: str):
        info = Mock(ScheduleListDescription)
        info.id = schedule_id
        return info

    async def test_no_registered_schedules(self, mock_client: Mock):
        mock_client.list_schedules.return_value = AsyncIteratorMock([])

        await setup_schedules(mock_client)

        assert mock_client.create_schedule.call_count == len(SCHEDULES)
        for schedule_id in SCHEDULES:
            mock_client.create_schedule.assert_any_call(
                schedule_id, SCHEDULES[schedule_id]
            )

        mock_client.get_schedule_handle.assert_not_called()

    async def test_deletes_unregistered_schedules(self, mock_client: Mock):
        obsolete_schedule_id = "obsolete_schedule"
        registered = [
            self.mock_schedule_info(obsolete_schedule_id),
        ]
        mock_client.list_schedules.return_value = AsyncIteratorMock(registered)

        mock_handle = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle

        await setup_schedules(mock_client)

        mock_client.get_schedule_handle.assert_called_once_with(
            obsolete_schedule_id
        )
        mock_handle.delete.assert_called_once()

    async def test_creates_new_schedules(self, mock_client: Mock):
        mock_client.list_schedules.return_value = AsyncIteratorMock([])

        await setup_schedules(mock_client)

        assert mock_client.create_schedule.call_count == len(SCHEDULES)
        for schedule_id, schedule_def in SCHEDULES.items():
            mock_client.create_schedule.assert_any_call(
                schedule_id, schedule_def
            )

    async def test_updates_existing_schedules(self, mock_client: Mock):
        registered = [
            self.mock_schedule_info(schedule_id)
            for schedule_id in SCHEDULES.keys()
        ]
        mock_client.list_schedules.return_value = AsyncIteratorMock(registered)

        mock_handle = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle

        await setup_schedules(mock_client)

        mock_client.create_schedule.assert_not_called()

        schedules = set(SCHEDULES.keys())
        # The master image sync must be updated separately
        schedules.discard(MASTER_IMAGE_SYNC_WORKFLOW_NAME)

        for schedule_id in schedules:
            mock_client.get_schedule_handle.assert_any_call(schedule_id)

        assert mock_handle.update.call_count == len(SCHEDULES) - 1
        mock_handle.update.assert_called_with(update_schedule)


@pytest.mark.asyncio
class TestUpdateMasterImageSyncSchedule:
    async def test_updates_only_master_image_sync_schedule(
        self, mock_client: Mock
    ):
        mock_handle = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle

        await update_master_image_sync_schedule_interval(mock_client, 30)

        mock_client.get_schedule_handle.assert_called_once_with(
            MASTER_IMAGE_SYNC_WORKFLOW_NAME
        )
        mock_handle.update.assert_called_once()

    async def test_updates_sync_interval(self):
        mock_input = Mock()
        mock_input.description.schedule.state = Mock()

        result = await _master_image_sync_updater(100)(mock_input)

        assert result.schedule.spec.intervals[0].every == timedelta(
            minutes=100
        )

    async def test_preserves_current_state(self):
        mock_state = Mock()
        mock_state.paused = False
        mock_input = Mock()
        mock_input.description.schedule.state = mock_state

        result = await _master_image_sync_updater(30)(mock_input)

        assert result.schedule.state is mock_state
        assert result.schedule.state.paused is False

    async def test_state_changes_based_on_config(self):
        mock_state = Mock()
        mock_state.paused = True
        mock_input = Mock()
        mock_input.description.schedule.state = mock_state

        result = await _master_image_sync_updater(
            sync_interval_minutes=30, auto_import_enabled_config=True
        )(mock_input)

        assert result.schedule.state is mock_state
        assert result.schedule.state.paused is False


@pytest.mark.asyncio
class TestPauseUnpauseMasterImageSyncSchedule:
    @pytest.mark.parametrize("auto_import_enabled", [True, False])
    async def test_calls_the_right_method(
        self, mock_client: Client, auto_import_enabled: bool
    ):
        mock_handle = AsyncMock()
        mock_client.get_schedule_handle.return_value = mock_handle

        await pause_or_unpause_master_image_sync_schedule(
            mock_client, auto_import_enabled
        )
        mock_client.get_schedule_handle.assert_called_once_with(
            MASTER_IMAGE_SYNC_WORKFLOW_NAME
        )

        if auto_import_enabled:
            mock_handle.unpause.assert_called_once()
        else:
            mock_handle.pause.assert_called_once()
