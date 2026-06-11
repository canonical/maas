# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Sources."""

from temporalio.common import WorkflowIDReusePolicy
from twisted.internet import reactor

from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
)
from maasserver.bootresources import start_workflow
from maasserver.utils.orm import post_commit_do
from maasserver.workflow import REGION_TASK_QUEUE
from provisioningserver.logger import get_maas_logger, LegacyLogger

log = LegacyLogger()
maaslog = get_maas_logger("bootsources")


def cache_boot_sources(boot_source_id: int | None = None):
    workflow_id = "fetch-manifest"
    if boot_source_id is not None:
        workflow_id += f"-{boot_source_id}"
    start_workflow(
        FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
        workflow_id=workflow_id,
        param=boot_source_id,
        task_queue=REGION_TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )


def update_boot_source_cache(boot_source_id: int | None = None):
    """Update the `BootSourceCache` using the updated source.

    This only begins after a successful commit to the database, and is then
    run in a thread. Nothing waits for its completion.

    Args:
        boot_source_id (int | None): if specified, updates the cache only for this
            specific boot source
    """
    post_commit_do(reactor.callLater, 0, cache_boot_sources, boot_source_id)
