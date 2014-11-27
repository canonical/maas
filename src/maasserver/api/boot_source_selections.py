# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootSourceSelection`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootSourceSelectionHandler',
    'BootSourceSelectionsHandler',
    ]


from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.exceptions import MAASAPIValidationError
from maasserver.forms import BootSourceSelectionForm
from maasserver.models import (
    BootSource,
    BootSourceSelection,
    )
from piston.utils import rc


DISPLAYED_BOOTSOURCESELECTION_FIELDS = (
    'id',
    'os',
    'release',
    'arches',
    'subarches',
    'labels',
)


class BootSourceSelectionHandler(OperationsHandler):
    """Manage a boot source selection."""
    api_doc_section_name = "Boot source selection"
    create = replace = None

    model = BootSourceSelection
    fields = DISPLAYED_BOOTSOURCESELECTION_FIELDS

    def read(self, request, boot_source_id, id):
        """Read a boot source selection."""
        boot_source = get_object_or_404(
            BootSource, id=boot_source_id)
        return get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id)

    def update(self, request, boot_source_id, id):
        """Update a specific boot source selection.

        :param release: The release for which to import resources.
        :param arches: The list of architectures for which to import resources.
        :param subarches: The list of subarchitectures for which to import
            resources.
        :param labels: The list of labels for which to import resources.
        """
        boot_source = get_object_or_404(
            BootSource, id=boot_source_id)
        boot_source_selection = get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id)
        form = BootSourceSelectionForm(
            data=request.data, instance=boot_source_selection)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, boot_source_id, id):
        """Delete a specific boot source."""
        boot_source = get_object_or_404(
            BootSource, id=boot_source_id)
        boot_source_selection = get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id)
        boot_source_selection.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, bootsourceselection=None):
        if bootsourceselection is None:
            id = 'id'
            boot_source_id = 'boot_source_id'
        else:
            id = bootsourceselection.id
            boot_source = bootsourceselection.boot_source
            boot_source_id = boot_source.id
        return ('boot_source_selection_handler', (boot_source_id, id))


class BootSourceSelectionBackwardHandler(BootSourceSelectionHandler):
    """Manage a boot source selection.

    It used to be that boot-sources could be set per cluster. Now it can only
    be set globally for the whole region and clusters. This api is now
    deprecated, and only exists for backwards compatibility.
    """
    hidden = True

    def read(self, request, uuid, boot_source_id, id):
        """Read a boot source selection."""
        return super(BootSourceSelectionBackwardHandler, self).read(
            request, boot_source_id, id)

    def update(self, request, uuid, boot_source_id, id):
        """Update a specific boot source selection.

        :param release: The release for which to import resources.
        :param arches: The list of architectures for which to import resources.
        :param subarches: The list of subarchitectures for which to import
            resources.
        :param labels: The list of labels for which to import resources.
        """
        return super(BootSourceSelectionBackwardHandler, self).update(
            request, boot_source_id, id)

    def delete(self, request, uuid, boot_source_id, id):
        """Delete a specific boot source."""
        return super(BootSourceSelectionBackwardHandler, self).delete(
            request, boot_source_id, id)


class BootSourceSelectionsHandler(OperationsHandler):
    """Manage the collection of boot source selections."""
    api_doc_section_name = "Boot source selections"

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls, boot_source=None):
        if boot_source is None:
            boot_source_id = 'boot_source_id'
        else:
            boot_source_id = boot_source.id
        return ('boot_source_selections_handler', [boot_source_id])

    def read(self, request, boot_source_id):
        """List boot source selections.

        Get a listing of a boot source's selections.
        """
        boot_source = get_object_or_404(
            BootSource, id=boot_source_id)
        return BootSourceSelection.objects.filter(boot_source=boot_source)

    def create(self, request, boot_source_id):
        """Create a new boot source selection.

        :param release: The release for which to import resources.
        :param arches: The architecture list for which to import resources.
        :param subarches: The subarchitecture list for which to import
            resources.
        :param labels: The label lists for which to import resources.
        """
        boot_source = get_object_or_404(
            BootSource, id=boot_source_id)
        form = BootSourceSelectionForm(
            data=request.data, boot_source=boot_source)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class BootSourceSelectionsBackwardHandler(BootSourceSelectionsHandler):
    """Manage a boot source selection.

    It used to be that boot-sources could be set per cluster. Now it can only
    be set globally for the whole region and clusters. This api is now
    deprecated, and only exists for backwards compatibility.
    """
    hidden = True

    def read(self, request, uuid, boot_source_id):
        """List boot source selections.

        Get a listing of a boot source's selections.
        """
        return super(BootSourceSelectionsBackwardHandler, self).read(
            request, boot_source_id)

    def create(self, request, uuid, boot_source_id):
        """Create a new boot source selection.

        :param release: The release for which to import resources.
        :param arches: The architecture list for which to import resources.
        :param subarches: The subarchitecture list for which to import
            resources.
        :param labels: The label lists for which to import resources.
        """
        return super(BootSourceSelectionsBackwardHandler, self).create(
            request, boot_source_id)
