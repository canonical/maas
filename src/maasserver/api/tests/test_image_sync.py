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


class TestImageSyncProgressHandler(APITestCase.ForAdmin):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/images-sync-progress/1/a/",
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
        uri = get_image_sync_uri(file.id, region.system_id)
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
        uri = get_image_sync_uri(file.id, region.system_id)
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
        uri = get_image_sync_uri(file.id, region.system_id)
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
        uri = get_image_sync_uri((file.id + 1), region.system_id)
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
        uri = get_image_sync_uri(file.id, region.system_id)
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
        uri = get_image_sync_uri(file.id, region.system_id)
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
        uri = get_image_sync_uri((file.id + 1), region.system_id)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )


class TestImagesSyncProgressHandler(APITestCase.ForAdmin):
    def test_read(self):
        regions = [factory.make_RegionController() for _ in range(3)]
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)

        complete = factory.make_BootResourceFile(
            resource_set=resource_set,
            synced=[(r, -1) for r in regions],
        )
        partial_sync = factory.make_BootResourceFile(
            resource_set=resource_set,
            synced=[(r, -1) for r in regions[2:]],
        )
        factory.make_BootResourceFile(
            resource_set=resource_set,
            size=512,
            synced=[(regions[0], 256)],
        )
        response = self.client.get(reverse("images_sync_progress_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        status = response.json()
        self.assertEqual(complete.size, status[str(complete.id)]["size"])
        self.assertEqual(complete.sha256, status[str(complete.id)]["sha256"])
        self.assertEqual(
            partial_sync.size, status[str(partial_sync.id)]["size"]
        )
        self.assertEqual(
            partial_sync.sha256, status[str(partial_sync.id)]["sha256"]
        )
        self.assertItemsEqual(
            (str(partial_sync.id), str(complete.id)), set(status.keys())
        )
        self.assertItemsEqual(
            [r.system_id for r in regions], status[str(complete.id)]["sources"]
        )
        self.assertItemsEqual(
            [r.system_id for r in regions[2:]],
            status[str(partial_sync.id)]["sources"],
        )

    def test_bulk_create(self):
        regions = [factory.make_RegionController() for _ in range(2)]
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        rfiles = [
            factory.make_BootResourceFile(resource_set=resource_set)
            for _ in range(3)
        ]
        response = self.client.post(
            reverse("images_sync_progress_handler"),
            {
                "ids": [f.id for f in rfiles[:1]],
                "system_id": regions[0].system_id,
                "size": 1,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        for f in rfiles[:1]:
            self.assertEqual(
                1, f.bootresourcefilesync_set.get(region=regions[0]).size
            )
        self.assertFalse(
            rfiles[0]
            .bootresourcefilesync_set.filter(region=regions[1])
            .exists()
        )
        self.assertFalse(
            rfiles[2]
            .bootresourcefilesync_set.filter(region=regions[0])
            .exists()
        )

    def test_bulk_create_single_val(self):
        regions = [factory.make_RegionController() for _ in range(2)]
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        rfiles = [factory.make_BootResourceFile(resource_set=resource_set)]
        response = self.client.post(
            reverse("images_sync_progress_handler"),
            {
                "ids": [f.id for f in rfiles],
                "system_id": regions[0].system_id,
                "size": 1,
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        for f in rfiles:
            self.assertEqual(
                1, f.bootresourcefilesync_set.get(region=regions[0]).size
            )
