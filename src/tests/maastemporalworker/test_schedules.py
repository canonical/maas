# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from temporalio.client import Client, ScheduleListDescription

from maastemporalworker.schedules import (
    SCHEDULES,
    setup_schedules,
    update_schedule,
)
from tests.fixtures import AsyncIteratorMock


@pytest.mark.asyncio
class TestSetupSchedules:
    @pytest.fixture
    def mock_client(self):
        client = Mock(Client)
        return client

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

        for schedule_id in SCHEDULES.keys():
            mock_client.get_schedule_handle.assert_any_call(schedule_id)

        assert mock_handle.update.call_count == len(SCHEDULES)
        mock_handle.update.assert_called_with(update_schedule)
