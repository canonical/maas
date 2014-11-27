# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootSource`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootSourceHandler',
    'BootSourcesHandler',
    ]

from base64 import b64encode
import httplib

from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import BootSourceForm
from maasserver.models import BootSource
from piston.emitters import JSONEmitter
from piston.handler import typemapper
from piston.utils import rc


DISPLAYED_BOOTSOURCE_FIELDS = (
    'id',
    'url',
    'keyring_filename',
    'keyring_data',
)


def json_boot_source(boot_source, request):
    """Convert boot_source into a json object.

    Use the same fields used when serialising objects, but base64-encode
    keyring_data.
    """
    dict_representation = {
        fieldname: getattr(boot_source, fieldname)
        for fieldname in DISPLAYED_BOOTSOURCE_FIELDS
        }
    # Encode the keyring_data as base64.
    keyring_data = getattr(boot_source, 'keyring_data')
    dict_representation['keyring_data'] = b64encode(keyring_data)
    dict_representation['resource_uri'] = reverse(
        'boot_source_handler',
        args=[boot_source.id])
    emitter = JSONEmitter(dict_representation, typemapper, None)
    stream = emitter.render(request)
    return stream


class BootSourceHandler(OperationsHandler):
    """Manage a boot source."""
    api_doc_section_name = "Boot source"
    create = replace = None

    model = BootSource
    fields = DISPLAYED_BOOTSOURCE_FIELDS

    def read(self, request, id):
        """Read a boot source."""
        boot_source = get_object_or_404(
            BootSource, id=id)
        stream = json_boot_source(boot_source, request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    def update(self, request, id):
        """Update a specific boot source.

        :param url: The URL of the BootSource.
        :param keyring_filename: The path to the keyring file for this
            BootSource.
        :param keyring_filename: The GPG keyring for this BootSource,
            base64-encoded data.
        """
        boot_source = get_object_or_404(
            BootSource, id=id)
        form = BootSourceForm(
            data=request.data, files=request.FILES, instance=boot_source)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """Delete a specific boot source."""
        boot_source = get_object_or_404(
            BootSource, id=id)
        boot_source.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, bootsource=None):
        if bootsource is None:
            id = 'id'
        else:
            id = bootsource.id
        return ('boot_source_handler', (id, ))


class BootSourceBackwardHandler(BootSourceHandler):
    """Manage a boot source.

    It used to be that boot-sources could be set per cluster. Now it can only
    be set globally for the whole region and clusters. This api is now
    deprecated, and only exists for backwards compatibility.
    """
    hidden = True

    def read(self, request, uuid, id):
        """Read a boot source."""
        return super(BootSourceBackwardHandler, self).read(request, id)

    def update(self, request, uuid, id):
        """Update a specific boot source.

        :param url: The URL of the BootSource.
        :param keyring_filename: The path to the keyring file for this
            BootSource.
        :param keyring_filename: The GPG keyring for this BootSource,
            base64-encoded data.
        """
        return super(BootSourceBackwardHandler, self).update(request, id)

    def delete(self, request, uuid, id):
        """Delete a specific boot source."""
        return super(BootSourceBackwardHandler, self).delete(request, id)


class BootSourcesHandler(OperationsHandler):
    """Manage the collection of boot sources."""
    api_doc_section_name = "Boot sources"

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls):
        return ('boot_sources_handler', [])

    def read(self, request):
        """List boot sources.

        Get a listing of boot sources.
        """
        return BootSource.objects.all()

    def create(self, request):
        """Create a new boot source.

        :param url: The URL of the BootSource.
        :param keyring_filename: The path to the keyring file for
            this BootSource.
        :param keyring_data: The GPG keyring for this BootSource,
            base64-encoded.
        """
        form = BootSourceForm(
            data=request.data, files=request.FILES)
        if form.is_valid():
            boot_source = form.save()
            stream = json_boot_source(boot_source, request)
            return HttpResponse(
                stream, mimetype='application/json; charset=utf-8',
                status=httplib.CREATED)
        else:
            raise MAASAPIValidationError(form.errors)


class BootSourcesBackwardHandler(BootSourcesHandler):
    """Manage the collection of boot sources.

    It used to be that boot-sources could be set per cluster. Now it can only
    be set globally for the whole region and clusters. This api is now
    deprecated, and only exists for backwards compatibility.
    """
    hidden = True

    def read(self, request, uuid):
        """List boot sources.

        Get a listing of a cluster's boot sources.

        :param uuid: This is deprecated, only exists for backwards
            compatibility. Boot sources are now global for all of MAAS.
        """
        return super(BootSourcesBackwardHandler, self).read(request)

    def create(self, request, uuid):
        """Create a new boot source.

        :param url: The URL of the BootSource.
        :param keyring_filename: The path to the keyring file for
            this BootSource.
        :param keyring_data: The GPG keyring for this BootSource,
            base64-encoded.
        """
        return super(BootSourcesBackwardHandler, self).create(request)
