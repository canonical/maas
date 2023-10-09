# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.shortcuts import get_object_or_404

from maasserver.api.support import OperationsHandler
from maasserver.models.bootresourcefile import BootResourceFile
from maasserver.models.node import RegionController


class ImageSyncProgressHandler(OperationsHandler):
    """Internal endpoint to update progress of image sync"""

    api_doc_section_name = "ImageSyncProgress"
    create = delete = None
    fields = ()

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

    def update(self, request, file_id, system_id):
        data = request.data
        size = data.get("size", 0)
        boot_file = get_object_or_404(BootResourceFile, id=file_id)
        region = get_object_or_404(RegionController, id=system_id)
        syncstatus, _ = boot_file.bootresourcefilesync_set.get_or_create(
            region=region
        )
        syncstatus.size = size
        syncstatus.save()

    def read(self, request, file_id, system_id):
        boot_file = get_object_or_404(BootResourceFile, id=file_id)
        region = get_object_or_404(RegionController, id=system_id)
        if boot_file.bootresourcefilesync_set.exists():
            syncstatus = boot_file.bootresourcefilesync_set.get(region=region)
        else:
            return {"size": 0}
        return {"size": syncstatus.size}
