# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Resources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ensure_boot_source_definition",
    "get_simplestream_endpoint",
    "simplestreams_file_handler",
    "simplestreams_stream_handler",
    "SIMPLESTREAMS_URL_REGEXP",
]

import threading
import time

from django.db import (
    close_old_connections,
    transaction,
    )
from django.http import (
    Http404,
    HttpResponse,
    StreamingHttpResponse,
    )
from django.shortcuts import get_object_or_404
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.fields import LargeObjectFile
from maasserver.models import (
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSource,
    BootSourceSelection,
    LargeFile,
    )
from maasserver.utils import absolute_reverse
from maasserver.utils.async import transactional
from maasserver.utils.orm import get_one
from provisioningserver.import_images.helpers import get_os_from_product
from provisioningserver.logger import get_maas_logger
from simplestreams import util as sutil
from simplestreams.objectstores import ObjectStore


maaslog = get_maas_logger("bootresources")

# Used by maasserver.middleware.AccessMiddleware to allow
# anonymous access to the simplestreams endpoint.
SIMPLESTREAMS_URL_REGEXP = '^/images-stream/'


def get_simplestream_endpoint():
    """Returns the simplestreams endpoint for the Region."""
    return {
        'url': absolute_reverse(
            'simplestreams_stream_handler', kwargs={'filename': 'index.json'}),
        'selections': [],
        }


def ensure_boot_source_definition():
    """Set default boot source if none is currently defined."""
    if not BootSource.objects.exists():
        source = BootSource.objects.create(
            url='http://maas.ubuntu.com/images/ephemeral-v2/releases/',
            keyring_filename=(
                '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'))
        # Default is to import newest Ubuntu LTS releases, for only amd64
        # release versions only.
        BootSourceSelection.objects.create(
            boot_source=source, release='trusty',
            arches=['amd64'], subarches=['*'], labels=['release'])


class TransactionWrapper:
    """Wraps `LargeObjectFile` in transaction, so `StreamingHttpResponse`
    can be used. Once the stream is done, then the transaction is
    closed.
    """

    def __init__(self, largeobject):
        self.largeobject = largeobject
        self._atomic = None
        self._stream = None

    def __iter__(self):
        return self

    def next(self):
        if self._atomic is None:
            self._atomic = transaction.atomic()
            self._atomic.__enter__()
        if self._stream is None:
            self._stream = self.largeobject.open('rb')
        data = self._stream.read(self.largeobject.block_size)
        if len(data) == 0:
            raise StopIteration
        return data

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        if self._atomic is not None:
            self._atomic.__exit__()
            self._atomic = None
        close_old_connections()


class SimpleStreamsHandler:
    """Simplestreams endpoint, that the clusters talk to.

    This is not called from piston, as piston uses emitters which
    breaks the ability to return streaming content.

    Anyone can access this endpoint. No credentials are required.
    """

    def get_json_response(self, content):
        """Return `HttpResponse` for JSON content."""
        response = HttpResponse(content.encode('utf-8'))
        response['Content-Type'] = "application/json"
        return response

    def get_boot_resource_identifiers(self, resource):
        """Return tuple (os, arch, subarch, series) for the given resource."""
        arch, subarch = resource.split_arch()
        if resource.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            os = 'custom'
            series = resource.name
        else:
            os, series = resource.name.split('/')
        return (os, arch, subarch, series)

    def get_product_name(self, resource):
        """Return product name for the given resource."""
        return 'maas:boot:%s:%s:%s:%s' % self.get_boot_resource_identifiers(
            resource)

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
            'index': {
                'maas:v2:download': {
                    'datatype': "image-downloads",
                    'path': "streams/v1/maas:v2:download.json",
                    'updated': updated,
                    'products': products,
                    'format': "products:1.0",
                    },
                },
            'updated': updated,
            'format': "index:1.0"
            }
        data = sutil.dump_data(index) + "\n"
        return self.get_json_response(data)

    def get_product_item(self, resource, resource_set, rfile):
        """Returns the item description for the `rfile`."""
        os, arch, subarch, series = self.get_boot_resource_identifiers(
            resource)
        path = '%s/%s/%s/%s/%s/%s' % (
            os, arch, subarch, series, resource_set.version, rfile.filename)
        item = {
            'path': path,
            'ftype': rfile.filetype,
            'sha256': rfile.largefile.sha256,
            'size': rfile.largefile.total_size,
            }
        item.update(rfile.extra)
        return item

    def get_product_data(self, resource):
        """Returns the product data for this resource."""
        os, arch, subarch, series = self.get_boot_resource_identifiers(
            resource)
        versions = {}
        label = None
        for resource_set in resource.sets.order_by('id').reverse():
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
                    resource, resource_set, rfile)
                for rfile in resource_set.files.all()
                }
            versions[resource_set.version] = {
                'items': items
                }
        product = {
            'versions': versions,
            'subarch': subarch,
            'label': label,
            'version': series,
            'arch': arch,
            'release': series,
            'krel': series,
            'os': os,
            }
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
            'datatype': "image-downloads",
            'updated': updated,
            'content_id': "maas:v2:download",
            'products': products,
            'format': "products:1.0"
            }
        data = sutil.dump_data(index) + "\n"
        return self.get_json_response(data)

    def streams_handler(self, request, filename):
        """Handles requests into the "streams/" content."""
        if filename == 'index.json':
            return self.get_product_index()
        elif filename == 'maas:v2:download.json':
            return self.get_product_download()
        raise Http404()

    def files_handler(
            self, request, os, arch, subarch, series, version, filename):
        """Handles requests for getting the boot resource data."""
        if os == "custom":
            name = series
        else:
            name = '%s/%s' % (os, series)
        arch = '%s/%s' % (arch, subarch)
        resource = get_object_or_404(
            BootResource, name=name, architecture=arch)
        try:
            resource_set = resource.sets.get(version=version)
        except BootResourceSet.DoesNotExist:
            raise Http404()
        try:
            rfile = resource_set.files.get(filename=filename)
        except BootResourceFile.DoesNotExist:
            raise Http404()
        response = StreamingHttpResponse(
            TransactionWrapper(rfile.largefile.content),
            content_type='application/octet-stream')
        response['Content-Length'] = rfile.largefile.total_size
        return response


def simplestreams_stream_handler(request, filename):
    handler = SimpleStreamsHandler()
    return handler.streams_handler(request, filename)


def simplestreams_file_handler(
        request, os, arch, subarch, series, version, filename):
    handler = SimpleStreamsHandler()
    return handler.files_handler(
        request, os, arch, subarch, series, version, filename)


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

    def __init__(self):
        """Initialize store."""
        self.cache_current_resources()
        self._content_to_finalize = {}

    def get_resource_identifiers(self, resource):
        """Return os, arch, subarch, and series for the given resource."""
        os, series = resource.name.split('/')
        arch, subarch = resource.split_arch()
        return os, arch, subarch, series

    def get_resource_identity(self, resource):
        """Return the formatted identity for the given resource."""
        return '%s/%s/%s/%s' % self.get_resource_identifiers(resource)

    def cache_current_resources(self):
        """Load all current synced resources into 'self._resources_to_delete'.

        Each resource that is being updated will be removed from the list. The
        remaining at the end of the sync will be removed.
        """
        self._resources_to_delete = {
            self.get_resource_identity(resource)
            for resource in BootResource.objects.filter(
                rtype=BOOT_RESOURCE_TYPE.SYNCED)
            }

    def prevent_resource_deletion(self, resource):
        """Remove the `BootResource` from the resources to delete list.

        This will make sure that this synced resource will not be deleted at
        the end of the syncing process.
        """
        ident = self.get_resource_identity(resource)
        if ident in self._resources_to_delete:
            self._resources_to_delete.remove(ident)

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
        series = product['release']
        arch = product['arch']
        subarch = product['subarch']
        name = '%s/%s' % (os, series)
        architecture = '%s/%s' % (arch, subarch)
        resource = get_one(
            BootResource.objects.filter(
                rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name,
                architecture=architecture))
        if resource is None:
            # No resource currently exists for this product.
            resource = BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name,
                architecture=architecture)
        else:
            # Resource already exists and was in the simplestream content,
            # so we do not want it removed.
            self.prevent_resource_deletion(resource)

        # Simplestreams content from maas.ubuntu.com includes the following
        # extra fields. Looping through the extra product data and adding it to
        # extra will not work as the product data that is passed into this
        # object store contains additional data that should not be stored into
        # the database. If kflavor and/or subarches exist in the product then
        # we store those values to expose in the simplestreams endpoint on the
        # region.
        resource.extra = {}
        if 'kflavor' in product:
            resource.extra['kflavor'] = product['kflavor']
        if 'subarches' in product:
            resource.extra['subarches'] = product['subarches']

        resource.save()
        return resource

    def get_or_create_boot_resource_set(self, resource, product):
        """Get existing `BootResourceSet` for the given resource and product
        or create a new one if one does not exist."""
        version = product['version_name']
        resource_set = get_one(resource.sets.filter(version=version))
        if resource_set is None:
            resource_set = BootResourceSet(resource=resource, version=version)
        resource_set.label = product['label']
        resource_set.save()
        return resource_set

    def get_or_create_boot_resource_file(self, resource_set, product):
        """Get existing `BootResourceFile` for the given resource set and
        product or create a new one if one does not exist."""
        # For synced resources the filename is the same as the filetype. This
        # is the way the data is from maas.ubuntu.com so we emulate that here.
        filetype = product['ftype']
        filename = filetype
        rfile = get_one(resource_set.files.filter(filename=filename))
        if rfile is None:
            rfile = BootResourceFile(
                resource_set=resource_set, filename=filename)
        rfile.filetype = filetype
        rfile.extra = {}

        # Simplestreams content from maas.ubuntu.com includes the following
        # extra fields. Looping through the extra product data and adding it to
        # extra will not work as the product data that is passed into this
        # object store contains additional data that should not be stored into
        # the database. If kpackage and/or di_version exist in the product then
        # we store those values to expose in the simplestreams endpoint on the
        # region.
        if 'kpackage' in product:
            rfile.extra['kpackage'] = product['kpackage']
        if 'di_version' in product:
            rfile.extra['di_version'] = product['di_version']

        # Don't save rfile here, because if new then largefile is None which
        # will cause a ValidationError. The setting of largefile and saving of
        # object should be handled by the calling function.
        return rfile

    def get_resource_file_log_identifier(
            self, rfile, resource_set=None, resource=None):
        """Return identifier that is used for the maaslog."""
        if resource_set is None:
            resource_set = rfile.resource_set
        if resource is None:
            resource = resource_set.resource
        return '%s/%s/%s' % (
            self.get_resource_identity(resource),
            resource_set.version, rfile.filename)

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
        resource_set = self.get_or_create_boot_resource_set(
            resource, product)
        rfile = self.get_or_create_boot_resource_file(
            resource_set, product)

        checksums = sutil.item_checksums(product)
        sha256 = checksums['sha256']
        total_size = int(product['size'])
        needs_saving = False
        prev_largefile = None

        try:
            largefile = rfile.largefile
        except LargeFile.DoesNotExist:
            largefile = None
        else:
            if largefile.sha256 != sha256:
                # The content from simplestreams is different then what is in
                # the database. We hold the previous largefile so that it can
                # be removed once the new largefile is created. The largefile
                # cannot be removed here, because then the `BootResourceFile`
                # would have to set the largefile field to null, and that is
                # not allowed.
                prev_largefile = largefile
                largefile = None

        if largefile is None:
            # The resource file current does not have a largefile linked. Lets
            # check that a largefile does not already exist for this sha256.
            # If it does then there will be no reason to save the content into
            # the database.
            largefile = get_one(
                LargeFile.objects.filter(sha256=sha256))

        if largefile is None:
            # No largefile exist for this resource file in the database, so a
            # new one will be created to store the data for this file.
            largeobject = LargeObjectFile()
            largeobject.open().close()
            largefile = LargeFile.objects.create(
                sha256=sha256, total_size=total_size,
                content=largeobject)
            needs_saving = True

        # A largefile now exists for this resource file. Its either a new
        # largefile or an existing one that already existed in the database.
        rfile.largefile = largefile
        rfile.save()

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
                rfile, resource_set, resource)
            maaslog.debug('Boot resource already up-to-date %s.' % ident)

    def write_content(self, rfile, reader):
        """Writes the data from the given reader, into the object storage
        for the given `BootResourceFile`."""
        ident = self.get_resource_file_log_identifier(rfile)
        cksummer = sutil.checksummer(
            {'sha256': rfile.largefile.sha256})
        maaslog.debug("Syncing boot resource %s." % ident)

        # Write the contents into the database, while calculating the sha256
        # hash for the read data.
        with rfile.largefile.content.open('wb') as stream:
            while True:
                buf = reader.read(self.read_size)
                stream.write(buf)
                cksummer.update(buf)
                if len(buf) != self.read_size:
                    break

        if not cksummer.check():
            # Calculated sha256 hash from the data does not match, what
            # simplestreams is telling us it should be. This resource file
            # will be deleted since it is corrupt.
            maaslog.error(
                "Failed to sync boot resource %s. Unexpected "
                "checksum '%s' (found: %s expected: %s)" % (
                    ident, cksummer.algorithm,
                    cksummer.hexdigest(), cksummer.expected,
                    ))
            rfile.delete()
        else:
            maaslog.debug('Finished syncing boot resource %s.' % ident)

    @transactional
    def write_content_thread(self, rid, reader):
        """Calls `write_content` inside its own thread."""
        rfile = BootResourceFile.objects.get(id=rid)
        self.write_content(rfile, reader)

    def perform_write(self):
        """Performs all writing of content into the object storage.

        This method will spawn threads to perform the writing. Maximum of
        `write_threads` will be running at once."""
        threads = []
        while True:
            # Update list to only those that are still running.
            threads = [thread for thread in threads if thread.isAlive()]
            if len(threads) >= self.write_threads:
                # Cannot start any more threads as the maximum is already
                # running. Lets wait a second and try again.
                time.sleep(1)
                continue

            if len(self._content_to_finalize) == 0:
                # No more threads to spawn as all of the content has
                # been de-queued. Let's wait for all the remaining running
                # threads to finish.
                for thread in threads:
                    thread.join()
                break

            # Spawn a writer thread with a resource file and reader from
            # the queue of content to be saved.
            rid, reader = self._content_to_finalize.popitem()
            thread = threading.Thread(
                target=self.write_content_thread,
                args=(rid, reader))
            thread.start()
            threads.append(thread)

    @transactional
    def resource_cleaner(self):
        """Removes all of the `BootResource`'s that were not synced."""
        for ident in self._resources_to_delete:
            os, arch, subarch, series = ident.split('/')
            name = '%s/%s' % (os, series)
            architecture = '%s/%s' % (arch, subarch)
            delete_resource = get_one(
                BootResource.objects.filter(
                    rtype=BOOT_RESOURCE_TYPE.SYNCED,
                    name=name, architecture=architecture))
            if delete_resource is not None:
                delete_resource.delete()

    @transactional
    def resource_set_cleaner(self):
        """Removes all of the old `BootResourceSet`'s for the synced
        `BootResource`'s."""
        # Remove the sets that are incomplete and older versions.
        for resource in BootResource.objects.filter(
                rtype=BOOT_RESOURCE_TYPE.SYNCED):
            found_complete = False
            # Reverse order by id, so that we keep the newest completed set.
            for resource_set in resource.sets.order_by('id').reverse():
                if not resource_set.complete:
                    # At this point all resource sets should be complete.
                    # Delete the extras that are not.
                    resource_set.delete()
                else:
                    # It is complete, only keep the newest complete set.
                    if not found_complete:
                        found_complete = True
                    else:
                        resource_set.delete()

        # Cleanup the resources that don't have sets. This is done because
        # it could be possible that the previous for loop removes all sets
        # from a boot resource, so the resource should be removed, instead
        # of being empty.
        for resource in BootResource.objects.filter(
                rtype=BOOT_RESOURCE_TYPE.SYNCED):
            if not resource.sets.exists():
                resource.delete()

    def finalize(self):
        """Perform the finalization of data into the database.

        This will remove the un-needed `BootResource`'s and write the
        file data into the large object store.
        """
        self.resource_cleaner()
        self.perform_write()
        self.resource_set_cleaner()
        close_old_connections()
