# Copyright 2014 Canonical Ltd.  This software is licensed under the
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
    ]

import httplib

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    operation,
    OperationsHandler,
    )
from maasserver.api.utils import get_mandatory_param
from maasserver.bootresources import import_resources
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
    )
from maasserver.exceptions import MAASAPIBadRequest
from maasserver.forms import BootResourceForm
from maasserver.models import (
    BootResource,
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


def get_content_parameter(request):
    """Get the "content" parameter from a POST or PUT."""
    content_file = get_mandatory_param(request.FILES, 'content')
    return content_file.read()


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
        content = SimpleUploadedFile(
            content=get_content_parameter(request),
            name='file', content_type='application/octet-stream')
        if 'filetype' not in data:
            data['filetype'] = 'tgz'
        form = BootResourceForm(data=data, files={'content': content})
        if not form.is_valid():
            raise ValidationError(form.errors)
        resource = form.save()

        # Boot resource is now available. Have the clusters sync boot images.
        NodeGroup.objects.import_boot_images_on_accepted_clusters()

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
    """Manage a boot resource.

    This functionality is only available to administrators.
    """
    api_doc_section_name = "Boot resource"
    model = BootResource

    create = update = None

    def read(self, request, id):
        """Read a boot source."""
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
