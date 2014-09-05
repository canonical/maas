# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Boot Images` API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json

from apiclient.maas_client import MAASClient
from crochet import TimeoutError
from django.conf import settings
from django.core.urlresolvers import reverse
from fixtures import EnvironmentVariableFixture
from maasserver.api import boot_images as boot_images_module
from maasserver.api.boot_images import (
    summarise_boot_image_dict,
    summarise_boot_image_object,
    warn_if_missing_boot_images,
    )
from maasserver.enum import (
    COMPONENT,
    NODEGROUP_STATUS,
    )
from maasserver.models import (
    BootImage,
    NodeGroup,
    )
from maasserver.refresh_worker import refresh_worker
from maasserver.testing.api import (
    APITestCase,
    log_in_as_normal_user,
    make_worker_client,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import absolute_reverse
from maastesting.celery import CeleryFixture
from maastesting.matchers import MockCalledOnceWith
from mock import (
    ANY,
    Mock,
    )
from provisioningserver import (
    boot_images,
    tasks,
    )
from provisioningserver.boot import tftppath
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.testing.boot_images import make_boot_image_params
from testresources import FixtureResource


class TestWarnIfMissingBootImages(MAASServerTestCase):
    """Test `warn_if_missing_boot_images`."""

    def test_warns_if_no_images_found(self):
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        recorder = self.patch(boot_images_module, 'register_persistent_error')
        warn_if_missing_boot_images()
        self.assertIn(
            COMPONENT.IMPORT_PXE_FILES,
            [args[0][0] for args in recorder.call_args_list])
        # The persistent error message links to the clusters listing.
        self.assertIn(
            absolute_reverse("cluster-list"),
            recorder.call_args_list[0][0][1])

    def test_warns_if_any_nodegroup_has_no_images(self):
        factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        recorder = self.patch(boot_images_module, 'register_persistent_error')
        warn_if_missing_boot_images()
        self.assertIn(
            COMPONENT.IMPORT_PXE_FILES,
            [args[0][0] for args in recorder.call_args_list])

    def test_ignores_non_accepted_groups(self):
        factory.make_NodeGroup(status=NODEGROUP_STATUS.PENDING)
        factory.make_NodeGroup(status=NODEGROUP_STATUS.REJECTED)
        recorder = self.patch(boot_images_module, 'register_persistent_error')
        warn_if_missing_boot_images()
        self.assertEqual([], recorder.mock_calls)

    def test_removes_warning_if_images_found(self):
        self.patch(boot_images_module, 'register_persistent_error')
        self.patch(boot_images_module, 'discard_persistent_error')
        factory.make_boot_image(
            nodegroup=factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ACCEPTED))
        warn_if_missing_boot_images()
        self.assertEqual(
            [], boot_images_module.register_persistent_error.mock_calls)
        self.assertThat(
            boot_images_module.discard_persistent_error,
            MockCalledOnceWith(COMPONENT.IMPORT_PXE_FILES))


class TestBootImagesAPI(APITestCase):
    """Test the the boot images API."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/uuid/boot-images/',
            reverse('boot_images_handler', args=['uuid']))

    def make_boot_image(self):
        rpc_image = {
            'osystem': factory.make_name('osystem'),
            'release': factory.make_name('release'),
            'architecture': factory.make_name('arch'),
            'subarchitecture': factory.make_name('subarch'),
            'label': factory.make_name('label'),
            'purpose': factory.make_name('purpose'),
            'xinstall_type': factory.make_name('xi_type'),
            'xinstall_path': factory.make_name('xi_path'),
            }
        api_image = rpc_image.copy()
        del api_image['xinstall_type']
        del api_image['xinstall_path']
        return rpc_image, api_image

    def test_GET_returns_boot_image_list(self):
        nodegroup = factory.make_NodeGroup()
        rpc_images = []
        api_images = []
        for _ in range(3):
            rpc_image, api_image = self.make_boot_image()
            rpc_images.append(rpc_image)
            api_images.append(api_image)
        self.patch(
            boot_images_module, 'get_boot_images').return_value = rpc_images

        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(api_images, parsed_result)

    def test_GET_returns_404_when_invalid_nodegroup(self):
        uuid = factory.make_UUID()
        response = self.client.get(
            reverse('boot_images_handler', args=[uuid]))
        self.assertEqual(
            httplib.NOT_FOUND, response.status_code, response.content)

    def test_GET_returns_503_when_no_connection_avaliable(self):
        nodegroup = factory.make_NodeGroup()
        mock_get_boot_images = self.patch(
            boot_images_module, 'get_boot_images')
        mock_get_boot_images.side_effect = NoConnectionsAvailable

        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(
            httplib.SERVICE_UNAVAILABLE,
            response.status_code, response.content)

    def test_GET_returns_503_when_timeout_error(self):
        nodegroup = factory.make_NodeGroup()
        mock_get_boot_images = self.patch(
            boot_images_module, 'get_boot_images')
        mock_get_boot_images.side_effect = TimeoutError

        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(
            httplib.SERVICE_UNAVAILABLE,
            response.status_code, response.content)


class TestBootImagesReportImagesAPI(APITestCase):
    """Test the method report_boot_images from the boot images API."""

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def report_images(self, nodegroup, images, client=None):
        if client is None:
            client = self.client
        return client.post(
            reverse('boot_images_handler', args=[nodegroup.uuid]), {
                'images': json.dumps(images),
                'op': 'report_boot_images',
                })

    def test_summarise_boot_image_object_returns_tuple(self):
        image = factory.make_boot_image()
        self.assertEqual(
            (
                image.osystem,
                image.architecture,
                image.subarchitecture,
                image.release,
                image.label,
                image.purpose,
                image.supported_subarches,
                image.xinstall_path,
                image.xinstall_type,
            ),
            summarise_boot_image_object(image))

    def test_summarise_boot_image_dict_returns_tuple(self):
        image = make_boot_image_params()
        image['xinstall_path'] = factory.make_name('xi_path')
        image['xinstall_type'] = factory.make_name('xi_type')
        self.assertEqual(
            (
                image['osystem'],
                image['architecture'],
                image['subarchitecture'],
                image['release'],
                image['label'],
                image['purpose'],
                image['supported_subarches'],
                image['xinstall_path'],
                image['xinstall_type'],
            ),
            summarise_boot_image_dict(image))

    def test_summarise_boot_image_dict_substitutes_defaults(self):
        image = make_boot_image_params()
        del image['subarchitecture']
        del image['label']
        del image['supported_subarches']
        (_, _, subarchitecture, _, label, _,
            supported_subarches, xinstall_path,
            xinstall_type) = summarise_boot_image_dict(image)
        self.assertEqual(('generic', 'release'), (subarchitecture, label))
        self.assertEqual((xinstall_path, xinstall_type), (None, None))

    def test_summarise_boot_image_functions_are_compatible(self):
        image_dict = make_boot_image_params()
        image_dict['xinstall_path'] = factory.make_name('xi_path')
        image_dict['xinstall_type'] = factory.make_name('xi_type')
        image_obj = factory.make_boot_image(
            osystem=image_dict['osystem'],
            architecture=image_dict['architecture'],
            subarchitecture=image_dict['subarchitecture'],
            release=image_dict['release'], label=image_dict['label'],
            purpose=image_dict['purpose'],
            supported_subarches=[image_dict['supported_subarches']],
            xinstall_path=image_dict['xinstall_path'],
            xinstall_type=image_dict['xinstall_type'])
        self.assertEqual(
            summarise_boot_image_dict(image_dict),
            summarise_boot_image_object(image_obj))

    def test_report_boot_images_does_not_work_for_normal_user(self):
        nodegroup = NodeGroup.objects.ensure_master()
        log_in_as_normal_user(self.client)
        response = self.report_images(nodegroup, [])
        self.assertEqual(
            httplib.FORBIDDEN, response.status_code, response.content)

    def test_report_boot_images_works_for_master_worker(self):
        nodegroup = NodeGroup.objects.ensure_master()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(httplib.OK, response.status_code)

    def test_report_boot_images_stores_images(self):
        nodegroup = NodeGroup.objects.ensure_master()
        image = make_boot_image_params()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))
        self.assertTrue(
            BootImage.objects.have_image(nodegroup=nodegroup, **image))

    def test_report_boot_images_removes_unreported_images(self):
        deleted_image = factory.make_boot_image()
        nodegroup = deleted_image.nodegroup
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertIsNone(reload_object(deleted_image))

    def test_report_boot_images_pruning_ignores_non_key_field(self):
        image_dict = make_boot_image_params()
        image_dict_copy = image_dict.copy()
        existing_image = factory.make_boot_image(**image_dict_copy)
        image_dict['supported_subarches'] = 'foo'
        nodegroup = existing_image.nodegroup
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image_dict], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))
        self.assertTrue(
            BootImage.objects.have_image(nodegroup=nodegroup, **image_dict))

    def test_report_boot_images_keeps_known_images(self):
        nodegroup = factory.make_NodeGroup()
        image = make_boot_image_params()
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(httplib.OK, response.status_code)
        known_image = BootImage.objects.get(nodegroup=nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertEqual(known_image, reload_object(known_image))

    def test_report_boot_images_ignores_images_for_other_nodegroups(self):
        unrelated_image = factory.make_boot_image()
        deleted_image = factory.make_boot_image()
        nodegroup = deleted_image.nodegroup
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [], client=client)
        self.assertEqual(httplib.OK, response.status_code)
        self.assertIsNotNone(reload_object(unrelated_image))

    def test_report_boot_images_ignores_unknown_image_properties(self):
        nodegroup = NodeGroup.objects.ensure_master()
        image = make_boot_image_params()
        image['nonesuch'] = factory.make_name('nonesuch'),
        client = make_worker_client(nodegroup)
        response = self.report_images(nodegroup, [image], client=client)
        self.assertEqual(
            (httplib.OK, "OK"),
            (response.status_code, response.content))

    def test_report_boot_images_warns_about_missing_boot_images(self):
        register_error = self.patch(
            boot_images_module, 'register_persistent_error')
        nodegroup = factory.make_NodeGroup(status=NODEGROUP_STATUS.ACCEPTED)
        response = self.report_images(
            nodegroup, [], client=make_worker_client(nodegroup))
        self.assertEqual(httplib.OK, response.status_code)
        self.assertThat(
            register_error,
            MockCalledOnceWith(COMPONENT.IMPORT_PXE_FILES, ANY))

    def test_worker_calls_report_boot_images(self):
        # report_boot_images() uses the report_boot_images op on the nodes
        # handlers to send image information.
        self.useFixture(
            EnvironmentVariableFixture("MAAS_URL", settings.DEFAULT_MAAS_URL))
        refresh_worker(NodeGroup.objects.ensure_master())
        self.patch(MAASClient, 'post')
        self.patch(tftppath, 'list_boot_images', Mock(return_value=[]))
        nodegroup_uuid = factory.make_name('uuid')
        get_cluster_uuid = self.patch(boot_images, "get_cluster_uuid")
        get_cluster_uuid.return_value = nodegroup_uuid

        tasks.report_boot_images.delay()

        # We're not concerned about the payload (images) here;
        # this is tested in provisioningserver.tests.test_boot_images.
        MAASClient.post.assert_called_once_with(
            path=reverse(
                'boot_images_handler', args=[nodegroup_uuid]).lstrip('/'),
            op='report_boot_images', images=ANY)
