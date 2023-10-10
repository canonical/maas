# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceForm`."""


import random

from django.core.files.uploadedfile import SimpleUploadedFile

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, BOOT_RESOURCE_TYPE
from maasserver.forms import BootResourceForm, get_uploaded_filename
from maasserver.models import BootResource, BootResourceFile, Config
from maasserver.models.signals import bootsources
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.drivers.osystem import (
    CustomOS,
    OperatingSystemRegistry,
)
from provisioningserver.utils.env import MAAS_ID


class TestBootResourceForm(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()
        self.region = factory.make_RegionController()
        MAAS_ID.set(self.region.system_id)

    def pick_filetype(self):
        filetypes = {
            "tgz": BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
            "tbz": BOOT_RESOURCE_FILE_TYPE.ROOT_TBZ,
            "txz": BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ,
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

    def test_creates_boot_resource(self):
        name = factory.make_name("name")
        title = factory.make_name("title")
        architecture = make_usable_architecture(self)
        subarch = architecture.split("/")[1]
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": "custom/" + name,
            "title": title,
            "architecture": architecture,
            "filetype": upload_type,
            "base_image": factory.make_base_image_name(),
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = BootResource.objects.get(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=architecture,
        )
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        lfile = rfile.local_file()
        self.assertEqual(title, resource.extra["title"])
        self.assertEqual(subarch, resource.extra["subarches"])
        self.assertEqual(filetype, rfile.filetype)
        self.assertEqual(get_uploaded_filename(filetype), rfile.filename)
        self.assertEqual(size, rfile.size)
        with open(lfile.path, "rb") as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_prevents_reserved_name(self):
        bsc = factory.make_BootSourceCache()
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": f"{bsc.os}/{bsc.release}",
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_prevents_reserved_osystem(self):
        bsc = factory.make_BootSourceCache()
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": bsc.os,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_prevents_reserved_release(self):
        bsc = factory.make_BootSourceCache()
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": bsc.release,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_prevents_reversed_osystem_from_driver(self):
        reserved_name = factory.make_name("name")
        OperatingSystemRegistry.register_item(reserved_name, CustomOS())
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": reserved_name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_prevents_reserved_centos_names(self):
        reserved_name = f"centos{random.randint(0, 99)}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": reserved_name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_prevents_unsupported_osystem(self):
        reserved_name = (
            f"{factory.make_name('osystem')}/{factory.make_name('series')}"
        )
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": reserved_name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_windows_does_not_require_base_image(self):
        name = f"windows/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid())

    def test_esxi_does_not_require_base_image(self):
        name = f"esxi/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid())

    def test_rhel_does_not_require_base_image(self):
        name = f"rhel/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid())

    def test_validates_custom_image_base_os(self):
        name = f"custom/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
            "base_image": factory.make_base_image_name(),
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid())

    def test_validates_custom_image_base_image_no_prefix(self):
        name = factory.make_name("name")
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
            "base_image": factory.make_base_image_name(),
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid())

    def test_saved_bootresource_saves_base_image(self):
        name = f"custom/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
            "base_image": factory.make_base_image_name(),
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        image = form.save()
        self.assertEqual(image.base_image, data["base_image"])

    def test_update_does_not_require_base_image(self):
        name = f"custom/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
            "base_image": factory.make_base_image_name(),
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        form.save()
        del form.data["base_image"]
        image = form.save()
        self.assertEqual(image.base_image, data["base_image"])

    def test_uses_commissioning_os_for_nonexistent_custom_image_base_os(self):
        name = f"custom/{factory.make_name('name')}"
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
            "base_image": "",
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        form.save()
        cfg = Config.objects.get_configs(
            ["commissioning_osystem", "commissioning_distro_series"]
        )
        self.assertEqual(
            f"{cfg['commissioning_osystem']}/{cfg['commissioning_distro_series']}",
            form.instance.base_image,
        )

    def test_invalidates_nonexistent_custom_image_base_os_no_prefix(self):
        name = factory.make_name("name")
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "title": factory.make_name("title"),
            "architecture": make_usable_architecture(self),
            "filetype": upload_type,
            "base_image": factory.make_name("invalid"),
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertFalse(form.is_valid())

    def test_adds_boot_resource_set_to_existing_boot_resource(self):
        name = factory.make_name("name")
        architecture = make_usable_architecture(self)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=architecture,
            base_image="ubuntu/focal",
        )
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "architecture": architecture,
            "filetype": upload_type,
            "keep_old": True,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = reload_object(resource)
        resource_set = resource.sets.order_by("id").last()
        rfile = resource_set.files.first()
        lfile = rfile.local_file()
        self.assertEqual(filetype, rfile.filetype)
        self.assertEqual(get_uploaded_filename(filetype), rfile.filename)
        self.assertEqual(size, rfile.size)
        with open(lfile.path, "rb") as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_creates_boot_resoures_with_uploaded_rtype(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        OperatingSystemRegistry.register_item(os, CustomOS())
        self.addCleanup(OperatingSystemRegistry.unregister_item, os)
        name = f"{os}/{series}"
        architecture = make_usable_architecture(self)
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "architecture": architecture,
            "filetype": upload_type,
            "base_image": "ubuntu/focal",
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = BootResource.objects.get(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=architecture,
        )
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        lfile = rfile.local_file()
        self.assertEqual(filetype, rfile.filetype)
        self.assertEqual(get_uploaded_filename(filetype), rfile.filename)
        self.assertEqual(size, rfile.size)
        with open(lfile.path, "rb") as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_adds_boot_resource_set_to_existing_uploaded_boot_resource(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        OperatingSystemRegistry.register_item(os, CustomOS())
        self.addCleanup(OperatingSystemRegistry.unregister_item, os)
        name = f"{os}/{series}"
        architecture = make_usable_architecture(self)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=architecture,
            base_image="ubuntu/focal",
        )
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "architecture": architecture,
            "filetype": upload_type,
            "keep_old": True,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = reload_object(resource)
        resource_set = resource.sets.order_by("id").last()
        rfile = resource_set.files.first()
        lfile = rfile.local_file()
        self.assertEqual(filetype, rfile.filetype)
        self.assertEqual(get_uploaded_filename(filetype), rfile.filename)
        self.assertEqual(size, rfile.size)
        with open(lfile.path, "rb") as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)
        self.assertEqual(resource.rtype, BOOT_RESOURCE_TYPE.UPLOADED)

    def test_requires_fields(self):
        form = BootResourceForm(data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEqual(
            {"name", "architecture", "filetype", "content"},
            form.errors.keys(),
        )

    def test_removes_old_bootresourcefiles(self):
        # Regression test for LP:1660418
        os = factory.make_name("os")
        series = factory.make_name("series")
        OperatingSystemRegistry.register_item(os, CustomOS())
        self.addCleanup(OperatingSystemRegistry.unregister_item, os)
        name = f"{os}/{series}"
        architecture = make_usable_architecture(self)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=architecture,
        )
        upload_type, _ = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": name,
            "architecture": architecture,
            "filetype": upload_type,
            "base_image": "ubuntu/focal",
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        self.assertEqual(
            1,
            BootResourceFile.objects.filter(
                resource_set__resource=resource
            ).count(),
        )

    def test_clean_base_image_sets_commissioning_osystem_and_distro_series_where_none_is_given(
        self,
    ):
        architecture = make_usable_architecture(self)
        upload_type, _ = self.pick_filetype()
        content = factory.make_string(1024).encode("utf-8")
        upload_name = factory.make_name("filename")
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            "name": f"custom/{factory.make_name()}",
            "architecture": architecture,
            "filetype": upload_type,
        }
        form = BootResourceForm(data=data, files={"content": uploaded_file})
        form.save()
        cfg = Config.objects.get_configs(
            ["commissioning_osystem", "commissioning_distro_series"]
        )
        self.assertEqual(
            "/".join(
                [
                    cfg["commissioning_osystem"],
                    cfg["commissioning_distro_series"],
                ]
            ),
            form.instance.base_image,
        )
