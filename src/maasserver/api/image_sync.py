# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db.models import F
from django.shortcuts import get_object_or_404

from maasserver.api.support import admin_method, OperationsHandler
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.node import RegionController


class ImagesSyncProgressHandler(OperationsHandler):
    api_doc_section_name = "ImagesSyncProgress"
    create = update = delete = None
    fields = ()
    hidden = True

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("images_sync_progress_handler", [])

    @admin_method
    def read(self, request):
        qs = (
            BootResourceFile.objects.prefetch_related(
                "bootresourcefilesync_set__region"
            )
            .filter(size=F("bootresourcefilesync__size"))
            .order_by("id")
        )
        return {
            file.id: {
                "sha256": file.sha256,
                "size": file.size,
                "sources": [
                    r.region.system_id
                    for r in file.bootresourcefilesync_set.all()
                ],
            }
            for file in qs
        }


class ImageSyncProgressHandler(OperationsHandler):
    """Internal endpoint to update progress of image sync"""

    api_doc_section_name = "ImageSyncProgress"
    create = delete = None
    fields = ()
    hidden = True

    @classmethod
    def resource_uri(cls, file_id=None, system_id=None):
        f_id = "file_id"
        sys_id = "system_id"
        if file_id is not None:
            f_id = str(file_id)
        if system_id is not None:
            sys_id = system_id
        return (
            "image_sync_progress_handler",
            (
                f_id,
                sys_id,
            ),
        )

    @admin_method
    def update(self, request, file_id, system_id):
        data = request.data
        size = data.get("size", 0)
        boot_file = get_object_or_404(BootResourceFile, id=file_id)
        region = get_object_or_404(RegionController, system_id=system_id)
        syncstatus, _ = boot_file.bootresourcefilesync_set.get_or_create(
            region=region
        )
        syncstatus.size = size
        syncstatus.save()

    @admin_method
    def read(self, request, file_id, system_id):
        boot_file = get_object_or_404(BootResourceFile, id=file_id)
        region = get_object_or_404(RegionController, system_id=system_id)
        if boot_file.bootresourcefilesync_set.exists():
            syncstatus = boot_file.bootresourcefilesync_set.get(region=region)
        else:
            return {"size": 0}
        return {"size": syncstatus.size}
