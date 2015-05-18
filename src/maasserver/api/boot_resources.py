# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootResouce`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'BootResourceHandler',
    'BootResourcesHandler',
    'BootResourceFileUploadHandler',
    ]

import httplib
import os

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_optional_param
from maasserver.bootresources import import_resources
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIForbidden,
    MAASAPIValidationError,
)
from maasserver.forms import (
    BootResourceForm,
    BootResourceNoContentForm,
)
from maasserver.models import (
    BootResource,
    BootResourceFile,
    NodeGroup,
)
from piston.emitters import JSONEmitter
from piston.handler import typemapper
from piston.utils import rc


TYPE_MAPPING = {
    'synced': BOOT_RESOURCE_TYPE.SYNCED,
    'generated': BOOT_RESOURCE_TYPE.GENERATED,
    'uploaded': BOOT_RESOURCE_TYPE.UPLOADED,
}


# XXX blake_r 2014-09-22 bug=1361370: We currently allow both generated and
# uploaded resource to be uploaded. This is until the MAAS can generate its
# own images.
ALLOW_UPLOAD_RTYPES = [
    BOOT_RESOURCE_TYPE.GENERATED,
    BOOT_RESOURCE_TYPE.UPLOADED,
    ]


def get_content_parameter(request):
    """Get the "content" parameter from a POST or PUT."""
    content = get_optional_param(request.FILES, 'content', None)
    if content is None:
        return None
    return content.read()


def boot_resource_file_to_dict(rfile):
    """Return dictionary representation of `BootResourceFile`."""
    dict_representation = {
        'filename': rfile.filename,
        'filetype': rfile.filetype,
        'sha256': rfile.largefile.sha256,
        'size': rfile.largefile.total_size,
        'complete': rfile.largefile.complete,
        }
    if not dict_representation['complete']:
        dict_representation['progress'] = rfile.largefile.progress
        resource = rfile.resource_set.resource
        if resource.rtype in ALLOW_UPLOAD_RTYPES:
            dict_representation['upload_uri'] = reverse(
                'boot_resource_file_upload_handler',
                args=[resource.id, rfile.id])

    return dict_representation


def boot_resource_set_to_dict(resource_set):
    """Return dictionary representation of `BootResourceSet`."""
    dict_representation = {
        'version': resource_set.version,
        'label': resource_set.label,
        'size': resource_set.total_size,
        'complete': resource_set.complete,
        }
    if not dict_representation['complete']:
        dict_representation['progress'] = resource_set.progress
    dict_representation['files'] = {}
    for rfile in resource_set.files.all():
        rfile_dict = boot_resource_file_to_dict(rfile)
        dict_representation['files'][rfile_dict['filename']] = rfile_dict
    return dict_representation


def boot_resource_to_dict(resource, with_sets=False):
    """Return dictionary representation of `BootResource`."""
    dict_representation = {
        'id': resource.id,
        'type': BOOT_RESOURCE_TYPE_CHOICES_DICT[resource.rtype],
        'name': resource.name,
        'architecture': resource.architecture,
        'resource_uri': reverse('boot_resource_handler', args=[resource.id]),
        }
    dict_representation.update(resource.extra)
    if with_sets:
        dict_representation['sets'] = {}
        for resource_set in resource.sets.all().order_by('id').reverse():
            set_dict = boot_resource_set_to_dict(resource_set)
            dict_representation['sets'][set_dict['version']] = set_dict
    return dict_representation


def json_object(obj, request):
    """Convert object into a json object."""
    emitter = JSONEmitter(obj, typemapper, None)
    stream = emitter.render(request)
    return stream


class BootResourcesHandler(OperationsHandler):
    """Manage the boot resources."""
    api_doc_section_name = "Boot resources"

    update = delete = None

    def read(self, request):
        """List all boot resources.

        :param type: Type of boot resources to list. Default: all
        """
        if 'type' not in request.GET:
            rtype = 'all'
        else:
            rtype = request.GET['type']

        if rtype == 'all':
            resources = BootResource.objects.all().order_by(
                'rtype', 'name', 'architecture')
        elif rtype in TYPE_MAPPING:
            resources = BootResource.objects.filter(
                rtype=TYPE_MAPPING[rtype]).order_by('name', 'architecture')
        else:
            raise MAASAPIBadRequest("Bad type '%s'" % rtype)

        resource_list = [
            boot_resource_to_dict(resource)
            for resource in resources
            ]
        stream = json_object(resource_list, request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    @admin_method
    def create(self, request):
        """Uploads a new boot resource.

        :param name: Name of the boot resource.
        :param title: Title for the boot resource.
        :param architecture: Architecture the boot resource supports.
        :param filetype: Filetype for uploaded content. (Default: tgz)
        :param content: Image content. Note: this is not a normal parameter,
            but a file upload.
        """
        # If the user provides no parameters to the create command, then
        # django will treat the form as valid, and so it won't actually
        # validate any of the data.
        data = request.data
        if data is None:
            data = {}
        if 'filetype' not in data:
            data['filetype'] = 'tgz'
        file_content = get_content_parameter(request)
        if file_content is not None:
            content = SimpleUploadedFile(
                content=file_content, name='file',
                content_type='application/octet-stream')
            form = BootResourceForm(data=data, files={
                'content': content,
                })
        else:
            form = BootResourceNoContentForm(data=data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        resource = form.save()

        # If an upload contained the full file, then we can have the clusters
        # sync a new resource.
        if file_content is not None:
            NodeGroup.objects.import_boot_images_on_enabled_clusters()

        stream = json_object(
            boot_resource_to_dict(resource, with_sets=True), request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.CREATED)

    @admin_method
    @operation(idempotent=False, exported_as='import')
    def import_resources(self, request):
        """Import the boot resources."""
        import_resources()
        return HttpResponse(
            "Import of boot resources started",
            status=httplib.OK)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('boot_resources_handler', [])


class BootResourceHandler(OperationsHandler):
    """Manage a boot resource."""
    api_doc_section_name = "Boot resource"
    model = BootResource

    create = update = None

    def read(self, request, id):
        """Read a boot resource."""
        resource = get_object_or_404(BootResource, id=id)
        stream = json_object(
            boot_resource_to_dict(resource, with_sets=True), request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    @admin_method
    def delete(self, request, id):
        """Delete boot resource."""
        resource = BootResource.objects.get(id=id)
        if resource is not None:
            resource.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, resource=None):
        if resource is None:
            id = 'id'
        else:
            id = resource.id
        return ('boot_resource_handler', (id, ))


class BootResourceFileUploadHandler(OperationsHandler):
    """Upload a boot resource file."""
    api_doc_section_name = "Boot resource file upload"
    model = BootResource

    read = create = delete = None

    hidden = True

    @admin_method
    def update(self, request, id, file_id):
        """Upload piece of boot resource file."""
        resource = get_object_or_404(BootResource, id=id)
        rfile = get_object_or_404(BootResourceFile, id=file_id)
        size = int(request.META.get('CONTENT_LENGTH', '0'))
        data = request.body
        if size == 0:
            raise MAASAPIBadRequest("Missing data.")
        if size != len(data):
            raise MAASAPIBadRequest(
                "Content-Length doesn't equal size of recieved data.")
        if resource.rtype not in ALLOW_UPLOAD_RTYPES:
            raise MAASAPIForbidden(
                "Cannot upload to a resource of type: %s. " % resource.rtype)
        if rfile.largefile.complete:
            raise MAASAPIBadRequest(
                "Cannot upload to a complete file.")

        with rfile.largefile.content.open('wb') as stream:
            stream.seek(0, os.SEEK_END)

            # Check that the uploading data will not make the file larger
            # than expected.
            current_size = stream.tell()
            if current_size + size > rfile.largefile.total_size:
                raise MAASAPIBadRequest(
                    "Too much data recieved.")

            stream.write(data)

        if rfile.largefile.complete:
            if not rfile.largefile.valid:
                raise MAASAPIBadRequest(
                    "Saved content does not match given SHA256 value.")
            NodeGroup.objects.import_boot_images_on_enabled_clusters()
        return rc.ALL_OK

    @classmethod
    def resource_uri(cls, resource=None, rfile=None):
        if resource is None:
            id = 'id'
        else:
            id = resource.id
        if rfile is None:
            file_id = 'id'
        else:
            file_id = rfile.id
        return ('boot_resource_file_upload_handler', (id, file_id))
