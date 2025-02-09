# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootSource`."""

from base64 import b64encode
import http.client

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper
from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import BootSourceForm
from maasserver.models import BootSource

DISPLAYED_BOOTSOURCE_FIELDS = (
    "id",
    "url",
    "keyring_filename",
    "keyring_data",
    "created",
    "updated",
)


class BootSourceHandler(OperationsHandler):
    """Manage a boot source."""

    api_doc_section_name = "Boot source"
    create = None

    model = BootSource
    fields = DISPLAYED_BOOTSOURCE_FIELDS

    def read(self, request, id):
        """@description-title Read a boot source
        @description Read a boot source with the given id.

        @param (string) "{id}" [required=true] A boot-source id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        boot-source object.
        @success-example "success-json" [exkey=boot-sources-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source is not found.
        @error-example "not-found"
            No BootSource matches the given query.
        """
        return get_object_or_404(BootSource, id=id)

    def update(self, request, id):
        """@description-title Update a boot source
        @description Update a boot source with the given id.

        @param (string) "{id}" [required=true] A boot-source id.

        @param (string) "url" [required=false] The URL of the BootSource.

        @param (string) "keyring_filename" [required=false] The path to the
        keyring file for this BootSource.

        @param (string) "keyring_data" [required=false] The GPG keyring for
        this BootSource, base64-encoded data.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the updated
        boot-source object.
        @success-example "success-json" [exkey=boot-sources-update] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source is not found.
        @error-example "not-found"
            No BootSource matches the given query.

        """
        boot_source = get_object_or_404(BootSource, id=id)
        form = BootSourceForm(
            data=request.data, files=request.FILES, instance=boot_source
        )
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, id):
        """@description-title Delete a boot source
        @description Delete a boot source with the given id.

        @param (string) "{id}" [required=true] A boot-source id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source is not found.
        @error-example "not-found"
            No BootSource matches the given query.
        """
        boot_source = get_object_or_404(BootSource, id=id)
        boot_source.delete()
        return rc.DELETED

    @classmethod
    def keyring_data(cls, boot_source):
        return b64encode(boot_source.keyring_data)

    @classmethod
    def resource_uri(cls, bootsource=None):
        if bootsource is None:
            id = "id"
        else:
            id = bootsource.id
        return ("boot_source_handler", (id,))


class BootSourcesHandler(OperationsHandler):
    """Manage the collection of boot sources."""

    api_doc_section_name = "Boot sources"
    update = delete = None

    @classmethod
    def resource_uri(cls):
        return ("boot_sources_handler", [])

    def read(self, request):
        """@description-title List boot sources
        @description List all boot sources.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of all
        available boot-source objects.
        @success-example "success-json" [exkey=boot-sources-read] placeholder
        text
        """
        return BootSource.objects.all()

    def create(self, request):
        """@description-title Create a boot source
        @description Create a new boot source. Note that in addition to
        ``url``, you must supply either ``keyring_data`` or
        ``keyring_filename``.

        @param (string) "url" [required=true] The URL of the BootSource.

        @param (string) "keyring_filename" [required=false] The path to the
        keyring file for this BootSource.

        @param (string) "keyring_data" [required=false] The GPG keyring for
        this BootSource, base64-encoded.

        @success (http-status-code) "server-success" 201
        @success (json) "success-json" A JSON object containing the new boot
        source.
        @success-example "success-json" [exkey=boot-sources-create] placeholder
        text
        """
        form = BootSourceForm(data=request.data, files=request.FILES)
        if form.is_valid():
            boot_source = form.save()
            handler = BootSourceHandler()
            emitter = JSONEmitter(
                boot_source, typemapper, handler, handler.fields, False
            )
            return HttpResponse(
                emitter.render(request),
                content_type="application/json; charset=utf-8",
                status=int(http.client.CREATED),
            )
        else:
            raise MAASAPIValidationError(form.errors)
