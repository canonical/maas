# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

__all__ = [
    "ensure_boot_source_definition",
    "get_simplestream_endpoint",
    "ImportResourcesProgressService",
    "ImportResourcesService",
    "IMPORT_RESOURCES_SERVICE_PERIOD",
    "is_import_resources_running",
    "simplestreams_file_handler",
    "simplestreams_stream_handler",
]

from datetime import timedelta
from operator import itemgetter
import os
from pathlib import Path
from subprocess import CalledProcessError
from textwrap import dedent
import threading
import time

from django.db import connection, connections, transaction
from django.db.utils import load_backend
from django.http import HttpResponse, StreamingHttpResponse
from pkg_resources import parse_version
from simplestreams import util as sutil
from simplestreams.mirrors import BasicMirrorWriter, UrlMirrorReader
from simplestreams.objectstores import ObjectStore
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks
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
from maasserver.exceptions import MAASAPINotFound
from maasserver.fields import LargeObjectFile
from maasserver.models import (
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSourceSelection,
    Config,
    Event,
    LargeFile,
)
from maasserver.release_notifications import ReleaseNotifications
from maasserver.rpc import getAllClients
from maasserver.utils import (
    absolute_reverse,
    get_maas_user_agent,
    synchronised,
)
from maasserver.utils.dblocks import DatabaseLockNotHeld
from maasserver.utils.orm import (
    get_one,
    in_transaction,
    transactional,
    with_connection,
)
from maasserver.utils.threads import deferToDatabase
from provisioningserver.config import is_dev_environment
from provisioningserver.events import EVENT_TYPES
from provisioningserver.import_images.download_descriptions import (
    download_all_image_descriptions,
    image_passes_filter,
    validate_product,
)
from provisioningserver.import_images.helpers import (
    get_os_from_product,
    get_signing_policy,
)
from provisioningserver.import_images.keyrings import write_all_keyrings
from provisioningserver.import_images.product_mapping import map_products
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.cluster import ListBootImages
from provisioningserver.upgrade_cluster import create_gnupg_home
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


def get_simplestream_endpoint():
    """Returns the simplestreams endpoint for the Region."""
    return {
        "url": absolute_reverse(
            "simplestreams_stream_handler", kwargs={"filename": "index.json"}
        ),
        "keyring_data": b"",
        "selections": [],
    }


class ConnectionWrapper:
    """Wraps `LargeObjectFile` in a new database connection.

    `StreamingHttpResponse` runs outside of django context, so connection
    that is not shared by django is needed.

    A new database connection is made at the start of the interation and is
    closed upon close of wrapper.
    """

    def __init__(self, largeobject, alias="default"):
        self.largeobject = largeobject
        self.alias = alias
        self._connection = None
        self._stream = None

    def _get_new_connection(self):
        """Create new database connection."""
        db = connections.databases[self.alias]
        backend = load_backend(db["ENGINE"])
        return backend.DatabaseWrapper(db, self.alias)

    def _set_up(self):
        """Sets up the connection and stream.

        This uses lazy initialisation because it is called each time
        `next` is called.
        """
        if self._connection is None:
            self._connection = self._get_new_connection()
            self._connection.connect()
            self._connection.set_autocommit(False)
            self._connection.in_atomic_block = True
        if self._stream is None:
            self._stream = self.largeobject.open(
                "rb", connection=self._connection
            )

    def __iter__(self):
        return self

    def __next__(self):
        self._set_up()
        data = self._stream.read(self.largeobject.block_size)
        if len(data) == 0:
            raise StopIteration
        return data

    def close(self):
        """Close the connection and stream."""
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        if self._connection is not None:
            self._connection.in_atomic_block = False
            self._connection.commit()
            self._connection.set_autocommit(True)
            self._connection.close()
            self._connection = None


class SimpleStreamsHandler:
    """Simplestreams endpoint, that the racks talk to.

    This is not called from piston3, as piston uses emitters which
    breaks the ability to return streaming content.

    Anyone can access this endpoint. No credentials are required.
    """

    def get_json_response(self, content):
        """Return `HttpResponse` for JSON content."""
        response = HttpResponse(content)
        response["Content-Type"] = "application/json"
        return response

    def get_boot_resource_identifiers(self, resource):
        """Return tuple (os, arch, subarch, series) for the given resource."""
        arch, subarch = resource.split_arch()
        if "/" in resource.name:
            os, series = resource.name.split("/")
        else:
            os = "custom"
            series = resource.name
        return (os, arch, subarch, series)

    def get_product_name(self, resource):
        """Return product name for the given resource."""
        return "maas:boot:%s:%s:%s:%s" % self.get_boot_resource_identifiers(
            resource
        )

    def gen_complete_boot_resources(self):
        """Return generator of `BootResource` that contains a complete set."""
        resources = BootResource.objects.all()
        for resource in resources:
            # Only add resources that have a complete set.
            if resource.get_latest_complete_set() is None:
                continue
            yield resource

    def gen_products_names(self):
        """Return generator of avaliable products on the endpoint."""
        for resource in self.gen_complete_boot_resources():
            yield self.get_product_name(resource)

    def get_product_index(self):
        """Returns the streams product index `index.json`."""
        products = list(self.gen_products_names())
        updated = sutil.timestamp()
        index = {
            "index": {
                "maas:v2:download": {
                    "datatype": "image-downloads",
                    "path": "streams/v1/maas:v2:download.json",
                    "updated": updated,
                    "products": products,
                    "format": "products:1.0",
                }
            },
            "updated": updated,
            "format": "index:1.0",
        }
        data = sutil.dump_data(index) + b"\n"
        log.debug(
            "Simplestreams product index: {index}.",
            index=data.decode("utf-8", "replace"),
        )
        return self.get_json_response(data)

    def get_product_item(self, resource, resource_set, rfile):
        """Returns the item description for the `rfile`."""
        os, arch, subarch, series = self.get_boot_resource_identifiers(
            resource
        )
        path = "{}/{}/{}/{}/{}/{}".format(
            os,
            arch,
            subarch,
            series,
            resource_set.version,
            rfile.filename,
        )
        item = {
            "path": path,
            "ftype": rfile.filetype,
            "sha256": rfile.largefile.sha256,
            "size": rfile.largefile.total_size,
        }
        item.update(rfile.extra)
        return item

    def get_product_data(self, resource):
        """Returns the product data for this resource."""
        os, arch, subarch, series = self.get_boot_resource_identifiers(
            resource
        )
        versions = {}
        label = None
        for resource_set in resource.sets.order_by("id").reverse():
            if not resource_set.complete:
                continue
            # Set the label to the latest complete set label. In most cases the
            # label will be the same for all sets. Only time it will differ is
            # when daily has been enabled for a resource, that was previously
            # only release. Only the latest version of the resource will be
            # downloaded.
            if label is None:
                label = resource_set.label
            items = {
                rfile.filename: self.get_product_item(
                    resource, resource_set, rfile
                )
                for rfile in resource_set.files.all()
            }
            versions[resource_set.version] = {"items": items}
        product = {
            "versions": versions,
            "subarch": subarch,
            "label": label,
            "version": series,
            "arch": arch,
            "release": series,
            "os": os,
        }
        if resource.kflavor is not None:
            product["kflavor"] = resource.kflavor
        if resource.bootloader_type is not None:
            product["bootloader-type"] = resource.bootloader_type
        if resource.rolling:
            product["rolling"] = resource.rolling
        product.update(resource.extra)
        return product

    def get_product_download(self):
        """Returns the streams download index `download.json`."""
        products = {}
        for resource in self.gen_complete_boot_resources():
            name = self.get_product_name(resource)
            products[name] = self.get_product_data(resource)
        updated = sutil.timestamp()
        index = {
            "datatype": "image-downloads",
            "updated": updated,
            "content_id": "maas:v2:download",
            "products": products,
            "format": "products:1.0",
        }
        data = sutil.dump_data(index) + b"\n"
        return self.get_json_response(data)

    def streams_handler(self, request, filename):
        """Handles requests into the "streams/" content."""
        if filename == "index.json":
            return self.get_product_index()
        elif filename == "maas:v2:download.json":
            return self.get_product_download()
        raise MAASAPINotFound()

    def files_handler(
        self, request, os, arch, subarch, series, version, filename
    ):
        """Handles requests for getting the boot resource data."""
        if os == "custom":
            name = series
        else:
            name = f"{os}/{series}"
        arch = f"{arch}/{subarch}"
        try:
            resource = BootResource.objects.get(name=name, architecture=arch)
        except BootResource.DoesNotExist:
            raise MAASAPINotFound()
        try:
            resource_set = resource.sets.get(version=version)
        except BootResourceSet.DoesNotExist:
            raise MAASAPINotFound()
        try:
            rfile = resource_set.files.get(filename=filename)
        except BootResourceFile.DoesNotExist:
            raise MAASAPINotFound()
        response = StreamingHttpResponse(
            ConnectionWrapper(rfile.largefile.content),
            content_type="application/octet-stream",
        )
        return response


def simplestreams_stream_handler(request, filename):
    handler = SimpleStreamsHandler()
    return handler.streams_handler(request, filename)


def simplestreams_file_handler(
    request, os, arch, subarch, series, version, filename
):
    handler = SimpleStreamsHandler()
    return handler.files_handler(
        request, os, arch, subarch, series, version, filename
    )


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

    # Number of threads to run at the same time to write the contents of
    # files from simplestreams into the database. Increasing this number
    # might cause high network and database load.
    write_threads = 2

    # Read at 10MiB per chunk.
    read_size = 1024 * 1024 * 10

    def __init__(self):
        """Initialize store."""
        self.cache_current_resources()
        self._content_to_finalize = {}
        self._finalizing = False
        self._cancel_finalize = False

    def get_resource_identifiers(self, resource):
        """Return os, arch, subarch, and series for the given resource."""
        os, series = resource.name.split("/")
        arch, subarch = resource.split_arch()
        return os, arch, subarch, series

    def get_resource_identity(self, resource):
        """Return the formatted identity for the given resource."""
        return "%s/%s/%s/%s" % self.get_resource_identifiers(resource)

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

        # XXX blake_r 2014-10-30 bug=1387133: We store a copy of the resources
        # to delete, so we can check if all the same resources will be delete
        # in the finalize call.
        self._init_resources_to_delete = set(self._resources_to_delete)

    def prevent_resource_deletion(self, resource):
        """Remove the `BootResource` from the resources to delete list.

        This will make sure that this synced resource will not be deleted at
        the end of the syncing process.
        """
        ident = self.get_resource_identity(resource)
        self._resources_to_delete.discard(ident)

    def save_content_later(self, rfile, content):
        """Register content to be saved later on to the given resource file.

        This action will actually be performed during the finalize method.

        :param rfile: Resource file.
        :type rfile: BootResourceFile
        :param content: File-like object.
        """
        self._content_to_finalize[rfile.id] = content

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
            architecture = "%s/generic" % arch
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
            architecture = "%s/generic" % arch
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
            "Got boot resource set id={id} {set}.",
            id=resource_set.id,
            set=resource_set,
        )
        resource_set.save()
        return resource_set

    def get_or_create_boot_resource_file(self, resource_set, product):
        """Get existing `BootResourceFile` for the given resource set and
        product or create a new one if one does not exist."""
        # For synced resources the filename is the same as the filetype. This
        # is the way the data is from maas.io so we emulate that here.
        filetype = product["ftype"]
        filename = os.path.basename(product["path"])
        rfile = get_one(resource_set.files.filter(filename=filename))
        if rfile is None:
            rfile = BootResourceFile(
                resource_set=resource_set, filename=filename
            )
        log.debug(
            "Got boot resource file id={id} {set}.", id=rfile.id, set=rfile
        )
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

        # Don't save rfile here, because if new then largefile is None which
        # will cause a ValidationError. The setting of largefile and saving of
        # object should be handled by the calling function.
        return rfile

    def get_resource_file_log_identifier(
        self, rfile, resource_set=None, resource=None
    ):
        """Return identifier that is used for the maaslog."""
        if resource_set is None:
            resource_set = rfile.resource_set
        if resource is None:
            resource = resource_set.resource
        return "{}/{}/{}".format(
            self.get_resource_identity(resource),
            resource_set.version,
            rfile.filename,
        )

    @transactional
    def insert(self, product, reader):
        """Insert file into store.

        This method only stores the metadata from the product in the database.
        The actual writing of the content will be performed in the finalize
        method. Not calling the finalize method will result in the metadata
        being present in the database, but none of the created sets will be
        complete.

        :param product: Entries product data.
        :type product: dict
        :param reader: File-like object.
        """
        resource = self.get_or_create_boot_resource(product)
        is_resource_initially_complete = (
            resource.get_latest_complete_set() is not None
        )
        resource_set = self.get_or_create_boot_resource_set(resource, product)
        rfile = self.get_or_create_boot_resource_file(resource_set, product)

        # A ROOT_IMAGE may already be downloaded for the release if the stream
        # switched from one not containg SquashFS images to one that does. We
        # want to use the SquashFS image so ignore the tgz.
        if product["ftype"] == BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE:
            resource_set.files.filter(
                filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
            ).delete()

        checksums = sutil.item_checksums(product)
        sha256 = checksums["sha256"]
        total_size = int(product["size"])
        needs_saving = False
        prev_largefile = None

        largefile = rfile.largefile
        if largefile is not None and largefile.sha256 != sha256:
            # The content from simplestreams is different then what is in
            # the database. We hold the previous largefile so that it can
            # be removed once the new largefile is created. The largefile
            # cannot be removed here, because then the `BootResourceFile`
            # would have to set the largefile field to null, and that is
            # not allowed.
            prev_largefile = largefile
            largefile = None
            msg = f"Hash mismatch for prev_file={prev_largefile} resourceset={resource_set} resource={resource}"
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_WARNING, msg
            )
            maaslog.warning(msg)

        if largefile is None:
            # The resource file current does not have a largefile linked. Lets
            # check that a largefile does not already exist for this sha256.
            # If it does then there will be no reason to save the content into
            # the database.
            largefile = get_one(LargeFile.objects.filter(sha256=sha256))

        if largefile is None:
            # No largefile exist for this resource file in the database, so a
            # new one will be created to store the data for this file.
            largeobject = LargeObjectFile()
            largeobject.open().close()
            largefile = LargeFile.objects.create(
                sha256=sha256, total_size=total_size, content=largeobject
            )
            needs_saving = True
            log.debug("New large file created {lf}.", lf=largefile)

        # A largefile now exists for this resource file. Its either a new
        # largefile or an existing one that already existed in the database.
        rfile.largefile = largefile
        rfile.sha256 = largefile.sha256
        rfile.size = largefile.total_size
        rfile.save()

        is_resource_broken = (
            is_resource_initially_complete
            and resource.get_latest_complete_set() is None
        )
        if is_resource_broken:
            msg = "Resource %s has no complete resource set!" % resource
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_ERROR, msg
            )
            maaslog.error(msg)

        if prev_largefile is not None:
            # If the previous largefile had a miss matching sha256 then it
            # will be deleted so that its not taking up space in the database.
            #
            # Note: This is done after the resource file has been saved with
            # the new largefile. Doing so removed the previous largefile
            # reference to the resource file. Without removing the reference
            # then the largefile would not be deleted, because it was still
            # referenced by another object. See `LargeFile.delete`.
            prev_largefile.delete()

        if needs_saving:
            # The content for this resource file needs to be placed into the
            # database. This method only performs the saving of metadata into
            # the database. This resource is marked to be saved later, which
            # will occur in the finalize method.
            self.save_content_later(rfile, reader)
        else:
            ident = self.get_resource_file_log_identifier(
                rfile, resource_set, resource
            )
            log.debug("Boot image already up-to-date {ident}.", ident=ident)

    def write_content_thread(self, rid, reader):
        """Writes the data from the given reader, into the object storage
        for the given `BootResourceFile`."""

        @transactional
        def get_rfile_and_ident():
            rfile = BootResourceFile.objects.get(id=rid)
            ident = self.get_resource_file_log_identifier(rfile)
            rfile.largefile  # Preload largefile in the transaction.
            return rfile, ident

        rfile, ident = get_rfile_and_ident()
        cksummer = sutil.checksummer({"sha256": rfile.largefile.sha256})
        log.debug("Finalizing boot image {ident}.", ident=ident)

        # Ensure that the size of the largefile starts at zero.
        rfile.largefile.size = 0
        transactional(rfile.largefile.save)(update_fields=["size"])

        @transactional
        def write_chunk():
            """Write a chunk into the database with a transaction per trunk.

            This ensures that the content and the size is committed into the
            database per chunk. This makes the process be reported correctly.
            """
            with rfile.largefile.content.open("wb") as stream:
                buf = reader.read(self.read_size)
                stream.seek(0, 2)
                stream.write(buf)
                cksummer.update(buf)
                buf_len = len(buf)
                rfile.largefile.size += buf_len
                rfile.largefile.save(update_fields=["size"])
                if buf_len != self.read_size:
                    return True
                else:
                    return False

        # Write chunks until it says its done.
        while not self._cancel_finalize:
            if write_chunk():
                break

        # Don't check the checksum if finalization was cancelled.
        if self._cancel_finalize:
            return

        if not cksummer.check():
            # Calculated sha256 hash from the data does not match, what
            # simplestreams is telling us it should be. This resource file
            # will be deleted since it is corrupt.
            msg = (
                "Failed to finalize boot image %s. Unexpected "
                "checksum '%s' (found: %s expected: %s)"
                % (
                    ident,
                    cksummer.algorithm,
                    cksummer.hexdigest(),
                    cksummer.expected,
                )
            )
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_ERROR, msg
            )
            maaslog.error(msg)
            transactional(rfile.delete)()
        else:
            log.debug("Finalized boot image {ident}.", ident=ident)

    def perform_write(self):
        """Performs all writing of content into the object storage.

        This method will spawn threads to perform the writing. Maximum of
        `write_threads` will be running at once."""
        threads = []
        while True:
            # Update list to only those that are still running.
            threads = [thread for thread in threads if thread.is_alive()]
            if len(threads) >= self.write_threads:
                # Cannot start any more threads as the maximum is already
                # running. Lets wait a second and try again.
                time.sleep(1)
                continue

            if self._cancel_finalize or len(self._content_to_finalize) == 0:
                # No more threads to spawn because the finalization has been
                # cancelled or all of the content has been de-queued. Wait for
                # all the remaining running threads to finish.
                for thread in threads:
                    thread.join()
                break

            # Spawn a writer thread with a resource file and reader from
            # the queue of content to be saved.
            rid, reader = self._content_to_finalize.popitem()
            # FIXME: Use deferToDatabase and the coiterator if possible.
            thread = threading.Thread(
                target=self.write_content_thread, args=(rid, reader)
            )
            thread.start()
            threads.append(thread)

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
                        log.debug(
                            "Deleting boot image {ident}.",
                            ident=self.get_resource_identity(delete_resource),
                        )
                        delete_resource.delete()
                    else:
                        msg = (
                            "Boot image %s no longer exists in stream, but "
                            "remains in selections. To delete this image "
                            "remove its selection."
                            % self.get_resource_identity(delete_resource)
                        )
                        Event.objects.create_region_event(
                            EVENT_TYPES.REGION_IMPORT_INFO, msg
                        )
                        maaslog.info(msg)
                else:
                    # No resource set on the boot resource so it should be
                    # removed as it has not files.
                    log.debug(
                        "Deleting boot image {ident}.",
                        ident=self.get_resource_identity(delete_resource),
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
                        "Deleting incomplete resourceset {set}.",
                        set=resource_set,
                    )
                    resource_set.delete()
                else:
                    # It is complete, only keep the newest complete set.
                    if not found_complete:
                        found_complete = True
                    else:
                        log.debug(
                            "Deleting obsolete resourceset {set}.",
                            set=resource_set,
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
                log.debug("Deleting empty resource {res}.", res=resource)
                resource.delete()

    @transactional
    def delete_content_to_finalize(self):
        """Deletes all content that was set to be finalized."""
        for rid in self._content_to_finalize.keys():
            BootResourceFile.objects.filter(id=rid).delete()
        self._content_to_finalize = {}

    def finalize(self, notify=None):
        """Perform the finalization of data into the database.

        This will remove the un-needed `BootResource`'s and write the
        file data into the large object store.

        :param notify: Instance of `Deferred` that is called when all the
            metadata has been downloaded and the image data download has been
            started.
        """
        # XXX blake_r 2014-10-30 bug=1387133: A scenario can occur where insert
        # never gets called by the writer, causing this method to delete all
        # of the synced resources. The actual cause of this issue is unknown,
        # but we want to handle the case or all the images will be deleted and
        # no nodes will be able to be provisioned.
        log.debug(
            "Finalize will delete {num} images(s).",
            num=len(self._resources_to_delete),
        )
        log.debug(
            "Finalize will save {num} new images(s).",
            num=len(self._content_to_finalize),
        )
        if (
            self._resources_to_delete == self._init_resources_to_delete
            and len(self._content_to_finalize) == 0
        ):
            error_msg = (
                "Finalization of imported images skipped, "
                "or all %s synced images would be deleted."
                % (self._resources_to_delete)
            )
            Event.objects.create_region_event(
                EVENT_TYPES.REGION_IMPORT_ERROR, error_msg
            )
            maaslog.error(error_msg)
            if notify is not None:
                failure = Failure(Exception(error_msg))
                reactor.callFromThread(notify.errback, failure)
            return

        # Cancel finalize was set before the threading operation is started.
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
            self.perform_write()
            if self._cancel_finalize:
                self.delete_content_to_finalize()
            self.resource_set_cleaner()

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
            # Setting to True triggers that running thread spawning process
            # to stop, and perform the cleanup.
            self._cancel_finalize = True


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
                "max_items": 1
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

    def insert_item(self, data, src, target, pedigree, contentsource):
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
                    "Ignoring %s, requires a newer version of MAAS(%s)"
                    % (product_name, supported_version)
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
                "Ignoring unsupported filetype(%s) from %s %s"
                % (item["ftype"], product_name, version_name)
            )
            return
        elif not validate_product(item, product_name):
            maaslog.warning("Ignoring unsupported product %s" % product_name)
            return
        else:
            self.store.insert(item, contentsource)


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
    try:
        reader = UrlMirrorReader(
            mirror, policy=policy, user_agent=get_maas_user_agent()
        )
    except TypeError:
        # UrlMirrorReader doesn't support the user_agent argument.
        # simplestream >=bzr429 is required for this feature.
        reader = UrlMirrorReader(mirror, policy=policy)
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
            msg = "Importing images from source: %s" % source["url"]
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
    # Avoid circular import.
    from maasserver.clusterrpc.boot_images import RackControllersImporter

    # Sync boot resources into the region.
    d = deferToDatabase(_import_resources_with_lock, notify=notify)

    def cb_import(_):
        d = deferToDatabase(RackControllersImporter.new)
        d.addCallback(lambda importer: importer.run())
        return d

    def eb_import(failure):
        failure.trap(DatabaseLockNotHeld)
        maaslog.info("Skipping import as another import is already running.")

    return d.addCallbacks(cb_import, eb_import)


def _import_resources_without_lock(notify=None):
    """Import boot resources once the `import_images` without a lock.

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

    # Cache the boot sources before import.
    cache_boot_sources()

    # FIXME: This modifies the environment of the entire process, which is Not
    # Cool. We should integrate with simplestreams in a more Pythonic manner.
    set_simplestreams_env()

    with tempdir("keyrings") as keyrings_path:
        sources = get_boot_sources()
        sources = write_all_keyrings(keyrings_path, sources)
        msg = "Started importing of boot images from %d source(s)." % len(
            sources
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
            _import_resources_without_lock(notify)
        else:
            maaslog.info(
                "Finished importing of boot images from %d source(s).",
                len(sources),
            )
    else:
        maaslog.warning(
            "Importing of boot images from %d source(s) was cancelled.",
            len(sources),
        )


@synchronous
@with_connection
@synchronised(locks.import_images.TRY)  # TRY is important; read docstring.
def _import_resources_with_lock(notify=None):
    """Import boot resources once the `import_images` lock is held."""
    return _import_resources_without_lock(notify)


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
        # Nothing to do as its not running.
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
        yield pause(0.2)


# How often the import service runs.
IMPORT_RESOURCES_SERVICE_PERIOD = timedelta(hours=1)


class ImportResourcesService(TimerService):
    """Service to periodically import boot resources.

    This will run immediately when it's started, then once again every hour,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=IMPORT_RESOURCES_SERVICE_PERIOD):
        super().__init__(interval.total_seconds(), self.maybe_import_resources)

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
            # The region has boot resources. The racks will too soon if
            # they haven't already. Nothing to see here, please move along.
            yield deferToDatabase(self.clear_import_warning)
        else:
            # We can ask racks if they somehow have some imported images
            # already, from another source perhaps. We can provide a better
            # message to the user in this case.
            if (yield self.are_boot_images_available_in_any_rack()):
                warning = self.warning_rack_has_boot_images
            else:
                warning = self.warning_rack_has_no_boot_images
            yield deferToDatabase(self.set_import_warning, warning)

    warning_rack_has_boot_images = dedent(
        """\
    One or more of your rack controller(s) currently has boot images, but your
    region controller does not. Machines will not be able to provision until
    you import boot images into the region. Visit the
    <a href="%(images_link)s">boot images</a> page to start the import.
    """
    )

    warning_rack_has_no_boot_images = dedent(
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

    @asynchronous(timeout=90)
    def are_boot_images_available_in_any_rack(self):
        """Return true if there are boot images available in any rack.

        Only considers racks that are currently connected, and ignores
        errors resulting from communicating with the racks.
        """
        clients = getAllClients()

        def get_images(client):
            d = client(ListBootImages)
            d.addCallback(itemgetter("images"))
            return d

        d = DeferredList(map(get_images, clients), consumeErrors=True)

        def has_boot_images(results):
            return any(
                len(result) > 0
                for success, result in results
                if success  # Ignore failures.
            )

        return d.addCallback(has_boot_images)


def export_images_from_db(target_dir: Path):
    def _unlink_largefile(file):
        file.sha256 = file.largefile.sha256
        file.size = file.largefile.total_size
        file.largefile = None
        file.save()

    log.info(f"Exporting image files to {target_dir}")
    target_dir.mkdir(parents=True, exist_ok=True)

    largefile_ids_to_delete = set()
    oids_to_delete = set()
    with transaction.atomic():
        files = BootResourceFile.objects.all().select_related("largefile")

        expected_images = set()
        for file in files:
            imagename = file.largefile.sha256

            def msg(message: str):
                log.msg(f"{imagename}: {message}")

            total_size = file.largefile.total_size
            if file.largefile.size != total_size:
                msg(f"skipping, size is {file.largefile.size} of {total_size}")
                oids_to_delete.add(file.largefile.content.oid)
                continue

            image = target_dir / imagename
            expected_images.add(image)

            if image.exists() and image.lstat().st_size == total_size:
                msg("skipping, file already present")
                largefile_ids_to_delete.add(file.largefile_id)
                _unlink_largefile(file)
                continue

            msg("writing")
            with (
                file.largefile.content.open("rb") as sfd,
                image.open("wb") as dfd,
            ):
                # read data in blocks to avoid using too much memory with big
                # images
                while data := sfd.read(1024 * 1024):
                    dfd.write(data)
                largefile_ids_to_delete.add(file.largefile_id)
                oids_to_delete.add(file.largefile.content.oid)
                _unlink_largefile(file)

        existing_images = set(target_dir.iterdir())
        for image in existing_images - expected_images:
            image.unlink()

        LargeFile.objects.filter(id__in=largefile_ids_to_delete).delete()
        with connection.cursor() as cursor:
            for oid in oids_to_delete:
                cursor.execute("SELECT lo_unlink(%s)", [oid])
