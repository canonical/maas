# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
MAAS Site Manager Connector service
"""
import asyncio
from typing import Any

from jose import jwt
from jose.exceptions import JWTClaimsError
from temporalio.common import WorkflowIDReusePolicy

from maasserver.models.config import Config
from maasserver.secrets import SecretManager
from maasserver.utils.orm import with_connection
from maasserver.workflow import cancel_workflow, start_workflow
from maasserver.workflow.worker.worker import get_client_async
from maastemporalworker.workflow.msm import MSM_SECRET, MSMEnrolParam
from provisioningserver.logger import get_maas_logger

_TASK_QUEUE = "region"

maaslog = get_maas_logger("msm")

AUDIENCE = "site"
ENROLMENT = "enrolment"
ACCESS = "access"


class MSMException(Exception):
    """Base exception for MSM Connector."""


@with_connection
def msm_enrol(encoded: str, metainfo: str | None = None) -> None:
    """Send enrolment request.

    Args:
        encoded (str): the enrolment token serialized as a string
        metainfo (str | None, optional): Additional site information. Defaults to None.
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

    param = MSMEnrolParam(
        site_name=configs["maas_name"],
        site_url=configs["maas_url"].rstrip("/").removesuffix("/MAAS"),
        url=url,
        jwt=encoded,
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


@with_connection
def msm_status() -> dict[str, Any]:
    """Get MSM connection status."""
    msm_creds = SecretManager().get_composite_secret(MSM_SECRET, default=None)
    if not msm_creds:
        return {}

    running, start = asyncio.run(_query_workflow())
    return {
        "sm-url": msm_creds["url"],
        "running": bool(running),
        "start-time": start.isoformat() if start else None,
    }
