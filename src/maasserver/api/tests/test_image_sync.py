# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import http.client
import json
import random

from django.urls import reverse

from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory


def get_image_sync_uri(file_id, system_id):
    return reverse("image_sync_progress_handler", args=[file_id, system_id])


class TestImageSyncProgressHandler(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/image-sync-progress/1/a/",
            get_image_sync_uri(1, "a"),
        )

    def test_update_creates_default_size(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        uri = get_image_sync_uri(file.id, region.id)
        response = self.client.put(uri, {})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        syncstatus = file.bootresourcefilesync_set.get(region=region)
        self.assertEqual(syncstatus.size, 0)

    def test_update(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        test_size = random.randint(1, 30)
        uri = get_image_sync_uri(file.id, region.id)
        response = self.client.put(uri, {"size": test_size})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        syncstatus = file.bootresourcefilesync_set.get(region=region)
        self.assertEqual(test_size, syncstatus.size)

    def test_update_existing_brfsync(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        syncset = file.bootresourcefilesync_set.create(region=region)
        test_size = random.randint(1, 30)
        uri = get_image_sync_uri(file.id, region.id)
        response = self.client.put(uri, {"size": test_size})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        syncset = file.bootresourcefilesync_set.get(region=region)
        self.assertEqual(syncset.size, test_size)

    def test_update_fail_no_file(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        test_size = random.randint(1, 30)
        uri = get_image_sync_uri((file.id + 1), region.id)
        response = self.client.put(uri, {"size": test_size})
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_read_nonexistent_brfsync(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        uri = get_image_sync_uri(file.id, region.id)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        r = json.loads(response.content)
        self.assertEqual(r.get("size"), 0)

    def test_read_existing_brfsync(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        test_size = random.randint(1, 10)
        filesync = file.bootresourcefilesync_set.create(
            region=region, size=test_size
        )
        uri = get_image_sync_uri(file.id, region.id)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        r = json.loads(response.content)
        self.assertEqual(r.get("size"), filesync.size)

    def test_read_nonexistent_file(self):
        region = factory.make_RegionController()
        total_size = random.randint(1024, 2048)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        file = factory.make_boot_resource_file_with_content(
            resource_set, size=total_size
        )
        uri = get_image_sync_uri((file.id + 1), region.id)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
