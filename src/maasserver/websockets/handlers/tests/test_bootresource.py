# Copyright 2016-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import datetime
import random
from unittest.mock import ANY

from testtools.matchers import ContainsAll, HasLength
from twisted.internet import reactor
from twisted.internet.defer import succeed

from maasserver.enum import BOOT_RESOURCE_TYPE, NODE_STATUS
from maasserver.models import BootResource, BootSourceSelection, Config
from maasserver.models.signals import bootsources
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_objects
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils import get_maas_user_agent
from maasserver.utils.converters import human_readable_bytes
from maasserver.utils.orm import get_one, reload_object
from maasserver.websockets.base import HandlerError, HandlerValidationError
from maasserver.websockets.handlers import bootresource
from maasserver.websockets.handlers.bootresource import BootResourceHandler
from maastesting.matchers import MockCalledOnce, MockCalledOnceWith
from provisioningserver.config import DEFAULT_IMAGES_URL, DEFAULT_KEYRINGS_PATH
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
)
from provisioningserver.import_images.testing.factory import (
    make_image_spec,
    set_resource,
)


class PatchOSInfoMixin:
    def patch_get_os_info_from_boot_sources(
        self, sources, releases=None, arches=None
    ):
        if releases is None:
            releases = [factory.make_name("release") for _ in range(3)]
        if arches is None:
            arches = [factory.make_name("arch") for _ in range(3)]
        mock_get_os_info = self.patch(
            bootresource, "get_os_info_from_boot_sources"
        )
        mock_get_os_info.return_value = (sources, releases, arches)
        return mock_get_os_info


class TestBootResourcePoll(MAASServerTestCase, PatchOSInfoMixin):
    def make_other_resource(
        self, os=None, arch=None, subarch=None, release=None, extra=None
    ):
        if os is None:
            os = factory.make_name("os")
        if arch is None:
            arch = factory.make_name("arch")
        if subarch is None:
            subarch = factory.make_name("subarch")
        if release is None:
            release = factory.make_name("release")
        name = f"{os}/{release}"
        architecture = f"{arch}/{subarch}"
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
            extra=extra,
        )
        resource_set = factory.make_BootResourceSet(resource)
        factory.make_boot_resource_file_with_content(resource_set)
        return resource

    def test_returns_connection_error_True(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        mock_get_os_info = self.patch(
            bootresource, "get_os_info_from_boot_sources"
        )
        mock_get_os_info.side_effect = ConnectionError()
        response = handler.poll({})
        self.assertTrue(response["connection_error"])

    def test_returns_connection_error_False(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        response = handler.poll({})
        self.assertFalse(response["connection_error"])

    def test_returns_no_ubuntu_sources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        response = handler.poll({})
        self.assertEqual([], response["ubuntu"]["sources"])

    def test_returns_ubuntu_sources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        sources = [factory.make_BootSource() for _ in range(2)]
        self.patch_get_os_info_from_boot_sources(sources)
        response = handler.poll({})
        self.assertEqual(
            [
                {
                    "source_type": "custom",
                    "url": source.url,
                    "keyring_filename": source.keyring_filename,
                    "keyring_data": source.keyring_data.decode("ascii"),
                }
                for source in sources
            ],
            response["ubuntu"]["sources"],
        )

    def test_returns_maas_io_source(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource(
            url=DEFAULT_IMAGES_URL, keyring_filename=DEFAULT_KEYRINGS_PATH
        )
        self.patch_get_os_info_from_boot_sources([source])
        response = handler.poll({})
        self.assertEqual(
            [
                {
                    "source_type": "maas.io",
                    "url": source.url,
                    "keyring_filename": source.keyring_filename,
                    "keyring_data": "",
                }
            ],
            response["ubuntu"]["sources"],
        )

    def test_shows_ubuntu_release_options(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        sources = [factory.make_BootSource()]
        releases = ["20.04"] + [factory.make_name("release") for _ in range(3)]
        self.patch_get_os_info_from_boot_sources(sources, releases=releases)
        response = handler.poll({})
        self.assertCountEqual(
            [
                {
                    "name": release,
                    "title": release,
                    "unsupported_arches": (
                        ["i386"] if release == "20.04" else []
                    ),
                    "checked": False,
                    "deleted": False,
                }
                for release in releases
            ],
            response["ubuntu"]["releases"],
        )

    def test_shows_ubuntu_selected_and_deleted_release_options(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        sources = [factory.make_BootSource()]
        releases = [factory.make_name("release") for _ in range(3)]
        selected_release = releases.pop()
        factory.make_BootSourceSelection(
            boot_source=sources[0],
            os="ubuntu",
            release=selected_release,
            arches=["*"],
            subarches=["*"],
            labels=["*"],
        )
        self.patch_get_os_info_from_boot_sources(sources, releases=releases)
        response = handler.poll({})
        self.assertCountEqual(
            [
                {
                    "name": release,
                    "title": release,
                    "unsupported_arches": [],
                    "checked": False,
                    "deleted": False,
                }
                for release in releases
            ]
            + [
                {
                    "name": selected_release,
                    "title": selected_release,
                    "unsupported_arches": [],
                    "checked": True,
                    "deleted": True,
                }
            ],
            response["ubuntu"]["releases"],
        )

    def test_shows_ubuntu_architecture_options(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        sources = [factory.make_BootSource()]
        arches = [factory.make_name("arch") for _ in range(3)]
        self.patch_get_os_info_from_boot_sources(sources, arches=arches)
        response = handler.poll({})
        self.assertCountEqual(
            [
                {
                    "name": arch,
                    "title": arch,
                    "checked": False,
                    "deleted": False,
                }
                for arch in arches
            ],
            response["ubuntu"]["arches"],
        )

    def test_shows_ubuntu_select_and_deleted_architecture_options(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        sources = [factory.make_BootSource()]
        arches = [factory.make_name("arch") for _ in range(3)]
        selected_arch = arches.pop()
        factory.make_BootSourceSelection(
            boot_source=sources[0],
            os="ubuntu",
            release=["*"],
            arches=[selected_arch],
            subarches=["*"],
            labels=["*"],
        )
        self.patch_get_os_info_from_boot_sources(sources, arches=arches)
        response = handler.poll({})
        self.assertCountEqual(
            [
                {
                    "name": arch,
                    "title": arch,
                    "checked": False,
                    "deleted": False,
                }
                for arch in arches
            ]
            + [
                {
                    "name": selected_arch,
                    "title": selected_arch,
                    "checked": True,
                    "deleted": True,
                }
            ],
            response["ubuntu"]["arches"],
        )

    def test_shows_ubuntu_commissioning_release(self):
        commissioning_series, _ = Config.objects.get_or_create(
            name="commissioning_distro_series"
        )
        commissioning_series.value = factory.make_name("commissioning_series")
        commissioning_series.save()
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        response = handler.poll({})
        self.assertEqual(
            commissioning_series.value,
            response["ubuntu"]["commissioning_series"],
        )

    def test_returns_region_import_running_True(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(
            bootresource, "is_import_resources_running"
        ).return_value = True
        response = handler.poll({})
        self.assertTrue(response["region_import_running"])

    def test_returns_region_import_running_False(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(
            bootresource, "is_import_resources_running"
        ).return_value = False
        response = handler.poll({})
        self.assertFalse(response["region_import_running"])

    def test_returns_rack_import_running_True(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(
            bootresource, "is_import_boot_images_running"
        ).return_value = True
        response = handler.poll({})
        self.assertTrue(response["rack_import_running"])

    def test_returns_rack_import_running_False(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(
            bootresource, "is_import_boot_images_running"
        ).return_value = False
        response = handler.poll({})
        self.assertFalse(response["rack_import_running"])

    def test_returns_resources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resources = [factory.make_usable_boot_resource() for _ in range(3)]
        resource_ids = [resource.id for resource in resources]
        response = handler.poll({})
        ids = [resource["id"] for resource in response["resources"]]
        self.assertCountEqual(resource_ids, ids)

    def test_returns_resources_datetime_format(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource()
        resource_updated = handler.get_last_update_for_resources([resource])
        response = handler.poll({})
        updated = datetime.datetime.strptime(
            response["resources"][0]["lastUpdate"], "%a, %d %b. %Y %H:%M:%S"
        )
        self.assertEqual(resource_updated.timetuple(), updated.timetuple())

    def test_returns_resource_attributes(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        factory.make_usable_boot_resource()
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertThat(
            resource,
            ContainsAll(
                [
                    "id",
                    "rtype",
                    "name",
                    "title",
                    "arch",
                    "size",
                    "complete",
                    "status",
                    "icon",
                    "downloading",
                    "numberOfNodes",
                    "lastUpdate",
                ]
            ),
        )

    def test_returns_ubuntu_release_version_name(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        # Use trusty as known to map to "14.04 LTS"
        version = "14.04 LTS"
        name = "ubuntu/trusty"
        factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name
        )
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(version, resource["title"])

    def test_shows_last_deployment_time(self) -> None:
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        os_name, series = resource.name.split("/")
        # The polled datetime only has granularity of order seconds
        start_time = datetime.datetime.now().replace(microsecond=0)
        architecture = BootResource.objects.get_usable_architectures()[0]
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            osystem=os_name,
            distro_series=series,
            architecture=architecture,
        )
        node.end_deployment()
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertIn("lastDeployed", resource)
        self.assertGreaterEqual(
            datetime.datetime.strptime(
                resource["lastDeployed"], "%a, %d %b. %Y %H:%M:%S"
            ),
            start_time,
        )

    def test_shows_latest_deployment_time(self) -> None:
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        os_name, series = resource.name.split("/")
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            osystem=os_name,
            distro_series=series,
            architecture=resource.architecture,
        )
        node.end_deployment()
        start_time = datetime.datetime.now().replace(microsecond=0)
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYED,
            osystem=os_name,
            distro_series=series,
            architecture=resource.architecture,
        )
        node.end_deployment()
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertGreaterEqual(
            datetime.datetime.strptime(
                resource["lastDeployed"], "%a, %d %b. %Y %H:%M:%S"
            ),
            start_time,
        )

    def test_shows_number_of_machines_deployed_at_current(self) -> None:
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        os_name, series = resource.name.split("/")
        node = factory.make_Machine(
            status=NODE_STATUS.DEPLOYED,
            osystem=os_name,
            distro_series=series,
            architecture=resource.architecture,
        )
        factory.make_Node(
            status=NODE_STATUS.DEPLOYED, architecture=resource.architecture
        )
        factory.make_RegionController(
            status=NODE_STATUS.DEPLOYED,
        )
        response = handler.poll({})
        self.assertEqual(1, response["resources"][0]["machineCount"])
        node.delete()

        response = handler.poll({})
        self.assertEqual(0, response["resources"][0]["machineCount"])

    def test_shows_number_of_nodes_deployed_for_resource(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        os_name, series = resource.name.split("/")
        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED,
                osystem=os_name,
                distro_series=series,
                architecture=resource.architecture,
            )
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(number_of_nodes, resource["numberOfNodes"])

    def test_shows_number_of_nodes_deployed_for_resource_with_defaults(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        os_name, series = resource.name.split("/")
        Config.objects.set_config("default_osystem", os_name)
        Config.objects.set_config("default_distro_series", series)
        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED, architecture=resource.architecture
            )
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(number_of_nodes, resource["numberOfNodes"])

    def test_shows_number_of_nodes_deployed_for_ubuntu_subarch_resource(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED
        )
        arch, subarch = resource.split_arch()
        extra_subarch = factory.make_name("subarch")
        extra = resource.extra.copy()
        extra["subarches"] = ",".join([subarch, extra_subarch])
        resource.extra = extra
        resource.save()

        os_name, series = resource.name.split("/")
        node_architecture = f"{arch}/{extra_subarch}"
        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED,
                osystem=os_name,
                distro_series=series,
                architecture=node_architecture,
            )
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(number_of_nodes, resource["numberOfNodes"])

    def test_combines_subarch_resources_into_one_resource(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        for subarch in subarches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
        response = handler.poll({})
        self.assertEqual(
            1,
            len(response["resources"]),
            "More than one resource was returned.",
        )

    def test_combined_subarch_resource_calculates_unique_size(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        largefile = factory.make_LargeFile()
        for subarch in subarches:
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
            resource_set = factory.make_BootResourceSet(resource)
            factory.make_BootResourceFile(resource_set, largefile)
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(
            human_readable_bytes(largefile.total_size), resource["size"]
        )

    def test_combined_subarch_resource_calculates_num_of_nodes_deployed(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        osystem = "ubuntu"
        series = factory.make_name("series")
        name = f"{osystem}/{series}"
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        for subarch in subarches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )

        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            subarch = random.choice(subarches)
            node_architecture = f"{arch}/{subarch}"
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED,
                osystem=osystem,
                distro_series=series,
                architecture=node_architecture,
            )

        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(number_of_nodes, resource["numberOfNodes"])

    def test_combined_subarch_resource_calculates_complete_True(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        resources = [
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
            for subarch in subarches
        ]
        self.patch(
            BootResource.objects, "get_resources_matching_boot_images"
        ).return_value = resources
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertTrue(resource["complete"])

    def test_combined_subarch_resource_calculates_complete_False(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        incomplete_subarch = subarches.pop()
        factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=f"{arch}/{incomplete_subarch}",
        )
        for subarch in subarches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertFalse(resource["complete"])

    def test_combined_subarch_resource_calculates_progress(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        largefile = factory.make_LargeFile()
        largefile.total_size = largefile.total_size * 2
        largefile.save()
        for subarch in subarches:
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
            resource_set = factory.make_BootResourceSet(resource)
            factory.make_BootResourceFile(resource_set, largefile)
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual("Downloading  50%", resource["status"])
        self.assertEqual("in-progress", resource["icon"])

    def test_combined_subarch_resource_shows_queued_if_no_progress(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        largefile = factory.make_LargeFile(content=b"", size=1000)
        for subarch in subarches:
            resource = factory.make_BootResource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
            resource_set = factory.make_BootResourceSet(resource)
            factory.make_BootResourceFile(resource_set, largefile)
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual("Queued for download", resource["status"])
        self.assertEqual("queued", resource["icon"])

    def test_combined_subarch_resource_shows_complete_status(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        resources = [
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
            for subarch in subarches
        ]
        self.patch(
            BootResource.objects, "get_resources_matching_boot_images"
        ).return_value = resources
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual("Synced", resource["status"])
        self.assertEqual("succeeded", resource["icon"])

    def test_combined_subarch_resource_shows_waiting_for_cluster_to_sync(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        for subarch in subarches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
        self.patch(
            BootResource.objects, "get_resources_matching_boot_images"
        ).return_value = []
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual(
            "Waiting for rack controller(s) to sync", resource["status"]
        )
        self.assertEqual("waiting", resource["icon"])

    def test_combined_subarch_resource_shows_clusters_syncing(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = "ubuntu/%s" % factory.make_name("series")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        for subarch in subarches:
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=name,
                architecture=f"{arch}/{subarch}",
            )
        self.patch(
            BootResource.objects, "get_resources_matching_boot_images"
        ).return_value = []
        self.patch(
            bootresource, "is_import_boot_images_running"
        ).return_value = True
        response = handler.poll({})
        resource = response["resources"][0]
        self.assertEqual("Syncing to rack controller(s)", resource["status"])
        self.assertEqual("in-progress", resource["icon"])

    def test_ubuntu_core_images_returns_images_from_cache(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        cache = factory.make_BootSourceCache(os="ubuntu-core")
        response = handler.poll({})
        ubuntu_core_images = response["ubuntu_core_images"]
        self.assertEqual(
            [
                {
                    "name": "%s/%s/%s/%s"
                    % (cache.os, cache.arch, cache.subarch, cache.release),
                    "title": cache.release,
                    "checked": False,
                    "deleted": False,
                }
            ],
            ubuntu_core_images,
        )

    def test_ubuntu_core_images_returns_image_checked_when_synced(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        cache = factory.make_BootSourceCache(os="ubuntu-core")
        self.make_other_resource(
            os=cache.os,
            arch=cache.arch,
            subarch=cache.subarch,
            release=cache.release,
        )
        response = handler.poll({})
        ubuntu_core_images = response["ubuntu_core_images"]
        self.assertEqual(
            [
                {
                    "name": "%s/%s/%s/%s"
                    % (cache.os, cache.arch, cache.subarch, cache.release),
                    "title": cache.release,
                    "checked": True,
                    "deleted": False,
                }
            ],
            ubuntu_core_images,
        )

    def test_other_images_returns_images_from_cache(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        cache = factory.make_BootSourceCache()
        response = handler.poll({})
        other_images = response["other_images"]
        self.assertEqual(
            [
                {
                    "name": "%s/%s/%s/%s"
                    % (cache.os, cache.arch, cache.subarch, cache.release),
                    "title": f"{cache.os}/{cache.release}",
                    "checked": False,
                    "deleted": False,
                }
            ],
            other_images,
        )

    def test_other_images_returns_image_checked_when_synced(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        cache = factory.make_BootSourceCache()
        self.make_other_resource(
            os=cache.os,
            arch=cache.arch,
            subarch=cache.subarch,
            release=cache.release,
        )
        response = handler.poll({})
        other_images = response["other_images"]
        self.assertEqual(
            [
                {
                    "name": "%s/%s/%s/%s"
                    % (cache.os, cache.arch, cache.subarch, cache.release),
                    "title": f"{cache.os}/{cache.release}",
                    "checked": True,
                    "deleted": False,
                }
            ],
            other_images,
        )

    def test_other_images_filters_out_ubuntu(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        factory.make_BootSourceCache(os="ubuntu")
        factory.make_BootSourceCache(os="ubuntu-core")
        response = handler.poll({})
        self.assertEqual([], response["other_images"])

    def test_other_images_filters_out_bootloaders(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        factory.make_BootSourceCache(
            bootloader_type=factory.make_name("bootloader-type")
        )
        response = handler.poll({})
        self.assertEqual([], response["other_images"])

    def test_prefers_title_from_boot_resource_extra(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        title = factory.make_name("title")
        self.make_other_resource(extra={"title": title})
        response = handler.poll({})
        self.assertEqual(title, response["resources"][0]["title"])


class TestBootResourceStopImport(MAASTransactionServerTestCase):
    def patch_stop_import_resources(self):
        mock_import = self.patch(bootresource, "stop_import_resources")
        mock_import.return_value = succeed(None)
        return mock_import

    def test_calls_stop_import_and_returns_poll(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        mock_stop_import = self.patch_stop_import_resources()
        result = handler.stop_import({})
        self.assertThat(mock_stop_import, MockCalledOnceWith())
        self.assertEqual(handler.poll({}), result)


class TestBootResourceSaveUbuntu(
    MAASTransactionServerTestCase, PatchOSInfoMixin
):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def patch_stop_import_resources(self):
        mock_import = self.patch(bootresource, "stop_import_resources")
        mock_import.return_value = succeed(None)
        return mock_import

    def patch_import_resources(self):
        mock_import = self.patch(bootresource, "import_resources")
        mock_import.side_effect = lambda notify: reactor.callLater(
            0, notify.callback, None
        )
        return mock_import

    def test_asserts_is_admin(self):
        owner = factory.make_User()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(AssertionError, handler.save_ubuntu, {})

    def test_calls_stop_and_import_resources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        sources = [factory.make_BootSource()]
        self.patch_get_os_info_from_boot_sources(sources)
        mock_stop_import = self.patch_stop_import_resources()
        mock_import = self.patch_import_resources()
        handler.save_ubuntu(
            {"url": sources[0].url, "releases": [], "arches": []}
        )
        self.assertThat(mock_stop_import, MockCalledOnceWith())
        self.assertThat(mock_import, MockCalledOnceWith(notify=ANY))

    def test_sets_release_selections(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        releases = [factory.make_name("release") for _ in range(3)]
        self.patch_get_os_info_from_boot_sources([source])
        self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_ubuntu(
            {
                "url": source.url,
                "osystems": [
                    {"osystem": "ubuntu", "release": release, "arches": []}
                    for release in releases
                ],
            }
        )

        selections = BootSourceSelection.objects.filter(boot_source=source)
        self.assertThat(selections, HasLength(len(releases)))
        self.assertCountEqual(
            releases, [selection.release for selection in selections]
        )

    def test_sets_arches_on_selections(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        osystems = [
            {
                "osystem": "ubuntu",
                "release": factory.make_name("release"),
                "arches": [factory.make_name("arch") for _ in range(i + 1)],
            }
            for i in range(3)
        ]
        self.patch_get_os_info_from_boot_sources([source])
        self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_ubuntu({"url": source.url, "osystems": osystems})
        selections = BootSourceSelection.objects.filter(boot_source=source)
        self.assertCountEqual(
            [
                {
                    "osystem": selection.os,
                    "release": selection.release,
                    "arches": selection.arches,
                }
                for selection in selections
            ],
            osystems,
        )

    def test_removes_old_selections(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        release = factory.make_name("release")
        delete_selection = BootSourceSelection.objects.create(
            boot_source=source,
            os="ubuntu",
            release=factory.make_name("release"),
        )
        keep_selection = BootSourceSelection.objects.create(
            boot_source=source, os="ubuntu", release=release
        )
        self.patch_get_os_info_from_boot_sources([source])
        self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_ubuntu(
            {
                "url": source.url,
                "osystems": [
                    {"osystem": "ubuntu", "release": release, "arches": []}
                ],
            }
        )
        self.assertIsNone(reload_object(delete_selection))
        self.assertIsNotNone(reload_object(keep_selection))


class TestBootResourceSaveUbuntuCore(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def make_resource(self, arch="amd64"):
        if arch is None:
            arch = factory.make_name("arch")
        architecture = "%s/generic" % arch
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name="ubuntu-core/16-pc",
            architecture=architecture,
        )
        resource_set = factory.make_BootResourceSet(resource)
        factory.make_boot_resource_file_with_content(resource_set)
        return resource

    def patch_stop_import_resources(self):
        mock_import = self.patch(bootresource, "stop_import_resources")
        mock_import.return_value = succeed(None)
        return mock_import

    def patch_import_resources(self):
        mock_import = self.patch(bootresource, "import_resources")
        mock_import.side_effect = lambda notify: reactor.callLater(
            0, notify.callback, None
        )
        return mock_import

    def test_asserts_is_admin(self):
        owner = factory.make_User()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(AssertionError, handler.save_ubuntu_core, {})

    def test_clears_all_ubuntu_core_selections(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        ubuntu_selection = BootSourceSelection.objects.create(
            boot_source=source, os="ubuntu"
        )
        ubuntu_core_selection = BootSourceSelection.objects.create(
            boot_source=source, os="ubuntu-core"
        )
        self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_ubuntu_core({"images": []})
        self.assertIsNotNone(reload_object(ubuntu_selection))
        self.assertIsNone(reload_object(ubuntu_core_selection))

    def test_creates_selection_with_multiple_arches(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        arches = [factory.make_name("arch") for _ in range(3)]
        images = []
        for arch in arches:
            factory.make_BootSourceCache(
                boot_source=source,
                os="ubuntu-core",
                release="16-pc",
                arch=arch,
            )
            images.append("ubuntu-core/%s/subarch/16-pc" % arch)
            self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_ubuntu_core({"images": images})

        selection = get_one(
            BootSourceSelection.objects.filter(
                boot_source=source, os="ubuntu-core", release="16-pc"
            )
        )
        self.assertIsNotNone(selection)
        self.assertCountEqual(arches, selection.arches)

    def test_calls_stop_and_import_resources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        mock_stop_import = self.patch_stop_import_resources()
        mock_import = self.patch_import_resources()
        handler.save_ubuntu_core({"images": []})
        self.assertThat(mock_stop_import, MockCalledOnceWith())
        self.assertThat(mock_import, MockCalledOnceWith(notify=ANY))


class TestBootResourceSaveOther(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def make_other_resource(
        self, os=None, arch=None, subarch=None, release=None
    ):
        if os is None:
            os = factory.make_name("os")
        if arch is None:
            arch = factory.make_name("arch")
        if subarch is None:
            subarch = factory.make_name("subarch")
        if release is None:
            release = factory.make_name("release")
        name = f"{os}/{release}"
        architecture = f"{arch}/{subarch}"
        resource = factory.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name,
            architecture=architecture,
        )
        resource_set = factory.make_BootResourceSet(resource)
        factory.make_boot_resource_file_with_content(resource_set)
        return resource

    def patch_stop_import_resources(self):
        mock_import = self.patch(bootresource, "stop_import_resources")
        mock_import.return_value = succeed(None)
        return mock_import

    def patch_import_resources(self):
        mock_import = self.patch(bootresource, "import_resources")
        mock_import.side_effect = lambda notify: reactor.callLater(
            0, notify.callback, None
        )
        return mock_import

    def test_asserts_is_admin(self):
        owner = factory.make_User()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(AssertionError, handler.save_other, {})

    def test_clears_all_other_os_selections(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        ubuntu_selection = BootSourceSelection.objects.create(
            boot_source=source, os="ubuntu"
        )
        other_selection = BootSourceSelection.objects.create(
            boot_source=source, os=factory.make_name("os")
        )
        self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_other({"images": []})
        self.assertIsNotNone(reload_object(ubuntu_selection))
        self.assertIsNone(reload_object(other_selection))

    def test_creates_selection_with_multiple_arches(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        source = factory.make_BootSource()
        os = factory.make_name("os")
        release = factory.make_name("release")
        arches = [factory.make_name("arch") for _ in range(3)]
        images = []
        for arch in arches:
            factory.make_BootSourceCache(
                boot_source=source, os=os, release=release, arch=arch
            )
            images.append(f"{os}/{arch}/subarch/{release}")
            self.patch_stop_import_resources()
        self.patch_import_resources()
        handler.save_other({"images": images})

        selection = get_one(
            BootSourceSelection.objects.filter(
                boot_source=source, os=os, release=release
            )
        )
        self.assertIsNotNone(selection)
        self.assertCountEqual(arches, selection.arches)

    def test_calls_stop_and_import_resources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        mock_stop_import = self.patch_stop_import_resources()
        mock_import = self.patch_import_resources()
        handler.save_other({"images": []})
        self.assertThat(mock_stop_import, MockCalledOnceWith())
        self.assertThat(mock_import, MockCalledOnceWith(notify=ANY))


class TestBootResourceFetch(MAASServerTestCase):
    def test_asserts_is_admin(self):
        owner = factory.make_User()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(AssertionError, handler.fetch, {})

    def test_makes_correct_calls_for_downloading_resources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        mock_set_env = self.patch(bootresource, "set_simplestreams_env")
        mock_write_keyrings = self.patch(bootresource, "write_all_keyrings")
        mock_write_keyrings.side_effect = lambda _, sources: sources
        mock_download = self.patch(
            bootresource, "download_all_image_descriptions"
        )
        mock_download.return_value = BootImageMapping()
        url = factory.make_url(scheme=random.choice(["http", "https"]))
        keyring_data = factory.make_string()
        expected_source = {
            "url": url,
            "keyring_data": keyring_data.encode("utf-8"),
            "selections": [],
        }
        error = self.assertRaises(
            HandlerError,
            handler.fetch,
            {"url": url, "keyring_data": keyring_data},
        )
        self.assertEqual("Mirror provides no Ubuntu images.", str(error))
        self.assertThat(mock_set_env, MockCalledOnce())
        self.assertThat(
            mock_write_keyrings, MockCalledOnceWith(ANY, [expected_source])
        )
        self.assertThat(
            mock_download,
            MockCalledOnceWith(
                [expected_source], user_agent=get_maas_user_agent()
            ),
        )

    def test_raises_error_on_downloading_resources(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(bootresource, "set_simplestreams_env")
        mock_write_keyrings = self.patch(bootresource, "write_all_keyrings")
        mock_write_keyrings.side_effect = lambda _, sources: sources
        mock_download = self.patch(
            bootresource, "download_all_image_descriptions"
        )
        exc = factory.make_exception()
        mock_download.side_effect = exc
        url = factory.make_url(scheme=random.choice(["http", "https"]))
        keyring_data = factory.make_string()
        error = self.assertRaises(
            HandlerError,
            handler.fetch,
            {"url": url, "keyring_data": keyring_data},
        )
        self.assertEqual(str(exc), str(error))

    def test_raises_error_on_node_ubuntu_images(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(bootresource, "set_simplestreams_env")
        mock_write_keyrings = self.patch(bootresource, "write_all_keyrings")
        mock_write_keyrings.side_effect = lambda _, sources: sources
        mock_download = self.patch(
            bootresource, "download_all_image_descriptions"
        )

        # Only centos image is present.
        mapping = BootImageMapping()
        not_ubuntu = make_image_spec(os="centos")
        set_resource(mapping, not_ubuntu)

        mock_download.return_value = mapping
        url = factory.make_url(scheme=random.choice(["http", "https"]))
        keyring_data = factory.make_string()
        error = self.assertRaises(
            HandlerError,
            handler.fetch,
            {"url": url, "keyring_data": keyring_data},
        )
        self.assertEqual("Mirror provides no Ubuntu images.", str(error))

    def test_raises_error_on_invalid_field(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(
            HandlerValidationError,
            handler.fetch,
            {
                "url": factory.make_string(),
                "keyring_data": factory.make_string(),
            },
        )

    def test_returns_releases_and_arches(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(bootresource, "set_simplestreams_env")
        mock_write_keyrings = self.patch(bootresource, "write_all_keyrings")
        mock_write_keyrings.side_effect = lambda _, sources: sources
        mock_download = self.patch(
            bootresource, "download_all_image_descriptions"
        )

        # Make releases and arches.
        mapping = BootImageMapping()
        releases = [factory.make_name("release") for _ in range(3)]
        arches = [factory.make_name("arch") for _ in range(3)]
        image_specs = [
            make_image_spec(os="ubuntu", arch=arch, release=release)
            for release, arch in zip(releases, arches)
        ]
        for spec in image_specs:
            set_resource(mapping, spec, {})

        mock_download.return_value = mapping
        url = factory.make_url(scheme=random.choice(["http", "https"]))
        keyring_data = factory.make_string()
        observed = handler.fetch({"url": url, "keyring_data": keyring_data})
        self.assertCountEqual(
            [
                {
                    "name": release,
                    "title": release,
                    "checked": False,
                    "deleted": False,
                }
                for release in releases
            ],
            observed["releases"],
        )
        self.assertCountEqual(
            [
                {
                    "name": arch,
                    "title": arch,
                    "checked": False,
                    "deleted": False,
                }
                for arch in arches
            ],
            observed["arches"],
        )

    def test_title_pulled_from_product(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(bootresource, "set_simplestreams_env")
        mock_write_keyrings = self.patch(bootresource, "write_all_keyrings")
        mock_write_keyrings.side_effect = lambda _, sources: sources
        mock_download = self.patch(
            bootresource, "download_all_image_descriptions"
        )

        # Make releases and arches.
        mapping = BootImageMapping()
        release = factory.make_name("release")
        title = factory.make_name("title")
        arch = factory.make_name("arch")
        spec = make_image_spec(os="ubuntu", arch=arch, release=release)
        set_resource(mapping, spec, {"release_title": title})

        mock_download.return_value = mapping
        url = factory.make_url(scheme=random.choice(["http", "https"]))
        keyring_data = factory.make_string()
        observed = handler.fetch({"url": url, "keyring_data": keyring_data})
        self.assertCountEqual(
            [
                {
                    "name": release,
                    "title": title,
                    "checked": False,
                    "deleted": False,
                }
            ],
            observed["releases"],
        )
        self.assertCountEqual(
            [
                {
                    "name": arch,
                    "title": arch,
                    "checked": False,
                    "deleted": False,
                }
            ],
            observed["arches"],
        )

    def test_title_pulled_from_distro_info(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.patch(bootresource, "set_simplestreams_env")
        mock_write_keyrings = self.patch(bootresource, "write_all_keyrings")
        mock_write_keyrings.side_effect = lambda _, sources: sources
        mock_download = self.patch(
            bootresource, "download_all_image_descriptions"
        )

        # Make releases and arches.
        mapping = BootImageMapping()
        release = "trusty"
        title = "14.04 LTS"  # Known name for 'trusty' in distro_info.
        arch = factory.make_name("arch")
        spec = make_image_spec(os="ubuntu", arch=arch, release=release)
        set_resource(mapping, spec, {})

        mock_download.return_value = mapping
        url = factory.make_url(scheme=random.choice(["http", "https"]))
        keyring_data = factory.make_string()
        observed = handler.fetch({"url": url, "keyring_data": keyring_data})
        self.assertCountEqual(
            [
                {
                    "name": release,
                    "title": title,
                    "checked": False,
                    "deleted": False,
                }
            ],
            observed["releases"],
        )
        self.assertCountEqual(
            [
                {
                    "name": arch,
                    "title": arch,
                    "checked": False,
                    "deleted": False,
                }
            ],
            observed["arches"],
        )


class TestBootResourceDeleteImage(MAASServerTestCase):
    def test_asserts_is_admin(self):
        owner = factory.make_User()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(AssertionError, handler.delete_image, {})

    def test_raises_ValidationError_when_id_missing(self):
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        self.assertRaises(HandlerValidationError, handler.delete_image, {})

    def test_makes_correct_calls_for_downloading_resources(self):
        self.useFixture(SignalsDisabled("bootsources"))
        self.useFixture(SignalsDisabled("largefiles"))
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        os = factory.make_name("os")
        release = factory.make_name("release")
        arch = factory.make_name("arch")
        subarches = [factory.make_name("subarch") for _ in range(3)]
        resources = [
            factory.make_usable_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
                name=f"{os}/{release}",
                architecture=f"{arch}/{subarch}",
            )
            for subarch in subarches
        ]
        selection = factory.make_BootSourceSelection(
            os=os,
            release=release,
            arches=[arch],
            subarches=subarches,
            labels=["*"],
        )
        handler.delete_image({"id": resources[0].id})
        self.assertCountEqual([], reload_objects(BootResource, resources))
        self.assertIsNone(reload_object(selection))

    def test_deletes_uploaded_image(self):
        self.useFixture(SignalsDisabled("bootsources"))
        self.useFixture(SignalsDisabled("largefiles"))
        owner = factory.make_admin()
        handler = BootResourceHandler(owner, {}, None)
        name = factory.make_name("name")
        arch = factory.make_name("arch")
        subarch = factory.make_name("subarch")
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=f"{arch}/{subarch}",
        )
        handler.delete_image({"id": resource.id})
        self.assertIsNone(reload_object(resource))
