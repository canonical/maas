# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Boot Resources` API."""


import hashlib
import http.client
from io import BytesIO
import random
from typing import Iterable

from django.urls import reverse

from maasserver.api import boot_resources
from maasserver.api.boot_resources import (
    boot_resource_file_to_dict,
    boot_resource_set_to_dict,
    boot_resource_to_dict,
    filestore_add_file,
)
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
)
from maasserver.forms import get_uploaded_filename
from maasserver.models import BootResource
from maasserver.models.node import RegionController
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from maasserver.workflow.worker.worker import REGION_TASK_QUEUE
from maastesting.utils import sample_binary_data
from provisioningserver.utils.env import MAAS_ID


def get_boot_resource_uri(resource):
    """Return a boot resource's URI on the API."""
    return reverse("boot_resource_handler", args=[resource.id])


class TestHelpers(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()

    def test_boot_resource_file_to_dict(self):
        size = random.randint(512, 1023)
        total_size = random.randint(1024, 2048)
        content = factory.make_bytes(size)
        lfile = factory.make_boot_file(content, total_size)
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        resource_set = factory.make_BootResourceSet(resource)
        rfile = factory.make_BootResourceFile(
            resource_set, size=total_size, sha256=lfile.sha256
        )
        dict_representation = boot_resource_file_to_dict(rfile)
        self.assertEqual(rfile.filename, dict_representation["filename"])
        self.assertEqual(rfile.filetype, dict_representation["filetype"])
        self.assertEqual(rfile.sha256, dict_representation["sha256"])
        self.assertEqual(total_size, dict_representation["size"])
        self.assertFalse(dict_representation["complete"])
        self.assertEqual(rfile.sync_progress, dict_representation["progress"])
        self.assertEqual(
            reverse(
                "boot_resource_file_upload_handler",
                args=[resource.id, rfile.id],
            ),
            dict_representation["upload_uri"],
        )

    def test_boot_resource_set_to_dict(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        total_size = random.randint(1024, 2048)
        content = factory.make_bytes(random.randint(512, 1023))
        lfile = factory.make_boot_file(content, total_size)
        rfile = factory.make_BootResourceFile(
            resource_set, size=total_size, sha256=lfile.sha256
        )
        dict_representation = boot_resource_set_to_dict(resource_set)
        self.assertEqual(resource_set.version, dict_representation["version"])
        self.assertEqual(resource_set.label, dict_representation["label"])
        self.assertEqual(resource_set.total_size, dict_representation["size"])
        self.assertFalse(dict_representation["complete"])
        self.assertEqual(
            resource_set.sync_progress, dict_representation["progress"]
        )
        self.assertEqual(
            boot_resource_file_to_dict(rfile),
            dict_representation["files"][rfile.filename],
        )

    def test_boot_resource_to_dict_without_sets(self):
        resource = factory.make_BootResource()
        factory.make_BootResourceSet(resource)
        dict_representation = boot_resource_to_dict(resource, with_sets=False)
        self.assertEqual(resource.id, dict_representation["id"])
        self.assertEqual(
            BOOT_RESOURCE_TYPE_CHOICES_DICT[resource.rtype],
            dict_representation["type"],
        )
        self.assertEqual(resource.name, dict_representation["name"])
        self.assertEqual(
            resource.architecture, dict_representation["architecture"]
        )
        self.assertEqual(
            get_boot_resource_uri(resource),
            dict_representation["resource_uri"],
        )
        self.assertIsNone(dict_representation["last_deployed"])
        self.assertNotIn("sets", dict_representation)
        self.assertNotIn("base_image", dict_representation)

    def test_boot_resource_to_dict_with_sets(self):
        resource = factory.make_BootResource()
        resource_set = factory.make_BootResourceSet(resource)
        dict_representation = boot_resource_to_dict(resource, with_sets=True)
        self.assertEqual(
            boot_resource_set_to_dict(resource_set),
            dict_representation["sets"][resource_set.version],
        )

    def test_boot_resource_to_dict_custom(self):
        base_image = factory.make_base_image_name()
        resource = factory.make_BootResource(base_image=base_image)
        dict_representation = boot_resource_to_dict(resource)
        self.assertIn("base_image", dict_representation)

    def test_filestore_add_file(self):
        exec_mock = self.patch(boot_resources, "execute_workflow")
        bootres = factory.make_BootResource()
        bootres_set = factory.make_BootResourceSet(bootres)
        bootres_file = factory.make_BootResourceFile(bootres_set)
        filestore_add_file(bootres_file)
        exec_mock.assert_called()
        workflow, wid, params = exec_mock.call_args.args
        self.assertEqual(workflow, "sync-bootresources")
        self.assertEqual(wid, f"sync-boot-resources:upload:{bootres_file.id}")
        self.assertCountEqual(params.resources[0].rfile_ids, [bootres_file.id])
        self.assertEqual(
            exec_mock.call_args.kwargs["task_queue"], REGION_TASK_QUEUE
        )


class TestBootResourcesAPI(APITestCase.ForUser):
    """Test the the boot resource API."""

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()
        MAAS_ID.set(self.region.system_id)

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/boot-resources/", reverse("boot_resources_handler")
        )

    def test_GET_returns_boot_resources_list(self):
        resources = [factory.make_BootResource() for _ in range(3)]
        response = self.client.get(reverse("boot_resources_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            [resource.id for resource in resources],
            [resource.get("id") for resource in parsed_result],
        )

    def test_GET_synced_returns_synced_boot_resources(self):
        resources = [
            factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
            for _ in range(3)
        ]
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        response = self.client.get(
            reverse("boot_resources_handler"), {"type": "synced"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            [resource.id for resource in resources],
            [resource.get("id") for resource in parsed_result],
        )

    def test_GET_uploaded_returns_uploaded_boot_resources(self):
        resources = [
            factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
            for _ in range(3)
        ]
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        response = self.client.get(
            reverse("boot_resources_handler"), {"type": "uploaded"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            [resource.id for resource in resources],
            [resource.get("id") for resource in parsed_result],
        )

    def test_GET_doesnt_include_full_definition_of_boot_resource(self):
        factory.make_BootResource()
        response = self.client.get(reverse("boot_resources_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertNotIn("sets", parsed_result[0])

    def test_POST_requires_admin(self):
        params = {
            "name": factory.make_name("name"),
            "architecture": make_usable_architecture(self),
            "content": (factory.make_file_upload(content=sample_binary_data)),
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def pick_filetype(self):
        filetypes = {
            "tgz": BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
            "ddtgz": BOOT_RESOURCE_FILE_TYPE.ROOT_DDTGZ,
            "ddtar": BOOT_RESOURCE_FILE_TYPE.ROOT_DDTAR,
            "ddraw": BOOT_RESOURCE_FILE_TYPE.ROOT_DDRAW,
            "ddtbz": BOOT_RESOURCE_FILE_TYPE.ROOT_DDTBZ,
            "ddtxz": BOOT_RESOURCE_FILE_TYPE.ROOT_DDTXZ,
            "ddbz2": BOOT_RESOURCE_FILE_TYPE.ROOT_DDBZ2,
            "ddgz": BOOT_RESOURCE_FILE_TYPE.ROOT_DDGZ,
            "ddxz": BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ,
        }

        return random.choice(list(filetypes.items()))

    def test_POST_creates_boot_resource(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        upload_type, filetype = self.pick_filetype()
        params = {
            "name": name,
            "architecture": architecture,
            "filetype": upload_type,
            "content": (factory.make_file_upload(content=sample_binary_data)),
            "base_image": "ubuntu/focal",
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)

        resource = BootResource.objects.get(id=parsed_result["id"])
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertEqual(name, resource.name)
        self.assertEqual(architecture, resource.architecture)
        self.assertEqual("uploaded", resource_set.label)
        self.assertEqual(get_uploaded_filename(filetype), rfile.filename)
        self.assertEqual(filetype, rfile.filetype)
        lfile = rfile.local_file()
        with open(lfile.path, "rb") as stream:
            written_data = stream.read()
        self.assertEqual(sample_binary_data, written_data)
        mock_filestore.assert_called_once()

    def test_POST_creates_boot_resource_with_default_filetype(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        params = {
            "name": name,
            "architecture": architecture,
            "content": (factory.make_file_upload(content=sample_binary_data)),
            "base_image": "ubuntu/focal",
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)

        resource = BootResource.objects.get(id=parsed_result["id"])
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertEqual(BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ, rfile.filetype)
        mock_filestore.assert_called_once()

    def test_POST_creates_boot_resource_with_already_existing_file(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        lfile = factory.make_boot_file()
        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        params = {
            "name": name,
            "architecture": architecture,
            "sha256": lfile.sha256,
            "size": lfile.total_size,
            "base_image": "ubuntu/focal",
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)

        resource = BootResource.objects.get(id=parsed_result["id"])
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        lfile = rfile.local_file()
        self.assertTrue(lfile.path.exists())
        mock_filestore.assert_not_called()

    def test_POST_creates_boot_resource_with_empty_file(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        sha256 = factory.make_string(size=64)
        total_size = random.randint(512, 1023)
        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        params = {
            "name": name,
            "architecture": architecture,
            "sha256": sha256,
            "size": total_size,
            "base_image": "ubuntu/focal",
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)

        resource = BootResource.objects.get(id=parsed_result["id"])
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertEqual(
            (sha256, total_size, False),
            (
                rfile.sha256,
                rfile.size,
                rfile.complete,
            ),
        )
        mock_filestore.assert_not_called()

    def test_POST_validates_size_matches_total_size_for_file(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        other = factory.make_usable_boot_resource()
        rset = other.sets.first()
        rfile = rset.files.first()
        sha256 = rfile.sha256
        total_size = rfile.size
        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        params = {
            "name": name,
            "architecture": architecture,
            "sha256": sha256,
            "size": total_size + 1,
            "base_image": "ubuntu/focal",
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        mock_filestore.assert_not_called()

    def test_POST_returns_full_definition_of_boot_resource(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        params = {
            "name": name,
            "architecture": architecture,
            "content": (factory.make_file_upload(content=sample_binary_data)),
            "base_image": "ubuntu/focal",
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)
        self.assertIn("sets", parsed_result)
        mock_filestore.assert_called_once()

    def test_POST_validates_boot_resource(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        params = {
            "name": factory.make_name("name"),
        }
        response = self.client.post(reverse("boot_resources_handler"), params)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        mock_filestore.assert_not_called()

    def test_import_requires_admin(self):
        response = self.client.post(
            reverse("boot_resources_handler"), {"op": "import"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_stop_import_requires_admin(self):
        response = self.client.post(
            reverse("boot_resources_handler"), {"op": "stop_import"}
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_stop_import_calls_stop_import_resources(self):
        self.become_admin()
        mock_stop = self.patch(boot_resources, "stop_import_resources")
        response = self.client.post(
            reverse("boot_resources_handler"), {"op": "stop_import"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        mock_stop.assert_called_once_with()

    def test_is_importing_returns_import_status(self):
        mock_running = self.patch(
            boot_resources, "is_import_resources_running"
        )
        mock_running.return_value = factory.pick_bool()
        response = self.client.get(
            reverse("boot_resources_handler"), {"op": "is_importing"}
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.assertEqual(
            mock_running.return_value, json_load_bytes(response.content)
        )


class TestBootResourceAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/boot-resources/3/",
            reverse("boot_resource_handler", args=["3"]),
        )

    def test_GET_returns_boot_resource(self):
        resource = factory.make_usable_boot_resource()
        response = self.client.get(get_boot_resource_uri(resource))
        self.assertEqual(http.client.OK, response.status_code)
        returned_resource = json_load_bytes(response.content)
        # The returned object contains a 'resource_uri' field.
        self.assertEqual(
            reverse("boot_resource_handler", args=[resource.id]),
            returned_resource["resource_uri"],
        )
        self.assertGreaterEqual(
            returned_resource.keys(), {"id", "type", "name", "architecture"}
        )

    def test_DELETE_deletes_boot_resource(self):
        self.become_admin()
        resource = factory.make_BootResource()
        response = self.client.delete(get_boot_resource_uri(resource))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(resource))

    def test_DELETE_requires_admin(self):
        resource = factory.make_BootResource()
        response = self.client.delete(get_boot_resource_uri(resource))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestBootResourceFileUploadAPI(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()
        MAAS_ID.set(self.region.system_id)

    def get_boot_resource_file_upload_uri(self, rfile):
        """Return a boot resource file's URI on the API."""
        return reverse(
            "boot_resource_file_upload_handler",
            args=[rfile.resource_set.resource.id, rfile.id],
        )

    def make_empty_resource_file(
        self,
        rtype=None,
        content: bytes | None = None,
        synced: Iterable[tuple[RegionController, int]] | None = None,
    ):
        if content is None:
            content = factory.make_bytes(1024)
        total_size = len(content)
        sha256 = hashlib.sha256()
        sha256.update(content)
        hexdigest = sha256.hexdigest()
        if rtype is None:
            rtype = BOOT_RESOURCE_TYPE.UPLOADED
        resource = factory.make_BootResource(rtype=rtype)
        resource_set = factory.make_BootResourceSet(resource)
        rfile = factory.make_BootResourceFile(
            resource_set,
            sha256=hexdigest,
            size=total_size,
            synced=synced,
        )
        return rfile, content

    def read_content(self, rfile):
        """Return the content saved in resource file."""
        lfile = rfile.local_file()
        with open(lfile.path, "rb") as stream:
            return stream.read()

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/boot-resources/3/upload/5/",
            reverse("boot_resource_file_upload_handler", args=["3", "5"]),
        )

    def test_PUT_resource_file_writes_content(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()
        rfile, content = self.make_empty_resource_file()
        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile), data=content
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(content, self.read_content(rfile))
        mock_filestore.assert_called_once()

    def test_PUT_requires_admin(self):
        rfile, content = self.make_empty_resource_file()
        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile), data=content
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_PUT_returns_bad_request_when_no_content(self):
        self.become_admin()
        rfile, _ = self.make_empty_resource_file()
        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile)
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_PUT_returns_forbidden_when_resource_is_synced(self):
        self.become_admin()
        rfile, content = self.make_empty_resource_file(
            BOOT_RESOURCE_TYPE.SYNCED
        )
        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile), data=content
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_PUT_returns_bad_request_when_resource_file_is_complete(self):
        self.become_admin()
        rfile, content = self.make_empty_resource_file(
            synced=[(self.region, -1)]
        )

        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile), data=content
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_PUT_returns_bad_request_when_content_is_too_large(self):
        self.become_admin()
        rfile, content = self.make_empty_resource_file()
        content = factory.make_bytes(len(content) + 1)
        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile), data=content
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_PUT_returns_bad_request_when_content_doesnt_match_sha256(self):
        self.become_admin()
        rfile, content = self.make_empty_resource_file()
        content = factory.make_bytes(size=len(content))
        response = self.client.put(
            self.get_boot_resource_file_upload_uri(rfile), data=content
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_PUT_with_multiple_requests_and_large_content(self):
        mock_filestore = self.patch(boot_resources, "filestore_add_file")
        self.become_admin()

        # Get large amount of data to test with
        content = factory.make_bytes(1 << 24)  # 16MB
        rfile, _ = self.make_empty_resource_file(content=content)
        buffer = BytesIO(content)
        while send_content := buffer.read(1 << 22):
            response = self.client.put(
                self.get_boot_resource_file_upload_uri(rfile),
                data=send_content,
            )
            self.assertEqual(
                http.client.OK, response.status_code, response.content
            )
        self.assertEqual(content, self.read_content(rfile))
        mock_filestore.assert_called_once()
