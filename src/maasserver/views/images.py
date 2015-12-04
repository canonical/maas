# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Image views."""

__all__ = [
    "ImagesView",
    "ImageDeleteView",
    ]

from collections import defaultdict
import json

from distro_info import UbuntuDistroInfo
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import (
    HttpResponse,
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
from maasserver.clusterrpc.boot_images import (
    get_common_available_boot_images,
    is_import_boot_images_running,
)
from maasserver.clusterrpc.osystems import get_os_release_title
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODE_STATUS,
)
from maasserver.models import (
    BootResource,
    BootSourceCache,
    BootSourceSelection,
    Config,
    LargeFile,
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

    def get(self, request, *args, **kwargs):
        # Load all the nodes, so its not done on every call
        # to the method get_number_of_nodes_deployed_for.
        self.nodes = Node.objects.filter(
            status__in=[NODE_STATUS.DEPLOYED, NODE_STATUS.DEPLOYING]).only(
            'osystem', 'distro_series')
        self.default_osystem = Config.objects.get_config(
            'default_osystem')
        self.default_distro_series = Config.objects.get_config(
            'default_distro_series')

        # Load list of boot resources that currently exist on all clusters.
        cluster_images = get_common_available_boot_images()
        self.clusters_syncing = is_import_boot_images_running()
        self.cluster_resources = (
            BootResource.objects.get_resources_matching_boot_images(
                cluster_images))

        # If the request is ajax, then return the list of resources as json.
        if request.is_ajax():
            return self.ajax(request, *args, **kwargs)
        return super(ImagesView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Return context data that is passed into the template."""
        context = super(ImagesView, self).get_context_data(**kwargs)
        context['region_import_running'] = is_import_resources_running()
        context['cluster_import_running'] = self.clusters_syncing
        context['connection_error'] = self.connection_error
        context['ubuntu_streams_count'] = len(self.ubuntu_sources)
        context['ubuntu_releases'] = self.format_ubuntu_releases()
        context['ubuntu_arches'] = self.format_ubuntu_arches()
        context['other_resources'] = self.get_other_resources()
        context['generated_resources'] = self.get_generated_resources()
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
        elif 'other_images' in request.POST:
            images = request.POST.getlist('image')
            self.update_other_images_source_selection(images)
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

    def get_resource_title(self, resource):
        """Return the title for the resource based on the type and name."""
        rtypes_with_split_names = [
            BOOT_RESOURCE_TYPE.SYNCED,
            BOOT_RESOURCE_TYPE.GENERATED,
            ]
        if resource.rtype in rtypes_with_split_names:
            os, series = resource.name.split('/')
            if resource.name.startswith('ubuntu/'):
                return format_ubuntu_distro_series(series)
            else:
                title = get_os_release_title(os, series)
                if title is None:
                    return resource.name
                else:
                    return title
        else:
            if 'title' in resource.extra and len(resource.extra['title']) > 0:
                return resource.extra['title']
            else:
                return resource.name

    def add_resource_template_attributes(self, resource):
        """Adds helper attributes to the resource."""
        resource.title = self.get_resource_title(resource)
        resource.arch, resource.subarch = resource.split_arch()
        resource.number_of_nodes = self.get_number_of_nodes_deployed_for(
            resource)
        resource_set = resource.get_latest_set()
        if resource_set is None:
            resource.size = format_size(0)
            resource.last_update = resource.updated
            resource.complete = False
            resource.status = "Queued for download"
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
                    resource.status = "Queued for download"
                    resource.downloading = False
            else:
                # See if the resource also exists on all the clusters.
                if resource in self.cluster_resources:
                    resource.status = "Complete"
                    resource.downloading = False
                else:
                    resource.complete = False
                    if self.clusters_syncing:
                        resource.status = "Syncing to clusters"
                        resource.downloading = True
                    else:
                        resource.status = "Waiting for clusters to sync"
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

    def get_other_synced_resources(self):
        """Return all synced resources that are not Ubuntu."""
        resources = list(BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.SYNCED).exclude(
            name__startswith='ubuntu/').order_by('-name', 'architecture'))
        for resource in resources:
            self.add_resource_template_attributes(resource)
        return resources

    def check_if_image_matches_resource(self, resource, image):
        """Return True if the resource matches the image."""
        os, series = resource.name.split('/')
        arch, subarch = resource.split_arch()
        if os != image.os or series != image.release or arch != image.arch:
            return False
        if not resource.supports_subarch(subarch):
            return False
        return True

    def get_matching_resource_for_image(self, resources, image):
        """Return True if the image matches one of the resources."""
        for resource in resources:
            if self.check_if_image_matches_resource(resource, image):
                return resource
        return None

    def get_other_resources(self):
        """Return all other resources if they are synced or not."""
        # Get the resource that already exist in the
        resources = self.get_other_synced_resources()
        images = list(BootSourceCache.objects.exclude(os='ubuntu'))
        for image in images:
            resource = self.get_matching_resource_for_image(resources, image)
            if resource is None:
                image.exists = False
                image.complete = False
                image.size = '-'
                image.last_update = 'not synced'
                image.status = ""
                image.downloading = False
                image.number_of_nodes = '-'
            else:
                self.add_resource_template_attributes(resource)
                image.exists = True
                image.complete = resource.complete
                image.size = resource.size
                image.last_update = resource.last_update
                image.status = resource.status
                image.downloading = resource.downloading
                image.number_of_nodes = (
                    self.get_number_of_nodes_deployed_for(resource))
            image.title = get_os_release_title(image.os, image.release)
            if image.title is None:
                image.title = '%s/%s' % (image.os, image.release)

        # Only superusers can change selections about other images, so we only
        # show the images that already exist for standard users.
        if not self.request.user.is_superuser:
            images = [
                image
                for image in images
                if image.exists
                ]
        return images

    def update_other_images_source_selection(self, images):
        """Update `BootSourceSelection`'s to only include the selected
        images."""
        # Remove all selections that are not Ubuntu.
        BootSourceSelection.objects.exclude(os='ubuntu').delete()

        # Break down the images into os/release with multiple arches.
        selections = defaultdict(list)
        for image in images:
            os, arch, _, release = image.split('/', 4)
            name = '%s/%s' % (os, release)
            selections[name].append(arch)

        # Create each selection for the source.
        for name, arches in selections.items():
            os, release = name.split('/')
            cache = BootSourceCache.objects.filter(
                os=os, arch=arch, release=release).first()
            if cache is None:
                # It is possible the cache changed while waiting for the user
                # to perform an action. Ignore the selection as its no longer
                # available.
                continue
            # Create the selection for the source.
            BootSourceSelection.objects.create(
                boot_source=cache.boot_source,
                os=os, release=release,
                arches=arches, subarches=["*"], labels=["*"])

        # Start the import process, now that the selections have changed.
        import_resources()

    def get_generated_resources(self):
        """Return all generated resources."""
        resources = list(BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.GENERATED).order_by(
            '-name', 'architecture'))
        for resource in resources:
            self.add_resource_template_attributes(resource)
        return resources

    def get_uploaded_resources(self):
        """Return all uploaded resources, for usage in the template."""
        resources = list(BootResource.objects.filter(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED).order_by(
            'name', 'architecture'))
        for resource in resources:
            self.add_resource_template_attributes(resource)
        return resources

    def pick_latest_datetime(self, time, other_time):
        """Return the datetime that is the latest."""
        if time is None:
            return other_time
        return max([time, other_time])

    def calculate_unique_size_for_resources(self, resources):
        """Return size of all unique largefiles for the given resources."""
        shas = set()
        size = 0
        for resource in resources:
            resource_set = resource.get_latest_set()
            if resource_set is None:
                continue
            for rfile in resource_set.files.all():
                try:
                    largefile = rfile.largefile
                except LargeFile.DoesNotExist:
                    continue
                if largefile.sha256 not in shas:
                    size += largefile.total_size
                    shas.add(largefile.sha256)
        return size

    def are_all_resources_complete(self, resources):
        """Return the complete status for all the given resources."""
        for resource in resources:
            resource_set = resource.get_latest_set()
            if resource_set is None:
                return False
            if not resource_set.complete:
                return False
        return True

    def get_last_update_for_resources(self, resources):
        """Return the latest updated time for all resources."""
        last_update = None
        for resource in resources:
            last_update = self.pick_latest_datetime(
                last_update, resource.updated)
            resource_set = resource.get_latest_set()
            if resource_set is not None:
                last_update = self.pick_latest_datetime(
                    last_update, resource_set.updated)
        return last_update

    def get_number_of_nodes_for_resources(self, resources):
        """Return the number of nodes used by all resources."""
        return sum([
            self.get_number_of_nodes_deployed_for(resource)
            for resource in resources])

    def get_progress_for_resources(self, resources):
        """Return the overall progress for all resources."""
        size = 0
        total_size = 0
        for resource in resources:
            resource_set = resource.get_latest_set()
            if resource_set is not None:
                size += resource_set.size
                total_size += resource_set.total_size
        if size <= 0:
            # Handle division by zero
            return 0
        return 100.0 * (size / float(total_size))

    def resource_group_to_resource(self, group):
        """Convert the list of resources into one resource to be used in
        the UI."""
        # Calculate all of the values using all of the resources for
        # this combination.
        last_update = self.get_last_update_for_resources(group)
        unique_size = self.calculate_unique_size_for_resources(group)
        number_of_nodes = self.get_number_of_nodes_for_resources(group)
        complete = self.are_all_resources_complete(group)
        progress = self.get_progress_for_resources(group)

        # Set the computed attributes on the first resource as that will
        # be the only one returned to the UI.
        resource = group[0]
        resource.arch, resource.subarch = resource.split_arch()
        resource.title = self.get_resource_title(resource)
        resource.complete = complete
        resource.size = format_size(unique_size)
        resource.last_update = last_update
        resource.number_of_nodes = number_of_nodes
        resource.complete = complete
        if not complete:
            if progress > 0:
                resource.status = "Downloading %3.0f%%" % progress
                resource.downloading = True
            else:
                resource.status = "Queued for download"
                resource.downloading = False
        else:
            # See if all the resources exist on all the clusters.
            cluster_has_resources = any(
                res in group for res in self.cluster_resources)
            if cluster_has_resources:
                resource.status = "Complete"
                resource.downloading = False
            else:
                resource.complete = False
                if self.clusters_syncing:
                    resource.status = "Syncing to clusters"
                    resource.downloading = True
                else:
                    resource.status = "Waiting for clusters to sync"
                    resource.downloading = False
        return resource

    def combine_resources(self, resources):
        """Return a list of resources combining all of subarchitecture
        resources into one resource."""
        resource_group = defaultdict(list)
        for resource in resources:
            arch = resource.split_arch()[0]
            key = '%s/%s' % (resource.name, arch)
            resource_group[key].append(resource)
        return [
            self.resource_group_to_resource(group)
            for _, group in resource_group.items()
            ]

    def ajax(self, request, *args, **kwargs):
        """Return all resources in a json object.

        This is used by the image model list on the client side to update
        the status of images."""
        resources = self.combine_resources(BootResource.objects.all())
        json_resources = [
            dict(
                id=resource.id,
                rtype=resource.rtype, name=resource.name,
                title=resource.title, arch=resource.arch, size=resource.size,
                complete=resource.complete, status=resource.status,
                downloading=resource.downloading,
                numberOfNodes=resource.number_of_nodes,
                lastUpdate=resource.last_update.strftime(
                    "%a, %d %b. %Y %H:%M:%S")
            )
            for resource in resources
            ]
        data = dict(
            region_import_running=is_import_resources_running(),
            cluster_import_running=self.clusters_syncing,
            resources=json_resources)
        json_data = json.dumps(data)
        return HttpResponse(json_data, content_type='application/json')


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
        if resource.rtype == BOOT_RESOURCE_TYPE.SYNCED:
            raise PermissionDenied()
        if resource.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            if 'title' in resource.extra:
                resource.title = resource.extra['title']
            else:
                resource.title = resource.name
        else:
            os, release = resource.name.split('/')
            title = get_os_release_title(os, release)
            if title is not None:
                resource.title = title
            else:
                resource.title = resource.name
        return resource

    def get_next_url(self):
        return reverse('images')

    def name_object(self, obj):
        """See `HelpfulDeleteView`."""
        title = ""
        if obj.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            if 'title' in obj.extra:
                title = obj.extra['title']
            else:
                title = obj.name
        else:
            os, release = obj.name.split('/')
            rpc_title = get_os_release_title(os, release)
            if rpc_title is not None:
                title = rpc_title
            else:
                title = obj.name
        return "%s (%s)" % (title, obj.architecture)
