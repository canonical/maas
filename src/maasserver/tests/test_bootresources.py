# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime
from email.utils import format_datetime
from io import BytesIO
import logging
import os
from os import environ
import random
from random import randint
from subprocess import CalledProcessError
from typing import BinaryIO
from unittest.mock import ANY, MagicMock, Mock, sentinel
from urllib.parse import urljoin

from django.db import transaction
from fixtures import FakeLogger, Fixture
from twisted.application.internet import TimerService
from twisted.internet.defer import Deferred, fail, inlineCallbacks, succeed

from maasserver import __version__, bootresources
from maasserver.bootresources import (
    BootResourceRepoWriter,
    BootResourceStore,
    download_all_boot_resources,
    download_boot_resources,
    set_global_default_releases,
)
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
)
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_FILE_TYPE_CHOICES,
    BOOT_RESOURCE_TYPE,
    COMPONENT,
)
from maasserver.import_images.product_mapping import ProductMapping
from maasserver.listener import PostgresListenerService
from maasserver.models import (
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSource,
    Config,
    signals,
)
from maasserver.models.node import RegionController
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.testing.config import RegionConfigurationFixture
from maasserver.testing.dblocks import lock_held_in_other_thread
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils import get_maas_user_agent
from maasserver.utils.orm import (
    get_one,
    post_commit_hooks,
    reload_object,
    transactional,
)
from maasserver.utils.threads import deferToDatabase
from maasserver.workflow.bootresource import ResourceDownloadParam
from maastesting import get_testing_timeout
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase
from maastesting.twisted import extract_result, TwistedLoggerFixture
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.text import normalise_whitespace
from provisioningserver.utils.twisted import asynchronous, DeferredValue

TIMEOUT = get_testing_timeout()
wait_for_reactor = wait_for()


def make_boot_resource_file_with_stream(
    size=None,
) -> tuple[BootResourceFile, BinaryIO, bytes]:
    resource = factory.make_usable_boot_resource(
        rtype=BOOT_RESOURCE_TYPE.SYNCED, size=size
    )
    rfile = resource.sets.first().files.first()
    lfile = rfile.local_file()
    with open(lfile.path, "rb") as stream:
        content = stream.read()
    lfile.unlink()
    rfile.bootresourcefilesync_set.all().delete()
    return rfile, BytesIO(content), content


class SimplestreamsEnvFixture(Fixture):
    """Clears the env variables set by the methods that interact with
    simplestreams."""

    def setUp(self):
        super().setUp()
        prior_env = {}
        for key in ["GNUPGHOME", "http_proxy", "https_proxy", "no_proxy"]:
            prior_env[key] = os.environ.get(key, "")
        self.addCleanup(os.environ.update, prior_env)


def make_product(ftype=None, kflavor=None, subarch=None, platform=None):
    """Make product dictionary that is just like the one provided
    from simplsetreams."""
    if ftype is None:
        ftype = factory.pick_choice(BOOT_RESOURCE_FILE_TYPE_CHOICES)
    if kflavor is None:
        kflavor = "generic"
    if subarch is None:
        subarch = factory.make_name("subarch")
    if platform is None:
        platform = factory.make_name("platform")
    subarches = [factory.make_name("subarch") for _ in range(3)]
    subarches.insert(0, subarch)
    subarches = ",".join(subarches)
    supported_platforms = ",".join(
        [factory.make_name("platform") for _ in range(3)]
    )
    name = factory.make_name("name")
    product = {
        "os": factory.make_name("os"),
        "arch": factory.make_name("arch"),
        "subarch": subarch,
        "release": factory.make_name("release"),
        "kflavor": kflavor,
        "subarches": subarches,
        "version_name": factory.make_name("version"),
        "label": factory.make_name("label"),
        "ftype": ftype,
        "kpackage": factory.make_name("kpackage"),
        "item_name": name,
        "path": "/path/to/%s" % name,
        "rolling": factory.pick_bool(),
        "platform": platform,
        "supported_platforms": supported_platforms,
    }
    name = "{}/{}".format(product["os"], product["release"])
    if kflavor == "generic":
        subarch = product["subarch"]
    else:
        subarch = "{}-{}".format(product["subarch"], kflavor)
    architecture = "{}/{}".format(product["arch"], subarch)
    return name, architecture, product


def make_boot_resource_group(
    rtype=None,
    name=None,
    architecture=None,
    version=None,
    filename=None,
    filetype=None,
):
    """Make boot resource that contains one set and one file."""
    resource = factory.make_BootResource(
        rtype=rtype, name=name, architecture=architecture
    )
    resource_set = factory.make_BootResourceSet(resource, version=version)
    rfile = factory.make_boot_resource_file_with_content(
        resource_set, filename=filename, filetype=filetype
    )
    return resource, resource_set, rfile


def make_boot_resource_group_from_product(product):
    """Make boot resource that contains one set and one file, using the
    information from the given product.

    The product dictionary is also updated to include the sha256 and size
    for the created largefile. The calling function should use the returned
    product in place of the passed product.
    """
    name = "{}/{}".format(product["os"], product["release"])
    architecture = "{}/{}".format(product["arch"], product["subarch"])
    resource = factory.make_BootResource(
        rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name, architecture=architecture
    )
    resource_set = factory.make_BootResourceSet(
        resource, version=product["version_name"]
    )
    rfile = factory.make_boot_resource_file_with_content(
        resource_set, filename=product["item_name"], filetype=product["ftype"]
    )
    product["sha256"] = rfile.sha256
    product["size"] = rfile.size
    return product, resource


class TestBootResourceStore(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        region = factory.make_RegionController()
        MAAS_ID.set(region.system_id)

    def make_boot_resources(self):
        resources = [
            factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
            for _ in range(3)
        ]
        resource_names = []
        for resource in resources:
            os, series = resource.name.split("/")
            arch, subarch = resource.split_arch()
            name = f"{os}/{arch}/{subarch}/{series}"
            resource_names.append(name)
        return resources, resource_names

    def test_init_initializes_variables(self):
        _, resource_names = self.make_boot_resources()
        store = BootResourceStore()
        self.assertCountEqual(resource_names, store._resources_to_delete)
        self.assertEqual({}, store._content_to_finalize)

    def test_prevent_resource_deletion_removes_resource(self):
        resources, resource_names = self.make_boot_resources()
        store = BootResourceStore()
        resource = resources.pop()
        resource_names.pop()
        store.prevent_resource_deletion(resource)
        self.assertCountEqual(resource_names, store._resources_to_delete)

    def test_prevent_resource_deletion_doesnt_remove_unknown_resource(self):
        resources, resource_names = self.make_boot_resources()
        store = BootResourceStore()
        resource = factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        store.prevent_resource_deletion(resource)
        self.assertCountEqual(resource_names, store._resources_to_delete)

    def test_save_content_later_adds_to__content_to_finalize_var(self):
        _, _, rfile = make_boot_resource_group()
        req = ResourceDownloadParam(
            rfile_ids=[rfile.id],
            source_list=[],
            sha256=rfile.sha256,
            total_size=rfile.size,
        )
        store = BootResourceStore()
        store.save_content_later(rfile, [])
        self.assertEqual({rfile.sha256: req}, store._content_to_finalize)

    def test_get_or_create_boot_resource_creates_resource(self):
        name, architecture, product = make_product()
        store = BootResourceStore()
        resource = store.get_or_create_boot_resource(product)
        self.assertEqual(BOOT_RESOURCE_TYPE.SYNCED, resource.rtype)
        self.assertEqual(name, resource.name)
        self.assertEqual(architecture, resource.architecture)
        self.assertEqual(product["kflavor"], resource.kflavor)
        self.assertEqual(product["subarches"], resource.extra["subarches"])
        self.assertEqual(product["platform"], resource.extra["platform"])
        self.assertEqual(
            product["supported_platforms"],
            resource.extra["supported_platforms"],
        )
        self.assertEqual(product["rolling"], resource.rolling)

    def test_get_or_create_boot_resource_gets_resource(self):
        name, architecture, product = make_product()
        expected = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
        )
        store = BootResourceStore()
        resource = store.get_or_create_boot_resource(product)
        self.assertEqual(expected, resource)
        self.assertEqual(product["kflavor"], resource.kflavor)
        self.assertEqual(product["subarches"], resource.extra["subarches"])
        self.assertEqual(product["platform"], resource.extra["platform"])
        self.assertEqual(
            product["supported_platforms"],
            resource.extra["supported_platforms"],
        )

    def test_get_or_create_boot_resource_calls_prevent_resource_deletion(self):
        name, architecture, product = make_product()
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
        )
        store = BootResourceStore()
        mock_prevent = self.patch(store, "prevent_resource_deletion")
        store.get_or_create_boot_resource(product)
        mock_prevent.assert_called_once_with(resource)

    def test_get_or_create_boot_resource_adds_kflavor_to_subarch(self):
        kflavor = factory.make_name("kflavor")
        _, architecture, product = make_product(
            kflavor=kflavor, subarch=random.choice(["hwe-16.04", "ga-16.04"])
        )
        store = BootResourceStore()
        resource = store.get_or_create_boot_resource(product)
        self.assertEqual(architecture, reload_object(resource).architecture)
        self.assertTrue(architecture.endswith(kflavor))

    def test_get_or_create_boot_resources_add_no_kflavor_for_generic(self):
        _, architecture, product = make_product(kflavor="generic")
        store = BootResourceStore()
        resource = store.get_or_create_boot_resource(product)
        resource = reload_object(resource)
        self.assertEqual(architecture, resource.architecture)
        self.assertNotIn("generic", resource.architecture)

    def test_get_or_create_boot_resource_handles_ubuntu_core(self):
        product = {
            "arch": "amd64",
            "gadget_snap": "pc",
            "gadget_title": "PC",
            "kernel_snap": "pc-kernel",
            "label": "daily",
            "maas_supported": "2.2",
            "os": "ubuntu-core",
            "os_title": "Ubuntu Core",
            "release": "16",
            "release_title": "16",
            "item_name": "root-dd.xz",
            "ftype": BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ,
            "path": "/path/to/root-dd.xz",
        }
        store = BootResourceStore()
        resource = store.get_or_create_boot_resource(product)
        self.assertEqual(BOOT_RESOURCE_TYPE.SYNCED, resource.rtype)
        self.assertEqual("ubuntu-core/16-pc", resource.name)
        self.assertEqual("amd64/generic", resource.architecture)
        self.assertIsNone(resource.bootloader_type)
        self.assertEqual("pc-kernel", resource.kflavor)
        self.assertDictEqual({"title": "Ubuntu Core 16 PC"}, resource.extra)

    def test_get_or_create_boot_resource_set_creates_resource_set(self):
        _, _, product = make_product()
        product, resource = make_boot_resource_group_from_product(product)
        with post_commit_hooks:
            resource.sets.all().delete()
        store = BootResourceStore()
        resource_set = store.get_or_create_boot_resource_set(resource, product)
        self.assertEqual(product["version_name"], resource_set.version)
        self.assertEqual(product["label"], resource_set.label)

    def test_get_or_create_boot_resource_set_gets_resource_set(self):
        _, _, product = make_product()
        product, resource = make_boot_resource_group_from_product(product)
        expected = resource.sets.first()
        store = BootResourceStore()
        resource_set = store.get_or_create_boot_resource_set(resource, product)
        self.assertEqual(expected, resource_set)
        self.assertEqual(product["label"], resource_set.label)

    def test_get_or_create_boot_resource_file_creates_resource_file(self):
        _, _, product = make_product()
        product, resource = make_boot_resource_group_from_product(product)
        resource_set = resource.sets.first()
        with post_commit_hooks:
            resource_set.files.all().delete()
        store = BootResourceStore()
        rfile, _ = store.get_or_create_boot_resource_file(
            resource_set, product
        )
        self.assertEqual(os.path.basename(product["path"]), rfile.filename)
        self.assertEqual(product["ftype"], rfile.filetype)
        self.assertEqual(product["kpackage"], rfile.extra["kpackage"])

    def test_get_or_create_boot_resource_file_gets_resource_file(self):
        _, _, product = make_product()
        product, resource = make_boot_resource_group_from_product(product)
        resource_set = resource.sets.first()
        expected = resource_set.files.first()
        store = BootResourceStore()
        rfile, _ = store.get_or_create_boot_resource_file(
            resource_set, product
        )
        self.assertEqual(expected, rfile)
        self.assertEqual(product["ftype"], rfile.filetype)
        self.assertEqual(product["kpackage"], rfile.extra["kpackage"])

    def test_get_or_create_boot_resource_file_captures_extra_fields(self):
        extra_fields = [
            "kpackage",
            "src_package",
            "src_release",
            "src_version",
        ]
        _, _, product = make_product()
        for extra_field in extra_fields:
            product[extra_field] = factory.make_name(extra_field)
        product, resource = make_boot_resource_group_from_product(product)
        resource_set = resource.sets.first()
        store = BootResourceStore()
        rfile, _ = store.get_or_create_boot_resource_file(
            resource_set, product
        )
        for extra_field in extra_fields:
            self.assertEqual(product[extra_field], rfile.extra[extra_field])

    def test_get_or_create_boot_resources_can_handle_duplicate_ftypes(self):
        _, _, product = make_product()
        product, resource = make_boot_resource_group_from_product(product)
        resource_set = resource.sets.first()
        store = BootResourceStore()
        files = [resource_set.files.first().filename]
        with post_commit_hooks:
            for _ in range(3):
                item_name = factory.make_name("item_name")
                product["item_name"] = item_name
                files.append(item_name)
                rfile, _ = store.get_or_create_boot_resource_file(
                    resource_set, product
                )
            for rfile in resource_set.files.all():
                self.assertIn(rfile.filename, files)
                self.assertEqual(rfile.filetype, product["ftype"])

    def test_get_resource_file_log_identifier_returns_valid_ident(self):
        os = factory.make_name("os")
        series = factory.make_name("series")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        version = factory.make_name("version")
        filename = factory.make_name("filename")
        name = f"{os}/{series}"
        architecture = f"{arch}/{subarch}"
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
        )
        resource_set = factory.make_BootResourceSet(resource, version=version)
        rfile = factory.make_boot_resource_file_with_content(
            resource_set, filename=filename
        )
        store = BootResourceStore()
        self.assertEqual(
            "%s/%s/%s/%s/%s/%s"
            % (os, arch, subarch, series, version, filename),
            store.get_resource_file_log_identifier(rfile),
        )
        self.assertEqual(
            "%s/%s/%s/%s/%s/%s"
            % (os, arch, subarch, series, version, filename),
            store.get_resource_file_log_identifier(
                rfile, resource_set, resource
            ),
        )

    def test_delete_content_to_finalize_deletes_items(self):
        rfile_one, _, _ = make_boot_resource_file_with_stream()
        rfile_two, _, _ = make_boot_resource_file_with_stream()
        store = BootResourceStore()
        store._content_to_finalize = {
            rfile_one.sha256: ResourceDownloadParam(
                rfile_ids=[rfile_one.id, rfile_two.id],
                source_list=[],
                sha256=rfile_one.sha256,
                total_size=rfile_one.size,
            ),
        }
        store.delete_content_to_finalize()
        self.assertIsNone(reload_object(rfile_one))
        self.assertIsNone(reload_object(rfile_two))
        self.assertEqual({}, store._content_to_finalize)

    def test_finalize_does_nothing_if_resources_to_delete_hasnt_changed(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        store = BootResourceStore()
        mock_resource_cleaner = self.patch(store, "resource_cleaner")
        mock_execute_workflow = self.patch(bootresources, "execute_workflow")
        mock_resource_set_cleaner = self.patch(store, "resource_set_cleaner")
        store.finalize()
        mock_resource_cleaner.assert_not_called()
        mock_execute_workflow.assert_not_called()
        mock_resource_set_cleaner.assert_not_called()

    def test_finalize_calls_methods_if_new_resources_need_to_be_saved(self):
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        store = BootResourceStore()
        store._content_to_finalize = {1: sentinel.content}
        mock_resource_cleaner = self.patch(store, "resource_cleaner")
        mock_execute_workflow = self.patch(bootresources, "execute_workflow")
        mock_resource_set_cleaner = self.patch(store, "resource_set_cleaner")
        store.finalize()
        self.assertTrue(store._finalizing)
        mock_resource_cleaner.assert_called_once()
        mock_execute_workflow.assert_called_once()
        mock_resource_set_cleaner.assert_called_once()

    def test_finalize_calls_methods_if_resources_to_delete_has_changed(self):
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        store = BootResourceStore()
        store._resources_to_delete = set()
        mock_resource_cleaner = self.patch(store, "resource_cleaner")
        mock_resource_set_cleaner = self.patch(store, "resource_set_cleaner")
        store.finalize()
        mock_resource_cleaner.assert_called_once()
        mock_resource_set_cleaner.assert_called_once()

    def test_finalize_calls_methods_with_delete_if_cancel_finalize(self):
        factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        store = BootResourceStore()
        store._content_to_finalize = {1: sentinel.content}
        mock_resource_cleaner = self.patch(store, "resource_cleaner")
        mock_delete = self.patch(store, "delete_content_to_finalize")
        mock_resource_set_cleaner = self.patch(store, "resource_set_cleaner")
        store._cancel_finalize = True
        store.finalize()
        self.assertFalse(store._finalizing)
        mock_resource_cleaner.assert_called_once()
        mock_delete.assert_called_once()
        mock_resource_set_cleaner.assert_called_once()


class TestBootResourceTransactional(MAASTransactionServerTestCase):
    """Test methods on `BootResourceStore` that manage their own transactions.

    This is done using `MAASTransactionServerTestCase` so the database is
    flushed after each test run.
    """

    def setUp(self):
        super().setUp()
        self.region = factory.make_RegionController()
        MAAS_ID.set(self.region.system_id)

    def test_insert_does_nothing_if_file_already_synced(self):
        _, _, product = make_product()
        with transaction.atomic():
            product, resource = make_boot_resource_group_from_product(product)
            rfile = resource.sets.first().files.first()
            rfile.bootresourcefilesync_set.create(
                region=self.region, size=rfile.size
            )
        store = BootResourceStore()
        mock_save_later = self.patch(store, "save_content_later")
        store.insert(product, [])
        lfile = rfile.local_file()
        self.assertTrue(lfile.path.exists())
        mock_save_later.assert_not_called()

    def test_insert_deletes_mismatch_largefile(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        _, _, product = make_product()
        with transaction.atomic():
            product, resource = make_boot_resource_group_from_product(product)
            rfile = resource.sets.first().files.first()
            lfile = rfile.local_file()
            orig_path = lfile.path
        product["sha256"] = "cadecafe"
        product["size"] = rfile.size
        self.assertTrue(orig_path.exists())
        store = BootResourceStore()
        self.patch(store, "save_content_later")
        mock_remove = self.patch(
            bootresources.BootResourceFile.objects, "filestore_remove_file"
        )
        store.insert(product, [])
        mock_remove.assert_called_once()

    def test_insert_deletes_root_image_if_squashfs_available(self):
        _, _, product = make_product(BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE)
        with transaction.atomic():
            product, resource = make_boot_resource_group_from_product(product)
            rfile = resource.sets.first().files.first()
        product["ftype"] = BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE
        product["itemname"] = "squashfs"
        product["path"] = "/path/to/squashfs"
        product["sha256"] = rfile.sha256
        product["size"] = rfile.size
        store = BootResourceStore()
        mock_filestore_remove_files = self.patch(
            bootresources.BootResourceFile.objects, "filestore_remove_files"
        )
        mock_save_later = self.patch(store, "save_content_later")
        store.insert(product, [])
        brs = resource.get_latest_set()
        self.assertEqual(
            0,
            brs.files.filter(
                filetype=BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
            ).count(),
        )
        self.assertEqual(
            1,
            brs.files.filter(
                filetype=BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE
            ).count(),
        )
        mock_filestore_remove_files.assert_called()
        mock_save_later.assert_called()

    def test_insert_prints_warning_if_mismatch_largefile(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        _, _, product = make_product()
        with transaction.atomic():
            product, resource = make_boot_resource_group_from_product(product)
            rfile = resource.sets.first().files.first()
        product["sha256"] = "cadecafe"
        product["size"] = rfile.size
        store = BootResourceStore()
        with FakeLogger("maas", logging.WARNING) as logger:
            store.insert(product, [])
        self.assertIn("Hash mismatch for resourceset=", logger.output)

    def test_insert_deletes_mismatch_largefile_keeps_other_resource_file(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        name, architecture, product = make_product(
            ftype=BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
        )
        with transaction.atomic():
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=architecture,
            )
            resource_set = factory.make_BootResourceSet(
                resource, version=product["version_name"]
            )
            other_type = factory.pick_enum(
                BOOT_RESOURCE_FILE_TYPE,
                but_not=[
                    product["ftype"],
                    BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
                ],
            )
            other_file = factory.make_boot_resource_file_with_content(
                resource_set, filename=other_type, filetype=other_type
            )
            other_lfile = other_file.local_file()
            factory.make_BootResourceFile(
                resource_set,
                filename=product["item_name"],
                filetype=product["ftype"],
                sha256=other_file.sha256,
                size=other_file.size,
            )
            lfile = factory.make_boot_file()
        product["sha256"] = lfile.sha256
        product["size"] = lfile.total_size
        store = BootResourceStore()
        mock_save_later = self.patch(store, "save_content_later")
        mock_filestore_remove_file = self.patch(
            bootresources.BootResourceFile.objects, "filestore_remove_file"
        )
        store.insert(product, [])
        self.assertTrue(other_lfile.path.exists())
        self.assertTrue(
            BootResourceFile.objects.filter(id=other_file.id).exists()
        )
        mock_filestore_remove_file.assert_called_once()
        mock_save_later.assert_called_once()

    def test_insert_creates_new_largefile(self):
        name, architecture, product = make_product()
        with transaction.atomic():
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=architecture,
            )
            resource_set = factory.make_BootResourceSet(
                resource, version=product["version_name"]
            )
        product["sha256"] = factory.make_string(size=64)
        product["size"] = randint(1024, 2048)
        store = BootResourceStore()
        mock_save_later = self.patch(store, "save_content_later")
        store.insert(product, [])
        rfile = get_one(reload_object(resource_set).files.all())
        self.assertEqual(product["sha256"], rfile.sha256)
        self.assertEqual(product["size"], rfile.size)
        mock_save_later.assert_called_once_with(
            rfile, source_list=[], force=False, extract_path=None
        )

    def test_insert_prints_error_when_breaking_resources(self):
        # Test case for bug 1419041: if the call to insert() makes
        # an existing complete resource incomplete: print an error in the
        # log.
        self.patch(bootresources.Event.objects, "create_region_event")
        name, architecture, product = make_product()
        with transaction.atomic():
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=architecture,
                kflavor="generic",
            )
            resource_set = factory.make_BootResourceSet(
                resource,
                version=product["version_name"],
            )
            factory.make_boot_resource_file_with_content(
                resource_set,
                filename=product["ftype"],
                filetype=product["ftype"],
                synced=[(self.region, -1)],
            )
            # The resource has a complete set.
            self.assertIsNotNone(resource.get_latest_complete_set())
        product["sha256"] = factory.make_string(size=64)
        product["size"] = randint(1024, 2048)
        store = BootResourceStore()
        with FakeLogger("maas", logging.ERROR) as logger:
            store.insert(product, [])

        self.assertIsNone(resource.get_latest_complete_set())
        self.assertIn(
            f"Resource {resource} has no complete resource set!",
            logger.output,
        )

    def test_get_latest_complete_set_not_in_sync_between_regions(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        name, architecture, product = make_product()
        second_region = factory.make_RegionController()
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
            kflavor="generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource,
            version=product["version_name"],
        )
        factory.make_boot_resource_file_with_content(
            resource_set,
            filename=product["ftype"],
            filetype=product["ftype"],
            synced=[
                (self.region, -1),
                (second_region, 0),
            ],  # Not in sync between regions
        )
        self.assertIsNone(resource.get_latest_complete_set())

    def test_get_latest_complete_set_has_completed(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        name, architecture, product = make_product()
        second_region = factory.make_RegionController()
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
            kflavor="generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource,
            version=product["version_name"],
        )
        factory.make_boot_resource_file_with_content(
            resource_set,
            filename=product["ftype"],
            filetype=product["ftype"],
            synced=[
                (self.region, -1),
                (second_region, -1),
            ],  # In Sync between regions
        )
        self.assertEqual(resource_set, resource.get_latest_complete_set())

    def test_get_latest_complete_multiple_sets_incomplete(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        name, architecture, product = make_product()
        second_region = factory.make_RegionController()
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
            kflavor="generic",
        )
        resource_set = factory.make_BootResourceSet(
            resource,
            version=product["version_name"],
        )
        incomplete_resource_set = factory.make_BootResourceSet(
            resource,
            version="alpha",
        )
        factory.make_boot_resource_file_with_content(
            resource_set,
            filename=product["ftype"],
            filetype=product["ftype"],
            synced=[
                (self.region, -1),
                (second_region, -1),
            ],  # This is the latest completed
        )
        factory.make_boot_resource_file_with_content(
            incomplete_resource_set,
            filename=product["ftype"],
            filetype=product["ftype"],
            synced=[(self.region, 0)],  # Not in sync yet
        )
        self.assertEqual(resource_set, resource.get_latest_complete_set())

    def test_insert_doesnt_print_error_when_first_import(self):
        name, architecture, product = make_product()
        with transaction.atomic():
            factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=architecture,
            )
        product["sha256"] = factory.make_string(size=64)
        product["size"] = randint(1024, 2048)
        store = BootResourceStore()

        with FakeLogger("maas", logging.ERROR) as logger:
            store.insert(product, [])

        self.assertEqual("", logger.output)

    def test_resource_cleaner_removes_boot_resources_without_sets(self):
        with transaction.atomic():
            resources = [
                factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
                for _ in range(3)
            ]
        store = BootResourceStore()
        store.resource_cleaner()
        for resource in resources:
            os, series = resource.name.split("/")
            arch, subarch = resource.split_arch()
            self.assertFalse(
                BootResource.objects.has_synced_resource(
                    os, arch, subarch, series
                )
            )

    def test_resource_cleaner_removes_boot_resources_not_in_selections(self):
        self.useFixture(SignalsDisabled("bootsources"))
        with transaction.atomic():
            # Make random selection as one is required, and empty set of
            # selections will not delete anything.
            factory.make_BootSourceSelection()
            resources = [
                factory.make_usable_boot_resource(
                    rtype=BOOT_RESOURCE_TYPE.SYNCED
                )
                for _ in range(3)
            ]
        store = BootResourceStore()
        store.resource_cleaner()
        for resource in resources:
            os, series = resource.name.split("/")
            arch, subarch = resource.split_arch()
            self.assertFalse(
                BootResource.objects.has_synced_resource(
                    os, arch, subarch, series
                )
            )

    def test_resource_cleaner_removes_extra_subarch_boot_resource(self):
        self.useFixture(SignalsDisabled("bootsources"))
        with transaction.atomic():
            # Make selection that will keep both subarches.
            arch = factory.make_name("arch")
            selection = factory.make_BootSourceSelection(
                arches=[arch], subarches=["*"], labels=["*"]
            )
            # Create first subarch for selection.
            subarch_one = factory.make_name("subarch")
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=f"{selection.os}/{selection.release}",
                architecture=f"{arch}/{subarch_one}",
            )
            # Create second subarch for selection.
            subarch_two = factory.make_name("subarch")
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=f"{selection.os}/{selection.release}",
                architecture=f"{arch}/{subarch_two}",
            )
        store = BootResourceStore()
        store._resources_to_delete = [
            "%s/%s/%s/%s"
            % (selection.os, arch, subarch_two, selection.release)
        ]
        store.resource_cleaner()
        self.assertTrue(
            BootResource.objects.has_synced_resource(
                selection.os, arch, subarch_one, selection.release
            )
        )
        self.assertFalse(
            BootResource.objects.has_synced_resource(
                selection.os, arch, subarch_two, selection.release
            )
        )

    def test_resource_cleaner_keeps_boot_resources_in_selections(self):
        self.patch(bootresources.Event.objects, "create_region_event")
        self.useFixture(SignalsDisabled("bootsources"))
        with transaction.atomic():
            resources = [
                factory.make_usable_boot_resource(
                    rtype=BOOT_RESOURCE_TYPE.SYNCED
                )
                for _ in range(3)
            ]
            for resource in resources:
                os, series = resource.name.split("/")
                arch, subarch = resource.split_arch()
                resource_set = resource.get_latest_set()
                factory.make_BootSourceSelection(
                    os=os,
                    release=series,
                    arches=[arch],
                    subarches=[subarch],
                    labels=[resource_set.label],
                )
        store = BootResourceStore()
        store.resource_cleaner()
        for resource in resources:
            os, series = resource.name.split("/")
            arch, subarch = resource.split_arch()
            self.assertTrue(
                BootResource.objects.has_synced_resource(
                    os, arch, subarch, series
                )
            )

    def test_resource_set_cleaner_removes_incomplete_set(self):
        with transaction.atomic():
            resource = factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED
            )
            incomplete_set = factory.make_BootResourceSet(resource)
        store = BootResourceStore()
        store.resource_set_cleaner()
        self.assertFalse(
            BootResourceSet.objects.filter(id=incomplete_set.id).exists()
        )

    def test_resource_set_cleaner_keeps_only_newest_completed_set(self):
        with transaction.atomic():
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED
            )
            old_complete_sets = []
            sync = [(r, -1) for r in RegionController.objects.all()]
            for _ in range(3):
                resource_set = factory.make_BootResourceSet(resource)
                factory.make_boot_resource_file_with_content(
                    resource_set, synced=sync
                )
                old_complete_sets.append(resource_set)
            newest_set = factory.make_BootResourceSet(resource)
            factory.make_boot_resource_file_with_content(
                newest_set, synced=sync
            )
        store = BootResourceStore()
        store.resource_set_cleaner()
        self.assertCountEqual([newest_set], resource.sets.all())
        for resource_set in old_complete_sets:
            self.assertFalse(
                BootResourceSet.objects.filter(id=resource_set.id).exists()
            )

    def test_resource_set_cleaner_removes_resources_with_empty_sets(self):
        with transaction.atomic():
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED
            )
        store = BootResourceStore()
        store.resource_set_cleaner()
        self.assertFalse(BootResource.objects.filter(id=resource.id).exists())

    @wait_for_reactor
    def test_finalize_calls_notify_errback(self):
        @transactional
        def create_store(testcase):
            factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
            store = BootResourceStore()
            testcase.patch(store, "resource_cleaner")
            testcase.patch(store, "execute_workflow")
            testcase.patch(store, "resource_set_cleaner")
            testcase.patch(store, "_get_http_proxy")
            return store

        notify = Deferred()
        d = deferToDatabase(create_store, self)
        d.addCallback(lambda store: store.finalize(notify=notify))
        d.addCallback(lambda _: notify)
        d.addErrback(lambda failure: failure.trap(Exception))
        return d

    @wait_for_reactor
    def test_finalize_calls_notify_callback(self):
        @transactional
        def create_store(testcase):
            factory.make_BootResource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
            store = BootResourceStore()
            store._content_to_finalize = {1: sentinel.content}
            testcase.patch(store, "resource_cleaner")
            testcase.patch(bootresources, "execute_workflow")
            testcase.patch(store, "resource_set_cleaner")
            testcase.patch(store, "_get_http_proxy")
            return store

        notify = Deferred()
        d = deferToDatabase(create_store, self)
        d.addCallback(lambda store: store.finalize(notify=notify))
        d.addCallback(lambda _: notify)
        return d


class TestSetGlobalDefaultReleases(MAASServerTestCase):
    def test_doesnt_change_anything(self):
        commissioning_release = factory.make_name("release")
        deploy_release = factory.make_name("release")
        Config.objects.set_config(
            "commissioning_distro_series", commissioning_release
        )
        Config.objects.set_config("default_distro_series", deploy_release)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        mock_available = self.patch(
            BootResource.objects, "get_available_commissioning_resources"
        )
        mock_available.return_value = [resource]
        set_global_default_releases()
        self.assertEqual(
            commissioning_release,
            Config.objects.get(name="commissioning_distro_series").value,
        )
        self.assertEqual(
            deploy_release,
            Config.objects.get(name="default_distro_series").value,
        )

    def test_sets_commissioning_release(self):
        os, release = factory.make_name("os"), factory.make_name("release")
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=f"{os}/{release}"
        )
        mock_available = self.patch(
            BootResource.objects, "get_available_commissioning_resources"
        )
        mock_available.return_value = [resource]
        set_global_default_releases()
        self.assertEqual(
            os, Config.objects.get(name="commissioning_osystem").value
        )
        self.assertEqual(
            release,
            Config.objects.get(name="commissioning_distro_series").value,
        )

    def test_sets_both_commissioning_deploy_release(self):
        os, release = factory.make_name("os"), factory.make_name("release")
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=f"{os}/{release}"
        )
        mock_available = self.patch(
            BootResource.objects, "get_available_commissioning_resources"
        )
        mock_available.return_value = [resource]
        set_global_default_releases()
        self.assertEqual(
            os, Config.objects.get(name="commissioning_osystem").value
        )
        self.assertEqual(
            release,
            Config.objects.get(name="commissioning_distro_series").value,
        )
        self.assertEqual(os, Config.objects.get(name="default_osystem").value)
        self.assertEqual(
            release, Config.objects.get(name="default_distro_series").value
        )


class TestImportImages(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SimplestreamsEnvFixture())
        # Don't create the gnupg home directory.
        self.patch_autospec(bootresources, "create_gnupg_home")
        # Don't actually create the sources as that will make the cache update.
        self.patch_autospec(
            bootresources, "ensure_boot_source_definition"
        ).return_value = False
        # We're not testing cache_boot_sources() here, so patch it out to
        # avoid inadvertently calling it and wondering why the test blocks.
        self.patch_autospec(bootresources, "cache_boot_sources")
        self.patch(bootresources.Event.objects, "create_region_event")

    def patch_and_capture_env_for_download_all_boot_resources(self):
        class CaptureEnv:
            """Fake function; records a copy of the environment."""

            def __call__(self, *args, **kwargs):
                self.args = args
                self.env = environ.copy()

        capture = self.patch(
            bootresources, "download_all_boot_resources", CaptureEnv()
        )
        return capture

    def test_download_boot_resources_syncs_repo(self):
        fake_sync = self.patch(bootresources.BootResourceRepoWriter, "sync")
        store = BootResourceStore()
        source_url = factory.make_url()
        download_boot_resources(source_url, store, None, None)
        self.assertEqual(1, len(fake_sync.mock_calls))

    def test_download_boot_resources_passes_user_agent(self):
        self.patch(bootresources.BootResourceRepoWriter, "sync")
        store = BootResourceStore()
        source_url = factory.make_url()
        mock_UrlMirrorReader = self.patch(bootresources, "UrlMirrorReader")
        download_boot_resources(source_url, store, None, None)
        mock_UrlMirrorReader.assert_called_once_with(
            ANY, policy=ANY, user_agent=get_maas_user_agent()
        )

    def test_download_all_boot_resources_calls_download_boot_resources(self):
        source = {
            "url": factory.make_url(),
            "keyring": self.make_file("keyring"),
        }
        product_mapping = ProductMapping()
        store = BootResourceStore()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = MagicMock()
        fake_download = self.patch(bootresources, "download_boot_resources")
        download_all_boot_resources(
            sources=[source], product_mapping=product_mapping, store=store
        )
        fake_download.assert_called_once_with(
            source["url"],
            store,
            product_mapping,
            keyring_file=source["keyring"],
        )

    def test_download_all_boot_resources_calls_finalize_on_store(self):
        product_mapping = ProductMapping()
        store = BootResourceStore()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = MagicMock()
        fake_finalize = self.patch(store, "finalize")
        success = download_all_boot_resources(
            sources=[], product_mapping=product_mapping, store=store
        )
        fake_finalize.assert_called_once_with(notify=None)
        self.assertTrue(success)

    def test_download_all_boot_resources_registers_stop_handler(self):
        product_mapping = ProductMapping()
        store = BootResourceStore()
        listener = MagicMock()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = listener
        self.patch(bootresources, "download_boot_resources")
        download_all_boot_resources(
            sources=[], product_mapping=product_mapping, store=store
        )
        listener.listen.assert_called_once_with("sys_stop_import", ANY)

    def test_download_all_boot_resources_calls_cancel_finalize(self):
        product_mapping = ProductMapping()
        store = BootResourceStore()
        listener = MagicMock()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = listener

        # Call the stop_import function register with the listener.
        def call_stop(*args, **kwargs):
            listener.listen.call_args[0][1]("sys_stop_import", "")

        self.patch(
            bootresources, "download_boot_resources"
        ).side_effect = call_stop

        mock_cancel = self.patch(store, "cancel_finalize")
        mock_finalize = self.patch(store, "finalize")
        success = download_all_boot_resources(
            sources=[{"url": "", "keyring": ""}],
            product_mapping=product_mapping,
            store=store,
        )
        mock_cancel.assert_called_once()
        mock_finalize.assert_not_called()
        self.assertFalse(success)

    def test_download_all_boot_resources_calls_cancel_finalize_in_stop(self):
        product_mapping = ProductMapping()
        store = BootResourceStore()
        listener = MagicMock()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = listener
        self.patch(bootresources, "download_boot_resources")

        # Call the stop_import function when finalize is called.
        def call_stop(*args, **kwargs):
            listener.listen.call_args[0][1]("sys_stop_import", "")

        mock_finalize = self.patch(store, "finalize")
        mock_finalize.side_effect = call_stop
        mock_cancel = self.patch(store, "cancel_finalize")

        success = download_all_boot_resources(
            sources=[{"url": "", "keyring": ""}],
            product_mapping=product_mapping,
            store=store,
        )
        mock_finalize.assert_called_once()
        mock_cancel.assert_called_once()
        self.assertFalse(success)

    def test_download_all_boot_resources_reraises_download_failure(self):
        product_mapping = ProductMapping()
        store = BootResourceStore()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = MagicMock()
        exc_text = "Expected"
        self.patch(
            bootresources, "download_boot_resources"
        ).side_effect = Exception(exc_text)

        with self.assertRaisesRegex(Exception, exc_text):
            download_all_boot_resources(
                sources=[{"url": "", "keyring": ""}],
                product_mapping=product_mapping,
                store=store,
            )

    def test_download_all_boot_resources_unregisters_listener_on_download_failure(
        self,
    ):
        product_mapping = ProductMapping()
        store = BootResourceStore()
        listener = PostgresListenerService()
        listener.register = MagicMock()
        listener.unregister = MagicMock()
        self.patch(
            bootresources.services, "getServiceNamed"
        ).return_value = listener
        exc_text = "Expected"
        self.patch(
            bootresources, "download_boot_resources"
        ).side_effect = Exception(exc_text)

        with self.assertRaisesRegex(Exception, exc_text):
            download_all_boot_resources(
                sources=[{"url": "", "keyring": ""}],
                product_mapping=product_mapping,
                store=store,
            )
        listener.register.assert_called_once_with("sys_stop_import", ANY)
        listener.unregister.assert_called_once_with("sys_stop_import", ANY)

    def test_import_resources_exits_early_if_lock_held(self):
        set_simplestreams_env = self.patch_autospec(
            bootresources, "set_simplestreams_env"
        )
        with lock_held_in_other_thread(bootresources.locks.import_images):
            bootresources._import_resources()
        # The test for set_simplestreams_env is not called if the
        # lock is already held.
        set_simplestreams_env.assert_not_called()

    def test_import_resources_holds_lock(self):
        fake_write_all_keyrings = self.patch(
            bootresources, "write_all_keyrings"
        )

        def test_for_held_lock(directory, sources):
            self.assertTrue(bootresources.locks.import_images.is_locked())
            return []

        fake_write_all_keyrings.side_effect = test_for_held_lock

        bootresources._import_resources()
        self.assertFalse(bootresources.locks.import_images.is_locked())

    def test_import_resources_calls_functions_with_correct_parameters(self):
        write_all_keyrings = self.patch(bootresources, "write_all_keyrings")
        write_all_keyrings.return_value = []
        image_descriptions = self.patch(
            bootresources, "download_all_image_descriptions"
        )
        descriptions = Mock()
        descriptions.is_empty.return_value = False
        image_descriptions.return_value = descriptions
        map_products = self.patch(bootresources, "map_products")
        map_products.return_value = sentinel.mapping
        download_all_boot_resources = self.patch(
            bootresources, "download_all_boot_resources"
        )
        set_global_default_releases = self.patch(
            bootresources, "set_global_default_releases"
        )

        bootresources._import_resources()

        bootresources.create_gnupg_home.assert_called_once()
        bootresources.ensure_boot_source_definition.assert_called_once()
        bootresources.cache_boot_sources.assert_called_once()
        write_all_keyrings.assert_called_once_with(ANY, [])
        image_descriptions.assert_called_once_with([], get_maas_user_agent())
        map_products.assert_called_once_with(descriptions)
        download_all_boot_resources.assert_called_once_with(
            [], sentinel.mapping, notify=None
        )
        set_global_default_releases.assert_called_once()

    def test_import_resources_has_env_GNUPGHOME_set(self):
        fake_image_descriptions = self.patch(
            bootresources, "download_all_image_descriptions"
        )
        descriptions = Mock()
        descriptions.is_empty.return_value = False
        fake_image_descriptions.return_value = descriptions
        self.patch(bootresources, "map_products")
        capture = self.patch_and_capture_env_for_download_all_boot_resources()

        bootresources._import_resources()
        self.assertEqual(get_maas_user_gpghome(), capture.env["GNUPGHOME"])

    def test_import_resources_has_env_http_and_https_proxy_set(self):
        proxy_address = factory.make_name("proxy")
        self.patch(signals.bootsources, "post_commit_do")
        Config.objects.set_config("http_proxy", proxy_address)

        fake_image_descriptions = self.patch(
            bootresources, "download_all_image_descriptions"
        )
        descriptions = Mock()
        descriptions.is_empty.return_value = False
        fake_image_descriptions.return_value = descriptions
        self.patch(bootresources, "map_products")
        capture = self.patch_and_capture_env_for_download_all_boot_resources()

        bootresources._import_resources()
        self.assertEqual(
            (proxy_address, proxy_address),
            (capture.env["http_proxy"], capture.env["http_proxy"]),
        )

    def test_restarts_import_if_source_changed(self):
        # Regression test for LP:1766370
        self.patch(signals.bootsources, "post_commit_do")
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        factory.make_BootSourceSelection(boot_source=boot_source)

        def write_all_keyrings(directory, sources):
            for source in sources:
                source["keyring"] = factory.make_name("keyring")
            return sources

        mock_write_all_keyrings = self.patch(
            bootresources, "write_all_keyrings"
        )
        mock_write_all_keyrings.side_effect = write_all_keyrings

        def image_descriptions(*args, **kwargs):
            # Simulate user changing sources
            if not image_descriptions.called:
                BootSource.objects.all().delete()
                boot_source = factory.make_BootSource(
                    keyring_data=factory.make_bytes()
                )
                factory.make_BootSourceSelection(boot_source=boot_source)
                image_descriptions.called = True

            class Ret:
                def is_empty(self):
                    return False

            return Ret()

        image_descriptions.called = False
        mock_image_descriptions = self.patch(
            bootresources, "download_all_image_descriptions"
        )
        mock_image_descriptions.side_effect = image_descriptions
        descriptions = Mock()
        descriptions.is_empty.return_value = False
        image_descriptions.return_value = descriptions
        map_products = self.patch(bootresources, "map_products")
        map_products.return_value = sentinel.mapping
        self.patch(bootresources, "download_all_boot_resources")
        self.patch(bootresources, "set_global_default_releases")

        bootresources._import_resources()

        # write_all_keyrings is called once per
        self.assertEqual(2, mock_write_all_keyrings.call_count)

    def test_restarts_import_if_selection_changed(self):
        # Regression test for LP:1766370
        self.patch(signals.bootsources, "post_commit_do")
        boot_source = factory.make_BootSource(
            keyring_data=factory.make_bytes()
        )
        factory.make_BootSourceSelection(boot_source=boot_source)

        def write_all_keyrings(directory, sources):
            for source in sources:
                source["keyring"] = factory.make_name("keyring")
            return sources

        mock_write_all_keyrings = self.patch(
            bootresources, "write_all_keyrings"
        )
        mock_write_all_keyrings.side_effect = write_all_keyrings

        def image_descriptions(*args, **kwargs):
            # Simulate user adding a selection.
            if not image_descriptions.called:
                factory.make_BootSourceSelection(boot_source=boot_source)
                image_descriptions.called = True

            class Ret:
                def is_empty(self):
                    return False

            return Ret()

        image_descriptions.called = False
        mock_image_descriptions = self.patch(
            bootresources, "download_all_image_descriptions"
        )
        mock_image_descriptions.side_effect = image_descriptions
        descriptions = Mock()
        descriptions.is_empty.return_value = False
        image_descriptions.return_value = descriptions
        map_products = self.patch(bootresources, "map_products")
        map_products.return_value = sentinel.mapping
        self.patch(bootresources, "download_all_boot_resources")
        self.patch(bootresources, "set_global_default_releases")

        bootresources._import_resources()

        # write_all_keyrings is called once per
        self.assertEqual(2, mock_write_all_keyrings.call_count)


class TestImportResourcesInThread(MAASTestCase):
    """Tests for `_import_resources_in_thread`."""

    def test_defers__import_resources_to_thread(self):
        deferToDatabase = self.patch(bootresources, "deferToDatabase")
        bootresources._import_resources_in_thread()
        deferToDatabase.assert_called_once_with(
            bootresources._import_resources, notify=None
        )

    def tests__defaults_force_to_False(self):
        deferToDatabase = self.patch(bootresources, "deferToDatabase")
        bootresources._import_resources_in_thread()
        deferToDatabase.assert_called_once_with(
            bootresources._import_resources, notify=None
        )

    def test_logs_errors_and_does_not_errback(self):
        logger = self.useFixture(TwistedLoggerFixture())
        exception_type = factory.make_exception_type()
        deferToDatabase = self.patch(bootresources, "deferToDatabase")
        deferToDatabase.return_value = fail(exception_type())
        d = bootresources._import_resources_in_thread()
        self.assertIsNone(extract_result(d))
        self.assertIn(
            (
                "Importing boot resources failed.\n"
                "Traceback (most recent call last):"
            ),
            logger.output,
        )

    def test_logs_subprocess_output_on_error(self):
        logger = self.useFixture(TwistedLoggerFixture())
        cmd = factory.make_name("command")
        output = factory.make_name("output")
        exception = CalledProcessError(2, [cmd], output)
        deferToDatabase = self.patch(bootresources, "deferToDatabase")
        deferToDatabase.return_value = fail(exception)
        d = bootresources._import_resources_in_thread()
        self.assertIsNone(extract_result(d))
        self.assertEqual(
            [
                "Importing boot resources failed.",
                "Traceback (most recent call last):",
                f"Failure: subprocess.CalledProcessError: Command `{cmd}` returned non-zero exit status 2:",
                output,
            ],
            logger.output.splitlines(),
        )


class TestStopImportResources(MAASTransactionServerTestCase):
    def make_listener_without_delay(self):
        listener = PostgresListenerService()
        self.patch(listener, "HANDLE_NOTIFY_DELAY", 0)
        return listener

    @wait_for_reactor
    @inlineCallbacks
    def test_does_nothing_if_import_not_running(self):
        mock_defer = self.patch(bootresources, "deferToDatabase")
        mock_defer.return_value = succeed(False)
        yield bootresources.stop_import_resources()
        mock_defer.assert_called_once()

    @wait_for_reactor
    @inlineCallbacks
    def test_sends_stop_import_notification(self):
        mock_running = self.patch(bootresources, "is_import_resources_running")
        mock_running.side_effect = [True, True, False]
        dv = DeferredValue()
        listener = self.make_listener_without_delay()
        listener.register("sys_stop_import", lambda *args: dv.set(args))
        yield listener.startService()
        try:
            yield bootresources.stop_import_resources()
            yield dv.get(2)
        finally:
            yield listener.stopService()


class TestImportResourcesService(MAASTestCase):
    """Tests for `ImportResourcesService`."""

    def test_is_a_TimerService(self):
        service = bootresources.ImportResourcesService()
        self.assertIsInstance(service, TimerService)

    def test_runs_once_an_hour(self):
        service = bootresources.ImportResourcesService()
        self.assertEqual(3600, service.step)

    def test_calls__maybe_import_resources(self):
        service = bootresources.ImportResourcesService()
        self.assertEqual(
            (service.maybe_import_resources, (), {}), service.call
        )

    def test_maybe_import_resources_does_not_error(self):
        service = bootresources.ImportResourcesService()
        deferToDatabase = self.patch(bootresources, "deferToDatabase")
        exception_type = factory.make_exception_type()
        deferToDatabase.return_value = fail(exception_type())
        d = service.maybe_import_resources()
        self.assertIsNone(extract_result(d))


class TestImportResourcesServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `ImportResourcesService`."""

    def test_imports_resources_in_thread_if_auto(self):
        self.patch(bootresources, "_import_resources_in_thread")
        self.patch(bootresources, "is_dev_environment").return_value = False

        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", True)

        service = bootresources.ImportResourcesService()
        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        bootresources._import_resources_in_thread.assert_called_once()

    def test_no_auto_import_if_dev(self):
        self.patch(bootresources, "_import_resources_in_thread")

        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", True)

        service = bootresources.ImportResourcesService()
        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        bootresources._import_resources_in_thread.assert_not_called()

    def test_does_not_import_resources_in_thread_if_not_auto(self):
        self.patch(bootresources, "_import_resources_in_thread")

        with transaction.atomic():
            Config.objects.set_config("boot_images_auto_import", False)

        service = bootresources.ImportResourcesService()
        maybe_import_resources = asynchronous(service.maybe_import_resources)
        maybe_import_resources().wait(TIMEOUT)

        bootresources._import_resources_in_thread.assert_not_called()


class TestImportResourcesProgressService(MAASServerTestCase):
    """Tests for `ImportResourcesProgressService`."""

    def test_is_a_TimerService(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertIsInstance(service, TimerService)

    def test_runs_every_three_minutes(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertEqual(180, service.step)

    def test_calls_try_check_boot_images(self):
        service = bootresources.ImportResourcesProgressService()
        func, args, kwargs = service.call
        self.assertEqual(func, service.try_check_boot_images)
        self.assertEqual(args, ())
        self.assertEqual(kwargs, {})


class TestImportResourcesProgressServiceAsync(MAASTransactionServerTestCase):
    """Tests for the async parts of `ImportResourcesProgressService`."""

    def set_maas_url(self):
        maas_url_path = "/path/%s" % factory.make_string()
        maas_url = factory.make_simple_http_url(path=maas_url_path)
        self.useFixture(RegionConfigurationFixture(maas_url=maas_url))
        return maas_url, maas_url_path

    def patch_are_functions(self, service, region_answer):
        # Patch the are_boot_images_available_* functions.
        are_region_func = self.patch_autospec(
            service, "are_boot_images_available_in_the_region"
        )
        are_region_func.return_value = region_answer

    def test_adds_warning_if_boot_image_import_not_started(self):
        maas_url, maas_url_path = self.set_maas_url()

        service = bootresources.ImportResourcesProgressService()
        self.patch_are_functions(service, False)

        check_boot_images = asynchronous(service.check_boot_images)
        check_boot_images().wait(TIMEOUT)

        error_observed = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        error_expected = """\
        Boot image import process not started. Machines will not be able to
        provision without boot images. Visit the <a href="%s">boot images</a>
        page to start the import.
        """
        images_link = maas_url + urljoin(maas_url_path, "/r/images")
        self.assertEqual(
            normalise_whitespace(error_expected % images_link),
            normalise_whitespace(error_observed),
        )

    def test_removes_warning_if_boot_image_process_started(self):
        register_persistent_error(
            COMPONENT.IMPORT_PXE_FILES,
            "You rotten swine, you! You have deaded me!",
        )

        service = bootresources.ImportResourcesProgressService()
        self.patch_are_functions(service, True)

        check_boot_images = asynchronous(service.check_boot_images)
        check_boot_images().wait(TIMEOUT)

        error = get_persistent_error(COMPONENT.IMPORT_PXE_FILES)
        self.assertIsNone(error)

    def test_logs_all_errors(self):
        logger = self.useFixture(TwistedLoggerFixture())

        exception = factory.make_exception()
        service = bootresources.ImportResourcesProgressService()
        check_boot_images = self.patch_autospec(service, "check_boot_images")
        check_boot_images.return_value = fail(exception)
        try_check_boot_images = asynchronous(service.try_check_boot_images)
        try_check_boot_images().wait(TIMEOUT)

        self.assertEqual(
            [
                "Failure checking for boot images.",
                "Traceback (most recent call last):",
                f"Failure: maastesting.factory.{type(exception).__name__}: ",
            ],
            logger.output.splitlines(),
        )

    def test_are_boot_images_available_in_the_region(self):
        service = bootresources.ImportResourcesProgressService()
        self.assertFalse(service.are_boot_images_available_in_the_region())
        factory.make_BootResource()
        self.assertTrue(service.are_boot_images_available_in_the_region())


class TestBootResourceRepoWriter(MAASServerTestCase):
    """Tests for `BootResourceRepoWriter`."""

    def create_ubuntu_simplestream(
        self, ftypes, stream_version=None, osystem=None, maas_supported=None
    ):
        version = "16.04"
        arch = "amd64"
        subarch = "hwe-x"
        if osystem is None:
            osystem = "ubuntu"
        if stream_version is None and osystem == "ubuntu-core":
            stream_version = "v4"
        elif stream_version is None:
            stream_version = random.choice(["v2", "v3"])
        if maas_supported is None:
            maas_supported = __version__
        product = "com.ubuntu.maas.daily:{}:boot:{}:{}:{}".format(
            stream_version,
            version,
            arch,
            subarch,
        )
        version = datetime.now().date().strftime("%Y%m%d.0")
        versions = {
            version: {
                "items": {
                    ftype: {
                        "sha256": factory.make_name("sha256"),
                        "path": factory.make_name("path"),
                        "ftype": ftype,
                        "size": random.randint(0, 2**64),
                    }
                    for ftype in ftypes
                }
            }
        }
        products = {
            product: {
                "subarch": subarch,
                "label": "daily",
                "os": osystem,
                "arch": arch,
                "subarches": "generic,%s" % subarch,
                "kflavor": "generic",
                "version": version,
                "versions": versions,
                "maas_supported": maas_supported,
            }
        }
        src = {
            "datatype": "image-downloads",
            "format": "products:1.0",
            "updated": format_datetime(datetime.now()),
            "products": products,
            "content_id": "com.ubuntu.maas:daily:v2:download",
        }
        return src, product, version

    def test_insert_validates_maas_supported_if_available(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ], maas_supported="999.999"
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_not_called()

    def test_insert_prefers_squashfs_over_root_image(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [
                BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
                BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
            ]
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_not_called()

    def test_insert_allows_squashfs(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE]
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_called_once()

    def test_insert_allows_root_image(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE]
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_called_once()

    def test_insert_allows_archive_tar_xz(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ]
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.ARCHIVE_TAR_XZ)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_called_once()

    def test_insert_ignores_unknown_ftypes(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        unknown_ftype = factory.make_name("ftype")
        src, product, version = self.create_ubuntu_simplestream(
            [unknown_ftype]
        )
        data = src["products"][product]["versions"][version]["items"][
            unknown_ftype
        ]
        pedigree = (product, version, unknown_ftype)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_not_called()

    def test_insert_validates_ubuntu(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE]
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_called_once()

    def test_validate_ubuntu_rejects_unknown_version(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE],
            factory.make_name("stream_version"),
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_not_called()

    def test_validates_ubuntu_core(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ], osystem="ubuntu-core"
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_called_once()

    def test_validates_ubuntu_core_rejects_unknown_version(self):
        boot_resource_repo_writer = BootResourceRepoWriter(
            BootResourceStore(), None
        )
        src, product, version = self.create_ubuntu_simplestream(
            [BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ],
            factory.make_name("stream_version"),
            "ubuntu-core",
        )
        data = src["products"][product]["versions"][version]["items"][
            BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ
        ]
        pedigree = (product, version, BOOT_RESOURCE_FILE_TYPE.ROOT_DDXZ)
        mock_insert = self.patch(boot_resource_repo_writer.store, "insert")
        boot_resource_repo_writer.insert_item(data, src, None, pedigree, None)
        mock_insert.assert_not_called()
