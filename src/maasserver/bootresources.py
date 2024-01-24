# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "ensure_boot_source_definition",
    "ImportResourcesProgressService",
    "ImportResourcesService",
    "IMPORT_RESOURCES_SERVICE_PERIOD",
    "is_import_resources_running",
]

from datetime import timedelta
import os
from pathlib import Path
import shutil
from subprocess import CalledProcessError, check_call
from textwrap import dedent
import threading

from django.db import connection, transaction
from django.db.models import F
from pkg_resources import parse_version
from simplestreams import util as sutil
from simplestreams.log import LOG, WARNING
from simplestreams.mirrors import BasicMirrorWriter, UrlMirrorReader
from simplestreams.objectstores import ObjectStore
from temporalio.client import WorkflowFailureError
from temporalio.common import WorkflowIDReusePolicy
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.python.failure import Failure

from maasserver import locks
from maasserver.bootsources import (
    cache_boot_sources,
    ensure_boot_source_definition,
    get_boot_sources,
    get_product_title,
    set_simplestreams_env,
)
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
)
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_FILE_TYPE_CHOICES,
    BOOT_RESOURCE_TYPE,
    COMPONENT,
)
from maasserver.eventloop import services
from maasserver.import_images.download_descriptions import (
    download_all_image_descriptions,
    image_passes_filter,
    validate_product,
)
from maasserver.import_images.helpers import (
    get_os_from_product,
    get_signing_policy,
)
from maasserver.import_images.keyrings import write_all_keyrings
from maasserver.import_images.product_mapping import map_products
from maasserver.models import (
    BootResource,
    BootResourceFile,
    BootResourceFileSync,
    BootResourceSet,
    BootSourceSelection,
    Config,
    Event,
    RegionController,
)
from maasserver.release_notifications import ReleaseNotifications
from maasserver.utils import (
    absolute_reverse,
    get_maas_user_agent,
    synchronised,
)
from maasserver.utils.bootresource import (
    BOOTLOADERS_DIR,
    get_bootresource_store_path,
)
from maasserver.utils.dblocks import DatabaseLockNotHeld
from maasserver.utils.orm import (
    get_one,
    in_transaction,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from maasserver.workflow import (
    cancel_workflow,
    execute_workflow,
    REGION_TASK_QUEUE,
)
from maasserver.workflow.bootresource import (
    DOWNLOAD_TIMEOUT,
    ResourceDownloadParam,
    SyncRequestParam,
)
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.config import is_dev_environment
from provisioningserver.events import EVENT_TYPES
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.path import get_maas_lock_path
from provisioningserver.utils import snap
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.shell import ExternalProcessError
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
    pause,
    synchronous,
)
from provisioningserver.utils.version import DISTRIBUTION

maaslog = get_maas_logger("bootresources")
log = LegacyLogger()


class BootResourceStore(ObjectStore):
    """Stores the simplestream data into the `BootResource` model.

    Must be used with `BootResourceRepoWriter`, to retrieve the extra
    information from simplestreams to store into the model.

    This object store is implemented so that the metadata for the boot images
    from simplestreams is placed into the database first. The content is not
    immediately stored in the database at the same time as the metadata. Once
    all of the metadata is stored in the database, then the content is stored
    into the database.

    The boot resource model is design to handle this implementation, as
    `BootResourceSet`'s are not considered complete and usable until all of the
    content for all `BootResourceFile`'s are complete.

    Breakdown of the process of this object store:
        1. Save all new metadata from simplestreams into the database.
        2. Save all file content from simplestreams into the database.
        3. Remove all old non-synced resources from the database.

    Note: You must manage transactions manually thoughout this store as it
    should work outside of a transactional context. Working outside of
    transactional context is important, so the data appears to the user as
    soon as possible.
    """

    WORKFLOW_ID = "sync-boot-resources:streams"

    def __init__(self):
        """Initialize store."""
        self.cache_current_resources()
        self._content_to_finalize: dict[str, ResourceDownloadParam] = {}
        self._finalizing = False
        self._cancel_finalize = False

    def get_resource_identity(self, resource):
        """Return the formatted identity for the given resource."""
        os, series = resource.name.split("/")
        arch, subarch = resource.split_arch()
        return f"{os}/{arch}/{subarch}/{series}"

    def cache_current_resources(self):
        """Load all current synced resources into 'self._resources_to_delete'.

        Each resource that is being updated will be removed from the list. The
        remaining at the end of the sync will be removed.
        """
        self._resources_to_delete = {
            self.get_resource_identity(resource)
            for resource in BootResource.objects.filter(
                rtype=BOOT_RESOURCE_TYPE.SYNCED
            )
        }
        self._init_resources_to_delete = set(self._resources_to_delete)

    def prevent_resource_deletion(self, resource):
        """Remove the `BootResource` from the resources to delete list.

        This will make sure that this synced resource will not be deleted at
        the end of the syncing process.
        """
        ident = self.get_resource_identity(resource)
        self._resources_to_delete.discard(ident)

    def save_content_later(
        self,
        rfile: BootResourceFile,
        source_list: list[str],
        force: bool = False,
        extract_path: str | None = None,
    ):
        """Schedule a download operation

        Multiple requests for the same SHA256 are combined in a single
        operation.

        Args:
            rfile (BootResourceFile): resource file instance
            source_list (list[str]): sources for this resource
            force (bool, optional): truncate existing files. Defaults to False.
            extract_path (str | None, optional): extracts file to this path. Defaults to None.
        """
        req = self._content_to_finalize.setdefault(
            rfile.sha256,
            ResourceDownloadParam(
                rfile_ids=[],
                source_list=[],
                total_size=rfile.size,
                sha256=rfile.sha256,
                extract_paths=[],
            ),
        )
        req.rfile_ids.append(rfile.id)
        req.source_list.extend(source_list)
        if extract_path is not None:
            req.extract_paths.append(extract_path)
        req.force |= force

    def get_or_create_boot_resource(self, product):
        """Get existing `BootResource` for the given product or create a new
        one if one does not exist."""
        os = get_os_from_product(product)
        arch = product["arch"]
        kflavor = product.get("kflavor")
        bootloader_type = product.get("bootloader-type")
        if os == "ubuntu-core":
            kflavor = product.get("kernel_snap", "generic")
            release = product["release"]
            gadget = product["gadget_snap"]
            architecture = f"{arch}/generic"
            series = f"{release}-{gadget}"
        elif bootloader_type is None:
            # The rack controller assumes the subarch is the kernel. We need to
            # include the kflavor in the subarch otherwise the rack will
            # overwrite the generic kernel with each kernel flavor.
            subarch = product.get("subarch", "generic")
            has_kflavor = kflavor not in (None, "generic") and (
                "hwe-" in subarch or "ga-" in subarch
            )
            if has_kflavor and kflavor not in subarch:
                if subarch.endswith("-edge"):
                    subarch_parts = subarch.split("-")
                    subarch_parts.insert(-1, kflavor)
                    subarch = "-".join(subarch_parts)
                else:
                    subarch = f"{subarch}-{kflavor}"
            architecture = f"{arch}/{subarch}"
            series = product["release"]
        else:
            architecture = f"{arch}/generic"
            series = bootloader_type

        name = f"{os}/{series}"

        resource, _ = BootResource.objects.get_or_create(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
        )
        resource.kflavor = kflavor
        resource.bootloader_type = bootloader_type
        resource.rolling = product.get("rolling", False)
        # Simplestreams content from maas.io includes the following
        # extra fields. Looping through the extra product data and adding it to
        # extra will not work as the product data that is passed into this
        # object store contains additional data that should not be stored into
        # the database. If subarches exist in the product then we store those
        # values to expose in the simplestreams endpoint on the region.
        resource.extra = {
            key: product[key]
            for key in ("subarches", "platform", "supported_platforms")
            if key in product
        }

        self.prevent_resource_deletion(resource)

        title = get_product_title(product)
        if title is not None:
            resource.extra["title"] = title

        resource.save()
        return resource

    def get_or_create_boot_resource_set(self, resource, product):
        """Get existing `BootResourceSet` for the given resource and product
        or create a new one if one does not exist."""
        version = product["version_name"]
        resource_set = get_one(resource.sets.filter(version=version))
        if resource_set is None:
            resource_set = BootResourceSet(resource=resource, version=version)
        resource_set.label = product["label"]
        log.debug(
            f"Got boot resource set id={resource_set.id} {resource_set}."
        )
        resource_set.save()
        return resource_set

    def get_or_create_boot_resource_file(self, resource_set, product):
        """Get existing `BootResourceFile` for the given resource set and
        product or create a new one if one does not exist."""
        # For synced resources the filename is the same as the filetype. This
        # is the way the data is from maas.io so we emulate that here.
        created = False
        filetype = product["ftype"]
        filename = os.path.basename(product["path"])
        rfile = get_one(resource_set.files.filter(filename=filename))
        if rfile is None:
            sha256 = sutil.item_checksums(product)["sha256"]
            rfile = BootResourceFile(
                resource_set=resource_set,
                filename=filename,
                sha256=sha256,
                size=int(product["size"]),
            )
            created = True
        log.debug(f"Got boot resource file id={rfile}.")
        rfile.filetype = filetype
        rfile.extra = {}

        # Simplestreams content from maas.io includes the following
        # extra fields. Looping through the extra product data and adding it to
        # extra will not work as the product data that is passed into this
        # object store contains additional data that should not be stored into
        # the database. If kpackage exist in the product then we store those
        # values to expose in the simplestreams endpoint on the region.
        # src_{package,release,version} is useful in determining where the
        # bootloader came from.
        #
        # Updated the list below to allow for a simplestream server to also
        # provide an extra field called 'kparams' which allows someone to also
        # specify kernel parameters that are unique to the release. This is
        # needed for certain ephemeral images.
        for extra_key in [
            "kpackage",
            "src_package",
            "src_release",
            "src_version",
            "kparams",
        ]:
            if extra_key in product:
                rfile.extra[extra_key] = product[extra_key]

        return rfile, created

    def get_resource_file_log_identifier(
        self, rfile, resource_set=None, resource=None
    ):
        """Return identifier that is used for the maaslog."""
        resource_set = resource_set or rfile.resource_set
        resource = resource or resource_set.resource
        return f"{self.get_resource_identity(resource)}/{resource_set.version}/{rfile.filename}"

    @transactional
    def insert(self, product, source_list):
        """Insert file into store.

        This method only stores the metadata from the product in the database.
        The actual writing of the content will be performed in the finalize
        method. Not calling the finalize method will result in the metadata
        being present in the database, but none of the created sets will be
        complete.

        :param product: Entries product data.
        :type product: dict
        :param source_list: sources list
        """
        assert isinstance(source_list, list)
        resource = self.get_or_create_boot_resource(product)
        is_resource_initially_complete = (
            resource.get_latest_complete_set() is not None
        )
        resource_set = self.get_or_create_boot_resource_set(resource, product)
        rfile, new_rfile = self.get_or_create_boot_resource_file(
            resource_set, product
        )

        # A ROOT_IMAGE may already be downloaded for the release if the stream
        # switched from one not containg SquashFS images to one that does. We
        # want to use the SquashFS image so ignore the tgz.
        if product["ftype"] == BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE:
            qs = resource_set.files.filter(
                filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
            )
            BootResourceFile.objects.filestore_remove_files(qs)
            qs.delete()

        checksums = sutil.item_checksums(product)
        sha256 = checksums["sha256"]

        force_download = False
        if rfile.sha256 != sha256:
            BootResourceFile.objects.filestore_remove_file(rfile)
            force_download = True
            msg = f"Hash mismatch for resourceset={resource_set} resource={resource}"
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_WARNING, msg
            )
            maaslog.warning(msg)

        rfile.sha256 = sha256
        rfile.size = int(product["size"])
        rfile.save()

        is_resource_broken = (
            is_resource_initially_complete
            and resource.get_latest_complete_set() is None
        )
        if is_resource_broken:
            msg = f"Resource {resource} has no complete resource set!"
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_ERROR, msg
            )
            maaslog.error(msg)

        ident = self.get_resource_file_log_identifier(
            rfile, resource_set, resource
        )
        lfile = rfile.local_file()
        if lfile.complete and rfile.complete:
            log.debug(f"Boot image already up-to-date {ident}.")
            return

        log.info(f"Scheduling image download: {ident}")

        ext_sync = force_download or new_rfile or not rfile.has_complete_copy
        extract_path = None
        if (
            rfile.filetype == BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ
            and resource.bootloader_type
        ):
            arch = resource.architecture.split("/")[0]
            extract_path = (
                f"{BOOTLOADERS_DIR}/{resource.bootloader_type}/{arch}"
            )

        self.save_content_later(
            rfile,
            source_list=source_list if ext_sync else [],
            force=force_download,
            extract_path=extract_path,
        )

    def _other_resources_exists(self, os, arch, subarch, series):
        """Return `True` when simplestreams provided an image with the same
        os, arch, series combination.

        This is used to remove the extra subarches when they are deleted
        from the simplestreams, but if the whole image is deleted from
        simplestreams then all subarches for that image will remain. See'
        `resource_cleaner`.
        """
        # Filter all resources to only those that should remain.
        related_resources = BootResource.objects.all()
        for deleted_ident in self._resources_to_delete:
            (
                deleted_os,
                deleted_arch,
                deleted_subarch,
                deleted_series,
            ) = deleted_ident.split("/")
            related_resources = related_resources.exclude(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=f"{deleted_os}/{deleted_series}",
                architecture=f"{deleted_arch}/{deleted_subarch}",
            )
        # Filter the remaining resources to those related to this os,
        # arch, series.
        related_resources = related_resources.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=f"{os}/{series}",
            architecture__startswith=arch,
        )
        return related_resources.exists()

    @transactional
    def resource_cleaner(self):
        """Removes all of the `BootResource`'s that were not synced."""
        # Grab all the current selections from the BootSourceSelection.
        selections = [
            selection.to_dict()
            for selection in BootSourceSelection.objects.all()
        ]
        for ident in self._resources_to_delete:
            os, arch, subarch, series = ident.split("/")
            name = f"{os}/{series}"
            architecture = f"{arch}/{subarch}"
            delete_resource = get_one(
                BootResource.objects.filter(
                    rtype=BOOT_RESOURCE_TYPE.SYNCED,
                    name=name,
                    architecture=architecture,
                )
            )
            if delete_resource is not None:
                resource_set = delete_resource.get_latest_set()
                if resource_set is not None:
                    # It is possible that the image was removed from
                    # simplestreams but the user still wants that image to
                    # exist. This is done by looking at the selections. If any
                    # selection matches this resource then we keep it,
                    # otherwise we remove it. Extra subarches for an image
                    # are not kept when simplestreams is still providing that
                    # os, arch, series combination.
                    if not image_passes_filter(
                        selections,
                        os,
                        arch,
                        subarch,
                        series,
                        resource_set.label,
                    ) or self._other_resources_exists(
                        os, arch, subarch, series
                    ):
                        # It was selected for removal.
                        BootResourceFile.objects.filestore_remove_resource(
                            delete_resource
                        )
                        delete_resource.delete()
                    else:
                        msg = (
                            f"Boot image {self.get_resource_identity(delete_resource)} "
                            "no longer exists in stream, but "
                            "remains in selections. To delete this image "
                            "remove its selection."
                        )
                        Event.objects.create_region_event(
                            EVENT_TYPES.REGION_IMPORT_INFO, msg
                        )
                        maaslog.info(msg)
                else:
                    # No resource set on the boot resource so it should be
                    # removed as it has not files.
                    log.debug(
                        f"Deleting boot image {self.get_resource_identity(delete_resource)}."
                    )
                    delete_resource.delete()

    @transactional
    def resource_set_cleaner(self):
        """Removes all of the old `BootResourceSet`'s for the synced
        `BootResource`'s."""
        # Remove the sets that are incomplete and older versions.
        for resource in BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        ):
            found_complete = False
            # Reverse order by id, so that we keep the newest completed set.
            for resource_set in resource.sets.order_by("id").reverse():
                if not resource_set.complete:
                    # At this point all resource sets should be complete.
                    # Delete the extras that are not.
                    log.debug(
                        f"Deleting incomplete resourceset {resource_set}.",
                    )
                    BootResourceFile.objects.filestore_remove_set(resource_set)
                    resource_set.delete()
                else:
                    # It is complete, only keep the newest complete set.
                    if not found_complete:
                        found_complete = True
                    else:
                        log.debug(
                            f"Deleting obsolete resourceset {resource_set}.",
                        )
                        BootResourceFile.objects.filestore_remove_set(
                            resource_set
                        )
                        resource_set.delete()

        # Cleanup the resources that don't have sets. This is done because
        # it could be possible that the previous for loop removes all sets
        # from a boot resource, so the resource should be removed, instead
        # of being empty.
        for resource in BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        ):
            if not resource.sets.exists():
                log.debug(f"Deleting empty resource {resource}.")
                resource.delete()

    @transactional
    def delete_content_to_finalize(self):
        """Deletes all content that was set to be finalized."""
        for req in self._content_to_finalize.values():
            BootResourceFile.objects.filter(id__in=req.rfile_ids).delete()
        self._content_to_finalize.clear()

    def finalize(self, notify: Deferred | None = None):
        """Perform the finalization of data into the filesystem.

        This will remove the un-needed `BootResource`'s and download the
        file data into the file store.

        :param notify: Instance of `Deferred` that is called when all the
            metadata has been downloaded and the image data download has been
            started.
        """
        log.debug(
            f"Finalize will delete {len(self._resources_to_delete)} images(s).",
        )
        log.debug(
            f"Finalize will save {len(self._content_to_finalize)} new images(s).",
        )
        if (
            len(self._resources_to_delete) > 0
            and self._resources_to_delete == self._init_resources_to_delete
            and len(self._content_to_finalize) == 0
        ):
            error_msg = (
                "Finalization of imported images skipped, "
                f"or all {self._resources_to_delete} synced images would be deleted."
            )
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_ERROR, error_msg
            )
            maaslog.error(error_msg)
            if notify is not None:
                failure = Failure(Exception(error_msg))
                reactor.callFromThread(notify.errback, failure)
            return

        # Cancel finalize was set before the workflow operation is started.
        if self._cancel_finalize:
            self.resource_cleaner()
            self.delete_content_to_finalize()
            self.resource_set_cleaner()
            # Callback the notify even though the import was cancelled.
            if notify is not None:
                reactor.callFromThread(notify.callback, None)
        else:
            self._finalizing = True
            self.resource_cleaner()
            # Callback the notify before starting the download of the actual
            # data for the images.
            if notify is not None:
                reactor.callFromThread(notify.callback, None)

            try:
                if len(self._content_to_finalize) > 0:
                    sync_req = SyncRequestParam(
                        resources=[*self._content_to_finalize.values()],
                    )
                    execute_workflow(
                        "sync-bootresources",
                        self.WORKFLOW_ID,
                        sync_req,
                        task_queue=REGION_TASK_QUEUE,
                        execution_timeout=DOWNLOAD_TIMEOUT,
                        run_timeout=DOWNLOAD_TIMEOUT,
                        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
                    )
            except WorkflowFailureError:
                if not self._cancel_finalize:
                    raise
                log.info("Boot Resources synchronisation aborted")
                return
            finally:
                self._content_to_finalize.clear()
            self.resource_set_cleaner()
            log.info("Boot Resources synchronisation has completed")

    def cancel_finalize(self, notify=None):
        """Cancel the finalization. This can be called instead of `finalize` or
        while `finalize` is running in another thread."""
        if not self._finalizing:
            self._cancel_finalize = True
            self.finalize(notify=notify)
        else:
            assert (
                notify is None
            ), "notify is not supported if finalization already started."
            # Finalization is already started so cancel the finalization.
            self._cancel_finalize = True
            cancel_workflow(self.WORKFLOW_ID)


class BootResourceRepoWriter(BasicMirrorWriter):
    """Download boot resources from an upstream Simplestreams repo.

    :ivar store: A `ObjectStore` to store the data. This writer only supports
        the `BootResourceStore`.
    :ivar product_mapping: A `ProductMapping` describing the desired boot
        resources.
    """

    def __init__(self, store, product_mapping):
        assert isinstance(store, BootResourceStore)
        self.store = store
        self.product_mapping = product_mapping
        super().__init__(
            config={
                # Only download the latest version. Without this all versions
                # will be downloaded from simplestreams.
                "max_items": 1,
                "external_download": True,
            }
        )

    def load_products(self, path=None, content_id=None):
        """Overridable from `BasicMirrorWriter`."""
        # It looks as if this method only makes sense for MirrorReaders, not
        # for MirrorWriters.  The default MirrorWriter implementation just
        # raises NotImplementedError.  Stop it from doing that.
        return

    def filter_version(self, data, src, target, pedigree):
        """Overridable from `BasicMirrorWriter`."""
        return self.product_mapping.contains(
            sutil.products_exdata(src, pedigree)
        )

    def insert_item(self, data, src, target, pedigree, source_list):
        """Overridable from `BasicMirrorWriter`."""
        item = sutil.products_exdata(src, pedigree)
        product_name = pedigree[0]
        version_name = pedigree[1]
        versions = src["products"][product_name]["versions"]
        items = versions[version_name]["items"]
        maas_supported = item.get("maas_supported")
        # If the item requires a specific version of MAAS check the running
        # version meets or exceeds that requirement.
        if maas_supported is not None:
            supported_version = parse_version(maas_supported)
            if supported_version > DISTRIBUTION.parsed_version:
                maaslog.warning(
                    f"Ignoring {product_name}, requires a newer "
                    f"version of MAAS({supported_version})"
                )
                return
        if item["ftype"] == "notifications":
            ReleaseNotifications(
                data["release_notification"]
            ).maybe_check_release_notifications()
        if (
            item["ftype"] == BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
            and BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE in items.keys()
        ):
            # If both a SquashFS and root-image.gz are available only insert
            # the SquashFS image.
            return
        elif item["ftype"] not in dict(BOOT_RESOURCE_FILE_TYPE_CHOICES).keys():
            # Skip filetypes that we don't know about.
            maaslog.warning(
                f"Ignoring unsupported filetype({item['ftype']}) "
                f"from {product_name} {version_name}"
            )
        elif not validate_product(item, product_name):
            maaslog.warning(f"Ignoring unsupported product {product_name}")
        else:
            self.store.insert(item, source_list)


def download_boot_resources(path, store, product_mapping, keyring_file=None):
    """Download boot resources for one simplestreams source.

    :param path: The Simplestreams URL for this source.
    :param store: A simplestreams `ObjectStore` where downloaded resources
        should be stored.
    :param product_mapping: A `ProductMapping` describing the resources to be
        downloaded.
    :param keyring_file: Optional path to a keyring file for verifying
        signatures.
    """
    writer = BootResourceRepoWriter(store, product_mapping)
    (mirror, rpath) = sutil.path_from_mirror_url(path, None)
    policy = get_signing_policy(rpath, keyring_file)
    reader = UrlMirrorReader(
        mirror, policy=policy, user_agent=get_maas_user_agent()
    )
    writer.sync(reader, rpath)


def download_all_boot_resources(
    sources, product_mapping, store=None, notify=None
):
    """Downloads all of the boot resources from the sources.

    Boot resources are stored into the `BootResource` model.

    This process is long running and can be triggered to be stopped through
    a postgres notification of `sys_stop_import`. When that notification is
    received the running import will be stopped.

    :param sources: List of dicts describing the Simplestreams sources from
        which we should download.
    :param product_mapping: A `ProductMapping` describing the resources to be
        downloaded.
    :param notify: Instance of `Deferred` that is called when all the metadata
        has been downloaded and the image data download has been started.
    """
    log.debug("Initializing BootResourceStore.")
    if store is None:
        store = BootResourceStore()
    assert isinstance(store, BootResourceStore)

    lock = threading.Lock()  # Locked used to changed values here.
    finalizing = False  # True when finalizing is running.
    stop = False  # True when it should be stopped.

    # Grab the runnning postgres listener service to register the stop handler.
    listener = services.getServiceNamed("postgres-listener-worker")

    # Allow the import process to be stopped out-of-band.
    def stop_import(channel, payload):
        """Called when the import should be stopped."""
        nonlocal stop
        # Stop the actual import process.
        needs_cancel = False
        with lock:
            if stop:
                # Nothing need to be done as stop as already been called.
                return
            else:
                # First time stop has been called. Trigger stop and call cancel
                # if finalizing already started.
                stop = True
                if finalizing:
                    needs_cancel = True
        if needs_cancel:
            store.cancel_finalize()

    with listener.listen("sys_stop_import", stop_import):
        for source in sources:
            msg = f"Importing images from source: {source['url']}"
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_INFO, msg
            )
            maaslog.info(msg)
            download_boot_resources(
                source["url"],
                store,
                product_mapping,
                keyring_file=source.get("keyring"),
            )

        # Start finalizing or cancel finalizing.
        with lock:
            stopped = stop
        if stopped:
            log.debug(
                "Finalizing BootResourceStore was cancelled before starting."
            )
            store.cancel_finalize(notify=notify)
        else:
            log.debug("Finalizing BootResourceStore.")
            with lock:
                finalizing = True
            store.finalize(notify=notify)
    return not stop


def set_global_default_releases():
    """Sets the global configuration options for the deployment and
    commissioning images."""
    # Set the commissioning option to the longest LTS available.
    commissioning_resources = None
    try:
        Config.objects.get(name="commissioning_distro_series")
    except Config.DoesNotExist:
        commissioning_resources = (
            BootResource.objects.get_available_commissioning_resources()
        )
        if len(commissioning_resources) > 0:
            default_resource = commissioning_resources[0]
            osystem, release = default_resource.name.split("/")
            Config.objects.set_config("commissioning_osystem", osystem)
            Config.objects.set_config("commissioning_distro_series", release)

    # Set the default deploy option to the same as the commissioning option.
    try:
        Config.objects.get(name="default_distro_series")
    except Config.DoesNotExist:
        if commissioning_resources is None:
            commissioning_resources = (
                BootResource.objects.get_available_commissioning_resources()
            )
        if len(commissioning_resources) > 0:
            default_resource = commissioning_resources[0]
            osystem, release = default_resource.name.split("/")
            Config.objects.set_config("default_osystem", osystem)
            Config.objects.set_config("default_distro_series", release)


@asynchronous(timeout=FOREVER)
def _import_resources(notify=None):
    """Import boot resources.

    Pulls the sources from `BootSource`. This only starts the process if
    some SYNCED `BootResource` already exist.

    This MUST be called from outside of a database transaction.

    :param notify: Instance of `Deferred` that is called when all the metadata
        has been downloaded and the image data download has been started.
    """

    # Sync boot resources into the region.
    d = deferToDatabase(_import_resources_with_lock, notify=notify)

    def eb_import(failure):
        failure.trap(DatabaseLockNotHeld)
        maaslog.info("Skipping import as another import is already running.")

    return d.addErrback(eb_import)


def create_gnupg_home():
    """create maas user's GNUPG home directory."""
    gpghome = get_maas_user_gpghome()
    if not os.path.isdir(gpghome):
        os.makedirs(gpghome)
        if os.geteuid() == 0 and not snap.running_in_snap():
            # Make the maas user the owner of its GPG home.  Do this only if
            # running as root; otherwise it would probably fail.  We want to
            # be able to start a development instance without triggering that.
            check_call(["chown", "maas:maas", gpghome])


def _import_resources_internal(notify=None):
    """Import boot resources once the `import_images` lock is acquired.

    This should *not* be called in a transaction; it will manage transactions
    itself, and attempt to keep them short.

    See `_import_resources` for details.

    :raise DatabaseLockNotHeld: If the `import_images` lock cannot be acquired
        at the beginning of this method. This happens quickly because the lock
        is acquired using a TRY variant; see `dblocks`.

    :param notify: Instance of `Deferred` that is called when all the metadata
        has been downloaded and the image data download has been started.
    """
    assert not in_transaction(), (
        "_import_resources_with_lock() must not be called within a "
        "preexisting transaction; it manages its own."
    )

    # Make sure that notify is a `Deferred` that has not beed called.
    if notify is not None:
        assert isinstance(notify, Deferred), "Notify should be a `Deferred`"
        assert not notify.called, "Notify should not have already been called."

    # Make sure that maas user's GNUPG home directory exists. This is
    # needed for importing of boot resources, which occurs on the region
    # as well as the clusters.
    create_gnupg_home()

    # Ensure that boot sources exist.
    ensure_boot_source_definition()

    # TODO migrate files from DB

    # Cache the boot sources before import.
    cache_boot_sources()

    # FIXME: This modifies the environment of the entire process, which is Not
    # Cool. We should integrate with simplestreams in a more Pythonic manner.
    set_simplestreams_env()

    with tempdir("keyrings") as keyrings_path:
        sources = get_boot_sources()
        sources = write_all_keyrings(keyrings_path, sources)
        msg = (
            "Started importing of boot images from "
            f"{len(sources)} source(s)."
        )
        Event.objects.create_region_event(EVENT_TYPES.REGION_IMPORT_INFO, msg)
        maaslog.info(msg)

        image_descriptions = download_all_image_descriptions(
            sources, get_maas_user_agent()
        )
        if image_descriptions.is_empty():
            msg = (
                "Unable to import boot images, no image "
                "descriptions avaliable."
            )
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_WARNING, msg
            )
            maaslog.warning(msg)
            return
        product_mapping = map_products(image_descriptions)

        successful = download_all_boot_resources(
            sources, product_mapping, notify=notify
        )

    if successful:
        set_global_default_releases()
        # LP:1766370 - Check if the user updated boot sources or boot
        # source selections while imports are running. If so restart
        # the import process to make sure all user selected options
        # are downloaded.
        current_sources = get_boot_sources()
        new_selections = len(sources) != len(current_sources)
        for old, current in zip(sources, current_sources):
            # Keyring is added by write_all_keyrings above. It is the
            # temporary path of the GPG keyring file extracted from the
            # database.
            old.pop("keyring", None)
            current.pop("keyring", None)
            if current != old:
                new_selections = True
                break
        if new_selections:
            _import_resources_internal(notify)
        else:
            maaslog.info(
                f"Finished importing of boot images from {len(sources)} source(s)."
            )
    else:
        maaslog.warning(
            f"Importing of boot images from {len(sources)} source(s) was cancelled.",
        )


@synchronous
@with_connection
@synchronised(locks.import_images.TRY)  # TRY is important; read docstring.
def _import_resources_with_lock(notify=None):
    """Import boot resources once the `import_images` lock is held."""
    return _import_resources_internal(notify)


def _import_resources_in_thread(notify=None):
    """Import boot resources in a thread managed by Twisted.

    Errors are logged. The returned `Deferred` will never errback so it's safe
    to use in a `TimerService`, for example.

    :param notify: Instance of `Deferred` that is called when all the metadata
        has been downloaded and the image data download has been started.
    """
    d = deferToDatabase(_import_resources, notify=notify)
    d.addErrback(_handle_import_failures)
    return d


def _handle_import_failures(failure):
    if failure.check(CalledProcessError):
        # Upgrade CalledProcessError to ExternalProcessError in-place so that
        # we get the niceness of the latter but without losing the traceback.
        # That may not so relevant here because Failure will have captured the
        # traceback already, but it makes sense to be consistent.
        ExternalProcessError.upgrade(failure.value)

    log.err(failure, "Importing boot resources failed.")


def import_resources(notify=None):
    """Starts the importing of boot resources.

    Note: This function returns immediately. It only starts the process, it
    doesn't wait for it to be finished, as it can take several minutes to
    complete.

    :param notify: Instance of `Deferred` that is called when all the metadata
        has been downloaded and the image data download has been started.
    """
    reactor.callFromThread(_import_resources_in_thread, notify=notify)


def is_import_resources_running():
    """Return True if the import process is currently running."""
    return locks.import_images.is_locked()


@asynchronous
@inlineCallbacks
def stop_import_resources():
    """Stops the running import process."""
    running = yield deferToDatabase(transactional(is_import_resources_running))
    if not running:
        # Nothing to do as it's not running.
        return

    # Notify for the stop to occur.
    @transactional
    def notify():
        with connection.cursor() as cursor:
            cursor.execute("NOTIFY sys_stop_import;")

    yield deferToDatabase(notify)

    # Wait for the importing lock to be released, before saying it has
    # fully been stopped.
    while True:
        running = yield deferToDatabase(
            transactional(is_import_resources_running)
        )
        if not running:
            break
        yield pause(1)


# How often the import service runs.
IMPORT_RESOURCES_SERVICE_PERIOD = timedelta(hours=1)


class ImportResourcesService(TimerService):
    """Service to periodically import boot resources.

    This will run immediately when it's started, then once again every hour,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=IMPORT_RESOURCES_SERVICE_PERIOD):
        super().__init__(interval.total_seconds(), self.maybe_import_resources)
        LOG.setLevel(WARNING)  # reduce simplestreams verbosity
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
            return _import_resources_in_thread()
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


def export_images_from_db(region: RegionController):
    from maasserver.models import LargeFile

    log.info("Exporting image files to disk")

    largefile_ids_to_delete = set()
    oids_to_delete = set()
    with transaction.atomic():
        files = BootResourceFile.objects.filter(
            largefile__isnull=False
        ).select_related("largefile")

        for file in files:
            lfile = file.local_file()

            def msg(message: str):
                log.msg(f"{file.filename}: {message}")

            def set_sync_status():
                file.bootresourcefilesync_set.update_or_create(
                    defaults=dict(size=lfile.size),
                    region=region,
                )

            total_size = file.largefile.total_size
            if file.largefile.size != total_size:
                msg(f"skipping, size is {file.largefile.size} of {total_size}")
                oids_to_delete.add(file.largefile.content.oid)
                continue

            if lfile.valid:
                msg("skipping, file already present")
            else:
                lfile.unlink()
                msg("writing")
                with (
                    file.largefile.content.open("rb") as sfd,
                    lfile.store() as dfd,
                ):
                    shutil.copyfileobj(sfd, dfd)
                    oids_to_delete.add(file.largefile.content.oid)

            set_sync_status()

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

    export_images_from_db(region)

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
