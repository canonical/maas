# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections import defaultdict
from dataclasses import replace
import hashlib
import json
import re
from typing import Any
from unittest.mock import call, Mock, PropertyMock
import uuid

from aiohttp import ClientResponse, ClientSession
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity
from temporalio.client import Client, ScheduleHandle
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment
from temporalio.worker import Worker
from temporalio.workflow import ParentClosePolicy
import yaml

from maascommon.enums.node import NodeStatus
from maascommon.workflows.bootresource import MASTER_IMAGE_SYNC_WORKFLOW_NAME
from maascommon.workflows.msm import (
    MSM_CONFIGURE_PROFILE_WORKFLOW_NAME,
    MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME,
    MSMRestoreDefaultBootSourceParam,
)
from maasservicelayer.builders.bootsources import BootSourceBuilder
from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db import Database
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.bootsources import BootSource
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.models.secrets import MSMConnectorSecret
from maasservicelayer.services import CacheForServices
from maasservicelayer.services.boot_sources import (
    BootSourceSelectionsService,
    BootSourcesService,
)
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.image_sync import ImageSyncService
from maasservicelayer.services.secrets import LocalSecretsStorageService
from maasservicelayer.services.temporal import TemporalService
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.workflow.msm import (
    CONFIGURATION_ACTIVITIES,
    MachinesCountByStatus,
    MSM_CHECK_ENROL_ACTIVITY_NAME,
    MSM_CONFIG_EP,
    MSM_DELETE_BOOT_SOURCES_ACTIVITY_NAME,
    MSM_DETAIL_EP,
    MSM_ENROL_EP,
    MSM_GET_CONFIG_HASH_ACTIVITY_NAME,
    MSM_GET_ENROL_ACTIVITY_NAME,
    MSM_GET_FULL_PROFILE_CONFIG_ACTIVITY_NAME,
    MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME,
    MSM_GET_KNOWN_CONFIG_OPTIONS_ACTIVITY_NAME,
    MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME,
    MSM_GET_VERSION_ACTIVITY_NAME,
    MSM_REFRESH_EP,
    MSM_REPORT_CONFIG_PROGRESS_ACTIVITY_NAME,
    MSM_REPORT_PROGRESS_EP,
    MSM_RESTORE_DEFAULT_BOOT_SOURCE_ACTIVITY_NAME,
    MSM_SEND_ENROL_ACTIVITY_NAME,
    MSM_SEND_HEARTBEAT_ACTIVITY_NAME,
    MSM_SET_BOOT_SOURCE_ACTIVITY_NAME,
    MSM_SET_ENROL_ACTIVITY_NAME,
    MSM_SET_GLOBAL_CONFIG_ACTIVITY_NAME,
    MSM_SET_SELECTIONS_ACTIVITY_NAME,
    MSM_SS_EP,
    MSM_START_IMAGE_SYNC_ACTIVITY_NAME,
    MSM_VERIFY_EP,
    MSM_VERIFY_TOKEN_ACTIVITY_NAME,
    MSMConfigureProfileParam,
    MSMConfigureProfileWorkflow,
    MSMConnectorActivity,
    MSMConnectorParam,
    MSMEnrolParam,
    MSMEnrolSiteWorkflow,
    MSMHeartbeatParam,
    MSMHeartbeatResponse,
    MSMHeartbeatWorkflow,
    MSMReportConfigProgressParam,
    MSMRestoreDefaultBootSourceWorkflow,
    MSMSetBootSourceParam,
    MSMSetGlobalConfigParam,
    MSMSetSelectionsParam,
    MSMTokenRefreshParam,
    MSMTokenRefreshWorkflow,
    MSMTokenVerifyParam,
    SiteStatus,
    TaskStatus,
)
from tests.fixtures import AsyncContextManagerMock
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture

_MAAS_SITE_NAME = "maas-site"
_MAAS_URL = "http://maas.local/"
_MSM_BASE_URL = "http://msm.local/ingress"
_MSM_BOOT_SOURCE_URL = f"{_MSM_BASE_URL}{MSM_SS_EP}"
_MSM_ENROL_URL = f"{_MSM_BASE_URL}{MSM_ENROL_EP}"
_MSM_DETAIL_URL = f"{_MSM_BASE_URL}{MSM_DETAIL_EP}"
_MSM_CONFIG_URL = f"{_MSM_BASE_URL}{MSM_CONFIG_EP}"
_MSM_REPORT_PROGRESS_URL = f"{_MSM_BASE_URL}{MSM_REPORT_PROGRESS_EP}"
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
    act = MSMConnectorActivity(db, services_cache, Mock(Client), db_connection)
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
        version="3.8.0",
        known_config_options=None,
    )


@pytest.fixture
def config_profile_param() -> MSMConfigureProfileParam:
    return MSMConfigureProfileParam(
        sm_url=_MSM_BASE_URL,
        jwt=_JWT_ACCESS,
    )


@pytest.fixture
def report_progress_param() -> MSMReportConfigProgressParam:
    return MSMReportConfigProgressParam(
        sm_url=_MSM_BASE_URL,
        jwt=_JWT_ACCESS,
        site_status=SiteStatus(
            status=TaskStatus.STARTED,
            selections_status=TaskStatus.STARTED,
            global_config_status=TaskStatus.STARTED,
            image_sync_status=TaskStatus.STARTED,
            errors=[],
            clear_errors=False,
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


@pytest.fixture
def restore_param() -> MSMRestoreDefaultBootSourceParam:
    return MSMRestoreDefaultBootSourceParam(
        sm_url=_MSM_BASE_URL,
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
        self,
        mocker,
        mocked_session,
        status: int,
        body: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> Mock:
        mock_response = mocker.create_autospec(ClientResponse)
        type(mock_response).status = PropertyMock(return_value=status)
        mock_response.json.return_value = body
        mocked_session.get.return_value.__aenter__.return_value = mock_response
        return mock_response

    def _mock_delete(self, mocker, mocked_session, status: int) -> Mock:
        mock_response = mocker.create_autospec(ClientResponse)
        type(mock_response).status = PropertyMock(return_value=status)
        mocked_session.delete.return_value.__aenter__.return_value = (
            mock_response
        )
        return mock_response

    def _mock_patch(self, mocker, mocked_session, status: int) -> Mock:
        mock_response = mocker.create_autospec(ClientResponse)
        type(mock_response).status = PropertyMock(return_value=status)
        mocked_session.patch.return_value.__aenter__.return_value = (
            mock_response
        )
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
            body={
                "config_options_requested": False,
                "config_hash": "test-hash",
            },
            headers={
                "MSM-Heartbeat-Interval-Seconds": 300,
            },
        )

        env = ActivityEnvironment()
        result = await env.run(msm_act.send_heartbeat, hb_param)

        assert result.interval == 300
        assert result.send_config_options is False
        assert result.config_hash == "test-hash"
        mocked_session.post.assert_called_once()
        args = mocked_session.post.call_args.args
        kwargs = mocked_session.post.call_args.kwargs
        assert args[0] == _MSM_DETAIL_URL
        assert kwargs["headers"]["Authorization"] is not None
        assert kwargs["json"]["name"] == _MAAS_SITE_NAME
        assert kwargs["json"]["url"] == _MAAS_URL
        assert "machines_by_status" in kwargs["json"]
        assert kwargs["json"]["version"] == hb_param.version
        assert "known_config_options" not in kwargs["json"]

    async def test_send_heartbeat_with_cfg_options(
        self, mocker, msm_act, hb_param
    ):
        mocked_session = msm_act._session
        self._mock_post(
            mocker,
            mocked_session,
            True,
            200,
            "",
            body={
                "config_options_requested": True,
                "config_hash": "test-hash",
            },
            headers={
                "MSM-Heartbeat-Interval-Seconds": 300,
            },
        )

        env = ActivityEnvironment()
        hb_param.known_config_options = []
        result = await env.run(msm_act.send_heartbeat, hb_param)

        assert result.interval == 300
        assert result.send_config_options is True
        assert result.config_hash == "test-hash"
        mocked_session.post.assert_called_once()
        args = mocked_session.post.call_args.args
        kwargs = mocked_session.post.call_args.kwargs
        assert args[0] == _MSM_DETAIL_URL
        assert kwargs["headers"]["Authorization"] is not None
        assert kwargs["json"]["name"] == _MAAS_SITE_NAME
        assert kwargs["json"]["url"] == _MAAS_URL
        assert "machines_by_status" in kwargs["json"]
        assert kwargs["json"]["version"] == hb_param.version
        # TODO: update once config workflow is implemented
        assert kwargs["json"]["known_config_options"] == []

    async def test_send_heartbeat_cancel(self, mocker, msm_act, hb_param):
        mocked_session = msm_act._session
        self._mock_post(mocker, mocked_session, True, 401, "")

        env = ActivityEnvironment()
        result = await env.run(msm_act.send_heartbeat, hb_param)
        assert result.interval == -1
        assert result.send_config_options is False
        assert result.config_hash == ""

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

    async def test_set_boot_source_activity(
        self, mocker, msm_act, enrol_param, services_mock
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        await env.run(
            msm_act.set_bootsource,
            MSMSetBootSourceParam(sm_url=enrol_param.url),
        )
        services_mock.boot_sources.get_many.assert_not_called()
        services_mock.boot_sources.create.assert_called_once()
        (builder,), _ = services_mock.boot_sources.create.call_args
        assert isinstance(builder, BootSourceBuilder)
        assert builder.url == _MSM_BOOT_SOURCE_URL
        assert builder.keyring_filename == ""
        assert builder.keyring_data == b""
        assert builder.priority == 1
        assert builder.skip_keyring_verification

    async def test_set_selections_activity(
        self, mocker, msm_act, services_mock
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_one.return_value = BootSource(
            id=1,
            url=_MSM_BOOT_SOURCE_URL,
            priority=1,
            skip_keyring_verification=True,
        )
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        await env.run(
            msm_act.set_selections,
            MSMSetSelectionsParam(
                selections=["ubuntu/noble/amd64", "ubuntu/resolute/arm64"],
                sm_url=_MSM_BOOT_SOURCE_URL,
            ),
        )
        services_mock.boot_source_selections.delete_many.assert_called_once_with(
            QuerySpec(
                where=BootSourceSelectionClauseFactory.with_boot_source_id(1)
            )
        )
        # order of builders is not guaranteed, so cant do assert_called_with
        builders_arg = (
            services_mock.boot_source_selections.create_many.call_args.args[0]
        )
        assert (
            BootSourceSelectionBuilder(
                boot_source_id=1,
                os="ubuntu",
                release="noble",
                arch="amd64",
            )
            in builders_arg
        )
        assert (
            BootSourceSelectionBuilder(
                boot_source_id=1,
                os="ubuntu",
                release="resolute",
                arch="arm64",
            )
            in builders_arg
        )

    async def test_set_selections_activity_no_source(
        self, mocker, msm_act, services_mock
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_one.return_value = None
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        with pytest.raises(
            ApplicationError, match="Site Manager boot source does not exist"
        ):
            await env.run(
                msm_act.set_selections,
                MSMSetSelectionsParam(
                    selections=["ubuntu/noble/amd64", "ubuntu/resolute/arm64"],
                    sm_url=_MSM_BOOT_SOURCE_URL,
                ),
            )

    async def test_set_selections_activity_bad_selection_format(
        self, mocker, msm_act, services_mock
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        services_mock.boot_sources.get_one.return_value = BootSource(
            id=1,
            url=_MSM_BOOT_SOURCE_URL,
            priority=1,
            skip_keyring_verification=True,
        )
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        with pytest.raises(
            ApplicationError, match="Unexpected selection format"
        ):
            await env.run(
                msm_act.set_selections,
                MSMSetSelectionsParam(
                    selections=[
                        "ubuntu/noble/amd64/somethingelse",
                        "ubuntu/resolute",
                    ],
                    sm_url=_MSM_BOOT_SOURCE_URL,
                ),
            )

    async def test_set_global_config(self, mocker, msm_act, services_mock):
        services_mock.configurations = Mock(ConfigurationsService)
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        test_cfg = {"theme": "dark"}
        param = MSMSetGlobalConfigParam(configuration=test_cfg)
        await env.run(msm_act.set_global_config, param)
        services_mock.configurations.clear_and_set_many.assert_called_once_with(
            test_cfg
        )

    async def test_set_global_config_err_non_retryable(
        self, mocker, msm_act, services_mock
    ):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.clear_and_set_many.side_effect = (
            ValidationException
        )
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        test_cfg = {"theme": 2}
        param = MSMSetGlobalConfigParam(configuration=test_cfg)
        with pytest.raises(ApplicationError) as err:
            await env.run(msm_act.set_global_config, param)
        assert err.value.non_retryable

    async def test_start_image_sync(self, mocker, msm_act, services_mock):
        services_mock.temporal = Mock(TemporalService)
        temporal_client = Mock(Client)
        sched_handle = Mock(ScheduleHandle)
        temporal_client.get_schedule_handle.return_value = sched_handle
        services_mock.temporal.get_temporal_client.return_value = (
            temporal_client
        )
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        await env.run(msm_act.start_image_sync)
        temporal_client.get_schedule_handle.assert_called_once_with(
            MASTER_IMAGE_SYNC_WORKFLOW_NAME
        )
        sched_handle.trigger.assert_called_once()

    async def test_delete_bootsources_activity(
        self, mocker, msm_act, services_mock
    ):
        services_mock.boot_sources = Mock(BootSourcesService)
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        await env.run(msm_act.delete_bootsources)
        services_mock.boot_sources.delete_many.assert_called_once_with(
            QuerySpec()
        )

    async def test_restore_default_bootsource_activity(
        self,
        mocker,
        msm_act,
        services_mock,
    ):
        services_mock.image_sync = Mock(ImageSyncService)
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        env = ActivityEnvironment()
        await env.run(msm_act.restore_default_boot_source)
        services_mock.image_sync.ensure_boot_source_definition.assert_called_once()

    async def test_get_known_config_options(self, msm_act):
        env = ActivityEnvironment()
        config_opts = await env.run(msm_act.get_known_config_options)
        assert config_opts == list(CONFIGURATION_ACTIVITIES)

    async def test_get_running_version(self, msm_act):
        env = ActivityEnvironment()
        version = await env.run(msm_act.get_running_version)
        # Verify version is in X.Y.Z format
        assert re.match(r"^\d+\.\d+\.\d+$", version)

    async def test_get_full_profile_config(
        self, mocker, msm_act, config_profile_param
    ):
        mocked_session = msm_act._session
        test_profile = {
            "global_config": {"theme": "dark"},
            "selections": ["ubuntu/resolute/amd64"],
            "trigger_image_sync": True,
        }
        self._mock_get(
            mocker,
            mocked_session,
            200,
            body=test_profile,
        )
        env = ActivityEnvironment()
        config = await env.run(
            msm_act.get_full_profile_config, config_profile_param
        )

        assert config == test_profile
        mocked_session.get.assert_called_once_with(
            _MSM_CONFIG_URL,
            headers={"Authorization": f"bearer {config_profile_param.jwt}"},
        )

    @pytest.mark.parametrize("return_code", [(401,), (404,), (500,)])
    async def test_get_full_profile_config_failed_request(
        self, mocker, msm_act, config_profile_param, return_code
    ):
        mocked_session = msm_act._session
        self._mock_get(
            mocker,
            mocked_session,
            return_code,
            body={},
        )
        env = ActivityEnvironment()
        with pytest.raises(ApplicationError) as err:
            await env.run(
                msm_act.get_full_profile_config, config_profile_param
            )
        assert err.value.non_retryable == (return_code in [401, 404])

    async def test_report_config_progress(
        self, mocker, msm_act, report_progress_param
    ):
        mocked_session = msm_act._session
        self._mock_patch(
            mocker,
            mocked_session,
            204,
        )
        env = ActivityEnvironment()
        await env.run(msm_act.report_config_progress, report_progress_param)
        mocked_session.patch.assert_called_once_with(
            _MSM_REPORT_PROGRESS_URL,
            json={
                "status": TaskStatus.STARTED,
                "selections_status": TaskStatus.STARTED,
                "global_config_status": TaskStatus.STARTED,
                "image_sync_status": TaskStatus.STARTED,
                "errors": [],
                "clear_errors": False,
            },
            headers={"Authorization": f"bearer {report_progress_param.jwt}"},
        )

    @pytest.mark.parametrize("return_code", [(401), (404,), (500,)])
    async def test_report_config_progress_failed_request(
        self, mocker, msm_act, report_progress_param, return_code
    ):
        mocked_session = msm_act._session
        self._mock_patch(
            mocker,
            mocked_session,
            return_code,
        )
        env = ActivityEnvironment()
        with pytest.raises(ApplicationError) as err:
            await env.run(
                msm_act.report_config_progress, report_progress_param
            )
        assert err.value.non_retryable == (return_code in [401, 404])
<<<<<<< HEAD

=======
>>>>>>> cd343d0dd8 (add workflow tests)

    async def test_get_config_hash(self, mocker, services_mock, msm_act):
        services_mock.configurations = Mock(ConfigurationsService)
        services_mock.configurations.get_msm_config.return_value = {
            "theme": "dark",
            "default_dns_ttl": 21,
        }
        services_mock.boot_source_selections = Mock(
            BootSourceSelectionsService
        )
        services_mock.boot_source_selections.get_all_highest_priority.return_value = [
            BootSourceSelection(
                id=1,
                boot_source_id=1,
                legacyselection_id=1,
                os="ubuntu",
                release="resolute",
                arch="arm64",
            ),
            BootSourceSelection(
                id=2,
                boot_source_id=1,
                legacyselection_id=1,
                os="ubuntu",
                release="noble",
                arch="amd64",
            ),
        ]
        mocker.patch.object(
            msm_act, "start_transaction"
        ).return_value = AsyncContextManagerMock(services_mock)
        expected_cfg = {
            "global_config": {"default_dns_ttl": 21, "theme": "dark"},
            "selections": ["ubuntu/noble/amd64", "ubuntu/resolute/arm64"],
            "trigger_image_sync": False,
        }
        serialized = json.dumps(
            expected_cfg,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        expected_hash = hashlib.sha256(serialized).hexdigest()
        env = ActivityEnvironment()
        cfg_hash = await env.run(msm_act.get_config_hash)
        assert cfg_hash == expected_hash


class TestMSMEnrolWorkflow:
    async def test_enrolment(self, enrol_param):
        POLL_CALL_COUNT = 3
        calls = defaultdict(list)

        @activity.defn(name=MSM_SEND_ENROL_ACTIVITY_NAME)
        async def send_enrol(
            input: MSMEnrolParam,
        ) -> tuple[bool, dict[str, Any] | None]:
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

        @activity.defn(name=MSM_SET_BOOT_SOURCE_ACTIVITY_NAME)
        async def set_boot_source(input: MSMSetBootSourceParam) -> None:
            calls["msm-set-boot-source"].append(replace(input))

        @activity.defn(name=MSM_DELETE_BOOT_SOURCES_ACTIVITY_NAME)
        async def delete_boot_source() -> None:
            calls["msm-delete-boot-source"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMEnrolSiteWorkflow],
                activities=[
                    send_enrol,
                    delete_boot_source,
                    set_boot_source,
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
        assert len(calls["msm-set-boot-source"]) == 1
        assert calls["msm-set-boot-source"][0].sm_url == _MSM_BASE_URL
        assert len(calls["msm-delete-boot-source"]) == 1
        assert calls["msm-delete-boot-source"][0] is True

    async def test_enrolment_fail(self, enrol_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_SEND_ENROL_ACTIVITY_NAME)
        async def send_enrol(
            input: MSMEnrolParam,
        ) -> tuple[bool, dict[str, Any] | None]:
            calls["msm-send-enrol"].append(replace(input))
            return False, {"status": 401, "reason": "Unauthorized"}

        @activity.defn(name=MSM_CHECK_ENROL_ACTIVITY_NAME)
        async def check_enrol(input: MSMEnrolParam) -> tuple[str | None, int]:
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
        async def send_enrol(
            input: MSMEnrolParam,
        ) -> tuple[bool, dict[str, Any] | None]:
            calls["msm-send-enrol"].append(replace(input))
            return True, None

        @activity.defn(name=MSM_CHECK_ENROL_ACTIVITY_NAME)
        async def check_enrol(input: MSMEnrolParam) -> tuple[str | None, int]:
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
    async def test_heartbeat(self, mocker, hb_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME)
        async def get_heartbeat_data() -> MachinesCountByStatus:
            calls["msm-get-heartbeat-data"].append(True)
            return MachinesCountByStatus(allocated=1, deployed=1)

        @activity.defn(name=MSM_SEND_HEARTBEAT_ACTIVITY_NAME)
        async def send_heartbeat(
            input: MSMHeartbeatParam,
        ) -> MSMHeartbeatResponse:
            calls["msm-send-heartbeat"].append(True)
            if len(calls["msm-send-heartbeat"]) == 2:
                return MSMHeartbeatResponse(
                    interval=-1, config_hash="", send_config_options=False
                )
            return MSMHeartbeatResponse(
                interval=1, config_hash="testhash", send_config_options=True
            )

        @activity.defn(name=MSM_GET_CONFIG_HASH_ACTIVITY_NAME)
        async def get_config_hash() -> str:
            calls["get-config-hash"].append(True)
            return "testhash"

        @activity.defn(name=MSM_GET_ENROL_ACTIVITY_NAME)
        async def get_enrol() -> dict[str, Any]:
            calls["msm-get-enrol"].append(True)
            return {
                "jwt": _JWT_ACCESS,
                "url": _MSM_ENROL_URL,
                "rotation_interval_minutes": _JWT_ROTATION_INTERVAL,
                "jwt_refresh_url": _JWT_REFRESH_URL,
            }

        @activity.defn(name=MSM_GET_VERSION_ACTIVITY_NAME)
        async def get_version() -> str:
            calls["msm-get-version"].append(True)
            return "3.4.0"

        @activity.defn(name=MSM_GET_KNOWN_CONFIG_OPTIONS_ACTIVITY_NAME)
        async def get_config_options() -> list[str]:
            calls["msm-get-config-options"].append(True)
            return list(CONFIGURATION_ACTIVITIES)

        mock_start_wf = mocker.patch(
            "maastemporalworker.workflow.msm.workflow.start_child_workflow"
        )

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMHeartbeatWorkflow],
                activities=[
                    get_heartbeat_data,
                    get_config_hash,
                    send_heartbeat,
                    get_enrol,
                    get_version,
                    get_config_options,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMHeartbeatWorkflow.run,
                    hb_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert len(calls["msm-get-heartbeat-data"]) == 2
        assert len(calls["msm-send-heartbeat"]) == 2
        assert len(calls["msm-get-enrol"]) == 2
        assert len(calls["msm-get-version"]) == 2
        assert len(calls["msm-get-config-options"]) == 1
        mock_start_wf.assert_called_once_with(
            MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME,
            MSMRestoreDefaultBootSourceParam(
                sm_url=_MSM_BASE_URL,
            ),
            id=f"{MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            parent_close_policy=ParentClosePolicy.ABANDON,
        )

    async def test_heartbeat_triggers_config_profile_wf(
        self, mocker, hb_param
    ):
        calls = defaultdict(list)

        @activity.defn(name=MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME)
        async def get_heartbeat_data() -> MachinesCountByStatus:
            calls["msm-get-heartbeat-data"].append(True)
            return MachinesCountByStatus(allocated=1, deployed=1)

        @activity.defn(name=MSM_SEND_HEARTBEAT_ACTIVITY_NAME)
        async def send_heartbeat(
            input: MSMHeartbeatParam,
        ) -> MSMHeartbeatResponse:
            calls["msm-send-heartbeat"].append(True)
            if len(calls["msm-send-heartbeat"]) == 2:
                return MSMHeartbeatResponse(
                    interval=-1, config_hash="", send_config_options=False
                )
            return MSMHeartbeatResponse(
                interval=1, config_hash="testhash", send_config_options=True
            )

        @activity.defn(name=MSM_GET_CONFIG_HASH_ACTIVITY_NAME)
        async def get_config_hash() -> str:
            calls["get-config-hash"].append(True)
            return "other_hash"

        @activity.defn(name=MSM_GET_ENROL_ACTIVITY_NAME)
        async def get_enrol() -> dict[str, Any]:
            calls["msm-get-enrol"].append(True)
            return {
                "jwt": _JWT_ACCESS,
                "url": _MSM_ENROL_URL,
                "rotation_interval_minutes": _JWT_ROTATION_INTERVAL,
                "jwt_refresh_url": _JWT_REFRESH_URL,
            }

        @activity.defn(name=MSM_GET_VERSION_ACTIVITY_NAME)
        async def get_version() -> str:
            calls["msm-get-version"].append(True)
            return "3.4.0"

        @activity.defn(name=MSM_GET_KNOWN_CONFIG_OPTIONS_ACTIVITY_NAME)
        async def get_config_options() -> list[str]:
            calls["msm-get-config-options"].append(True)
            return list(CONFIGURATION_ACTIVITIES)

        mock_start_wf = mocker.patch(
            "maastemporalworker.workflow.msm.workflow.start_child_workflow"
        )

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMHeartbeatWorkflow],
                activities=[
                    get_heartbeat_data,
                    get_config_hash,
                    send_heartbeat,
                    get_enrol,
                    get_version,
                    get_config_options,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMHeartbeatWorkflow.run,
                    hb_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert len(calls["msm-get-heartbeat-data"]) == 2
        assert len(calls["msm-send-heartbeat"]) == 2
        assert len(calls["msm-get-enrol"]) == 2
        assert len(calls["msm-get-version"]) == 2
        assert len(calls["msm-get-config-options"]) == 1
        expected_calls = [
            call(
                MSM_CONFIGURE_PROFILE_WORKFLOW_NAME,
                MSMConfigureProfileParam(
                    sm_url=_MSM_BASE_URL, jwt=_JWT_ACCESS
                ),
                id=f"{MSM_CONFIGURE_PROFILE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                parent_close_policy=ParentClosePolicy.ABANDON,
            ),
            call(
                MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME,
                MSMRestoreDefaultBootSourceParam(
                    sm_url=_MSM_BASE_URL,
                ),
                id=f"{MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                parent_close_policy=ParentClosePolicy.ABANDON,
            ),
        ]
        assert mock_start_wf.call_args_list == expected_calls


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


class TestRestoreDefaultBootSourceWorkflow:
    async def test_restore_default_boot_source(self, restore_param):
        calls = defaultdict(list)

        @activity.defn(name=MSM_DELETE_BOOT_SOURCES_ACTIVITY_NAME)
        async def delete_sources() -> None:
            calls["msm-delete-boot-sources"].append(True)

        @activity.defn(name=MSM_RESTORE_DEFAULT_BOOT_SOURCE_ACTIVITY_NAME)
        async def restore_default_source() -> None:
            calls["msm-restore-default-source"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMRestoreDefaultBootSourceWorkflow],
                activities=[
                    delete_sources,
                    restore_default_source,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMRestoreDefaultBootSourceWorkflow.run,
                    restore_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )
        assert calls["msm-delete-boot-sources"] == [True]
        assert len(calls["msm-restore-default-source"]) == 1


class TestConfigureProfileWorkflow:
    @pytest.mark.parametrize("trigger_sync", [(True,), (False,)])
    async def test_workflow(self, config_profile_param, trigger_sync):
        calls = defaultdict(list)
        test_profile = {
            "global_config": {"theme": "dark"},
            "selections": ["ubuntu/resolute/amd64"],
            "trigger_image_sync": trigger_sync,
        }

        @activity.defn(name=MSM_GET_FULL_PROFILE_CONFIG_ACTIVITY_NAME)
        async def get_full_profile(
            input: MSMConfigureProfileParam,
        ) -> dict[str, Any]:
            calls["msm-get-full-profile"].append(True)
            return test_profile

        @activity.defn(name=MSM_REPORT_CONFIG_PROGRESS_ACTIVITY_NAME)
        async def report_progress(input: MSMReportConfigProgressParam) -> None:
            calls["msm-report-progress"].append(input)

        @activity.defn(name=MSM_SET_GLOBAL_CONFIG_ACTIVITY_NAME)
        async def set_global_config(input: MSMSetGlobalConfigParam) -> None:
            calls["msm-set-global-config"].append(input)

        @activity.defn(name=MSM_SET_SELECTIONS_ACTIVITY_NAME)
        async def set_selections(input: MSMSetSelectionsParam) -> None:
            calls["msm-set-selections"].append(input)

        @activity.defn(name=MSM_START_IMAGE_SYNC_ACTIVITY_NAME)
        async def image_sync() -> None:
            calls["msm-image-sync"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMConfigureProfileWorkflow],
                activities=[
                    get_full_profile,
                    report_progress,
                    set_global_config,
                    set_selections,
                    image_sync,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMConfigureProfileWorkflow.run,
                    config_profile_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert calls["msm-get-full-profile"] == [True]
        expected_report_calls = [
            # one at beginning to signal start of wf
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    status=TaskStatus.STARTED,
                    selections_status=TaskStatus.STARTED,
                    global_config_status=TaskStatus.STARTED,
                    image_sync_status=TaskStatus.STARTED
                    if trigger_sync
                    else None,
                ),
            ),
            # one for selections, global_config activities
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    selections_status=TaskStatus.COMPLETE,
                ),
            ),
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    global_config_status=TaskStatus.COMPLETE,
                ),
            ),
            # one for the end
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    status=TaskStatus.COMPLETE,
                    clear_errors=True,
                ),
            ),
        ]
        if trigger_sync:
            assert calls["msm-image-sync"] == [True]
            expected_report_calls.append(
                MSMReportConfigProgressParam(
                    sm_url=config_profile_param.sm_url,
                    jwt=config_profile_param.jwt,
                    site_status=SiteStatus(
                        image_sync_status=TaskStatus.COMPLETE,
                    ),
                )
            )
        else:
            assert calls["msm-image-sync"] == []

        for expected_call in expected_report_calls:
            assert expected_call in calls["msm-report-progress"]

        assert calls["msm-set-global-config"] == [
            MSMSetGlobalConfigParam(
                configuration=test_profile["global_config"]
            )
        ]

        assert calls["msm-set-selections"] == [
            MSMSetSelectionsParam(
                sm_url=config_profile_param.sm_url,
                selections=test_profile["selections"],
            )
        ]

    @pytest.mark.parametrize(
        "failed_activity", ["global_config", "selections", "image_sync"]
    )
    async def test_workflow_failed_activities(
        self, config_profile_param, failed_activity
    ):
        calls = defaultdict(list)
        test_profile = {
            "global_config": {"theme": "dark"},
            "selections": ["ubuntu/resolute/amd64"],
            "trigger_image_sync": True,
        }

        @activity.defn(name=MSM_GET_FULL_PROFILE_CONFIG_ACTIVITY_NAME)
        async def get_full_profile(
            input: MSMConfigureProfileParam,
        ) -> dict[str, Any]:
            calls["msm-get-full-profile"].append(True)
            return test_profile

        @activity.defn(name=MSM_REPORT_CONFIG_PROGRESS_ACTIVITY_NAME)
        async def report_progress(input: MSMReportConfigProgressParam) -> None:
            calls["msm-report-progress"].append(input)

        @activity.defn(name=MSM_SET_GLOBAL_CONFIG_ACTIVITY_NAME)
        async def set_global_config(input: MSMSetGlobalConfigParam) -> None:
            calls["msm-set-global-config"].append(input)
            if failed_activity == "global_config":
                raise ApplicationError(
                    "global_config failed", non_retryable=True
                )

        @activity.defn(name=MSM_SET_SELECTIONS_ACTIVITY_NAME)
        async def set_selections(input: MSMSetSelectionsParam) -> None:
            calls["msm-set-selections"].append(input)
            if failed_activity == "selections":
                raise ApplicationError("selections failed", non_retryable=True)

        @activity.defn(name=MSM_START_IMAGE_SYNC_ACTIVITY_NAME)
        async def image_sync() -> None:
            calls["msm-image-sync"].append(True)
            if failed_activity == "image_sync":
                raise ApplicationError("image_sync failed", non_retryable=True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMConfigureProfileWorkflow],
                activities=[
                    get_full_profile,
                    report_progress,
                    set_global_config,
                    set_selections,
                    image_sync,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMConfigureProfileWorkflow.run,
                    config_profile_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert calls["msm-get-full-profile"] == [True]
        expected_report_calls = [
            # one at beginning to signal start of wf
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    status=TaskStatus.STARTED,
                    selections_status=TaskStatus.STARTED,
                    global_config_status=TaskStatus.STARTED,
                    image_sync_status=TaskStatus.STARTED,
                ),
            ),
            # one for selections, global_config activities
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    selections_status=TaskStatus.FAILED
                    if failed_activity == "selections"
                    else TaskStatus.COMPLETE,
                    errors=[
                        "selections activity failed (Activity task failed)."
                    ]
                    if failed_activity == "selections"
                    else None,
                ),
            ),
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    global_config_status=TaskStatus.FAILED
                    if failed_activity == "global_config"
                    else TaskStatus.COMPLETE,
                    errors=[
                        "global_config activity failed (Activity task failed)."
                    ]
                    if failed_activity == "global_config"
                    else None,
                ),
            ),
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    image_sync_status=TaskStatus.FAILED
                    if failed_activity == "image_sync"
                    else TaskStatus.COMPLETE,
                    errors=[
                        "image_sync activity failed (Activity task failed)."
                    ]
                    if failed_activity == "image_sync"
                    else None,
                ),
            ),
            # one for the end
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    status=TaskStatus.FAILED,
                    errors=[
                        f"The following activities failed: ['{failed_activity}']"
                    ],
                ),
            ),
        ]
        for expected_call in expected_report_calls:
            assert expected_call in calls["msm-report-progress"]
        assert len(calls["msm-set-global-config"]) == 1
        assert len(calls["msm-set-selections"]) == 1
        assert len(calls["msm-image-sync"]) == 1

    async def test_workflow_unknown_activities(self, config_profile_param):
        calls = defaultdict(list)
        test_profile = {
            "global_config": {"theme": "dark"},
            "selections": ["ubuntu/resolute/amd64"],
            "trigger_image_sync": True,
            "something_else": 1,
        }

        @activity.defn(name=MSM_GET_FULL_PROFILE_CONFIG_ACTIVITY_NAME)
        async def get_full_profile(
            input: MSMConfigureProfileParam,
        ) -> dict[str, Any]:
            calls["msm-get-full-profile"].append(True)
            return test_profile

        @activity.defn(name=MSM_REPORT_CONFIG_PROGRESS_ACTIVITY_NAME)
        async def report_progress(input: MSMReportConfigProgressParam) -> None:
            calls["msm-report-progress"].append(input)

        @activity.defn(name=MSM_SET_GLOBAL_CONFIG_ACTIVITY_NAME)
        async def set_global_config(input: MSMSetGlobalConfigParam) -> None:
            calls["msm-set-global-config"].append(input)

        @activity.defn(name=MSM_SET_SELECTIONS_ACTIVITY_NAME)
        async def set_selections(input: MSMSetSelectionsParam) -> None:
            calls["msm-set-selections"].append(input)

        @activity.defn(name=MSM_START_IMAGE_SYNC_ACTIVITY_NAME)
        async def image_sync() -> None:
            calls["msm-image-sync"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMConfigureProfileWorkflow],
                activities=[
                    get_full_profile,
                    report_progress,
                    set_global_config,
                    set_selections,
                    image_sync,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMConfigureProfileWorkflow.run,
                    config_profile_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert calls["msm-get-full-profile"] == [True]
        assert calls["msm-report-progress"] == [
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    status=TaskStatus.FAILED,
                    errors=[
                        f"Unknown configuration options: {set(['something_else'])}"
                    ],
                    clear_errors=True,
                ),
            )
        ]
        assert len(calls["msm-set-global-config"]) == 0
        assert len(calls["msm-set-selections"]) == 0
        assert len(calls["msm-image-sync"]) == 0

    async def test_workflow_incomplete_cfg_provided(
        self, config_profile_param
    ):
        calls = defaultdict(list)
        test_profile = {
            "global_config": {"theme": "dark"},
            "selections": ["ubuntu/resolute/amd64"],
        }

        @activity.defn(name=MSM_GET_FULL_PROFILE_CONFIG_ACTIVITY_NAME)
        async def get_full_profile(
            input: MSMConfigureProfileParam,
        ) -> dict[str, Any]:
            calls["msm-get-full-profile"].append(True)
            return test_profile

        @activity.defn(name=MSM_REPORT_CONFIG_PROGRESS_ACTIVITY_NAME)
        async def report_progress(input: MSMReportConfigProgressParam) -> None:
            calls["msm-report-progress"].append(input)

        @activity.defn(name=MSM_SET_GLOBAL_CONFIG_ACTIVITY_NAME)
        async def set_global_config(input: MSMSetGlobalConfigParam) -> None:
            calls["msm-set-global-config"].append(input)

        @activity.defn(name=MSM_SET_SELECTIONS_ACTIVITY_NAME)
        async def set_selections(input: MSMSetSelectionsParam) -> None:
            calls["msm-set-selections"].append(input)

        @activity.defn(name=MSM_START_IMAGE_SYNC_ACTIVITY_NAME)
        async def image_sync() -> None:
            calls["msm-image-sync"].append(True)

        async with await WorkflowEnvironment.start_time_skipping() as env:
            async with Worker(
                env.client,
                task_queue="abcd:region",
                workflows=[MSMConfigureProfileWorkflow],
                activities=[
                    get_full_profile,
                    report_progress,
                    set_global_config,
                    set_selections,
                    image_sync,
                ],
            ) as worker:
                await env.client.execute_workflow(
                    MSMConfigureProfileWorkflow.run,
                    config_profile_param,
                    id=f"workflow-{uuid.uuid4()}",
                    task_queue=worker.task_queue,
                )

        assert calls["msm-get-full-profile"] == [True]
        assert calls["msm-report-progress"] == [
            MSMReportConfigProgressParam(
                sm_url=config_profile_param.sm_url,
                jwt=config_profile_param.jwt,
                site_status=SiteStatus(
                    status=TaskStatus.FAILED,
                    errors=[
                        "Incomplete configuration provided (missing {'trigger_image_sync'})"
                    ],
                    clear_errors=True,
                ),
            )
        ]
        assert len(calls["msm-set-global-config"]) == 0
        assert len(calls["msm-set-selections"]) == 0
        assert len(calls["msm-image-sync"]) == 0
