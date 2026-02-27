# Copyright 2014-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootResouce`."""

__all__ = [
    "BootResourceHandler",
    "BootResourcesHandler",
    "BootResourceFileUploadHandler",
]

import http.client

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from piston3.emitters import JSONEmitter
from piston3.handler import typemapper
from piston3.utils import rc
from temporalio.common import WorkflowIDReusePolicy

from maascommon.workflows.bootresource import (
    short_sha,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasserver.api.support import (
    check_permission,
    operation,
    OperationsHandler,
)
from maasserver.bootresources import (
    import_resources,
    is_import_resources_running,
    stop_import_resources,
)
from maasserver.enum import BOOT_RESOURCE_TYPE, BOOT_RESOURCE_TYPE_CHOICES_DICT
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIForbidden,
    MAASAPIValidationError,
)
from maasserver.forms import BootResourceForm
from maasserver.models import BootResource, BootResourceFile
from maasserver.models.bootresourceset import BootResourceSet
from maasserver.models.node import RegionController
from maasserver.utils.orm import post_commit_do
from maasserver.workflow import execute_workflow
from maasservicelayer.utils.image_local_files import (
    LocalStoreAllocationFail,
    LocalStoreFileSizeMismatch,
    LocalStoreInvalidHash,
    SyncLocalBootResourceFile,
)
from maastemporalworker.worker import REGION_TASK_QUEUE
from maastemporalworker.workflow.bootresource import (
    DOWNLOAD_TIMEOUT,
    ResourceDownloadParam,
)

TYPE_MAPPING = {
    "synced": BOOT_RESOURCE_TYPE.SYNCED,
    "uploaded": BOOT_RESOURCE_TYPE.UPLOADED,
}


def boot_resource_file_to_dict(rfile: BootResourceFile):
    """Return dictionary representation of `BootResourceFile`."""
    dict_representation = {
        "filename": rfile.filename,
        "filetype": rfile.filetype,
        "sha256": rfile.sha256,
        "filename_on_disk": rfile.filename_on_disk,
        "size": rfile.size,
        "complete": rfile.complete,
    }
    if not dict_representation["complete"]:
        dict_representation["progress"] = rfile.sync_progress
        resource = rfile.resource_set.resource
        if resource.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            dict_representation["upload_uri"] = reverse(
                "boot_resource_file_upload_handler",
                args=[resource.id, rfile.id],
            )

    return dict_representation


def boot_resource_set_to_dict(resource_set: BootResourceSet):
    """Return dictionary representation of `BootResourceSet`."""
    dict_representation = {
        "version": resource_set.version,
        "label": resource_set.label,
        "size": resource_set.total_size,
        "complete": resource_set.complete,
    }
    if not dict_representation["complete"]:
        dict_representation["progress"] = resource_set.sync_progress
    dict_representation["files"] = {}
    for rfile in resource_set.files.all():
        rfile_dict = boot_resource_file_to_dict(rfile)
        dict_representation["files"][rfile_dict["filename"]] = rfile_dict
    return dict_representation


def boot_resource_to_dict(resource, with_sets=False):
    """Return dictionary representation of `BootResource`."""
    dict_representation = {
        "id": resource.id,
        "type": BOOT_RESOURCE_TYPE_CHOICES_DICT[resource.rtype],
        "name": resource.name,
        "architecture": resource.architecture,
        "resource_uri": reverse("boot_resource_handler", args=[resource.id]),
        "last_deployed": resource.last_deployed,
    }
    dict_representation.update(resource.extra)
    if resource.base_image:
        dict_representation["base_image"] = resource.base_image
    if with_sets:
        dict_representation["sets"] = {}
        for resource_set in resource.sets.all().order_by("id").reverse():
            set_dict = boot_resource_set_to_dict(resource_set)
            dict_representation["sets"][set_dict["version"]] = set_dict
    return dict_representation


def json_object(obj, request):
    """Convert object into a json object."""
    emitter = JSONEmitter(obj, typemapper, None)
    stream = emitter.render(request)
    return stream


def filestore_add_file(rfile: BootResourceFile):
    param = SyncRequestParam(
        resource=ResourceDownloadParam(
            rfile_ids=[rfile.id],
            source_list=[],
            sha256=rfile.sha256,
            filename_on_disk=rfile.filename_on_disk,
            total_size=rfile.size,
        ),
    )
    return execute_workflow(
        SYNC_BOOTRESOURCES_WORKFLOW_NAME,
        f"sync-bootresources:{short_sha(rfile.sha256)}",
        param,
        task_queue=REGION_TASK_QUEUE,
        execution_timeout=DOWNLOAD_TIMEOUT,
        run_timeout=DOWNLOAD_TIMEOUT,
        id_reuse_policy=WorkflowIDReusePolicy.TERMINATE_IF_RUNNING,
    )


class BootResourcesHandler(OperationsHandler):
    """Manage the boot resources."""

    api_doc_section_name = "Boot resources"

    update = delete = None

    def read(self, request):
        """@description-title List boot resources
        @description List all boot resources

        @param (string) "type" [required=false] Type of boot resources to list.
        If not provided, returns all types.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing a list of boot
        resource objects.
        @success-example "success-json" [exkey=boot-res-read] placeholder text
        """
        if "type" not in request.GET:
            rtype = "all"
        else:
            rtype = request.GET["type"]

        if rtype == "all":
            resources = BootResource.objects.all().order_by(
                "rtype", "name", "architecture"
            )
        elif rtype in TYPE_MAPPING:
            resources = BootResource.objects.filter(
                rtype=TYPE_MAPPING[rtype]
            ).order_by("name", "architecture")
        else:
            raise MAASAPIBadRequest(
                "'%s' is not a valid boot resource type. Available "
                "types: %s" % (rtype, list(TYPE_MAPPING.keys()))
            )

        resource_list = [
            boot_resource_to_dict(resource) for resource in resources
        ]
        stream = json_object(resource_list, request)
        return HttpResponse(
            stream,
            content_type="application/json; charset=utf-8",
            status=int(http.client.OK),
        )

    @check_permission("can_edit_boot_entities")
    def create(self, request):
        """@description-title Create a new boot resource
        @description Creates a new boot resource. The file upload must be done
        in chunk, see Boot resource file upload.

        @param (string) "name" [required=true] Name of the boot resource.

        @param (string) "architecture" [required=true] Architecture the boot
        resource supports.

        @param (string) "sha256" [required=true] The ``sha256`` hash of the
        resource.

        @param (string) "size" [required=true] The size of the resource in
        bytes.

        @param (string) "title" [required=false] Title for the boot resource.

        @param (string) "filetype" [required=false] Filetype for uploaded
        content. (Default: ``tgz``. Supported: ``tgz``, ``tbz``, ``txz``,
        ``ddtgz``, ``ddtbz``, ``ddtxz``, ``ddtar``, ``ddbz2``, ``ddgz``,
        ``ddxz``, ``ddraw``)

        @param (string) "base_image" [required=false] The Base OS image a
        custom image is built on top of. Only required for custom image.

        @success (http-status-code) "server-success" 201
        @success (json) "success-json" A JSON object containing information
        about the uploaded resource.
        @success-example "success-json" [exkey=boot-res-create] placeholder
        text
        """
        # If the user provides no parameters to the create command, then
        # django will treat the form as valid, and so it won't actually
        # validate any of the data.
        data = request.data.copy()
        if data is None:
            data = {}
        if "filetype" not in data:
            data["filetype"] = "tgz"
        form = BootResourceForm(data=data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        resource = form.save()

        stream = json_object(
            boot_resource_to_dict(resource, with_sets=True), request
        )
        return HttpResponse(
            stream,
            content_type="application/json; charset=utf-8",
            status=int(http.client.CREATED),
        )

    @check_permission("can_edit_boot_entities")
    @operation(idempotent=False, exported_as="import")
    def import_resources(self, request):
        """@description-title Import boot resources
        @description Import the boot resources.

        @success (http-status-code) "server-success" 200
        @success (content) "success-content"
            Import of boot resources started
        """
        import_resources()
        return HttpResponse(
            "Import of boot resources started",
            content_type=("text/plain; charset=%s" % settings.DEFAULT_CHARSET),
        )

    @check_permission("can_edit_boot_entities")
    @operation(idempotent=False)
    def stop_import(self, request):
        """@description-title Stop import boot resources
        @description Stop import the boot resources.

        @success (http-status-code) "server-success" 200
        @success (content) "success-content"
            Import of boot resources is being stopped.
        """
        stop_import_resources()
        return HttpResponse(
            "Import of boot resources is being stopped",
            content_type=("text/plain; charset=%s" % settings.DEFAULT_CHARSET),
        )

    @operation(idempotent=True)
    def is_importing(self, request):
        """@description-title Importing status
        @description Get the status of importing resources.

        @success (http-status-code) "server-success" 200
        @success (content) "success-content-true"
            true
        @success (content) "success-content-false"
            false
        """
        return is_import_resources_running()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("boot_resources_handler", [])


class BootResourceHandler(OperationsHandler):
    """Manage a boot resource."""

    api_doc_section_name = "Boot resource"
    model = BootResource

    create = update = None

    def read(self, request, id):
        """@description-title Read a boot resource
        @description Reads a boot resource by id

        @param (int) "{id}" [required=true] The boot resource id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing information
        about the requested resource.
        @success-example "success-json" [exkey=boot-res-read-by-id] placeholder
        text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot resource is not found.
        @error-example "not-found"
            No BootResource matches the given query.
        """
        resource = get_object_or_404(BootResource, id=id)
        stream = json_object(
            boot_resource_to_dict(
                resource,
                with_sets=True,
            ),
            request,
        )
        return HttpResponse(
            stream,
            content_type="application/json; charset=utf-8",
            status=int(http.client.OK),
        )

    @check_permission("can_edit_boot_entities")
    def delete(self, request, id):
        """@description-title Delete a boot resource
        @description Delete a boot resource by id.

        @param (int) "{id}" [required=true] The boot resource id.

        @success (http-status-code) "server-success" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested boot resource is not found.
        @error-example "not-found"
            No BootResource matches the given query.
        """
        resource = BootResource.objects.get(id=id)
        if resource is not None:
            BootResourceFile.objects.filestore_remove_resource(resource)
            resource.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, resource=None):
        if resource is None:
            id = "id"
        else:
            id = resource.id
        return ("boot_resource_handler", (id,))


class BootResourceFileUploadHandler(OperationsHandler):
    """Upload a boot resource file."""

    api_doc_section_name = "Boot resource file upload"
    read = create = delete = None

    @check_permission("can_edit_boot_entities")
    def update(self, request, resource_id, id):
        """@description-title Upload chunk of boot resource file.
        @description Uploads a chunk of boot resource file

        @param (int) "{resource_id}" [required=true] The boot resource id.

        @param (int) "{id}" [required=true] The boot resource file id.

        @success (http-status-code) "200" 200
        @error (http-status-code) "400" 400
        @error (content) "bad-request" Error while uploading the file.
        @error (http-status-code) "403" 403
        @error (content) "forbidden" The user tried to upload to a boot resource of wrong type.
        """
        resource = get_object_or_404(BootResource, id=resource_id)
        rfile = get_object_or_404(BootResourceFile, id=id)
        size = int(request.headers.get("content-length", "0"))
        data = request.body
        if size == 0:
            raise MAASAPIBadRequest("Missing data.")
        if size != len(data):
            raise MAASAPIBadRequest(
                "Content-Length doesn't equal size of received data."
            )
        if resource.rtype != BOOT_RESOURCE_TYPE.UPLOADED:
            raise MAASAPIForbidden(
                f"Cannot upload to a resource of type: {resource.rtype}."
            )
        sync_status, _ = rfile.bootresourcefilesync_set.get_or_create(
            region=RegionController.objects.get_running_controller()
        )
        lfile = SyncLocalBootResourceFile(
            sha256=rfile.sha256,
            filename_on_disk=rfile.filename_on_disk,
            total_size=rfile.size,
        )
        if sync_status.size == lfile.total_size:
            raise MAASAPIBadRequest("Cannot upload to a complete file.")

        try:
            lfile.append_chunk(data)
            sync_status.size += size
            sync_status.save()
            if lfile.complete:
                if lfile.valid:
                    post_commit_do(filestore_add_file, rfile)
                else:
                    raise LocalStoreInvalidHash()
        except LocalStoreFileSizeMismatch as e:
            raise MAASAPIBadRequest("Too much data received.") from e
        except LocalStoreInvalidHash as e:
            raise MAASAPIBadRequest(
                "Saved content does not match given SHA256 value."
            ) from e
        except LocalStoreAllocationFail as e:
            raise MAASAPIBadRequest("No space left on device") from e
        return rc.ALL_OK

    @classmethod
    def resource_uri(cls, resource=None, rfile=None):
        if resource is None:
            resource_id = "resource_id"
        else:
            resource_id = resource.id
        if rfile is None:
            id = "id"
        else:
            id = rfile.id
        return ("boot_resource_file_upload_handler", (resource_id, id))
