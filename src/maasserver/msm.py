# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
MAAS Site Manager Connector service
"""
import asyncio
import time
from typing import Any

from jose import jwt
from jose.exceptions import JWTClaimsError
from temporalio.common import WorkflowIDReusePolicy

from maasserver.enum import MSM_STATUS
from maasserver.models.config import Config
from maasserver.secrets import SecretManager
from maasserver.utils.orm import with_connection
from maasserver.workflow import cancel_workflow, start_workflow
from maasserver.workflow.worker.worker import get_client_async
from maastemporalworker.workflow.msm import MSM_SECRET, MSMEnrolParam
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.env import MAAS_UUID

_TASK_QUEUE = "region"

maaslog = get_maas_logger("msm")

AUDIENCE = "site"
ENROLMENT = "enrolment"
ACCESS = "access"


class MSMException(Exception):
    """Base exception for MSM Connector."""


@with_connection
def msm_enrol(encoded: str, metainfo: str | None = None) -> str:
    """Send enrolment request.

    Args:
        encoded (str): the enrolment token serialized as a string
        metainfo (str | None, optional): Additional site information. Defaults to None.
    Returns:
        str: the name of this MAAS
    """
    configs: dict[str, str] = Config.objects.get_configs(
        ["maas_name", "maas_url"]
    )
    try:
        claims = jwt.decode(
            encoded,
            None,
            audience=AUDIENCE,
            options={"verify_signature": False},
        )
    except JWTClaimsError as ex:
        raise MSMException(f"invalid JWT: {str(ex)}")

    url = claims.get("enrolment-url", None)
    if not url:
        raise MSMException("missing 'enrolment-url' claim")

    status = msm_status()
    if status:
        match status["running"]:
            case MSM_STATUS.PENDING:
                raise MSMException("This site is already pending approval")
            case MSM_STATUS.CONNECTED:
                raise MSMException(
                    "This site is already enroled to a Site Manager instance"
                )

    param = MSMEnrolParam(
        site_name=configs["maas_name"],
        site_url=configs["maas_url"].rstrip("/").removesuffix("/MAAS"),
        url=url,
        jwt=encoded,
        cluster_uuid=MAAS_UUID.get(),
        metainfo=metainfo,
    )

    start_workflow(
        "msm-enrol-site",
        "msm-enrol-site:region",
        param,
        task_queue=_TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )
    maaslog.info(f"enroling MAAS to Site Manager ({url})")
    error = asyncio.run(_query_enrolment_error())
    timeout = time.time() + 3
    while error is None:
        time.sleep(0.1)
        error = asyncio.run(_query_enrolment_error())
        if time.time() > timeout:
            raise MSMException(
                "Could not verify that the enrolment request was sent successfully"
            )
    if error:
        raise MSMException(
            "Failed to enrol with MAAS Site Manager. "
            f"Got response: HTTP {error['status']}: {error['reason']}"
        )
    return configs["maas_name"]


def msm_withdraw() -> None:
    """Withdraw from MSM."""
    cancel_workflow("msm-enrol-site:region")
    # raise MSMException("not implemented")


async def _query_workflow():
    temporal_client = await get_client_async()
    hdl = temporal_client.get_workflow_handle(
        workflow_id="msm-heartbeat:region"
    )
    try:
        running = await hdl.query("is-running")
        desc = await hdl.describe()
        start = desc.start_time
        return running, start
    except Exception:
        return None, None


async def _query_pending():
    temporal_client = await get_client_async()
    hdl = temporal_client.get_workflow_handle(
        workflow_id="msm-enrol-site:region"
    )
    try:
        pending = await hdl.query("is-pending")
        desc = await hdl.describe()
        start = desc.start_time
        return pending, start
    except Exception:
        return None, None


async def _query_enrolment_error():
    temporal_client = await get_client_async()
    hdl = temporal_client.get_workflow_handle(
        workflow_id="msm-enrol-site:region"
    )
    try:
        return await hdl.query("enrolment-error")
    except Exception:
        return {}


@with_connection
def msm_status() -> dict[str, Any]:
    """Get MSM connection status."""
    msm_creds = SecretManager().get_composite_secret(MSM_SECRET, default=None)
    if not msm_creds:
        return {}

    pending, start = asyncio.run(_query_pending())
    if pending:
        return {
            "sm-url": msm_creds["url"],
            "running": MSM_STATUS.PENDING,
            "start-time": start.isoformat() if start else None,
        }

    running, start = asyncio.run(_query_workflow())
    if running:
        return {
            "sm-url": msm_creds["url"],
            "running": MSM_STATUS.CONNECTED,
            "start-time": start.isoformat() if start else None,
        }

    return {
        "sm-url": msm_creds["url"],
        "running": MSM_STATUS.NOT_CONNECTED,
        "start-time": start.isoformat() if start else None,
    }
