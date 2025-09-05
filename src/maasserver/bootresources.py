# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "ImportResourcesProgressService",
    "ImportResourcesService",
    "is_import_resources_running",
]

from datetime import timedelta
from pathlib import Path
import shutil
from textwrap import dedent

from django.db import connection, transaction
from django.db.models import F
from temporalio.client import WorkflowExecutionStatus
from temporalio.common import WorkflowIDReusePolicy
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks

from maascommon.constants import (
    BOOTLOADERS_DIR,
    IMPORT_RESOURCES_SERVICE_PERIOD,
)
from maascommon.workflows.bootresource import (
    MASTER_IMAGE_SYNC_WORKFLOW_NAME,
    SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME,
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
    BootResourceSet,
    Config,
    RegionController,
)
from maasserver.sqlalchemy import service_layer
from maasserver.utils import absolute_reverse
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.workflow import (
    cancel_workflow,
    cancel_workflows_of_type,
    start_workflow,
)
from maasservicelayer.utils.image_local_files import (
    get_bootresource_store_path,
)
from provisioningserver.config import is_dev_environment
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.path import get_maas_lock_path

maaslog = get_maas_logger("bootresources")
log = LegacyLogger()


def import_resources():
    """Starts the master image sync workflow."""
    start_workflow(
        MASTER_IMAGE_SYNC_WORKFLOW_NAME,
        "master-image-sync",
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )


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
        cancel_workflows_of_type(
            workflow_type=SYNC_REMOTE_BOOTRESOURCES_WORKFLOW_NAME
        )


class ImportResourcesService(TimerService):
    """Service to periodically import boot resources.

    This will run immediately when it's started, then once again every hour,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=IMPORT_RESOURCES_SERVICE_PERIOD):
        super().__init__(interval.total_seconds(), self.maybe_import_resources)
        for p in [get_maas_lock_path(), get_bootresource_store_path()]:
            p.mkdir(parents=True, exist_ok=True)

    def maybe_import_resources(self):
        def determine_auto():
            auto = Config.objects.get_config("boot_images_auto_import")
            if not auto:
                return auto
            dev_without_images = (
                is_dev_environment() and not BootResourceSet.objects.exists()
            )
            if dev_without_images:
                return False
            else:
                return auto

        d = deferToDatabase(transactional(determine_auto))
        d.addCallback(self.import_resources_if_configured)
        d.addErrback(log.err, "Failure importing boot resources.")
        return d

    def import_resources_if_configured(self, auto):
        if auto:
            return import_resources()
        else:
            maaslog.info(
                "Skipping periodic import of boot resources; "
                "it has been disabled."
            )


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
    <a href="%(images_link)s">boot images</a> page to start the import.
    """
    )

    @transactional
    def clear_import_warning(self):
        discard_persistent_error(COMPONENT.IMPORT_PXE_FILES)

    @transactional
    def set_import_warning(self, warning):
        warning %= {"images_link": absolute_reverse("/") + "r/images"}
        register_persistent_error(COMPONENT.IMPORT_PXE_FILES, warning)

    @transactional
    def are_boot_images_available_in_the_region(self):
        """Return true if there are boot images available in the region."""
        return BootResource.objects.all().exists()


def _get_available_space(target_dir: Path) -> int:
    _, _, free = shutil.disk_usage(target_dir)
    return free


def _get_db_images_size() -> int:
    return sum(
        BootResourceFile.objects.filter(largefile__isnull=False)
        .distinct("sha256")
        .values_list("size", flat=True)
    )


def export_images_from_db(region: RegionController, target_dir: Path):
    from maasserver.models import LargeFile

    required = _get_db_images_size()
    avail = _get_available_space(target_dir)

    if required > avail:
        msg = dedent(
            f"""\
                Failed to export boot-resources from the database.
                <br>Not enough disk space at '{target_dir}' on controller '{region.system_id}',
                 missing {human_readable_bytes(required - avail)}.
            """
        )
        register_persistent_error(COMPONENT.REGION_IMAGE_DB_EXPORT, msg)
        maaslog.error("Failed to export boot-resources from the database")
        return
    elif required == 0:
        # nothing to do
        discard_persistent_error(COMPONENT.REGION_IMAGE_DB_EXPORT)
        return

    maaslog.info("Exporting image files to disk")

    largefile_ids_to_delete = set()
    oids_to_delete = set()
    with transaction.atomic():
        files = BootResourceFile.objects.filter(
            largefile__isnull=False
        ).select_related("largefile")

        for file in files:
            lfile = file.local_file()

            def msg(message: str):
                maaslog.info(f"{file.filename}: {message}")  # noqa: B023

            def set_sync_status():
                file.bootresourcefilesync_set.update_or_create(  # noqa: B023
                    defaults=dict(size=lfile.size),  # noqa: B023
                    region=region,
                )

            total_size = file.largefile.total_size
            if lfile.valid:
                msg("skipping, file already present")
                set_sync_status()
            elif file.largefile.size != total_size:
                # we need to download this again
                msg(f"ignoring, size is {file.largefile.size} of {total_size}")
            else:
                lfile.unlink()
                msg("writing")
                with (
                    file.largefile.content.open("rb") as sfd,
                    lfile.store() as dfd,
                ):
                    shutil.copyfileobj(sfd, dfd)
                set_sync_status()

            oids_to_delete.add(file.largefile.content.oid)
            largefile_ids_to_delete.add(file.largefile_id)
            # need to unset it because the post-delete signal will otherwise
            # try to delete the largefile object, which is already handled
            # below
            file.largefile = None
            file.save()

        LargeFile.objects.filter(id__in=largefile_ids_to_delete).delete()
        with connection.cursor() as cursor:
            for oid in oids_to_delete:
                cursor.execute("SELECT lo_unlink(%s)", [oid])

    # clear any error status
    discard_persistent_error(COMPONENT.REGION_IMAGE_DB_EXPORT)


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

    export_images_from_db(region, target_dir)

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

    existing_files = set(target_dir.iterdir())
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
