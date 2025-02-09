# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.handlers.msm`"""

from datetime import datetime, timezone

import pytest

from maasserver.enum import MSM_STATUS
from maasserver.testing.factory import factory
from maasserver.websockets.handlers import msm


@pytest.mark.allow_transactions
@pytest.mark.usefixtures("maasdb")
class TestMSMHandler:
    def test_status_not_connected(self, mocker):
        owner, session = factory.make_User_with_session()
        mocker.patch.object(msm, "msm_status", return_value={})
        handler = msm.MAASSiteManagerHandler(
            owner, {}, None, session_id=session.session_key
        )
        result = handler.status({})
        assert result["sm-url"] is None
        assert result["start-time"] is None
        assert result["running"] == MSM_STATUS.NOT_CONNECTED

    def test_status_waiting_for_approval(self, mocker):
        owner, session = factory.make_User_with_session()
        expected_started = datetime.now(timezone.utc).strftime(
            "%a %d %b %Y, %I:%M%p"
        )
        expected_url = "http://test-maas"
        mocker.patch.object(
            msm,
            "msm_status",
            return_value={
                "sm-url": expected_url,
                "running": MSM_STATUS.PENDING,
                "start-time": expected_started,
            },
        )
        handler = msm.MAASSiteManagerHandler(
            owner, {}, None, session_id=session.session_key
        )
        result = handler.status({})
        assert result["sm-url"] == expected_url
        assert result["start-time"] == expected_started
        assert result["running"] == MSM_STATUS.PENDING

    def test_status_approved(self, mocker):
        owner, session = factory.make_User_with_session()
        expected_started = datetime.now(timezone.utc).strftime(
            "%a %d %b %Y, %I:%M%p"
        )
        expected_url = "http://test-maas"
        mocker.patch.object(
            msm,
            "msm_status",
            return_value={
                "sm-url": expected_url,
                "running": MSM_STATUS.CONNECTED,
                "start-time": expected_started,
            },
        )
        handler = msm.MAASSiteManagerHandler(
            owner, {}, None, session_id=session.session_key
        )
        result = handler.status({})
        assert result["sm-url"] == expected_url
        assert result["start-time"] == expected_started
        assert result["running"] == MSM_STATUS.CONNECTED
