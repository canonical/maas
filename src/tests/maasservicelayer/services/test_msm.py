# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from unittest.mock import AsyncMock, call, Mock
from urllib.parse import urlparse

from jose import jwt
import pytest
from temporalio.client import Client, WorkflowExecutionDescription
from temporalio.common import WorkflowIDReusePolicy

from maascommon.enums.msm import MSMStatusEnum
from maascommon.workflows.msm import (
    MSM_ENROL_SITE_WORKFLOW_NAME,
    MSM_HEARTBEAT_WORKFLOW_NAME,
    MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME,
    MSM_TOKEN_REFRESH_WORKFLOW_NAME,
    MSMRestoreDefaultBootSourceParam,
)
from maasserver.workflow import REGION_TASK_QUEUE
from maasservicelayer.models.configurations import (
    MAASNameConfig,
    MAASUrlConfig,
)
from maasservicelayer.models.secrets import MSMConnectorSecret
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.msm import (
    ACCESS_PURPOSE,
    ENROLMENT_PURPOSE,
    MSMException,
    MSMStatus,
    MSMTemporalQuery,
    SITE_AUDIENCE,
)
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.configuration import create_test_configuration
from tests.fixtures.factories.secret import create_test_secret
from tests.maasapiserver.fixtures.db import Fixture

TOKEN_ALGORITHM = "HS256"
TOKEN_DURATION = timedelta(minutes=10)


@pytest.fixture(autouse=True)
def patch_maas_uuid_file(mocker, factory):
    mocker.patch(
        "provisioningserver.utils.env.FileBackedValue.get"
    ).return_value = factory.make_UUID()


@pytest.fixture
async def maas_site(fixture: Fixture, factory):
    settings = {
        MAASNameConfig.name: factory.make_name(prefix="maas"),
        MAASUrlConfig.name: factory.make_simple_http_url(path="/MAAS"),
    }
    for name, value in settings.items():
        await create_test_configuration(fixture, name=name, value=value)

    yield settings


@pytest.fixture
def msm_site(factory):
    site = factory.make_simple_http_url(path="/ingress")
    yield site


@pytest.fixture
def msm_enrol_payload(factory, msm_site):
    issued = utcnow()
    expiration = issued + TOKEN_DURATION
    payload = {
        "sub": factory.make_UUID(),
        "iss": msm_site,
        "iat": issued.timestamp(),
        "exp": expiration.timestamp(),
        "aud": SITE_AUDIENCE,
        # private claims
        "purpose": ENROLMENT_PURPOSE,
        "service-url": msm_site,
    }
    yield payload


@pytest.fixture
def jwt_key(factory):
    key = factory.make_bytes(32)
    yield key


@pytest.fixture
async def msm_access(fixture: Fixture, factory, maasdb, msm_site, jwt_key):
    issued = utcnow()
    expiration = issued + TOKEN_DURATION
    payload = {
        "sub": factory.make_UUID(),
        "iss": msm_site,
        "iat": issued.timestamp(),
        "exp": expiration.timestamp(),
        "aud": SITE_AUDIENCE,
        # private claims
        "purpose": ACCESS_PURPOSE,
    }
    secret = {
        "url": urlparse(msm_site)._replace(path="/site/v1/details").geturl(),
        "jwt": jwt.encode(payload, jwt_key, algorithm=TOKEN_ALGORITHM),
        "started": issued.strftime("%a %d %b %Y, %I:%M%p"),
    }

    await create_test_secret(
        fixture, path=MSMConnectorSecret().get_secret_path(), value=secret
    )
    yield secret


@pytest.fixture
async def temporal_client_mock(services: ServiceCollectionV3):
    services.msm.temporal_service = Mock(TemporalService)
    temporal_client_mock = Mock(Client)
    services.msm.temporal_service.get_temporal_client = AsyncMock(
        return_value=temporal_client_mock
    )
    return temporal_client_mock


@pytest.mark.usefixtures("maasdb")
class TestMSMEnrol:
    async def test_enroll(
        self,
        maas_site,
        msm_enrol_payload,
        jwt_key,
        services: ServiceCollectionV3,
        temporal_client_mock: Mock,
    ):
        services.msm.temporal_service.query_workflow = AsyncMock(
            return_value=(False, None)
        )

        encoded = jwt.encode(
            msm_enrol_payload, jwt_key, algorithm=TOKEN_ALGORITHM
        )
        await services.msm.enrol(encoded)
        temporal_client_mock.start_workflow.assert_awaited_once()
        args = temporal_client_mock.start_workflow.call_args
        positional_args = args[0]
        msm_enrol_param = args[1]["arg"]
        assert positional_args[0] == MSM_ENROL_SITE_WORKFLOW_NAME
        assert msm_enrol_param.site_name == maas_site[MAASNameConfig.name]
        assert msm_enrol_param.url == msm_enrol_payload["service-url"]

    async def test_bad_jwt(
        self,
        msm_enrol_payload,
        jwt_key,
        services: ServiceCollectionV3,
        temporal_client_mock: Mock,
    ):
        bad_payload = dict(msm_enrol_payload, aud="bad-audience")
        encoded = jwt.encode(bad_payload, jwt_key, algorithm=TOKEN_ALGORITHM)
        with pytest.raises(MSMException):
            await services.msm.enrol(encoded)
        temporal_client_mock.start_workflow.assert_not_awaited()

    async def test_missing_url(
        self,
        msm_enrol_payload,
        jwt_key,
        services: ServiceCollectionV3,
        temporal_client_mock: Mock,
    ):
        bad_payload = msm_enrol_payload.copy()
        bad_payload.pop("service-url")
        encoded = jwt.encode(bad_payload, jwt_key, algorithm=TOKEN_ALGORITHM)
        with pytest.raises(MSMException):
            await services.msm.enrol(encoded)
        temporal_client_mock.start_workflow.assert_not_awaited()

    async def test_already_enroled(
        self,
        msm_enrol_payload,
        jwt_key,
        services: ServiceCollectionV3,
        temporal_client_mock: Mock,
    ):
        services.msm.get_status = AsyncMock(
            return_value=MSMStatus(
                sm_url="",
                sm_jwt="",
                running=MSMStatusEnum.PENDING,
                start_time=None,
            )
        )
        encoded = jwt.encode(
            msm_enrol_payload, jwt_key, algorithm=TOKEN_ALGORITHM
        )
        with pytest.raises(MSMException):
            await services.msm.enrol(encoded)
        temporal_client_mock.start_workflow.assert_not_awaited()


@pytest.mark.usefixtures("maasdb")
class TestMSMStatus:
    async def test_not_enroled(self, services, temporal_client_mock):
        status = await services.msm.get_status()

        assert status is None
        services.msm.temporal_service.query_workflow.assert_not_awaited()

    async def test_enroled_not_connected(
        self, msm_access, services: ServiceCollectionV3, temporal_client_mock
    ):
        start = utcnow()
        wf_exec = Mock(WorkflowExecutionDescription)
        wf_exec.start_time = start
        services.msm.temporal_service.query_workflow = AsyncMock(
            side_effect=[
                (False, None),  # is_pending
                (False, wf_exec),  # is_running
            ]
        )

        status = await services.msm.get_status()

        assert status is not None
        assert status.sm_url is not None
        assert status.running == MSMStatusEnum.NOT_CONNECTED
        assert status.start_time == start.isoformat()

        services.msm.temporal_service.query_workflow.assert_has_awaits(
            [
                call(
                    f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                    MSMTemporalQuery.IS_PENDING,
                ),
                call(
                    f"{MSM_HEARTBEAT_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                    MSMTemporalQuery.IS_RUNNING,
                ),
            ]
        )

    async def test_enroled_connected(
        self, msm_access, services, temporal_client_mock
    ):
        start = utcnow()
        wf_exec = Mock(WorkflowExecutionDescription)
        wf_exec.start_time = start
        services.msm.temporal_service.query_workflow = AsyncMock(
            side_effect=[
                (False, None),  # is_pending
                (True, wf_exec),  # is_running
            ]
        )

        status = await services.msm.get_status()

        assert status is not None
        assert status.sm_url is not None
        assert status.running == MSMStatusEnum.CONNECTED
        assert status.start_time == start.isoformat()

        services.msm.temporal_service.query_workflow.assert_has_awaits(
            [
                call(
                    f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                    MSMTemporalQuery.IS_PENDING,
                ),
                call(
                    f"{MSM_HEARTBEAT_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                    MSMTemporalQuery.IS_RUNNING,
                ),
            ]
        )


class TestMSMWithdraw:
    async def test_withdraw(self, services, temporal_client_mock):
        expected_url = "http://test-msm.dev"
        secret = {
            "url": expected_url,
        }
        services.msm.secrets_service = Mock(SecretsService)
        services.msm.secrets_service.get_composite_secret = AsyncMock(
            return_value=secret
        )
        services.msm.temporal_service.get_temporal_client = AsyncMock(
            return_value=temporal_client_mock
        )
        services.msm.temporal_service.cancel_workflow = AsyncMock()

        await services.msm.withdraw()

        expected_wf_cancels = [
            f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            f"{MSM_HEARTBEAT_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            f"{MSM_TOKEN_REFRESH_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
        ]
        expected_calls = [call(wf_id) for wf_id in expected_wf_cancels]
        assert (
            services.msm.temporal_service.cancel_workflow.call_args_list
            == expected_calls
        )
        temporal_client_mock.start_workflow.assert_called_once_with(
            MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME,
            arg=MSMRestoreDefaultBootSourceParam(sm_url=secret["url"]),
            id=f"{MSM_RESTORE_DEFAULT_BOOT_SOURCE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            task_queue=REGION_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
