# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Image views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ImagesView",
    "ImageDeleteView",
    ]


from distro_info import UbuntuDistroInfo
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponseForbidden,
    HttpResponseRedirect,
    )
from django.shortcuts import get_object_or_404
from django.views.generic.base import TemplateView
from django.views.generic.edit import (
    FormMixin,
    ProcessFormView,
    )
from maasserver.bootresources import (
    import_resources,
    is_import_resources_running,
    )
from maasserver.bootsources import get_os_info_from_boot_sources
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODE_STATUS,
    )
from maasserver.models import (
    BootResource,
    BootSourceSelection,
    Config,
    Node,
    )
from maasserver.views import HelpfulDeleteView
from requests import ConnectionError


def format_size(size):
    """Formats the size into human readable."""
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return "%3.1f %s" % (size, x)
        size /= 1024.0
    return "%3.1f %s" % (size, ' TB')


def get_distro_series_info_row(series):
    """Returns the distro series row information from python-distro-info.
    """
    info = UbuntuDistroInfo()
    for row in info._avail(info._date):
        if row['series'] == series:
            return row
    return None


def format_ubuntu_distro_series(series):
    """Formats the Ubuntu distro series into a version name."""
    row = get_distro_series_info_row(series)
    if row is None:
        return series
    return row['version']


class ImagesView(TemplateView, FormMixin, ProcessFormView):
    template_name = 'maasserver/images.html'
    context_object_name = "images"
    status = None

    def __init__(self, *args, **kwargs):
        super(ImagesView, self).__init__(*args, **kwargs)

        # Load the Ubuntu info from the `BootSource`'s. This is done in
        # __init__ so that it is not done, more that once.
        try:
            sources, releases, arches = get_os_info_from_boot_sources('ubuntu')
            self.connection_error = False
            self.ubuntu_sources = sources
            self.ubuntu_releases = releases
            self.ubuntu_arches = arches
        except ConnectionError:
            self.connection_error = True
            self.ubuntu_sources = []
            self.ubuntu_releases = set()
            self.ubuntu_arches = set()

    def get(self, *args, **kwargs):
        # Load all the nodes, so its not done on every call
        # to the method get_number_of_nodes_deployed_for.
        self.nodes = Node.objects.filter(
            status__in=[NODE_STATUS.DEPLOYED, NODE_STATUS.DEPLOYING]).only(
            'osystem', 'distro_series')
        self.default_osystem = Config.objects.get_config(
            'default_osystem')
        self.default_distro_series = Config.objects.get_config(
            'default_distro_series')
        return super(ImagesView, self).get(*args, **kwargs)

    def get_context_data(self, **kwargs):
        """Return context data that is passed into the template."""
        context = super(ImagesView, self).get_context_data(**kwargs)
        context['import_running'] = is_import_resources_running()
        context['connection_error'] = self.connection_error
        context['ubuntu_streams_count'] = len(self.ubuntu_sources)
        context['ubuntu_releases'] = self.format_ubuntu_releases()
        context['ubuntu_arches'] = self.format_ubuntu_arches()
        context['ubuntu_resources'] = self.get_ubuntu_resources()
        context['uploaded_resources'] = self.get_uploaded_resources()
        return context

    def post(self, request, *args, **kwargs):
        """Handle a POST request."""
        # Only administrators can change options on this page.
        if not self.request.user.is_superuser:
            return HttpResponseForbidden()
        if 'ubuntu_images' in request.POST:
            releases = request.POST.getlist('release')
            arches = request.POST.getlist('arch')
            self.update_source_selection(
                self.ubuntu_sources[0], 'ubuntu', releases, arches)
            return HttpResponseRedirect(reverse('images'))
        else:
            # Unknown action: redirect to the images page (this
            # shouldn't happen).
            return HttpResponseRedirect(reverse('images'))

    def get_ubuntu_release_selections(self):
        """Return list of all selected releases for Ubuntu. If first item in
        tuple is true, then all releases are selected by wildcard."""
        all_selected = False
        releases = set()
        for selection in BootSourceSelection.objects.all():
            if selection.os == "ubuntu":
                if selection.release == "*":
                    all_selected = True
                else:
                    releases.add(selection.release)
        return all_selected, releases

    def format_ubuntu_releases(self):
        """Return formatted Ubuntu release selections for the template."""
        releases = []
        all_releases, selected_releases = self.get_ubuntu_release_selections()
        for release in sorted(list(self.ubuntu_releases), reverse=True):
            if all_releases or release in selected_releases:
                checked = True
            else:
                checked = False
            releases.append({
                'name': release,
                'title': format_ubuntu_distro_series(release),
                'checked': checked,
                })
        return releases

    def get_ubuntu_arch_selections(self):
        """Return list of all selected arches for Ubuntu. If first item in
        tuple is true, then all arches are selected by wildcard."""
        all_selected = False
        arches = set()
        for selection in BootSourceSelection.objects.all():
            if selection.os == "ubuntu":
                for arch in selection.arches:
                    if arch == "*":
                        all_selected = True
                    else:
                        arches.add(arch)
        return all_selected, arches

    def format_ubuntu_arches(self):
        """Return formatted Ubuntu architecture selections for the template."""
        arches = []
        all_arches, selected_arches = self.get_ubuntu_arch_selections()
        for arch in sorted(list(self.ubuntu_arches)):
            if all_arches or arch in selected_arches:
                checked = True
            else:
                checked = False
            arches.append({
                'name': arch,
                'title': arch,
                'checked': checked,
                })
        return arches

    def get_ubuntu_resources(self):
        """Return all Ubuntu resources, for usage in the template."""
        resources = list(BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name__startswith='ubuntu/').order_by('-name', 'architecture'))
        for resource in resources:
            resource.os, resource.series = resource.name.split('/')
            resource.title = format_ubuntu_distro_series(resource.series)
            resource.number_of_nodes = self.get_number_of_nodes_deployed_for(
                resource)
            self.add_resource_template_attributes(resource)
        return resources

    def add_resource_template_attributes(self, resource):
        """Adds helper attributes to the resource."""
        resource.arch, resource.subarch = resource.split_arch()
        resource_set = resource.get_latest_set()
        if resource_set is None:
            resource.size = format_size(0)
            resource.last_update = resource.updated
            resource.complete = False
            resource.status = "Queued"
            resource.downloading = False
        else:
            resource.size = format_size(resource_set.total_size)
            resource.last_update = resource_set.updated
            resource.complete = resource_set.complete
            if not resource.complete:
                progress = resource_set.progress
                if progress > 0:
                    resource.status = "Downloading %3.0f%%" % progress
                    resource.downloading = True
                else:
                    resource.status = "Queued"
                    resource.downloading = False
            else:
                resource.status = "Queued"
                resource.downloading = False

    def node_has_architecture_for_resource(self, node, resource):
        """Return True if node is the same architecture as resource."""
        arch, _ = resource.split_arch()
        node_arch, node_subarch = node.split_arch()
        return arch == node_arch and resource.supports_subarch(node_subarch)

    def get_number_of_nodes_deployed_for(self, resource):
        """Return number of nodes that are deploying the given
        os, series, and architecture."""
        if resource.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            osystem = 'custom'
            distro_series = resource.name
        else:
            osystem, distro_series = resource.name.split('/')

        # Count the number of nodes with same os/release and architecture.
        count = 0
        for node in self.nodes.filter(
                osystem=osystem, distro_series=distro_series):
            if self.node_has_architecture_for_resource(node, resource):
                count += 1

        # Any node that is deployed without osystem and distro_series,
        # will be using the defaults.
        if (self.default_osystem == osystem and
                self.default_distro_series == distro_series):
            for node in self.nodes.filter(
                    osystem="", distro_series=""):
                if self.node_has_architecture_for_resource(node, resource):
                    count += 1
        return count

    def update_source_selection(self, boot_source, os, releases, arches):
        # Remove all selections, that are not of release.
        BootSourceSelection.objects.filter(
            boot_source=boot_source, os=os).exclude(
            release__in=releases).delete()

        if len(releases) > 0:
            # Create or update the selections.
            for release in releases:
                selection, _ = BootSourceSelection.objects.get_or_create(
                    boot_source=boot_source, os=os, release=release)
                selection.arches = arches
                selection.subarches = ["*"]
                selection.labels = ["*"]
                selection.save()
        else:
            # Create a selection that will cause nothing to be downloaded,
            # since no releases are selected.
            selection, _ = BootSourceSelection.objects.get_or_create(
                boot_source=boot_source, os=os, release="")
            selection.arches = arches
            selection.subarches = ["*"]
            selection.labels = ["*"]
            selection.save()

        # Start the import process, now that the selections have changed.
        import_resources()

    def get_uploaded_resources(self):
        """Return all uploaded resources, for usage in the template."""
        resources = list(BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED).order_by(
            'name', 'architecture'))
        for resource in resources:
            if 'title' in resource.extra:
                resource.title = resource.extra['title']
            else:
                resource.title = resource.name
            resource.number_of_nodes = self.get_number_of_nodes_deployed_for(
                resource)
            self.add_resource_template_attributes(resource)
        return resources


class ImageDeleteView(HelpfulDeleteView):

    template_name = 'maasserver/image_confirm_delete.html'
    context_object_name = 'image_to_delete'
    model = BootResource

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied()
        return super(ImageDeleteView, self).post(request, *args, **kwargs)

    def get_object(self):
        resource_id = self.kwargs.get('resource_id', None)
        resource = get_object_or_404(BootResource, id=resource_id)
        if resource.rtype != BOOT_RESOURCE_TYPE.UPLOADED:
            raise PermissionDenied()
        if 'title' in resource.extra:
            resource.title = resource.extra['title']
        else:
            resource.title = resource.name
        return resource

    def get_next_url(self):
        return reverse('images')

    def name_object(self, obj):
        """See `HelpfulDeleteView`."""
        if 'title' in obj.extra:
            return "%s (%s)" % (obj.extra['title'], obj.architecture)
        else:
            return "%s (%s)" % (obj.name, obj.architecture)
