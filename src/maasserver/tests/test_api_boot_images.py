# Copyright 2013 Canonical Ltd.  This software is licensed under the
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
from django.conf import settings
from django.core.urlresolvers import reverse
from fixtures import EnvironmentVariableFixture
from maasserver import api
from maasserver.api import (
    summarise_boot_image_dict,
    summarise_boot_image_object,
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
from maasserver.testing import reload_object
from maasserver.testing.api import (
    APITestCase,
    log_in_as_normal_user,
    make_worker_client,
    )
from maasserver.testing.factory import factory
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
from provisioningserver.pxe import tftppath
from provisioningserver.testing.boot_images import make_boot_image_params
from testresources import FixtureResource
from testtools.matchers import MatchesStructure


def get_boot_image_uri(boot_image):
    """Return a boot image's URI on the API."""
    return reverse(
        'boot_image_handler',
        args=[boot_image.nodegroup.uuid, boot_image.id])


class TestBootImageAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/uuid/boot-images/3/',
            reverse('boot_image_handler', args=['uuid', '3']))

    def test_GET_returns_boot_image(self):
        boot_image = factory.make_boot_image()
        response = self.client.get(get_boot_image_uri(boot_image))
        self.assertEqual(httplib.OK, response.status_code)
        returned_boot_image = json.loads(response.content)
        # The returned object contains a 'resource_uri' field.
        self.assertEqual(
            reverse(
                    'boot_image_handler',
                    args=[boot_image.nodegroup.uuid, boot_image.id]
            ),
            returned_boot_image['resource_uri'])
        # The other fields are the boot image's fields.
        del returned_boot_image['resource_uri']
        self.assertThat(
            boot_image,
            MatchesStructure.byEquality(**returned_boot_image))


class TestBootImagesAPI(APITestCase):
    """Test the the boot images API."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/nodegroups/uuid/boot-images/',
            reverse('boot_images_handler', args=['uuid']))

    def test_GET_returns_boot_image_list(self):
        nodegroup = factory.make_node_group()
        images = [
            factory.make_boot_image(nodegroup=nodegroup) for _ in range(3)]
        # Create images in another nodegroup.
        [factory.make_boot_image() for _ in range(3)]
        response = self.client.get(
            reverse('boot_images_handler', args=[nodegroup.uuid]))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [boot_image.id for boot_image in images],
            [boot_image.get('id') for boot_image in parsed_result])


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
                image.architecture,
                image.subarchitecture,
                image.release,
                image.label,
                image.purpose,
            ),
            summarise_boot_image_object(image))

    def test_summarise_boot_image_dict_returns_tuple(self):
        image = make_boot_image_params()
        self.assertEqual(
            (
                image['architecture'],
                image['subarchitecture'],
                image['release'],
                image['label'],
                image['purpose'],
            ),
            summarise_boot_image_dict(image))

    def test_summarise_boot_image_dict_substitutes_defaults(self):
        image = make_boot_image_params()
        del image['subarchitecture']
        del image['label']
        _, subarchitecture, _, label, _ = summarise_boot_image_dict(image)
        self.assertEqual(('generic', 'release'), (subarchitecture, label))

    def test_summarise_boot_image_functions_are_compatible(self):
        image_dict = make_boot_image_params()
        image_obj = factory.make_boot_image(
            architecture=image_dict['architecture'],
            subarchitecture=image_dict['subarchitecture'],
            release=image_dict['release'], label=image_dict['label'],
            purpose=image_dict['purpose'])
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

    def test_report_boot_images_keeps_known_images(self):
        nodegroup = factory.make_node_group()
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
        register_error = self.patch(api, 'register_persistent_error')
        nodegroup = factory.make_node_group(status=NODEGROUP_STATUS.ACCEPTED)
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
