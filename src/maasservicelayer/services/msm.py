# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from dataclasses import dataclass
from enum import StrEnum

from jose import jwt
from jose.exceptions import JWTClaimsError
import structlog
from temporalio.common import WorkflowIDReusePolicy

from maascommon.enums.msm import MSMStatusEnum
from maascommon.workflows.msm import (
    MSM_ENROL_SITE_WORKFLOW_NAME,
    MSM_HEARTBEAT_WORKFLOW_NAME,
    MSMEnrolParam,
)
from maasservicelayer.context import Context
from maasservicelayer.models.configurations import (
    MAASNameConfig,
    MAASUrlConfig,
)
from maasservicelayer.models.secrets import MSMConnectorSecret
from maasservicelayer.services.base import Service, ServiceCache
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.secrets import SecretsService
from maasservicelayer.services.temporal import TemporalService
from maastemporalworker.worker import REGION_TASK_QUEUE
from provisioningserver.utils.env import MAAS_UUID

logger = structlog.get_logger()

SITE_AUDIENCE = "site"
ENROLMENT_PURPOSE = "enrolment"
ACCESS_PURPOSE = "access"


class MSMException(Exception):
    """Base exception for MSM Connector."""


class MSMTemporalQuery(StrEnum):
    IS_PENDING = "is-pending"
    IS_RUNNING = "is-running"
    ENROLMENT_ERROR = "enrolment-error"


@dataclass
class MSMStatus:
    sm_url: str
    running: MSMStatusEnum
    start_time: str | None


class MSMService(Service):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        config_service: ConfigurationsService,
        secrets_service: SecretsService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, cache)
        self.temporal_service = temporal_service
        self.config_service = config_service
        self.secrets_service = secrets_service

    async def enrol(self, encoded: str, metainfo: str | None = None) -> str:
        """Send enrolment request.

        Args:
            encoded (str): the enrolment token serialized as a string
            metainfo (str | None, optional): Additional site information. Defaults to None.
        Returns:
            str: the name of this MAAS
        """
        maas_name = await self.config_service.get(MAASNameConfig.name)
        maas_url = await self.config_service.get(MAASUrlConfig.name)
        try:
            claims = jwt.decode(
                encoded,
                key="",  # empty key since we are not verifying the signature
                audience=SITE_AUDIENCE,
                options={"verify_signature": False},
            )
        except JWTClaimsError as ex:
            raise MSMException(f"invalid JWT: {str(ex)}") from ex

        url = claims.get("service-url", None)
        if not url:
            raise MSMException("missing 'service-url' claim")

        status = await self.get_status()
        if status:
            match status.running:
                case MSMStatusEnum.PENDING:
                    raise MSMException("This site is already pending approval")
                case MSMStatusEnum.CONNECTED:
                    raise MSMException(
                        "This site is already enroled to a Site Manager instance"
                    )

        maas_uuid = MAAS_UUID.get()
        assert maas_uuid is not None

        param = MSMEnrolParam(
            site_name=maas_name,
            site_url=maas_url.rstrip("/").removesuffix("/MAAS"),
            url=url,
            jwt=encoded,
            cluster_uuid=maas_uuid,
            metainfo=metainfo,
        )

        # get the client from the temporal service to not expose a `start_workflow`
        # method in the temporal service. That would confuse us on how to use the
        # temporal service.
        client = await self.temporal_service.get_temporal_client()
        await client.start_workflow(
            MSM_ENROL_SITE_WORKFLOW_NAME,
            arg=param,
            id=f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            task_queue=REGION_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )

        logger.info(f"enroling MAAS to Site Manager ({url})")

        async def query_for_enrolment_error():
            while True:
                error, _ = await self.temporal_service.query_workflow(
                    f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
                    MSMTemporalQuery.ENROLMENT_ERROR,
                )
                if error is not None:
                    return error
                await asyncio.sleep(0.1)

        try:
            error = await asyncio.wait_for(
                query_for_enrolment_error(), timeout=30.0
            )
            if error:
                raise MSMException(
                    "Failed to enrol with MAAS Site Manager. "
                    f"Got response: HTTP {error['status']}: {error['reason']}"
                )
        except asyncio.TimeoutError as err:
            raise MSMException(
                "Could not verify that the enrolment request was sent successfully"
            ) from err

        return maas_name

    async def get_status(self) -> MSMStatus | None:
        msm_creds = await self.secrets_service.get_composite_secret(
            MSMConnectorSecret(), default=None
        )
        if not msm_creds:
            return None

        pending, description = await self.temporal_service.query_workflow(
            f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            MSMTemporalQuery.IS_PENDING,
        )

        if pending:
            return MSMStatus(
                sm_url=msm_creds["url"],
                running=MSMStatusEnum.PENDING,
                start_time=description.start_time.isoformat()
                if description
                else None,
            )

        running, description = await self.temporal_service.query_workflow(
            f"{MSM_HEARTBEAT_WORKFLOW_NAME}:{REGION_TASK_QUEUE}",
            MSMTemporalQuery.IS_RUNNING,
        )
        if running:
            return MSMStatus(
                sm_url=msm_creds["url"],
                running=MSMStatusEnum.CONNECTED,
                start_time=description.start_time.isoformat()
                if description
                else None,
            )
        return MSMStatus(
            sm_url=msm_creds["url"],
            running=MSMStatusEnum.NOT_CONNECTED,
            start_time=description.start_time.isoformat()
            if description
            else None,
        )

    async def withdraw(self) -> None:
        await self.temporal_service.cancel_workflow(
            f"{MSM_ENROL_SITE_WORKFLOW_NAME}:{REGION_TASK_QUEUE}"
        )
