# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for node forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from crochet import TimeoutError
from django.forms import (
    CheckboxInput,
    HiddenInput,
    )
from maasserver import forms
from maasserver.clusterrpc.power_parameters import get_power_type_choices
from maasserver.clusterrpc.testing.osystems import (
    make_rpc_osystem,
    make_rpc_release,
    )
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.forms import (
    AdminNodeForm,
    BLANK_CHOICE,
    NodeForm,
    pick_default_architecture,
    )
import maasserver.forms as forms_module
from maasserver.testing.architecture import (
    make_usable_architecture,
    patch_usable_architectures,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.osystems import (
    make_osystem_with_releases,
    make_usable_osystem,
    patch_usable_osystems,
    )
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
    )


class TestNodeForm(MAASServerTestCase):

    def test_contains_limited_set_of_fields(self):
        form = NodeForm()

        self.assertEqual(
            [
                'hostname',
                'architecture',
                'osystem',
                'distro_series',
                'license_key',
                'disable_ipv4',
                'swap_size',
                'nodegroup',
            ], list(form.fields))

    def test_changes_node(self):
        node = factory.make_Node()
        hostname = factory.make_string()
        patch_usable_architectures(self, [node.architecture])

        form = NodeForm(
            data={
                'hostname': hostname,
                'architecture': make_usable_architecture(self),
                },
            instance=node)
        form.save()

        self.assertEqual(hostname, node.hostname)

    def test_accepts_usable_architecture(self):
        arch = make_usable_architecture(self)
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': arch,
            })
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_unusable_architecture(self):
        patch_usable_architectures(self)
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': factory.make_name('arch'),
            })
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['architecture'], form._errors.keys())

    def test_starts_with_default_architecture(self):
        arches = sorted([factory.make_name('arch') for _ in range(5)])
        patch_usable_architectures(self, arches)
        form = NodeForm()
        self.assertEqual(
            pick_default_architecture(arches),
            form.fields['architecture'].initial)

    def test_adds_blank_default_when_no_arches_available(self):
        patch_usable_architectures(self, [])
        form = NodeForm()
        self.assertEqual(
            [BLANK_CHOICE],
            form.fields['architecture'].choices)

    def test_accepts_osystem(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        osystem = make_usable_osystem(self)
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            },
            instance=node)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_invalid_osystem(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        patch_usable_osystems(self)
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': make_usable_architecture(self),
            'osystem': factory.make_name('os'),
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['osystem'], form._errors.keys())

    def test_starts_with_default_osystem(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        osystems = [make_osystem_with_releases(self) for _ in range(5)]
        patch_usable_osystems(self, osystems)
        form = NodeForm(instance=node)
        self.assertEqual(
            '',
            form.fields['osystem'].initial)

    def test_accepts_osystem_distro_series(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        osystem = make_usable_osystem(self)
        release = osystem['default_release']
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s' % (osystem['name'], release),
            },
            instance=node)
        self.assertTrue(form.is_valid(), form._errors)

    def test_rejects_invalid_osystem_distro_series(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        osystem = make_usable_osystem(self)
        release = factory.make_name('release')
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s' % (osystem['name'], release),
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['distro_series'], form._errors.keys())

    def test_starts_with_default_distro_series(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        osystems = [make_osystem_with_releases(self) for _ in range(5)]
        patch_usable_osystems(self, osystems)
        form = NodeForm(instance=node)
        self.assertEqual(
            '',
            form.fields['distro_series'].initial)

    def test_rejects_mismatch_osystem_distro_series(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        osystem = make_usable_osystem(self)
        release = osystem['default_release']
        invalid = factory.make_name('invalid_os')
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s' % (invalid, release),
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['distro_series'], form._errors.keys())

    def test_rejects_when_validate_license_key_returns_False(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        license_key = factory.make_name('key')
        mock_validate = self.patch(forms, 'validate_license_key')
        mock_validate.return_value = False
        form = NodeForm(data={
            'hostname': factory.make_name('host'),
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s*' % (osystem['name'], release['name']),
            'license_key': license_key,
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['license_key'], form._errors.keys())

    def test_calls_validate_license_key_for_with_nodegroup(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        license_key = factory.make_name('key')
        mock_validate_for = self.patch(forms, 'validate_license_key_for')
        mock_validate_for.return_value = True
        form = NodeForm(data={
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s*' % (osystem['name'], release['name']),
            'license_key': license_key,
            },
            instance=node)
        self.assertTrue(form.is_valid())
        self.assertThat(
            mock_validate_for,
            MockCalledOnceWith(
                node.nodegroup, osystem['name'], release['name'], license_key))

    def test_rejects_when_validate_license_key_for_returns_False(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        license_key = factory.make_name('key')
        mock_validate_for = self.patch(forms, 'validate_license_key_for')
        mock_validate_for.return_value = False
        form = NodeForm(data={
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s*' % (osystem['name'], release['name']),
            'license_key': license_key,
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['license_key'], form._errors.keys())

    def test_rejects_when_validate_license_key_for_raise_no_connection(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        license_key = factory.make_name('key')
        mock_validate_for = self.patch(forms, 'validate_license_key_for')
        mock_validate_for.side_effect = NoConnectionsAvailable()
        form = NodeForm(data={
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s*' % (osystem['name'], release['name']),
            'license_key': license_key,
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['license_key'], form._errors.keys())

    def test_rejects_when_validate_license_key_for_raise_timeout(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        license_key = factory.make_name('key')
        mock_validate_for = self.patch(forms, 'validate_license_key_for')
        mock_validate_for.side_effect = TimeoutError()
        form = NodeForm(data={
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s*' % (osystem['name'], release['name']),
            'license_key': license_key,
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['license_key'], form._errors.keys())

    def test_rejects_when_validate_license_key_for_raise_no_os(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        release = make_rpc_release(requires_license_key=True)
        osystem = make_rpc_osystem(releases=[release])
        patch_usable_osystems(self, osystems=[osystem])
        license_key = factory.make_name('key')
        mock_validate_for = self.patch(forms, 'validate_license_key_for')
        mock_validate_for.side_effect = NoSuchOperatingSystem()
        form = NodeForm(data={
            'architecture': make_usable_architecture(self),
            'osystem': osystem['name'],
            'distro_series': '%s/%s*' % (osystem['name'], release['name']),
            'license_key': license_key,
            },
            instance=node)
        self.assertFalse(form.is_valid())
        self.assertItemsEqual(['license_key'], form._errors.keys())

    def test_rejects_duplicate_fqdn_with_unmanaged_dns_on_one_nodegroup(self):
        # If a host with a given hostname exists on a managed nodegroup,
        # new nodes on unmanaged nodegroups with hostnames that match
        # that FQDN will be rejected.
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_Node(
            hostname=factory.make_name("hostname"), nodegroup=nodegroup)
        other_nodegroup = factory.make_NodeGroup()
        form = NodeForm(data={
            'nodegroup': other_nodegroup,
            'hostname': node.fqdn,
            'architecture': make_usable_architecture(self),
        })
        form.instance.nodegroup = other_nodegroup
        self.assertFalse(form.is_valid())

    def test_rejects_duplicate_fqdn_on_same_nodegroup(self):
        # If a node with a given FQDN exists on a managed nodegroup, new
        # nodes on that nodegroup with duplicate FQDNs will be rejected.
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ACCEPTED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = factory.make_Node(
            hostname=factory.make_name("hostname"), nodegroup=nodegroup)
        form = NodeForm(data={
            'nodegroup': nodegroup,
            'hostname': node.fqdn,
            'architecture': make_usable_architecture(self),
        })
        form.instance.nodegroup = nodegroup
        self.assertFalse(form.is_valid())

    def test_obeys_disable_ipv4_if_given(self):
        setting = factory.pick_bool()
        cluster = factory.make_NodeGroup(default_disable_ipv4=(not setting))
        form = NodeForm(
            data={
                'nodegroup': cluster,
                'architecture': make_usable_architecture(self),
                'disable_ipv4': setting,
                })
        form.instance.nodegroup = cluster
        node = form.save()
        self.assertEqual(setting, node.disable_ipv4)

    def test_takes_missing_disable_ipv4_as_False_in_UI(self):
        form = NodeForm(
            instance=factory.make_Node(disable_ipv4=True),
            data={
                'architecture': make_usable_architecture(self),
                'ui_submission': True,
                })
        node = form.save()
        self.assertFalse(node.disable_ipv4)

    def test_takes_missing_disable_ipv4_as_Unchanged_in_API(self):
        form = NodeForm(
            instance=factory.make_Node(disable_ipv4=True),
            data={
                'architecture': make_usable_architecture(self),
                })
        node = form.save()
        self.assertTrue(node.disable_ipv4)

    def test_takes_True_disable_ipv4_from_cluster_by_default(self):
        setting = True
        cluster = factory.make_NodeGroup(default_disable_ipv4=setting)
        form = NodeForm(
            data={
                'nodegroup': cluster,
                'architecture': make_usable_architecture(self),
                })
        form.instance.nodegroup = cluster
        node = form.save()
        self.assertEqual(setting, node.disable_ipv4)

    def test_takes_False_disable_ipv4_from_cluster_by_default(self):
        setting = False
        cluster = factory.make_NodeGroup(default_disable_ipv4=setting)
        form = NodeForm(
            data={
                'nodegroup': cluster,
                'architecture': make_usable_architecture(self),
                })
        form.instance.nodegroup = cluster
        node = form.save()
        self.assertEqual(setting, node.disable_ipv4)

    def test_shows_disable_ipv4_if_IPv6_revealed_and_configured(self):
        self.patch(forms_module, 'REVEAL_IPv6', True)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        factory.make_NodeGroupInterface(
            node.nodegroup, network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        form = NodeForm(
            instance=node,
            data={'architecture': make_usable_architecture(self)})
        self.assertIsInstance(
            form.fields['disable_ipv4'].widget, CheckboxInput)

    def test_hides_disable_ipv4_if_IPv6_not_revealed(self):
        self.patch(forms_module, 'REVEAL_IPv6', False)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        factory.make_NodeGroupInterface(
            node.nodegroup, network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        form = NodeForm(
            instance=node,
            data={'architecture': make_usable_architecture(self)})
        self.assertIsInstance(form.fields['disable_ipv4'].widget, HiddenInput)

    def test_hides_disable_ipv4_if_IPv6_not_configured(self):
        self.patch(forms_module, 'REVEAL_IPv6', True)
        node = factory.make_Node_with_MACAddress_and_NodeGroupInterface()
        factory.make_NodeGroupInterface(
            node.nodegroup, network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        form = NodeForm(
            instance=node,
            data={'architecture': make_usable_architecture(self)})
        self.assertIsInstance(form.fields['disable_ipv4'].widget, HiddenInput)

    def test_shows_disable_ipv4_on_new_node_if_any_cluster_supports_it(self):
        self.patch(forms_module, 'REVEAL_IPv6', True)
        factory.make_NodeGroupInterface(
            factory.make_NodeGroup(), network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        form = NodeForm(data={'architecture': make_usable_architecture(self)})
        self.assertIsInstance(
            form.fields['disable_ipv4'].widget, CheckboxInput)

    def test_hides_disable_ipv4_on_new_node_if_no_cluster_supports_it(self):
        self.patch(forms_module, 'REVEAL_IPv6', True)
        factory.make_NodeGroupInterface(
            factory.make_NodeGroup(), network=factory.make_ipv6_network(),
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        form = NodeForm(data={'architecture': make_usable_architecture(self)})
        self.assertIsInstance(form.fields['disable_ipv4'].widget, HiddenInput)


class TestAdminNodeForm(MAASServerTestCase):

    def test_AdminNodeForm_contains_limited_set_of_fields(self):
        self.client_log_in()
        node = factory.make_Node(owner=self.logged_in_user)
        form = AdminNodeForm(instance=node)

        self.assertEqual(
            [
                'hostname',
                'architecture',
                'osystem',
                'distro_series',
                'license_key',
                'disable_ipv4',
                'swap_size',
                'power_type',
                'power_parameters',
                'cpu_count',
                'memory',
                'zone',
            ],
            list(form.fields))

    def test_AdminNodeForm_initialises_zone(self):
        # The zone field uses "to_field_name", so that it can refer to a zone
        # by name instead of by ID.  A bug in Django breaks initialisation
        # from an instance: the field tries to initialise the field using a
        # zone's ID instead of its name, and ends up reverting to the default.
        # The code must work around this bug.
        zone = factory.make_Zone()
        node = factory.make_Node(zone=zone)
        # We'll create a form that makes a change, but not to the zone.
        data = {'hostname': factory.make_name('host')}
        form = AdminNodeForm(instance=node, data=data)
        # The Django bug would stop the initial field value from being set,
        # but the workaround ensures that it is initialised.
        self.assertEqual(zone.name, form.initial['zone'])

    def test_AdminNodeForm_changes_node(self):
        node = factory.make_Node()
        zone = factory.make_Zone()
        hostname = factory.make_string()
        power_type = factory.pick_power_type()
        form = AdminNodeForm(
            data={
                'hostname': hostname,
                'power_type': power_type,
                'architecture': make_usable_architecture(self),
                'zone': zone.name,
            },
            instance=node)
        form.save()

        node = reload_object(node)
        self.assertEqual(
            (node.hostname, node.power_type, node.zone),
            (hostname, power_type, zone))

    def test_AdminNodeForm_populates_power_type_choices(self):
        form = AdminNodeForm()
        self.assertEqual(
            [''] + [choice[0] for choice in get_power_type_choices()],
            [choice[0] for choice in form.fields['power_type'].choices])

    def test_AdminNodeForm_populates_power_type_initial(self):
        node = factory.make_Node()
        form = AdminNodeForm(instance=node)
        self.assertEqual(node.power_type, form.fields['power_type'].initial)

    def test_AdminNodeForm_changes_node_with_skip_check(self):
        node = factory.make_Node()
        hostname = factory.make_string()
        power_type = factory.pick_power_type()
        power_parameters_field = factory.make_string()
        arch = make_usable_architecture(self)
        form = AdminNodeForm(
            data={
                'hostname': hostname,
                'architecture': arch,
                'power_type': power_type,
                'power_parameters_field': power_parameters_field,
                'power_parameters_skip_check': True,
                },
            instance=node)
        form.save()

        self.assertEqual(
            (hostname, power_type, {'field': power_parameters_field}),
            (node.hostname, node.power_type, node.power_parameters))

    def test_AdminForm_does_not_permit_nodegroup_change(self):
        # We had to make Node.nodegroup editable to get Django to
        # validate it as non-blankable, but that doesn't mean that we
        # actually want to allow people to edit it through API or UI.
        old_nodegroup = factory.make_NodeGroup()
        node = factory.make_Node(
            nodegroup=old_nodegroup,
            architecture=make_usable_architecture(self))
        new_nodegroup = factory.make_NodeGroup()
        AdminNodeForm(data={'nodegroup': new_nodegroup}, instance=node).save()
        # The form saved without error, but the nodegroup change was ignored.
        self.assertEqual(old_nodegroup, node.nodegroup)
