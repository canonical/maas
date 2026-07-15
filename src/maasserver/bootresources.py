# Copyright 2014-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "ImportResourcesProgressService",
    "is_import_resources_running",
]

from datetime import timedelta
from pathlib import Path
import shutil
from textwrap import dedent

from django.db.models import F
from temporalio.client import WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maascommon.constants import BOOTLOADERS_DIR
from maascommon.workflows.bootresource import (
    FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
    MASTER_IMAGE_SYNC_WORKFLOW_NAME,
)
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
)
from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, COMPONENT
from maasserver.models import (
    BootResource,
    BootResourceFile,
    BootResourceFileSync,
    RegionController,
)
from maasserver.sqlalchemy import service_layer
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.workflow import (
    cancel_workflow,
    execute_workflow,
    start_workflow,
)
from maasservicelayer.utils.image_local_files import (
    get_bootresource_store_path,
)
from provisioningserver.logger import get_maas_logger, LegacyLogger

maaslog = get_maas_logger("bootresources")
log = LegacyLogger()


def import_resources():
    """Starts the master image sync workflow."""

    def _start():
        d = execute_workflow(
            workflow_name=FETCH_MANIFEST_AND_UPDATE_CACHE_WORKFLOW_NAME,
            workflow_id="fetch-manifest",
            id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
        )
        d.addCallback(
            lambda _: start_workflow(
                MASTER_IMAGE_SYNC_WORKFLOW_NAME,
                "master-image-sync",
                id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
            )
        )
        d.addErrback(log.err, "Failure importing boot resources.")
        return d

    reactor.callFromThread(_start)


def is_import_resources_running():
    """Return True if the master image sync workflow is currently running."""
    status = service_layer.services.temporal.workflow_status(
        workflow_id="master-image-sync"
    )
    return status == WorkflowExecutionStatus.RUNNING


def stop_import_resources():
    """Stops the master image sync workflow."""
    running = is_import_resources_running()
    if running:
        cancel_workflow(workflow_id="master-image-sync")


class ImportResourcesProgressService(TimerService):
    """Service to periodically check on the progress of boot imports."""

    def __init__(self, interval=timedelta(minutes=3)):
        super().__init__(interval.total_seconds(), self.try_check_boot_images)

    def try_check_boot_images(self):
        return self.check_boot_images().addErrback(
            log.err, "Failure checking for boot images."
        )

    @inlineCallbacks
    def check_boot_images(self):
        if (
            yield deferToDatabase(self.are_boot_images_available_in_the_region)
        ):
            # The region has boot resources. We are all set
            yield deferToDatabase(self.clear_import_warning)
        else:
            warning = self.warning_has_no_boot_images
            yield deferToDatabase(self.set_import_warning, warning)

    warning_has_no_boot_images = dedent(
        """\
    Boot image import process not started. Machines will not be able to
    provision without boot images. Visit the
    <a href="/MAAS/r/images">boot images</a> page to start the import.
    """
    )

    @transactional
    def clear_import_warning(self):
        discard_persistent_error(COMPONENT.IMPORT_PXE_FILES)

    @transactional
    def set_import_warning(self, warning):
        register_persistent_error(COMPONENT.IMPORT_PXE_FILES, warning)

    @transactional
    def are_boot_images_available_in_the_region(self):
        """Return true if there are boot images available in the region."""
        return BootResource.objects.all().exists()


def initialize_image_storage(region: RegionController):
    """Initialize the image storage

    MUST be called with the `startup` lock
    """
    from provisioningserver.config import ClusterConfiguration

    target_dir = get_bootresource_store_path()
    bootloaders_dir = target_dir / BOOTLOADERS_DIR

    if bootloaders_dir.exists():
        shutil.rmtree(bootloaders_dir)
    bootloaders_dir.mkdir()

    expected_files = {bootloaders_dir}

    with ClusterConfiguration.open() as rack_config:
        expected_files.add(Path(rack_config.tftp_root))

    resources = BootResourceFile.objects.filter(
        bootresourcefilesync__region=region
    ).annotate(
        architecture=F("resource_set__resource__architecture"),
        bootloader_type=F("resource_set__resource__bootloader_type"),
    )

    missing = set()
    for res in resources:
        lfile = res.local_file()
        if lfile.complete:
            expected_files.add(lfile.path)

            if (
                res.filetype == BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ
                and res.bootloader_type
            ):
                arch = res.architecture.split("/")[0]
                target = f"{BOOTLOADERS_DIR}/{res.bootloader_type}/{arch}"
                lfile.extract_file(target)
        else:
            missing.add(res)

    if missing:
        maaslog.warning(
            f"{len(missing)} missing resources need to be downloaded again"
        )
        BootResourceFileSync.objects.filter(
            file__in=missing, region=region
        ).delete()

    # TODO: Modify this when we have a better way to handle custom bootloaders
    # don't delete custom dir, contains custom bootloaders
    existing_files = {
        file
        for file in target_dir.iterdir()
        if file.name not in ("custom", "lost+found")
    }

    for file in existing_files - expected_files:
        maaslog.warning(
            f"removing unexpected {file} file from the image storage"
        )
        if file.is_symlink():
            file.unlink()
        elif file.is_dir():
            shutil.rmtree(file)
        else:
            file.unlink()
