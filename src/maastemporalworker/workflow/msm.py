# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
MAAS Site Manager Connector workflows
"""

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from aiohttp import ClientSession, ClientTimeout
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
import yaml

from maasapiserver.common.db import Database
from maastemporalworker.workflow.activity import ActivityBase

HEARTBEAT_TIMEOUT = timedelta(seconds=10)
MSM_TIMEOUT = timedelta(minutes=15)
MSM_POLL_INTERVAL = timedelta(minutes=1)
MSM_SECRET = "msm-connector"


@dataclass
class MSMEnrolParam:
    site_name: str
    site_url: str
    url: str
    jwt: str
    metainfo: str | None = None


@dataclass
class MSMConnectorParam:
    url: str
    jwt: str


@dataclass
class MSMHeartbeatParam:
    jwt: str
    interval: int


class MSMConnectorActivity(ActivityBase):
    def __init__(
        self, db: Database, connection: AsyncConnection | None = None
    ):
        super().__init__(db, connection)
        self._session = self._create_session()

    def _create_session(self) -> ClientSession:
        timeout = ClientTimeout(total=60 * 60, sock_read=120)
        return ClientSession(trust_env=True, timeout=timeout)

    @activity.defn(name="msm-send-enrol")
    async def send_enrol(self, input: MSMEnrolParam) -> bool:
        """Send enrolment request.

        Args:
            input (MSMEnrolParam): Enrolment parameters

        Returns:
            bool: whether the request was successful
        """
        activity.logger.debug(f"attempting to enrol to {input.url}")
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        data = {
            "name": input.site_name,
            "url": input.site_url,
            **(yaml.safe_load(input.metainfo) if input.metainfo else {}),
        }

        async with self._session.post(
            input.url, json=data, headers=headers
        ) as response:
            match response.status:
                case 404:
                    activity.logger.error(
                        "Enrolment cancelled by MSM, aborting"
                    )
                    return False
                case 202:
                    return True
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )

    @activity.defn(name="msm-check-enrol")
    async def check_enrol(self, input: MSMEnrolParam) -> str | None:
        """Check the enrolment status.

        Args:
            input (MSMEnrolParam): Enrolment parameters

        Returns:
            str: a new JWT if the enrolment was completed
        """
        headers = {
            "Authorization": f"bearer {input.jwt}",
        }
        async with self._session.get(input.url, headers=headers) as response:
            match response.status:
                case 204:
                    raise ApplicationError("waiting for MSM enrolment")
                case 200:
                    data = await response.json()
                    return data["access_token"]
                case 404:
                    activity.logger.error(
                        "Enrolment cancelled by MSM, aborting"
                    )
                    return None
                case _:
                    raise ApplicationError(
                        f"got unexpected return code: HTTP {response.status}"
                    )

    @activity.defn(name="msm-set-enrol")
    async def set_enrol(self, input: MSMConnectorParam) -> None:
        """Set enrolment data in the DB.

        Args:
            input (MSMConnectorParam): MSM connection data
        """
        from maasapiserver.v3.db.secrets import SecretsRepository

        async with self.start_transaction() as tx:
            # TODO add Vault support
            repo = SecretsRepository(tx)
            await repo.create_or_update(
                f"global/{MSM_SECRET}", {"url": input.url, "jwt": input.jwt}
            )

    @activity.defn(name="msm-send-heartbeat")
    async def send_heartbeat(self, input: MSMHeartbeatParam) -> int:
        """Send heartbeat data to MSM.

        Args:
            input (MSMHeartbeatParam): MSM heartbeat data

        Returns:
            int: interval for the next update
        """
        return 0


@workflow.defn(name="msm-enrol-site", sandboxed=False)
class MSMEnrolSiteWorkflow:
    """Enrol this site to MSM."""

    def __init__(self) -> None:
        self._pending = False

    @workflow.run
    async def run(self, input: MSMEnrolParam) -> None:
        """Run workflow.

        Args:
            input (MSMEnrolParam): Enrolment data
        """
        workflow.logger.info(f"enrolling to {input.url}")
        self._pending = True

        if not await workflow.execute_activity(
            "msm-send-enrol",
            input,
            start_to_close_timeout=MSM_TIMEOUT,
        ):
            self._pending = False
            workflow.logger.error(f"failed to enrol to {input.url}, aborting")
            return

        new_jwt = await workflow.execute_activity(
            "msm-check-enrol",
            input,
            start_to_close_timeout=MSM_TIMEOUT,
            retry_policy=RetryPolicy(
                backoff_coefficient=1.0,
                initial_interval=MSM_POLL_INTERVAL,
            ),
        )
        if new_jwt is None:
            self._pending = False
            workflow.logger.error("enrolment cancelled by MSM")
            return

        new_url = (
            urlparse(input.url)._replace(path="/site/v1/details").geturl()
        )
        param = MSMConnectorParam(
            url=new_url,
            jwt=new_jwt,
        )
        await workflow.execute_activity(
            "msm-set-enrol",
            param,
            start_to_close_timeout=MSM_TIMEOUT,
        )
        self._pending = False

        # TODO schedule heartbeat

    @workflow.query(name="is-pending")
    def is_pending(self) -> bool:
        return self._pending


@workflow.defn(name="msm-withdraw", sandboxed=False)
class MSMWithdrawWorkflow:
    """Withdraw this site from MSM."""

    @workflow.run
    async def run(self, input: MSMConnectorParam) -> None:
        """Run workflow.

        Args:
            input (MSMConnectorParam): Withdraw data
        """


@workflow.defn(name="msm-heartbeat", sandboxed=False)
class MSMHeartbeatWorkflow:
    """Send periodic heartbeats to MSM."""

    @workflow.run
    async def run(self, input: MSMHeartbeatParam) -> None:
        """Run workflow.

        Args:
            input (MSMHeartbeatParam): Heartbeat data
        """

    @workflow.query(name="is-running")
    def is_running(self) -> bool:
        # FIXME
        return True
