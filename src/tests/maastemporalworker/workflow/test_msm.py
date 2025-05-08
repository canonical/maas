# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from dataclasses import replace
from typing import Any
from unittest.mock import Mock, PropertyMock
import uuid

from aiohttp import ClientResponse, ClientSession
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker
import yaml

from maascommon.enums.node import NodeStatus
from maasservicelayer.context import Context
from maasservicelayer.db import Database
from maasservicelayer.models.secrets import MSMConnectorSecret
from maasservicelayer.services import CacheForServices
from maasservicelayer.services.secrets import LocalSecretsStorageService
from maastemporalworker.workflow.msm import (
    MachinesCountByStatus,
    MSM_CHECK_ENROL_ACTIVITY_NAME,
    MSM_DETAIL_EP,
    MSM_ENROL_EP,
    MSM_GET_ENROL_ACTIVITY_NAME,
    MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME,
    MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME,
    MSM_REFRESH_EP,
    MSM_SEND_ENROL_ACTIVITY_NAME,
    MSM_SEND_HEARTBEAT_ACTIVITY_NAME,
    MSM_SET_ENROL_ACTIVITY_NAME,
    MSM_VERIFY_EP,
    MSM_VERIFY_TOKEN_ACTIVITY_NAME,
    MSMConnectorActivity,
    MSMConnectorParam,
    MSMEnrolParam,
    MSMEnrolSiteWorkflow,
    MSMHeartbeatParam,
    MSMHeartbeatWorkflow,
    MSMTokenRefreshParam,
    MSMTokenRefreshWorkflow,
    MSMTokenVerifyParam,
)
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture

_MAAS_SITE_NAME = "maas-site"
_MAAS_URL = "http://maas.local/"
_MSM_BASE_URL = "http://msm.local/ingress"
_MSM_ENROL_URL = f"{_MSM_BASE_URL}{MSM_ENROL_EP}"
_MSM_DETAIL_URL = f"{_MSM_BASE_URL}{MSM_DETAIL_EP}"
_JWT_ENROL = "headers.claims.signature"
_JWT_ACCESS = "headers.new-claims.signature"
_CLUSTER_UUID = "abc-def"
_JWT_ROTATION_INTERVAL = 0
_JWT_REFRESH_URL = f"{_MSM_BASE_URL}{MSM_REFRESH_EP}"
_MSM_VERIFY_URL = f"{_MSM_BASE_URL}{MSM_VERIFY_EP}"


@pytest.fixture
async def msm_act(mocker, db: Database, db_connection: AsyncConnection):
    mock_session = mocker.create_autospec(ClientSession)
    mocker.patch.object(
        MSMConnectorActivity, "_create_session", return_value=mock_session
    )
    services_cache = CacheForServices()
    act = MSMConnectorActivity(db, services_cache, db_connection)
    return act


@pytest.fixture
async def secrets(db: Database, db_connection: AsyncConnection):
    store = LocalSecretsStorageService(Context(connection=db_connection))
    yield store


@pytest.fixture
def enrol_param() -> MSMEnrolParam:
    return MSMEnrolParam(
        site_name=_MAAS_SITE_NAME,
        site_url=_MAAS_URL,
        url=_MSM_BASE_URL,
        jwt=_JWT_ENROL,
        cluster_uuid=_CLUSTER_UUID,
    )


@pytest.fixture
def hb_param() -> MSMHeartbeatParam:
    return MSMHeartbeatParam(
        site_name=_MAAS_SITE_NAME,
        site_url=_MAAS_URL,
        sm_url=_MSM_BASE_URL,
        jwt=_JWT_ACCESS,
        rotation_interval_minutes=_JWT_ROTATION_INTERVAL,
        status=MachinesCountByStatus(
            allocated=1,
            deployed=2,
        ),
    )


@pytest.fixture
def refresh_param() -> MSMTokenRefreshParam:
    return MSMTokenRefreshParam(
        sm_url=_MSM_BASE_URL,
        jwt=_JWT_ACCESS,
        rotation_interval_minutes=_JWT_ROTATION_INTERVAL,
    )


@pytest.fixture
def verify_param() -> MSMTokenVerifyParam:
    return MSMTokenVerifyParam(
        sm_url=_MSM_BASE_URL,
        jwt=_JWT_ACCESS,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("maasdb")
class TestMSMActivities:
    def _mock_post(
        self,
        mocker,
        mocked_session,
        ok: bool,
        status: int,
        reason: str,
        body: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> Mock:
        mock_response = mocker.create_autospec(ClientResponse)
        type(mock_response).ok = PropertyMock(return_value=ok)
        type(mock_response).status = PropertyMock(return_value=status)
        type(mock_response).reason = PropertyMock(return_value=reason)
        if body:
            mock_response.json.return_value = body
        if headers:
            type(mock_response).headers = PropertyMock(return_value=headers)
        mocked_session.post.return_value.__aenter__.return_value = (
            mock_response
        )
        return mock_response

    def _mock_get(
        self, mocker, mocked_session, status: int, body: dict[str, Any] | None
    ) -> Mock:
        mock_response = mocker.create_autospec(ClientResponse)
        type(mock_response).status = PropertyMock(return_value=status)
        mock_response.json.return_value = body
        mocked_session.get.return_value.__aenter__.return_value = mock_response
        return mock_response

    async def test_send_enrol(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        self._mock_post(mocker, mocked_session, True, 202, "")

        env = ActivityEnvironment()
        ok, err = await env.run(msm_act.send_enrol, enrol_param)

        assert ok
        assert err is None
        mocked_session.post.assert_called_once()
        args = mocked_session.post.call_args.args
        kwargs = mocked_session.post.call_args.kwargs
        assert args[0] == _MSM_ENROL_URL
        assert kwargs["headers"]["Authorization"] is not None
        assert kwargs["json"]["name"] == _MAAS_SITE_NAME
        assert kwargs["json"]["url"] == _MAAS_URL
        assert "metadata" not in kwargs["json"]

    async def test_send_enrol_with_meta(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        self._mock_post(mocker, mocked_session, True, 202, "")

        env = ActivityEnvironment()
        meta = yaml.safe_dump(
            {"metadata": {"latitude": 0.0, "longitude": 0.0}}
        )
        param = replace(enrol_param, metainfo=meta)
        ok, err = await env.run(msm_act.send_enrol, param)

        assert ok
        assert err is None
        mocked_session.post.assert_called_once()
        kwargs = mocked_session.post.call_args.kwargs
        assert "metadata" in kwargs["json"]

    async def test_send_enrol_refused(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        self._mock_post(mocker, mocked_session, False, 404, "Some error")

        env = ActivityEnvironment()
        ok, err = await env.run(msm_act.send_enrol, enrol_param)
        assert not ok
        assert err == {"status": 404, "reason": "Some error"}

    async def test_check_enroll_pending(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 204, None)

        env = ActivityEnvironment()
        with pytest.raises(
            ApplicationError, match="waiting for MSM enrolment"
        ):
            await env.run(msm_act.check_enrol, enrol_param)

    async def test_check_enroll_cancel(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 404, None)

        env = ActivityEnvironment()
        (token, refresh_interval) = await env.run(
            msm_act.check_enrol, enrol_param
        )
        assert token is None
        assert refresh_interval == -1

    async def test_check_enroll_cancel_token(
        self, mocker, msm_act, enrol_param
    ):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 401, None)

        env = ActivityEnvironment()
        (token, refresh_interval) = await env.run(
            msm_act.check_enrol, enrol_param
        )
        assert token is None
        assert refresh_interval == -1

    async def test_check_enroll_complete(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        body = {
            "access_token": _JWT_ACCESS,
            "token_type": "bearer",
            "rotation_interval_minutes": _JWT_ROTATION_INTERVAL,
        }
        self._mock_get(mocker, mocked_session, 200, body)

        env = ActivityEnvironment()
        (new_token, rotation_interval) = await env.run(
            msm_act.check_enrol, enrol_param
        )
        assert new_token == _JWT_ACCESS
        assert rotation_interval == _JWT_ROTATION_INTERVAL
        args = mocked_session.get.call_args.args
        kwargs = mocked_session.get.call_args.kwargs
        assert args[0] == _MSM_ENROL_URL
        assert kwargs["headers"]["Authorization"] is not None

    async def test_set_enrol(self, msm_act, secrets):
        param = MSMConnectorParam(
            url=_MSM_BASE_URL,
            jwt=_JWT_ACCESS,
            rotation_interval_minutes=_JWT_ROTATION_INTERVAL,
        )
        env = ActivityEnvironment()
        await env.run(msm_act.set_enrol, param)
        cred = await secrets.get_composite_secret(MSMConnectorSecret())
        assert cred["url"] == _MSM_BASE_URL
        assert cred["jwt"] == _JWT_ACCESS
        assert cred["rotation_interval_minutes"] == _JWT_ROTATION_INTERVAL

    async def test_get_enrol(self, msm_act, secrets):
        await secrets.set_composite_secret(
            MSMConnectorSecret(),
            {
                "url": _MSM_BASE_URL,
                "jwt": _JWT_ACCESS,
                "rotation_interval_minutes": _JWT_ROTATION_INTERVAL,
            },
        )
        env = ActivityEnvironment()
        secrets = await env.run(msm_act.get_enrol)
        assert secrets["url"] == _MSM_BASE_URL
        assert secrets["jwt"] == _JWT_ACCESS
        assert secrets["rotation_interval_minutes"] == _JWT_ROTATION_INTERVAL

    async def test_get_heartbeat_data(self, msm_act, fixture: Fixture):
        for st in [
            NodeStatus.ALLOCATED,
            NodeStatus.DEPLOYED,
            NodeStatus.READY,
            NodeStatus.TESTING,
            NodeStatus.FAILED_COMMISSIONING,
            NodeStatus.FAILED_DEPLOYMENT,
            NodeStatus.FAILED_DISK_ERASING,
            NodeStatus.FAILED_ENTERING_RESCUE_MODE,
            NodeStatus.FAILED_EXITING_RESCUE_MODE,
            NodeStatus.FAILED_RELEASING,
            NodeStatus.FAILED_TESTING,
        ]:
            await create_test_machine_entry(fixture, status=st)
        env = ActivityEnvironment()
        data = await env.run(msm_act.get_heartbeat_data)
        assert data.allocated == 1
        assert data.deployed == 1
        assert data.ready == 1
        assert data.error == 7
        assert data.other == 1

    async def test_get_heartbeat_data_empty(self, msm_act):
        env = ActivityEnvironment()
        data = await env.run(msm_act.get_heartbeat_data)
        assert data.allocated == 0
        assert data.deployed == 0
        assert data.ready == 0
        assert data.error == 0
        assert data.other == 0

    async def test_send_heartbeat(self, mocker, msm_act, hb_param):
        mocked_session = msm_act._session
        self._mock_post(
            mocker,
            mocked_session,
            True,
            200,
            "",
            headers={
                "MSM-Heartbeat-Interval-Seconds": 300,
            },
        )

        env = ActivityEnvironment()
        intval = await env.run(msm_act.send_heartbeat, hb_param)

        assert intval == 300
        mocked_session.post.assert_called_once()
        args = mocked_session.post.call_args.args
        kwargs = mocked_session.post.call_args.kwargs
        assert args[0] == _MSM_DETAIL_URL
        assert kwargs["headers"]["Authorization"] is not None
        assert kwargs["json"]["name"] == _MAAS_SITE_NAME
        assert kwargs["json"]["url"] == _MAAS_URL
        assert "machines_by_status" in kwargs["json"]

    async def test_send_heartbeat_cancel(self, mocker, msm_act, hb_param):
        mocked_session = msm_act._session
        self._mock_post(mocker, mocked_session, True, 401, "")

        env = ActivityEnvironment()
        intval = await env.run(msm_act.send_heartbeat, hb_param)
        assert intval == -1

    async def test_refresh_token(self, mocker, msm_act, hb_param):
        mocked_session = msm_act._session
        self._mock_get(
            mocker,
            mocked_session,
            200,
            {
                "access_token": "test_access_token",
                "rotation_interval_minutes": 1,
            },
        )
        env = ActivityEnvironment()
        (token, interval) = await env.run(msm_act.refresh_token, hb_param)
        mocked_session.get.assert_called_once()
        args = mocked_session.get.call_args.args
        kwargs = mocked_session.get.call_args.kwargs
        assert args[0] == _JWT_REFRESH_URL
        assert _JWT_ACCESS in kwargs["headers"]["Authorization"]
        assert token == "test_access_token"
        assert interval == 1

    async def test_refresh_token_cancel(self, mocker, msm_act, hb_param):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 401, None)
        env = ActivityEnvironment()
        (token, interval) = await env.run(msm_act.refresh_token, hb_param)
        assert token is None
        assert interval == -1

    async def test_refresh_token_unknown_http_return(
        self, mocker, msm_act, hb_param
    ):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 500, None)
        env = ActivityEnvironment()
        with pytest.raises(ApplicationError):
            await env.run(msm_act.refresh_token, hb_param)

    async def test_verify_token(self, mocker, msm_act, verify_param):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 200, None)
        env = ActivityEnvironment()
        ret = await env.run(msm_act.verify_token, verify_param)
        mocked_session.get.assert_called_once()
        args = mocked_session.get.call_args.args
        kwargs = mocked_session.get.call_args.kwargs
        assert ret
        assert args[0] == _MSM_VERIFY_URL
        assert _JWT_ACCESS in kwargs["headers"]["Authorization"]

    async def test_verify_token_unauthorized(
        self, mocker, msm_act, verify_param
    ):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 401, None)
        env = ActivityEnvironment()
        ret = await env.run(msm_act.verify_token, verify_param)
        assert not ret

    async def test_verify_token_not_found(self, mocker, msm_act, verify_param):
        mocked_session = msm_act._session
        self._mock_get(mocker, mocked_session, 404, None)
        env = ActivityEnvironment()
        ret = await env.run(msm_act.verify_token, verify_param)
        assert not ret


class TestMSMEnrolWorkflow:
    async def test_enrolment(self, enrol_param):
        POLL_CALL_COUNT = 3
        calls = defaultdict(list)

        @activity.defn(name=MSM_SEND_ENROL_ACTIVITY_NAME)
        async def send_enrol(input: MSMEnrolParam) -> bool:
            calls["msm-send-enrol"].append(replace(input))
            return True, None

        @activity.defn(name=MSM_CHECK_ENROL_ACTIVITY_NAME)
        async def check_enrol(input: MSMEnrolParam) -> tuple[str, int]:
            calls["msm-check-enrol"].append(replace(input))
            if len(calls["msm-check-enrol"]) < POLL_CALL_COUNT:
                raise ApplicationError("waiting for MSM enrolment")
            return _JWT_ACCESS, _JWT_ROTATION_INTERVAL

        @activity.defn(name=MSM_SET_ENROL_ACTIVITY_NAME)
        async def set_enrol(input: MSMConnectorParam) -> None:
            calls["msm-set-enrol"].append(replace(input))

        @activity.defn(name=MSM_VERIFY_TOKEN_ACTIVITY_NAME)
        async def verify_token(input: MSMTokenVerifyParam) -> bool:
            calls["msm-verify-token"].append(replace(input))
            return True

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMEnrolSiteWorkflow],
                activities=[
                    send_enrol,
                    check_enrol,
                    set_enrol,
                    verify_token,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMEnrolSiteWorkflow.run,
                    enrol_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert calls["msm-send-enrol"][0] == enrol_param
        assert len(calls["msm-check-enrol"]) == POLL_CALL_COUNT
        assert calls["msm-check-enrol"][-1] == enrol_param
        cred = calls["msm-set-enrol"].pop()
        assert cred.jwt == _JWT_ACCESS
        assert cred.url == _MSM_BASE_URL
        assert cred.rotation_interval_minutes == _JWT_ROTATION_INTERVAL
        verify = calls["msm-verify-token"].pop()
        assert verify.jwt == _JWT_ACCESS

    async def test_enrolment_fail(self, enrol_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_SEND_ENROL_ACTIVITY_NAME)
        async def send_enrol(input: MSMEnrolParam) -> bool:
            calls["msm-send-enrol"].append(replace(input))
            return False, {"status": 401, "reason": "Unauthorized"}

        @activity.defn(name=MSM_CHECK_ENROL_ACTIVITY_NAME)
        async def check_enrol(input: MSMEnrolParam) -> tuple[str, int]:
            calls["msm-check-enrol"].append(replace(input))
            return None, -1

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMEnrolSiteWorkflow],
                activities=[
                    send_enrol,
                    check_enrol,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMEnrolSiteWorkflow.run,
                    enrol_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )
        assert len(calls["msm-send-enrol"]) == 1
        assert len(calls["msm-check-enrol"]) == 0

    async def test_enrolment_cancelled_by_msm(self, enrol_param):
        POLL_CALL_COUNT = 3
        calls = defaultdict(list)

        @activity.defn(name=MSM_SEND_ENROL_ACTIVITY_NAME)
        async def send_enrol(input: MSMEnrolParam) -> bool:
            calls["msm-send-enrol"].append(replace(input))
            return True, None

        @activity.defn(name=MSM_CHECK_ENROL_ACTIVITY_NAME)
        async def check_enrol(input: MSMEnrolParam) -> tuple[str, int]:
            calls["msm-check-enrol"].append(replace(input))
            if len(calls["msm-check-enrol"]) < POLL_CALL_COUNT:
                raise ApplicationError("waiting for MSM enrolment")
            return None, -1

        @activity.defn(name=MSM_SET_ENROL_ACTIVITY_NAME)
        async def set_enrol(input: MSMConnectorParam) -> None:
            calls["msm-set-enrol"].append(replace(input))

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMEnrolSiteWorkflow],
                activities=[
                    send_enrol,
                    check_enrol,
                    set_enrol,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMEnrolSiteWorkflow.run,
                    enrol_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert len(calls["msm-send-enrol"]) == 1
        assert len(calls["msm-check-enrol"]) == POLL_CALL_COUNT
        assert len(calls["msm-set-enrol"]) == 1


class TestMSMHeartbeatWorkflow:
    async def test_heartbeat(self, hb_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME)
        async def get_heartbeat_data() -> MachinesCountByStatus:
            calls["msm-get-heartbeat-data"].append(True)
            return MachinesCountByStatus(allocated=1, deployed=1)

        @activity.defn(name=MSM_SEND_HEARTBEAT_ACTIVITY_NAME)
        async def send_heartbeat(input: MSMHeartbeatParam) -> int:
            calls["msm-send-heartbeat"].append(True)
            return -1

        @activity.defn(name=MSM_GET_ENROL_ACTIVITY_NAME)
        async def get_enrol() -> dict[str, Any]:
            calls["msm-get-enrol"].append(True)
            return {
                "jwt": _JWT_ACCESS,
                "url": _MSM_ENROL_URL,
                "rotation_interval_minutes": _JWT_ROTATION_INTERVAL,
                "jwt_refresh_url": _JWT_REFRESH_URL,
            }

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMHeartbeatWorkflow],
                activities=[
                    get_heartbeat_data,
                    send_heartbeat,
                    get_enrol,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMHeartbeatWorkflow.run,
                    hb_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert len(calls["msm-get-heartbeat-data"]) == 1
        assert len(calls["msm-send-heartbeat"]) == 1
        assert len(calls["msm-get-enrol"]) == 1


class TestMSMTokenRefreshWorkflow:
    async def test_token_refresh(self, refresh_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME)
        async def refresh_token(
            input: MSMTokenRefreshParam,
        ) -> tuple[str | None, int]:
            calls["msm-get-token-refresh"].append(True)
            return ("new_token", -1)

        @activity.defn(name=MSM_SET_ENROL_ACTIVITY_NAME)
        async def set_enrol(input: MSMConnectorParam):
            calls["msm-set-enrol"].append(replace(input))

        @activity.defn(name=MSM_VERIFY_TOKEN_ACTIVITY_NAME)
        async def verify_token(input: MSMTokenVerifyParam) -> bool:
            calls["msm-verify-token"].append(replace(input))
            return True

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMTokenRefreshWorkflow],
                activities=[
                    refresh_token,
                    set_enrol,
                    verify_token,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMTokenRefreshWorkflow.run,
                    refresh_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )
        assert len(calls["msm-get-token-refresh"]) == 1
        assert len(calls["msm-set-enrol"]) == 1
        assert calls["msm-set-enrol"][0].jwt == "new_token"
        verify = calls["msm-verify-token"].pop()
        assert verify.jwt == "new_token"

    async def test_token_refresh_canceled_by_msm(self, refresh_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME)
        async def refresh_token(
            input: MSMTokenRefreshParam,
        ) -> tuple[str | None, int]:
            calls["msm-get-token-refresh"].append(True)
            return (None, -1)

        @activity.defn(name=MSM_SET_ENROL_ACTIVITY_NAME)
        async def set_enrol(input: MSMConnectorParam):
            calls["msm-set-enrol"].append(input)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMTokenRefreshWorkflow],
                activities=[
                    refresh_token,
                    set_enrol,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMTokenRefreshWorkflow.run,
                    refresh_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert len(calls["msm-get-token-refresh"]) == 1
        assert len(calls["msm-set-enrol"]) == 0
