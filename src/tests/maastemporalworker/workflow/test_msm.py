# Copyright 2024 Canonical Ltd.  This software is licensed under the
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

from maasapiserver.common.db import Database
from maasapiserver.v3.services.secrets import LocalSecretsStorageService
from maastemporalworker.workflow.msm import (
    MSM_SECRET,
    MSMConnectorActivity,
    MSMConnectorParam,
    MSMEnrolParam,
    MSMEnrolSiteWorkflow,
)

_MAAS_SITE_NAME = "maas-site"
_MAAS_URL = "http://maas.local/"
_MSM_ENROL_URL = "http://msm.local/site/v1/enrol"
_MSM_DETAIL_URL = "http://msm.local/site/v1/details"
_JWT_ENROL = "headers.claims.signature"
_JWT_ACCESS = "headers.new-claims.signature"


@pytest.fixture
async def msm_act(mocker, db: Database, db_connection: AsyncConnection):
    mock_session = mocker.create_autospec(ClientSession)
    mocker.patch.object(
        MSMConnectorActivity, "_create_session", return_value=mock_session
    )
    act = MSMConnectorActivity(db, db_connection)
    return act


@pytest.fixture
async def secrets(db: Database, db_connection: AsyncConnection):
    store = LocalSecretsStorageService(db_connection)
    yield store


@pytest.fixture
def enrol_param() -> MSMEnrolParam:
    return MSMEnrolParam(
        site_name=_MAAS_SITE_NAME,
        site_url=_MAAS_URL,
        url=_MSM_ENROL_URL,
        jwt=_JWT_ENROL,
    )


@pytest.mark.asyncio
@pytest.mark.usefixtures("maasdb")
class TestMSMActivities:
    def _mock_post(
        self, mocker, mocked_session, ok: bool, status: int, reason: str
    ) -> Mock:
        mock_response = mocker.create_autospec(ClientResponse)
        type(mock_response).ok = PropertyMock(return_value=ok)
        type(mock_response).status = PropertyMock(return_value=status)
        type(mock_response).reason = PropertyMock(return_value=reason)
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
        ok = await env.run(msm_act.send_enrol, enrol_param)

        assert ok
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
        meta = yaml.safe_dump({"latitude": 0.0, "longitude": 0.0})
        param = replace(enrol_param, metainfo=meta)
        ok = await env.run(msm_act.send_enrol, param)

        assert ok
        mocked_session.post.assert_called_once()
        kwargs = mocked_session.post.call_args.kwargs
        assert "metadata" in kwargs["json"]

    async def test_send_enrol_refused(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        self._mock_post(mocker, mocked_session, False, 404, "Some error")

        env = ActivityEnvironment()
        ok = await env.run(msm_act.send_enrol, enrol_param)
        assert not ok

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
        token = await env.run(msm_act.check_enrol, enrol_param)
        assert token is None

    async def test_check_enroll_complete(self, mocker, msm_act, enrol_param):
        mocked_session = msm_act._session
        body = {
            "access_token": _JWT_ACCESS,
            "token_type": "bearer",
        }
        self._mock_get(mocker, mocked_session, 200, body)

        env = ActivityEnvironment()
        new_token = await env.run(msm_act.check_enrol, enrol_param)
        assert new_token == _JWT_ACCESS
        args = mocked_session.get.call_args.args
        kwargs = mocked_session.get.call_args.kwargs
        assert args[0] == _MSM_ENROL_URL
        assert kwargs["headers"]["Authorization"] is not None

    async def test_set_enrol(self, msm_act, secrets):
        param = MSMConnectorParam(
            url=_MSM_DETAIL_URL,
            jwt=_JWT_ACCESS,
        )
        env = ActivityEnvironment()
        await env.run(msm_act.set_enrol, param)
        cred = await secrets.get_composite_secret(f"global/{MSM_SECRET}")
        assert cred["url"] == _MSM_DETAIL_URL
        assert cred["jwt"] == _JWT_ACCESS


class TestMSMEnrolWorkflow:
    async def test_enrolment(self, enrol_param):
        POLL_CALL_COUNT = 3
        calls = defaultdict(list)

        @activity.defn(name="msm-send-enrol")
        async def send_enrol(input: MSMEnrolParam) -> bool:
            calls["msm-send-enrol"].append(replace(input))
            return True

        @activity.defn(name="msm-check-enrol")
        async def check_enrol(input: MSMEnrolParam) -> str:
            calls["msm-check-enrol"].append(replace(input))
            if len(calls["msm-check-enrol"]) < POLL_CALL_COUNT:
                raise ApplicationError("waiting for MSM enrolment")
            return _JWT_ACCESS

        @activity.defn(name="msm-set-enrol")
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

        assert calls["msm-send-enrol"][0] == enrol_param
        assert len(calls["msm-check-enrol"]) == POLL_CALL_COUNT
        assert calls["msm-check-enrol"][-1] == enrol_param
        cred = calls["msm-set-enrol"].pop()
        assert cred.jwt == _JWT_ACCESS
        assert cred.url == _MSM_DETAIL_URL

    async def test_enrolment_fail(self, enrol_param):
        calls = defaultdict(list)

        @activity.defn(name="msm-send-enrol")
        async def send_enrol(input: MSMEnrolParam) -> bool:
            calls["msm-send-enrol"].append(replace(input))
            return False

        @activity.defn(name="msm-check-enrol")
        async def check_enrol(input: MSMEnrolParam) -> str:
            calls["msm-check-enrol"].append(replace(input))
            return None

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

        @activity.defn(name="msm-send-enrol")
        async def send_enrol(input: MSMEnrolParam) -> bool:
            calls["msm-send-enrol"].append(replace(input))
            return True

        @activity.defn(name="msm-check-enrol")
        async def check_enrol(input: MSMEnrolParam) -> str:
            calls["msm-check-enrol"].append(replace(input))
            if len(calls["msm-check-enrol"]) < POLL_CALL_COUNT:
                raise ApplicationError("waiting for MSM enrolment")
            return None

        @activity.defn(name="msm-set-enrol")
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
        assert len(calls["msm-set-enrol"]) == 0
