# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Sources."""

__all__ = [
    "get_os_info_from_boot_sources",
]


from temporalio.common import WorkflowIDReusePolicy
from twisted.internet import reactor

from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
)
from maasserver.bootresources import start_workflow
from maasserver.models import BootSource, BootSourceCache
from maasserver.utils.orm import post_commit_do
from maasserver.workflow import REGION_TASK_QUEUE
from provisioningserver.logger import get_maas_logger, LegacyLogger

log = LegacyLogger()
maaslog = get_maas_logger("bootsources")


def get_os_info_from_boot_sources(os):
    """Return sources, list of releases, and list of architectures that exists
    for the given operating system from the `BootSource`'s.

    This pulls the information for BootSourceCache.
    """
    os_sources = []
    releases = set()
    arches = set()
    for source in BootSource.objects.all():
        for cache_item in BootSourceCache.objects.filter(
            boot_source=source, os=os
        ):
            if source not in os_sources:
                os_sources.append(source)
            releases.add(cache_item.release)
            arches.add(cache_item.arch)
    return os_sources, releases, arches


def cache_boot_sources():
    start_workflow(
        FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
        workflow_id="fetch-manifest",
        task_queue=REGION_TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )


def update_boot_source_cache():
    """Update the `BootSourceCache` using the updated source.

    This only begins after a successful commit to the database, and is then
    run in a thread. Nothing waits for its completion.
    """
    post_commit_do(reactor.callLater, 0, cache_boot_sources)
