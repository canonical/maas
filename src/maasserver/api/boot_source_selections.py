# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootSourceSelection`"""

from django.shortcuts import get_object_or_404
from piston3.utils import rc

from maasserver.api.support import OperationsHandler
from maasserver.audit import create_audit_event
from maasserver.enum import ENDPOINT
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import BootSourceSelectionForm
from maasserver.models import BootSource, BootSourceSelection
from provisioningserver.events import EVENT_TYPES

DISPLAYED_BOOTSOURCESELECTION_FIELDS = (
    "boot_source_id",
    "id",
    "os",
    "release",
    "arches",
    "subarches",
    "labels",
)


class BootSourceSelectionHandler(OperationsHandler):
    """Manage a boot source selection."""

    api_doc_section_name = "Boot source selection"
    create = replace = None

    model = BootSourceSelection
    fields = DISPLAYED_BOOTSOURCESELECTION_FIELDS

    def read(self, request, boot_source_id, id):
        """@description-title Read a boot source selection
        @description Read a boot source selection with the given id.

        @param (string) "{boot_source_id}" [required=true] A boot-source id.
        @param (string) "{id}" [required=true] A boot-source selection id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        boot-source selection object.
        @success-example "success-json" [exkey=boot-source-sel-read-by-id]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source or boot-source
        selection is not found.
        @error-example "not-found"
            No BootSource matches the given query.
        """
        boot_source = get_object_or_404(BootSource, id=boot_source_id)
        return get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id
        )

    def update(self, request, boot_source_id, id):
        """@description-title Update a boot-source selection
        @description Update a boot source selection with the given id.

        @param (string) "{boot_source_id}" [required=true] A boot-source id.
        @param (string) "{id}" [required=true] A boot-source selection id.

        @param (string) "os" [required=false] The OS (e.g. ubuntu, centos) for
        which to import resources.

        @param (string) "release" [required=false] The release for which to
        import resources.

        @param (string) "arches" [required=false] The list of architectures for
        which to import resources.

        @param (string) "subarches" [required=false] The list of
        sub-architectures for which to import resources.

        @param (string) "labels" [required=false] The list of labels for which
        to import resources.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the requested
        boot-source selection object.
        @success-example "success-json" [exkey=boot-source-sel-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source or boot-source
        selection is not found.
        @error-example "not-found"
            No BootSource matches the given query.
        """
        boot_source = get_object_or_404(BootSource, id=boot_source_id)
        boot_source_selection = get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id
        )
        form = BootSourceSelectionForm(
            data=request.data, instance=boot_source_selection
        )
        if form.is_valid():
            boot_source_selection = form.save()
            create_audit_event(
                event_type=EVENT_TYPES.BOOT_SOURCE_SELECTION,
                endpoint=ENDPOINT.API,
                request=request,
                description=f"Updated boot source selection for {boot_source_selection.os}/{boot_source_selection.release} arches={boot_source_selection.arches}: {boot_source.url}",
            )
            return boot_source_selection
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, boot_source_id, id):
        """@description-title Delete a boot source
        @description Delete a boot source with the given id.

        @param (string) "{boot_source_id}" [required=true] A boot-source id.
        @param (string) "{id}" [required=true] A boot-source selection id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source or boot-source
        selection is not found.
        @error-example "not-found"
            No BootSource matches the given query.

        """
        boot_source = get_object_or_404(BootSource, id=boot_source_id)
        boot_source_selection = get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id
        )
        boot_source_selection.delete()
        create_audit_event(
            event_type=EVENT_TYPES.BOOT_SOURCE_SELECTION,
            endpoint=ENDPOINT.API,
            request=request,
            description=f"Deleted boot source selection for {boot_source_selection.os}/{boot_source_selection.release} arches={boot_source_selection.arches}",
        )
        return rc.DELETED

    @classmethod
    def resource_uri(cls, bootsourceselection=None):
        if bootsourceselection is None:
            id = "id"
            boot_source_id = "boot_source_id"
        else:
            id = bootsourceselection.id
            boot_source = bootsourceselection.boot_source
            boot_source_id = boot_source.id
        return ("boot_source_selection_handler", (boot_source_id, id))


class BootSourceSelectionsHandler(OperationsHandler):
    """Manage the collection of boot source selections."""

    api_doc_section_name = "Boot source selections"

    replace = update = delete = None

    @classmethod
    def resource_uri(cls, boot_source=None):
        if boot_source is None:
            boot_source_id = "boot_source_id"
        else:
            boot_source_id = boot_source.id
        return ("boot_source_selections_handler", [boot_source_id])

    def read(self, request, boot_source_id):
        """@description-title List boot-source selections
        @description List all available boot-source selections.

        @param (string) "{boot_source_id}" [required=true] A boot-source id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of all
        available boot-source selections.
        @success-example "success-json" [exkey=boot-source-sel-update]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source is not found.
        @error-example "not-found"
            No BootSource matches the given query.
        """
        boot_source = get_object_or_404(BootSource, id=boot_source_id)
        return BootSourceSelection.objects.filter(boot_source=boot_source)

    def create(self, request, boot_source_id):
        """@description-title Create a boot-source selection
        @description Create a new boot source selection.

        @param (string) "{boot_source_id}" [required=true] A boot-source id.

        @param (string) "os" [required=false] The OS (e.g. ubuntu, centos) for
        which to import resources.

        @param (string) "release" [required=false] The release for which to
        import resources.

        @param (string) "arches" [required=false] The architecture list for
        which to import resources.

        @param (string) "subarches" [required=false] The subarchitecture list
        for which to import resources.

        @param (string) "labels" [required=false] The label lists for which to
        import resources.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing the new
        boot-source selection.
        @success-example "success-json" [exkey=boot-source-sel-create]
        placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot-source is not found.
        @error-example "not-found"
            No BootSource matches the given query.

        """
        boot_source = get_object_or_404(BootSource, id=boot_source_id)
        form = BootSourceSelectionForm(
            data=request.data, boot_source=boot_source
        )
        if form.is_valid():
            boot_source_selection = form.save()
            create_audit_event(
                event_type=EVENT_TYPES.BOOT_SOURCE_SELECTION,
                endpoint=ENDPOINT.API,
                request=request,
                description=f"Created boot source selection for {boot_source_selection.os}/{boot_source_selection.release} arches={boot_source_selection.arches}: {boot_source.url}",
            )
            return boot_source_selection
        else:
            raise MAASAPIValidationError(form.errors)
