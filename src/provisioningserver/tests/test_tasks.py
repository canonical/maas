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

from datetime import datetime
import json
import os
import random
from subprocess import (
    CalledProcessError,
    PIPE,
    )

from apiclient.creds import convert_tuple_to_string
from apiclient.maas_client import MAASClient
from apiclient.testing.credentials import make_api_credentials
import celery
from celery import states
from celery.app import app_or_default
from celery.task import Task
from maastesting.celery import CeleryFixture
from maastesting.factory import factory
from maastesting.fakemethod import (
    FakeMethod,
    MultiFakeMethod,
    )
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    )
from mock import Mock
from netaddr import IPNetwork
from provisioningserver import (
    auth,
    boot_images,
    cache,
    tags,
    tasks,
    utils,
    )
from provisioningserver.boot import tftppath
from provisioningserver.dhcp import (
    config,
    leases,
    )
from provisioningserver.dns.config import (
    conf,
    DNSForwardZoneConfig,
    DNSReverseZoneConfig,
    MAAS_NAMED_CONF_NAME,
    MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME,
    MAAS_NAMED_RNDC_CONF_NAME,
    MAAS_RNDC_CONF_NAME,
    )
from provisioningserver.import_images import boot_resources
from provisioningserver.power.poweraction import PowerActionFail
from provisioningserver.tags import MissingCredentials
from provisioningserver.tasks import (
    add_new_dhcp_host_map,
    ALREADY_STOPPED_MESSAGE,
    ALREADY_STOPPED_RETURNCODE,
    enlist_nodes_from_mscm,
    enlist_nodes_from_ucsm,
    import_boot_images,
    Omshell,
    power_off,
    power_on,
    refresh_secrets,
    remove_dhcp_host_map,
    report_boot_images,
    restart_dhcp_server,
    rndc_command,
    RNDC_COMMAND_MAX_RETRY,
    setup_rndc_configuration,
    stop_dhcp_server,
    update_node_tags,
    UPDATE_NODE_TAGS_MAX_RETRY,
    write_dhcp_config,
    write_dns_config,
    write_dns_zone_config,
    write_full_dns_config,
    )
from provisioningserver.testing.boot_images import make_boot_image_params
from provisioningserver.testing.config import (
    BootSourcesFixture,
    set_tftp_root,
    )
from provisioningserver.testing.testcase import PservTestCase
from testresources import FixtureResource
from testtools.matchers import (
    ContainsAll,
    Equals,
    FileExists,
    MatchesListwise,
    )

# An arbitrary MAC address.  Not using a properly random one here since
# we might accidentally affect real machines on the network.
arbitrary_mac = "AA:BB:CC:DD:EE:FF"


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


class TestPowerTasks(PservTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def test_ether_wake_power_on_with_not_enough_template_args(self):
        # In eager test mode the assertion is raised immediately rather
        # than being stored in the AsyncResult, so we need to test for
        # that instead of using result.get().
        self.assertRaises(
            PowerActionFail, power_on.delay, "ether_wake")

    def test_ether_wake_power_on(self):
        result = power_on.delay(
            "ether_wake", mac_address=arbitrary_mac)
        self.assertTrue(result.successful())

    def test_ether_wake_does_not_support_power_off(self):
        self.assertRaises(
            PowerActionFail, power_off.delay,
            "ether_wake", mac=arbitrary_mac)


class TestDHCPTasks(PservTestCase):

    resources = (
        ("celery", FixtureResource(CeleryFixture())),
        )

    def assertRecordedStdin(self, recorder, *args):
        # Helper to check that the function recorder "recorder" has all
        # of the items mentioned in "args" which are extracted from
        # stdin.  We can just check that all the parameters that were
        # passed are being used.
        self.assertThat(
            recorder.extract_args()[0][0],
            ContainsAll(args))

    def make_dhcp_config_params(self):
        """Fake up a dict of dhcp configuration parameters."""
        param_names = [
            'interface',
            'subnet',
            'subnet_mask',
            'broadcast_ip',
            'dns_servers',
            'domain_name',
            'router_ip',
            'ip_range_low',
            'ip_range_high',
        ]
        return {
            'dhcp_subnets': [
                {param: factory.make_string() for param in param_names}
            ],
            'omapi_key': factory.make_string(),
        }

    def test_upload_dhcp_leases(self):
        self.patch(
            leases, 'parse_leases_file',
            Mock(return_value=(datetime.utcnow(), {})))
        self.patch(leases, 'process_leases', Mock())
        tasks.upload_dhcp_leases.delay()
        self.assertEqual(1, leases.process_leases.call_count)

    def test_add_new_dhcp_host_map(self):
        # We don't want to actually run omshell in the task, so we stub
        # out the wrapper class's _run method and record what it would
        # do.
        mac = factory.getRandomMACAddress()
        ip = factory.getRandomIPAddress()
        server_address = factory.make_string()
        key = factory.make_string()
        recorder = FakeMethod(result=(0, "hardware-type"))
        self.patch(Omshell, '_run', recorder)
        add_new_dhcp_host_map.delay({ip: mac}, server_address, key)

        self.assertRecordedStdin(recorder, ip, mac, server_address, key)

    def test_add_new_dhcp_host_map_failure(self):
        # Check that task failures are caught.  Nothing much happens in
        # the Task code right now though.
        mac = factory.getRandomMACAddress()
        ip = factory.getRandomIPAddress()
        server_address = factory.make_string()
        key = factory.make_string()
        self.patch(Omshell, '_run', FakeMethod(result=(0, "this_will_fail")))
        self.assertRaises(
            CalledProcessError, add_new_dhcp_host_map.delay,
            {mac: ip}, server_address, key)

    def test_remove_dhcp_host_map(self):
        # We don't want to actually run omshell in the task, so we stub
        # out the wrapper class's _run method and record what it would
        # do.
        ip = factory.getRandomIPAddress()
        server_address = factory.make_string()
        key = factory.make_string()
        recorder = FakeMethod(result=(0, "obj: <null>"))
        self.patch(Omshell, '_run', recorder)
        remove_dhcp_host_map.delay(ip, server_address, key)

        self.assertRecordedStdin(recorder, ip, server_address, key)

    def test_remove_dhcp_host_map_failure(self):
        # Check that task failures are caught.  Nothing much happens in
        # the Task code right now though.
        ip = factory.getRandomIPAddress()
        server_address = factory.make_string()
        key = factory.make_string()
        self.patch(Omshell, '_run', FakeMethod(result=(0, "this_will_fail")))
        self.assertRaises(
            CalledProcessError, remove_dhcp_host_map.delay,
            ip, server_address, key)

    def test_write_dhcp_config_invokes_script_correctly(self):
        mocked_proc = Mock()
        mocked_proc.returncode = 0
        mocked_proc.communicate = Mock(return_value=('output', 'error output'))
        mocked_popen = self.patch(
            utils, "Popen", Mock(return_value=mocked_proc))

        config_params = self.make_dhcp_config_params()
        write_dhcp_config(**config_params)

        # It should construct Popen with the right parameters.
        self.assertThat(mocked_popen, MockAnyCall(
            ["sudo", "-n", "maas-provision", "atomic-write", "--filename",
             celery_config.DHCP_CONFIG_FILE, "--mode", "0644"], stdin=PIPE))

        # It should then pass the content to communicate().
        content = config.get_config(**config_params).encode("ascii")
        self.assertThat(mocked_proc.communicate, MockAnyCall(content))

        # Similarly, it also writes the DHCPD interfaces to
        # /var/lib/maas/dhcpd-interfaces.
        self.assertThat(mocked_popen, MockAnyCall(
            [
                "sudo", "-n", "maas-provision", "atomic-write", "--filename",
                celery_config.DHCP_INTERFACES_FILE, "--mode", "0644",
            ],
            stdin=PIPE))

    def test_restart_dhcp_server_sends_command(self):
        self.patch(tasks, 'call_and_check')
        restart_dhcp_server()
        self.assertThat(tasks.call_and_check, MockCalledOnceWith(
            ['sudo', '-n', 'service', 'maas-dhcp-server', 'restart']))

    def test_stop_dhcp_server_sends_command_and_writes_empty_config(self):
        self.patch(tasks, 'call_and_check')
        self.patch(tasks, 'sudo_write_file')
        stop_dhcp_server()
        self.assertThat(tasks.call_and_check, MockCalledOnceWith(
            ['sudo', '-n', 'service', 'maas-dhcp-server', 'stop'],
            env={'LC_ALL': 'C'}))
        self.assertThat(tasks.sudo_write_file, MockCalledOnceWith(
            celery_config.DHCP_CONFIG_FILE, tasks.DISABLED_DHCP_SERVER))

    def test_stop_dhcp_server_ignores_already_stopped_error(self):
        # Add whitespaces around the error message to make sure they
        # are stipped off.
        output = ' ' + ALREADY_STOPPED_MESSAGE + '\n'
        exception = utils.ExternalProcessError(
            ALREADY_STOPPED_RETURNCODE, [], output=output)
        self.patch(tasks, 'call_and_check', Mock(side_effect=exception))
        self.patch(tasks, 'sudo_write_file')
        self.assertIsNone(stop_dhcp_server())

    def test_stop_dhcp_server_raises_other_returncodes(self):
        # Use a returncode that is *not* ALREADY_STOPPED_RETURNCODE.
        returncode = ALREADY_STOPPED_RETURNCODE + 1
        exception = utils.ExternalProcessError(
            returncode, [], output=ALREADY_STOPPED_MESSAGE)
        self.patch(tasks, 'call_and_check', Mock(side_effect=exception))
        self.patch(tasks, 'sudo_write_file')
        self.assertRaises(utils.ExternalProcessError, stop_dhcp_server)

    def test_stop_dhcp_server_raises_other_error_outputs(self):
        # Use an error output that is *not* ALREADY_STOPPED_MESSAGE.
        output = factory.make_string()
        exception = utils.ExternalProcessError(
            ALREADY_STOPPED_RETURNCODE, [], output=output)
        self.patch(tasks, 'call_and_check', Mock(side_effect=exception))
        self.patch(tasks, 'sudo_write_file')
        self.assertRaises(utils.ExternalProcessError, stop_dhcp_server)


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
        self.patch(conf, 'DNS_CONFIG_DIR', self.dns_conf_dir)
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
            mapping={factory.make_string(): ip},
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
        raised_exception = utils.ExternalProcessError(
            random.randint(100, 200), factory.make_name('exception'))
        simulate_failures = MultiFakeMethod(
            [FakeMethod(failure=raised_exception)] * number_of_failures +
            [FakeMethod()])
        self.patch(tasks, 'execute_rndc_command', simulate_failures)
        command = factory.make_string()
        self.assertRaises(
            utils.ExternalProcessError, rndc_command.delay,
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
                mapping={factory.make_string(): ip},
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


class TestImportBootImages(PservTestCase):

    def make_archive_url(self, name=None):
        if name is None:
            name = factory.make_name('archive')
        return 'http://%s.example.com/%s' % (name, factory.make_name('path'))

    def patch_boot_resources_function(self):
        """Patch out `boot_resources.import_images`.

        Returns the installed fake.  After the fake has been called, but not
        before, its `env` attribute will have a copy of the environment dict.
        """

        class CaptureEnv:
            """Fake function; records a copy of the environment."""

            def __call__(self, *args, **kwargs):
                self.args = args
                self.env = os.environ.copy()

        return self.patch(boot_resources, 'import_images', CaptureEnv())

    def test_import_boot_images_integrates_with_boot_resources_function(self):
        # If the config specifies no sources, nothing will be imported.  But
        # the task succeeds without errors.
        fixture = self.useFixture(BootSourcesFixture([]))
        self.patch(boot_resources, 'logger')
        self.patch(boot_resources, 'locate_config').return_value = (
            fixture.filename)
        import_boot_images(sources=[])
        self.assertIsInstance(import_boot_images, Task)

    def test_import_boot_images_sets_GPGHOME(self):
        home = factory.make_name('home')
        self.patch(tasks, 'MAAS_USER_GPGHOME', home)
        fake = self.patch_boot_resources_function()
        import_boot_images(sources=[])
        self.assertEqual(home, fake.env['GNUPGHOME'])

    def test_import_boot_images_sets_proxy_if_given(self):
        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        proxy_vars = ['http_proxy', 'https_proxy']
        fake = self.patch_boot_resources_function()
        import_boot_images(sources=[], http_proxy=proxy)
        self.assertEqual(
            {
                var: proxy
                for var in proxy_vars
            }, utils.filter_dict(fake.env, proxy_vars))

    def test_import_boot_images_leaves_proxy_unchanged_if_not_given(self):
        proxy_vars = ['http_proxy', 'https_proxy']
        fake = self.patch_boot_resources_function()
        import_boot_images(sources=[])
        self.assertEqual({}, utils.filter_dict(fake.env, proxy_vars))

    def test_import_boot_images_calls_callback(self):
        self.patch_boot_resources_function()
        mock_callback = Mock()
        import_boot_images(sources=[], callback=mock_callback)
        self.assertThat(mock_callback.delay, MockCalledOnceWith())

    def test_import_boot_images_accepts_sources_parameter(self):
        fake = self.patch(boot_resources, 'import_images')
        sources = [
            {
                'path': "http://example.com",
                'selections': [
                    {
                        'release': "trusty",
                        'arches': ["amd64"],
                        'subarches': ["generic"],
                        'labels': ["release"]
                    },
                ],
            },
        ]
        import_boot_images(sources=sources)
        self.assertThat(fake, MockCalledOnceWith(sources))


class TestAddUCSM(PservTestCase):

    def test_enlist_nodes_from_ucsm(self):
        url = 'url'
        username = 'username'
        password = 'password'
        mock = self.patch(tasks, 'probe_and_enlist_ucsm')
        enlist_nodes_from_ucsm(url, username, password)
        self.assertThat(mock, MockCalledOnceWith(url, username, password))


class TestAddMSCM(PservTestCase):

    def test_enlist_nodes_from_mscm(self):
        host = 'host'
        username = 'username'
        password = 'password'
        mock = self.patch(tasks, 'probe_and_enlist_mscm')
        enlist_nodes_from_mscm(host, username, password)
        self.assertThat(mock, MockCalledOnceWith(host, username, password))
