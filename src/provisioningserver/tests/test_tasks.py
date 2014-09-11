# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Celery tasks."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import json
import os
import random
from subprocess import CalledProcessError

from apiclient.creds import convert_tuple_to_string
from apiclient.maas_client import MAASClient
from apiclient.testing.credentials import make_api_credentials
import celery
from celery import states
from celery.app import app_or_default
from maastesting.celery import CeleryFixture
from maastesting.factory import factory
from maastesting.fakemethod import (
    FakeMethod,
    MultiFakeMethod,
    )
from mock import Mock
from netaddr import IPNetwork
from provisioningserver import (
    auth,
    boot_images,
    cache,
    tags,
    tasks,
    )
from provisioningserver.boot import tftppath
from provisioningserver.dns.config import (
    celery_conf,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    )
from provisioningserver.dns.zoneconfig import (
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    )
from provisioningserver.tags import MissingCredentials
from provisioningserver.tasks import (
    refresh_secrets,
    report_boot_images,
    rndc_command,
    RNDC_COMMAND_MAX_RETRY,
    setup_rndc_configuration,
    update_node_tags,
    UPDATE_NODE_TAGS_MAX_RETRY,
    write_dns_config,
    write_dns_zone_config,
    write_full_dns_config,
    )
from provisioningserver.testing.boot_images import make_boot_image_params
from provisioningserver.testing.config import set_tftp_root
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver.utils.shell import ExternalProcessError
from testresources import FixtureResource
from testtools.matchers import (
    Equals,
    FileExists,
    MatchesListwise,
    )


celery_config = app_or_default().conf


class TestRefreshSecrets(PservTestCase):
    """Tests for the `refresh_secrets` task."""

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_does_not_require_arguments(self):
        refresh_secrets()
        # Nothing is refreshed, but there is no error either.
        pass

    def test_breaks_on_unknown_item(self):
        self.assertRaises(AssertionError, refresh_secrets, not_an_item=None)

    def test_works_as_a_task(self):
        self.assertTrue(refresh_secrets.delay().successful())

    def test_updates_api_credentials(self):
        credentials = make_api_credentials()
        refresh_secrets(
            api_credentials=convert_tuple_to_string(credentials))
        self.assertEqual(credentials, auth.get_recorded_api_credentials())

    def test_updates_nodegroup_uuid(self):
        nodegroup_uuid = factory.make_name('nodegroupuuid')
        refresh_secrets(nodegroup_uuid=nodegroup_uuid)
        self.assertEqual(nodegroup_uuid, cache.cache.get('nodegroup_uuid'))


def assertTaskRetried(runner, result, nb_retries, task_name):
    # In celery version 2.5 (in Saucy) a retried tasks that eventually
    # succeeds comes out in a 'SUCCESS' state and in 3.1 (in Trusty) is comes
    # out with a 'RETRY' state.
    # In both cases the task is successfully retried.
    if celery.VERSION[0] == 2:
        runner.assertTrue(result.successful())
    else:
        runner.assertEqual(
            len(runner.celery.tasks), nb_retries)
        last_task = runner.celery.tasks[0]
        # The last task succeeded.
        runner.assertEqual(
            (last_task['task'].name, last_task['state']),
            (task_name, states.SUCCESS))


class TestDNSTasks(PservTestCase):

    def setUp(self):
        super(TestDNSTasks, self).setUp()
        # Patch DNS_CONFIG_DIR so that the configuration files will be
        # written in a temporary directory.
        self.dns_conf_dir = self.make_dir()
        self.patch(celery_conf, 'DNS_CONFIG_DIR', self.dns_conf_dir)
        # Record the calls to 'execute_rndc_command' (instead of
        # executing real rndc commands).
        self.rndc_recorder = FakeMethod()
        self.patch(tasks, 'execute_rndc_command', self.rndc_recorder)
        self.celery = self.useFixture(CeleryFixture())

    def test_write_dns_config_writes_file(self):
        zone_names = [random.randint(1, 100), random.randint(1, 100)]
        command = factory.make_string()
        result = write_dns_config.delay(
            zone_names=zone_names,
            callback=rndc_command.subtask(args=[command]))

        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    Equals([((command,), {})]),
                )),
            result)

    def test_write_dns_config_attached_to_dns_worker_queue(self):
        self.assertEqual(
            write_dns_config.queue,
            celery_config.WORKER_QUEUE_DNS)

    def test_write_dns_zone_config_writes_file(self):
        command = factory.make_string()
        domain = factory.make_string()
        network = IPNetwork('192.168.0.3/24')
        dns_ip = factory.pick_ip_in_network(network)
        ip = factory.pick_ip_in_network(network)
        forward_zone = DNSForwardZoneConfig(
            domain, serial=random.randint(1, 100),
            mapping={factory.make_string(): [ip]},
            dns_ip=dns_ip)
        reverse_zone = DNSReverseZoneConfig(
            domain, serial=random.randint(1, 100), network=network)
        result = write_dns_zone_config.delay(
            zones=[forward_zone, reverse_zone],
            callback=rndc_command.subtask(args=[command]))

        forward_file_name = 'zone.%s' % domain
        reverse_file_name = 'zone.0.168.192.in-addr.arpa'
        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, forward_file_name),
                os.path.join(self.dns_conf_dir, reverse_file_name),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    FileExists(),
                    Equals([((command, ), {})]),
                )),
            result)

    def test_write_dns_zone_config_attached_to_dns_worker_queue(self):
        self.assertEqual(
            write_dns_zone_config.queue,
            celery_config.WORKER_QUEUE_DNS)

    def test_setup_rndc_configuration_writes_files(self):
        command = factory.make_string()
        result = setup_rndc_configuration.delay(
            callback=rndc_command.subtask(args=[command]))

        self.assertThat(
            (
                result.successful(),
                os.path.join(self.dns_conf_dir, MAAS_RNDC_CONF_NAME),
                os.path.join(
                    self.dns_conf_dir, MAAS_NAMED_RNDC_CONF_NAME),
                self.rndc_recorder.calls,
            ),
            MatchesListwise(
                (
                    Equals(True),
                    FileExists(),
                    FileExists(),
                    Equals([((command,), {})]),
                )),
            result)

    def test_setup_rndc_configuration_attached_to_dns_worker_queue(self):
        self.assertEqual(
            setup_rndc_configuration.queue,
            celery_config.WORKER_QUEUE_DNS)

    def test_rndc_command_execute_command(self):
        command = factory.make_string()
        result = rndc_command.delay(command)

        self.assertThat(
            (result.successful(), self.rndc_recorder.calls),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([((command,), {})]),
                )))

    def test_rndc_command_can_be_retried(self):
        # The rndc_command task can be retried.
        # Simulate a temporary failure.
        number_of_failures = RNDC_COMMAND_MAX_RETRY
        raised_exception = CalledProcessError(
            factory.make_name('exception'), random.randint(100, 200))
        simulate_failures = MultiFakeMethod(
            [FakeMethod(failure=raised_exception)] * number_of_failures +
            [FakeMethod()])
        self.patch(tasks, 'execute_rndc_command', simulate_failures)
        command = factory.make_string()
        result = rndc_command.delay(command, retry=True)
        assertTaskRetried(
            self, result, RNDC_COMMAND_MAX_RETRY + 1,
            'provisioningserver.tasks.rndc_command')

    def test_rndc_command_is_retried_a_limited_number_of_times(self):
        # If we simulate RNDC_COMMAND_MAX_RETRY + 1 failures, the
        # task fails.
        number_of_failures = RNDC_COMMAND_MAX_RETRY + 1
        raised_exception = ExternalProcessError(
            random.randint(100, 200), factory.make_name('exception'))
        simulate_failures = MultiFakeMethod(
            [FakeMethod(failure=raised_exception)] * number_of_failures +
            [FakeMethod()])
        self.patch(tasks, 'execute_rndc_command', simulate_failures)
        command = factory.make_string()
        self.assertRaises(
            ExternalProcessError, rndc_command.delay,
            command, retry=True)

    def test_rndc_command_attached_to_dns_worker_queue(self):
        self.assertEqual(rndc_command.queue, celery_config.WORKER_QUEUE_DNS)

    def test_write_full_dns_config_sets_up_config(self):
        # write_full_dns_config writes the config file, writes
        # the zone files, and reloads the dns service.
        domain = factory.make_string()
        network = IPNetwork('192.168.0.3/24')
        ip = factory.pick_ip_in_network(network)
        dns_ip = factory.pick_ip_in_network(network)
        zones = [
            DNSForwardZoneConfig(
                domain, serial=random.randint(1, 100),
                mapping={factory.make_string(): [ip]},
                dns_ip=dns_ip,
            ),
            DNSReverseZoneConfig(
                domain, serial=random.randint(1, 100), network=network),
        ]
        command = factory.make_string()
        result = write_full_dns_config.delay(
            zones=zones,
            callback=rndc_command.subtask(args=[command]),
            upstream_dns=factory.getRandomIPAddress())

        forward_file_name = 'zone.%s' % domain
        reverse_file_name = 'zone.0.168.192.in-addr.arpa'
        self.assertThat(
            (
                result.successful(),
                self.rndc_recorder.calls,
                os.path.join(self.dns_conf_dir, forward_file_name),
                os.path.join(self.dns_conf_dir, reverse_file_name),
                os.path.join(self.dns_conf_dir, MAAS_NAMED_CONF_NAME),
                os.path.join(
                    self.dns_conf_dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME),
            ),
            MatchesListwise(
                (
                    Equals(True),
                    Equals([((command,), {})]),
                    FileExists(),
                    FileExists(),
                    FileExists(),
                    FileExists(),
                )))

    def test_write_full_dns_attached_to_dns_worker_queue(self):
        self.assertEqual(
            write_full_dns_config.queue,
            celery_config.WORKER_QUEUE_DNS)


class TestBootImagesTasks(PservTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_sends_boot_images_to_server(self):
        self.useFixture(set_tftp_root(self.make_dir()))
        self.set_maas_url()
        auth.record_api_credentials(':'.join(make_api_credentials()))
        image = make_boot_image_params()
        self.patch(tftppath, 'list_boot_images', Mock(return_value=[image]))
        self.patch(boot_images, "get_cluster_uuid")
        self.patch(MAASClient, 'post')

        report_boot_images.delay()

        args, kwargs = MAASClient.post.call_args
        self.assertItemsEqual([image], json.loads(kwargs['images']))


class TestTagTasks(PservTestCase):

    def setUp(self):
        super(TestTagTasks, self).setUp()
        self.celery = self.useFixture(CeleryFixture())

    def test_update_node_tags_can_be_retried(self):
        self.set_secrets()
        # The update_node_tags task can be retried.
        # Simulate a temporary failure.
        number_of_failures = UPDATE_NODE_TAGS_MAX_RETRY
        raised_exception = MissingCredentials(
            factory.make_name('exception'), random.randint(100, 200))
        simulate_failures = MultiFakeMethod(
            [FakeMethod(failure=raised_exception)] * number_of_failures +
            [FakeMethod()])
        self.patch(tags, 'process_node_tags', simulate_failures)
        tag = factory.make_string()
        result = update_node_tags.delay(
            tag, '//node', tag_nsmap=None, retry=True)
        assertTaskRetried(
            self, result, UPDATE_NODE_TAGS_MAX_RETRY + 1,
            'provisioningserver.tasks.update_node_tags')

    def test_update_node_tags_is_retried_a_limited_number_of_times(self):
        self.set_secrets()
        # If we simulate UPDATE_NODE_TAGS_MAX_RETRY + 1 failures, the
        # task fails.
        number_of_failures = UPDATE_NODE_TAGS_MAX_RETRY + 1
        raised_exception = MissingCredentials(
            factory.make_name('exception'), random.randint(100, 200))
        simulate_failures = MultiFakeMethod(
            [FakeMethod(failure=raised_exception)] * number_of_failures +
            [FakeMethod()])
        self.patch(tags, 'process_node_tags', simulate_failures)
        tag = factory.make_string()
        self.assertRaises(
            MissingCredentials, update_node_tags.delay, tag,
            '//node', tag_nsmap=None, retry=True)
