# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.msm`"""

from datetime import datetime, timezone

import pytest

from maascommon.enums.msm import MSMStatusEnum
from maasserver.testing.factory import factory
from maasserver.websockets.handlers import msm
from maasservicelayer.services.msm import MSMService, MSMStatus


@pytest.mark.allow_transactions
@pytest.mark.usefixtures("maasdb")
class TestMSMHandler:
    def test_status_not_connected(self, mocker):
        owner, session = factory.make_User_with_session()
        mocker.patch.object(MSMService, "get_status", return_value=None)
        handler = msm.MAASSiteManagerHandler(owner, {}, None)
        result = handler.status({})
        assert result["sm_url"] is None
        assert result["start_time"] is None
        assert result["running"] == MSMStatusEnum.NOT_CONNECTED

    def test_status_waiting_for_approval(self, mocker):
        owner, session = factory.make_User_with_session()
        expected_started = datetime.now(timezone.utc).strftime(
            "%a %d %b %Y, %I:%M%p"
        )
        expected_url = "http://test-maas"
        mocker.patch.object(
            MSMService,
            "get_status",
            return_value=MSMStatus(
                sm_url=expected_url,
                running=MSMStatusEnum.PENDING,
                start_time=expected_started,
            ),
        )
        handler = msm.MAASSiteManagerHandler(owner, {}, None)
        result = handler.status({})
        assert result["sm_url"] == expected_url
        assert result["start_time"] == expected_started
        assert result["running"] == MSMStatusEnum.PENDING

    def test_status_approved(self, mocker):
        owner, session = factory.make_User_with_session()
        expected_started = datetime.now(timezone.utc).strftime(
            "%a %d %b %Y, %I:%M%p"
        )
        expected_url = "http://test-maas"
        mocker.patch.object(
            MSMService,
            "get_status",
            return_value=MSMStatus(
                sm_url=expected_url,
                running=MSMStatusEnum.CONNECTED,
                start_time=expected_started,
            ),
        )
        handler = msm.MAASSiteManagerHandler(owner, {}, None)
        result = handler.status({})
        assert result["sm_url"] == expected_url
        assert result["start_time"] == expected_started
        assert result["running"] == MSMStatusEnum.CONNECTED
