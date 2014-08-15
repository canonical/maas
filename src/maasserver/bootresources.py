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
    "get_simplestream_endpoint",
    "simplestreams_file_handler",
    "simplestreams_stream_handler",
    "SIMPLESTREAMS_URL_REGEXP",
]

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
from maasserver.models import (
    BootResource,
    BootResourceFile,
    BootResourceSet,
    )
from maasserver.utils import absolute_reverse
from simplestreams import util as sutil

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
