# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
MAAS Site Manager Connector workflows
"""

import asyncio
import dataclasses
from datetime import timedelta
import ssl
from typing import Any

from aiohttp import ClientSession, ClientTimeout, FormData, TCPConnector
from sqlalchemy.ext.asyncio import AsyncConnection
import structlog
from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError
from temporalio.workflow import ParentClosePolicy
import yaml

from apiclient.maas_client import MAASOAuth
from maascommon.constants import SYSTEM_CA_FILE
from maascommon.workflows.msm import (
    MachinesCountByStatus,
    MSM_ENROL_SITE_WORKFLOW_NAME,
    MSM_HEARTBEAT_WORKFLOW_NAME,
    MSM_TOKEN_REFRESH_WORKFLOW_NAME,
    MSM_WITHDRAW_WORKFLOW_NAME,
    MSMConnectorParam,
    MSMDeleteBootSourcesParam,
    MSMEnrolParam,
    MSMHeartbeatParam,
    MSMSetBootSourceParam,
    MSMTokenRefreshParam,
)
from maasservicelayer.db import Database
from maasservicelayer.models.secrets import MSMConnectorSecret
from maasservicelayer.services import CacheForServices
from maastemporalworker.workflow.activity import ActivityBase
from maastemporalworker.workflow.utils import (
    activity_defn_with_context,
    workflow_run_with_context,
)

logger = structlog.getLogger()

HEARTBEAT_TIMEOUT = timedelta(seconds=10)
MSM_TIMEOUT = timedelta(minutes=15)
MSM_REFRESH_RETRY_INTERVAL = timedelta(minutes=1)
MSM_POLL_INTERVAL = timedelta(minutes=1)
MSM_SECRET = "msm-connector"

MSM_ENROL_EP = "/site/v1/enroll"
MSM_DETAIL_EP = "/site/v1/details"
MSM_REFRESH_EP = "/site/v1/enroll/refresh"
MSM_VERIFY_EP = "/site/v1/enroll/verify"
MSM_SS_EP = "/api/v1/images/latest/stable/streams/v1/index.json"

# Activities names
MSM_CHECK_ENROL_ACTIVITY_NAME = "msm-check-enrol"
MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME = "msm-get-token-refresh"
MSM_SET_ENROL_ACTIVITY_NAME = "msm-set-enrol"
MSM_VERIFY_TOKEN_ACTIVITY_NAME = "msm-verify-token"
MSM_GET_ENROL_ACTIVITY_NAME = "msm-get-enrol"
MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME = "msm-get-heartbeat-data"
MSM_SEND_HEARTBEAT_ACTIVITY_NAME = "msm-send-heartbeat"
MSM_SEND_ENROL_ACTIVITY_NAME = "msm-send-enrol"
MSM_SET_BOOT_SOURCE_ACTIVITY_NAME = "msm-set-bootsource"
MSM_GET_BOOT_SOURCES_ACTIVITY_NAME = "msm-get-bootsources"
MSM_DELETE_BOOT_SOURCES_ACTIVITY_NAME = "msm-delete-bootsources"


# Activities parameters
@dataclasses.dataclass
class MSMTokenVerifyParam:
    sm_url: str
    jwt: str


class MSMConnectorActivity(ActivityBase):
    MSM_CONNECTOR_SECRET = MSMConnectorSecret()

    def __init__(
        self,
        db: Database,
        services_cache: CacheForServices,
        connection: AsyncConnection | None = None,
    ):
        super().__init__(db, services_cache, connection)
        self._session = self._create_session()

    def _create_session(self) -> ClientSession:
        timeout = ClientTimeout(total=60 * 60, sock_read=120)
        context = ssl.create_default_context(cafile=SYSTEM_CA_FILE)
        tcp_conn = TCPConnector(ssl=context)
        return ClientSession(
            trust_env=True, timeout=timeout, connector=tcp_conn
        )

    @activity_defn_with_context(name=MSM_SEND_ENROL_ACTIVITY_NAME)
    async def send_enrol(
        self, input: MSMEnrolParam
    ) -> tuple[bool, dict[str, Any] | None]:
        """Send enrolment request.

        Args:
            input (MSMEnrolParam): Enrolment parameters

        Returns:
            bool: whether the request was successful
        """
        logger.debug(f"attempting to enrol to {input.url}")
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        data = {
            "name": input.site_name,
            "url": input.site_url,
            "cluster_uuid": input.cluster_uuid,
            **(yaml.safe_load(input.metainfo) if input.metainfo else {}),
        }

        enrolment_url = input.url + MSM_ENROL_EP

        async with self._session.post(
            enrolment_url, json=data, headers=headers
        ) as response:
            match response.status:
                case 404:
                    logger.error("Enrolment URL not found, aborting")
                    return (
                        False,
                        {
                            "status": response.status,
                            "reason": response.reason,
                        },
                    )
                case 202:
                    return (True, None)
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )

    @activity_defn_with_context(name=MSM_CHECK_ENROL_ACTIVITY_NAME)
    async def check_enrol(
        self, input: MSMEnrolParam
    ) -> tuple[str | None, int]:
        """Check the enrolment status.

        Args:
            input (MSMEnrolParam): Enrolment parameters

        Returns:
            tuple[str,int]:
                - a new JWT if the enrolment was completed
                - the token refresh interval in minutes
        """
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        enrolment_url = input.url + MSM_ENROL_EP
        async with self._session.get(
            enrolment_url, headers=headers
        ) as response:
            match response.status:
                case 204:
                    raise ApplicationError("waiting for MSM enrolment")
                case 200:
                    data = await response.json()
                    return (
                        data["access_token"],
                        data["rotation_interval_minutes"],
                    )
                case 401 | 404:
                    logger.error("Enrolment cancelled by MSM, aborting")
                    return (None, -1)
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )

    @activity_defn_with_context(name=MSM_VERIFY_TOKEN_ACTIVITY_NAME)
    async def verify_token(self, input: MSMTokenVerifyParam) -> bool:
        """Notify MSM that the new token was successfully installed.

        Args:
            input (MSMTokenVerifyParam): Token parameters

        Returns:
            bool: whether the new token is valid
        """
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        verify_url = input.sm_url + MSM_VERIFY_EP

        async with self._session.get(verify_url, headers=headers) as response:
            match response.status:
                case 200:
                    return True
                case 401 | 404:
                    logger.error("Failed to verify token")
                    return False
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )

    @activity_defn_with_context(name=MSM_SET_ENROL_ACTIVITY_NAME)
    async def set_enrol(self, input: MSMConnectorParam) -> None:
        """Set enrolment data in the DB.

        Args:
            input (MSMConnectorParam): MSM connection data
        """

        async with self.start_transaction() as services:
            await services.secrets.set_composite_secret(
                self.MSM_CONNECTOR_SECRET,
                {
                    "url": input.url,
                    "jwt": input.jwt,
                    "rotation_interval_minutes": input.rotation_interval_minutes,
                },
            )

    @activity_defn_with_context(name=MSM_GET_BOOT_SOURCES_ACTIVITY_NAME)
    async def get_bootsources(self) -> list[int]:
        """Get Boot Sources that existed before enrollment."""
        async with self.start_transaction() as services:
            api_key = await services.users.get_MAAS_user_apikey()
            key, token, secret = api_key.split(":")
            oauth = MAASOAuth(key, token, secret)
            maas_base_url = await services.configurations.get("maas_url")
            maas_url = f"{maas_base_url}/api/2.0/boot-sources/"
            headers = {}
            oauth.sign_request(maas_url, headers)
            async with self._session.get(
                maas_url, headers=headers
            ) as response:
                body = await response.text()
                if response.status != 200:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}, {body}"
                    )
                boot_sources = await response.json()
                return [bs["id"] for bs in boot_sources]

    @activity_defn_with_context(name=MSM_DELETE_BOOT_SOURCES_ACTIVITY_NAME)
    async def delete_bootsources(
        self, input: MSMDeleteBootSourcesParam
    ) -> None:
        """Delete old boot sources.

        Args:
            input (MSMDeleteBootSourcesParam): list of IDs to delete
        """
        async with self.start_transaction() as services:
            api_key = await services.users.get_MAAS_user_apikey()
            key, token, secret = api_key.split(":")
            oauth = MAASOAuth(key, token, secret)
            maas_base_url = await services.configurations.get("maas_url")
            for id in input.ids:
                maas_url = f"{maas_base_url}/api/2.0/boot-sources/{id}/"
                headers = {}
                oauth.sign_request(maas_url, headers)
                async with self._session.delete(
                    maas_url, headers=headers
                ) as response:
                    if response.status != 204:
                        body = await response.text()
                        raise ApplicationError(
                            f"got unexpected return code: HTTP {response.status}, {body}"
                        )

    @activity_defn_with_context(name=MSM_SET_BOOT_SOURCE_ACTIVITY_NAME)
    async def set_bootsource(self, input: MSMSetBootSourceParam) -> None:
        async with self.start_transaction() as services:
            api_key = await services.users.get_MAAS_user_apikey()
            key, token, secret = api_key.split(":")
            oauth = MAASOAuth(key, token, secret)
            maas_base_url = await services.configurations.get("maas_url")
            maas_url = f"{maas_base_url}/api/2.0/boot-sources/"
            headers = {}
            oauth.sign_request(maas_url, headers)
            data = {
                "url": input.sm_url + MSM_SS_EP,
                "keyring_data": b" ",
            }
            form_data = FormData()
            for key, value in data.items():
                form_data.add_field(name=key, value=value)
            async with self._session.post(
                maas_url, data=form_data, headers=headers
            ) as response:
                if response.status != 201:
                    body = await response.text()
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}, {body}"
                    )

    @activity_defn_with_context(name=MSM_GET_ENROL_ACTIVITY_NAME)
    async def get_enrol(self) -> dict[str, Any]:
        """Get enrolment data in the DB.

        Args:
            input (MSMConnectorParam): MSM connection data
        """
        async with self.start_transaction() as services:
            return await services.secrets.get_composite_secret(
                self.MSM_CONNECTOR_SECRET
            )

    @activity_defn_with_context(name=MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME)
    async def get_heartbeat_data(self) -> MachinesCountByStatus:
        """Get heartbeat data from MAAS DB

        Returns:
            MachinesCountByStatus: machine counters
        """
        async with self.start_transaction() as services:
            return await services.machines.count_machines_by_statuses()

    @activity_defn_with_context(name=MSM_SEND_HEARTBEAT_ACTIVITY_NAME)
    async def send_heartbeat(self, input: MSMHeartbeatParam) -> int:
        """Send heartbeat data to MSM.

        Args:
            input (MSMHeartbeatParam): MSM heartbeat data

        Returns:
            int: interval for the next update
        """
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        data = {
            "name": input.site_name,
            "url": input.site_url,
            "machines_by_status": dataclasses.asdict(input.status),
        }

        heartbeat_url = input.sm_url + MSM_DETAIL_EP

        async with self._session.post(
            heartbeat_url, json=data, headers=headers
        ) as response:
            match response.status:
                case 200:
                    return int(
                        response.headers["MSM-Heartbeat-Interval-Seconds"]
                    )
                case 401 | 404:
                    logger.error("Enrolment cancelled by MSM, aborting")
                    return -1
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )

    @activity_defn_with_context(name=MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME)
    async def refresh_token(
        self, input: MSMTokenRefreshParam
    ) -> tuple[str | None, int]:
        """Refresh the JWT.

        Args:
            input (MSMTokenRefreshParam): includes the current JWT and refresh URL

        Returns:
            tuple[str | None, int]: the new JWT and rotation interval if
            successful. None, -1 if not
        """
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        refresh_url = input.sm_url + MSM_REFRESH_EP
        async with self._session.get(refresh_url, headers=headers) as response:
            match response.status:
                case 200:
                    data = await response.json()
                    return (
                        data["access_token"],
                        data["rotation_interval_minutes"],
                    )
                case 401 | 404:
                    logger.error("Enrolment cancelled by MSM, aborting")
                    return (None, -1)
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )


@workflow.defn(name=MSM_ENROL_SITE_WORKFLOW_NAME, sandboxed=False)
class MSMEnrolSiteWorkflow:
    """Enrol this site to MSM."""

    def __init__(self) -> None:
        self._pending = False
        self._enrolment_error = None

    @workflow_run_with_context
    async def run(self, input: MSMEnrolParam) -> None:
        """Run workflow.

        Args:
            input (MSMEnrolParam): Enrolment data
        """
        # sanitize URL
        if input.url.endswith("/"):
            input.url = input.url[:-1]

        logger.info(f"enrolling to {input.url}")
        self._pending = True
        (sent, error) = await workflow.execute_activity(
            MSM_SEND_ENROL_ACTIVITY_NAME,
            input,
            start_to_close_timeout=MSM_TIMEOUT,
        )
        if not sent:
            self._pending = False
            self._enrolment_error = error
            logger.error(f"failed to enrol to {input.url}, aborting")
            return
        else:
            # important we set this to {} instead of None so
            # the CLI command knows when the request was sent
            # without error
            self._enrolment_error = {}

        param = MSMConnectorParam(
            url=input.url,
            jwt=input.jwt,
        )
        await workflow.execute_activity(
            MSM_SET_ENROL_ACTIVITY_NAME,
            param,
            start_to_close_timeout=MSM_TIMEOUT,
        )

        (new_jwt, rotation_interval_minutes) = await workflow.execute_activity(
            MSM_CHECK_ENROL_ACTIVITY_NAME,
            input,
            start_to_close_timeout=MSM_TIMEOUT,
            retry_policy=RetryPolicy(
                backoff_coefficient=1.0,
                initial_interval=MSM_POLL_INTERVAL,
            ),
        )
        if new_jwt is None:
            self._pending = False
            logger.error("enrolment cancelled by MSM")
            return

        param.jwt = new_jwt
        param.rotation_interval_minutes = rotation_interval_minutes

        await workflow.execute_activity(
            MSM_SET_ENROL_ACTIVITY_NAME,
            param,
            start_to_close_timeout=MSM_TIMEOUT,
        )

        await workflow.execute_activity(
            MSM_VERIFY_TOKEN_ACTIVITY_NAME,
            MSMTokenVerifyParam(
                sm_url=param.url,
                jwt=new_jwt,
            ),
            start_to_close_timeout=MSM_TIMEOUT,
        )

        current_boot_sources = await workflow.execute_activity(
            MSM_GET_BOOT_SOURCES_ACTIVITY_NAME,
            start_to_close_timeout=MSM_TIMEOUT,
        )

        await workflow.execute_activity(
            MSM_SET_BOOT_SOURCE_ACTIVITY_NAME,
            MSMSetBootSourceParam(
                sm_url=param.url,
            ),
            start_to_close_timeout=MSM_TIMEOUT,
        )

        await workflow.execute_activity(
            MSM_DELETE_BOOT_SOURCES_ACTIVITY_NAME,
            MSMDeleteBootSourcesParam(ids=current_boot_sources),
            start_to_close_timeout=MSM_TIMEOUT,
        )

        await workflow.start_child_workflow(
            MSM_HEARTBEAT_WORKFLOW_NAME,
            MSMHeartbeatParam(
                sm_url=param.url,
                jwt=new_jwt,
                site_name=input.site_name,
                site_url=input.site_url,
                rotation_interval_minutes=rotation_interval_minutes,
            ),
            id="msm-heartbeat:region",
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            parent_close_policy=ParentClosePolicy.ABANDON,
        )
        await workflow.start_child_workflow(
            MSM_TOKEN_REFRESH_WORKFLOW_NAME,
            MSMTokenRefreshParam(
                sm_url=param.url,
                jwt=new_jwt,
                rotation_interval_minutes=rotation_interval_minutes,
            ),
            id="msm-token-refresh:region",
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            parent_close_policy=ParentClosePolicy.ABANDON,
        )

        self._pending = False

    @workflow.query(name="is-pending")
    def is_pending(self) -> bool:
        return self._pending

    @workflow.query(name="enrolment-error")
    def enrolment_error(self) -> dict[str, Any] | None:
        return self._enrolment_error


@workflow.defn(name=MSM_WITHDRAW_WORKFLOW_NAME, sandboxed=False)
class MSMWithdrawWorkflow:
    """Withdraw this site from MSM."""

    @workflow_run_with_context
    async def run(self, input: MSMConnectorParam) -> None:
        """Run workflow.

        Args:
            input (MSMConnectorParam): Withdraw data
        """


@workflow.defn(name=MSM_HEARTBEAT_WORKFLOW_NAME, sandboxed=False)
class MSMHeartbeatWorkflow:
    """Send periodic heartbeats to MSM."""

    def __init__(self) -> None:
        self._running = False

    @workflow_run_with_context
    async def run(self, input: MSMHeartbeatParam) -> None:
        """Run workflow.

        Args:
            input (MSMHeartbeatParam): Heartbeat data
        """
        self._running = True
        next_update = 0
        while next_update >= 0:
            secret = await workflow.execute_activity(
                MSM_GET_ENROL_ACTIVITY_NAME,
                start_to_close_timeout=MSM_TIMEOUT,
            )
            data = await workflow.execute_activity(
                MSM_GET_HEARTBEAT_DATA_ACTIVITY_NAME,
                start_to_close_timeout=MSM_TIMEOUT,
            )
            next_update = await workflow.execute_activity(
                MSM_SEND_HEARTBEAT_ACTIVITY_NAME,
                dataclasses.replace(input, status=data, jwt=secret["jwt"]),
                start_to_close_timeout=MSM_TIMEOUT,
                retry_policy=RetryPolicy(
                    backoff_coefficient=1.0,
                    initial_interval=timedelta(seconds=next_update),
                ),
            )
            logger.debug(f"next refresh in {next_update} seconds")
            if next_update > 0:
                await asyncio.sleep(next_update)
        self._running = False

    @workflow.query(name="is-running")
    def is_running(self) -> bool:
        return self._running


@workflow.defn(name=MSM_TOKEN_REFRESH_WORKFLOW_NAME, sandboxed=False)
class MSMTokenRefreshWorkflow:
    """Retrieve a new JWT from MSM."""

    @workflow_run_with_context
    async def run(self, input: MSMTokenRefreshParam) -> None:
        next_refresh = input.rotation_interval_minutes * 60
        while next_refresh >= 0:
            if next_refresh > 0:
                await asyncio.sleep(next_refresh)
            (
                new_token,
                rotation_interval_minutes,
            ) = await workflow.execute_activity(
                MSM_GET_TOKEN_REFRESH_ACTIVITY_NAME,
                input,
                start_to_close_timeout=MSM_TIMEOUT,
                retry_policy=RetryPolicy(
                    backoff_coefficient=1.0,
                    initial_interval=MSM_REFRESH_RETRY_INTERVAL,
                ),
            )
            if new_token is None:
                break
            input.jwt = new_token
            next_refresh = rotation_interval_minutes * 60
            param = MSMConnectorParam(
                url=input.sm_url,
                jwt=new_token,
                rotation_interval_minutes=rotation_interval_minutes,
            )
            await workflow.execute_activity(
                MSM_SET_ENROL_ACTIVITY_NAME,
                param,
                start_to_close_timeout=MSM_TIMEOUT,
            )
            await workflow.execute_activity(
                MSM_VERIFY_TOKEN_ACTIVITY_NAME,
                MSMTokenVerifyParam(
                    sm_url=input.sm_url,
                    jwt=new_token,
                ),
                start_to_close_timeout=MSM_TIMEOUT,
            )
