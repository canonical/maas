# Copyright 2013-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from functools import partial
import random

from django import forms

from maasserver.enum import (
    DEPLOYMENT_TARGET,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
)
from maasserver.forms import (
    UnconstrainedMultipleChoiceField,
    UnconstrainedTypedMultipleChoiceField,
    ValidatorMultipleChoiceField,
)
from maasserver.models import Domain, Machine, NodeDevice, Zone
from maasserver.node_constraint_filter_forms import (
    AcquireNodeForm,
    detect_nonexistent_names,
    FilterNodeForm,
    FreeTextFilterNodeForm,
    generate_architecture_wildcards,
    get_architecture_wildcards,
    get_field_argument_type,
    get_storage_constraints_from_string,
    JUJU_ACQUIRE_FORM_FIELDS_MAPPING,
    nodes_by_interface,
    nodes_by_storage,
    parse_legacy_tags,
    ReadNodesForm,
)
from maasserver.testing.architecture import patch_usable_architectures
from maasserver.testing.factory import factory, RANDOM
from maasserver.testing.osystems import make_usable_osystem
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.enum import POWER_STATE
from provisioningserver.utils.constraints import LabeledConstraintMap


class TestUtils(MAASServerTestCase):
    def test_generate_architecture_wildcards(self):
        # Create a test architecture choice list of one architecture that only
        # has one available subarch (single_subarch) and two architectures that
        # have a matching primary architecture (double_subarch_{1,2})
        single_subarch = factory.make_name("arch"), factory.make_name("arch")
        double_subarch_1 = factory.make_name("arch"), factory.make_name("arch")
        double_subarch_2 = double_subarch_1[0], factory.make_name("arch")
        arches = [
            "/".join(single_subarch),
            "/".join(double_subarch_1),
            "/".join(double_subarch_2),
        ]

        # single_subarch should end up in the dict essentially unchanged, and
        # the double_subarchs should have been flattened into a single dict
        # element with a list of them.
        self.assertEqual(
            {
                single_subarch[0]: frozenset([arches[0]]),
                double_subarch_1[0]: frozenset([arches[1], arches[2]]),
            },
            generate_architecture_wildcards(arches),
        )

    def test_get_architecture_wildcards_aliases_armhf_as_arm(self):
        subarch = factory.make_name("sub")
        arches = ["armhf/%s" % subarch]
        self.assertEqual(
            {"arm": frozenset(arches), "armhf": frozenset(arches)},
            get_architecture_wildcards(arches),
        )

    def test_get_architecture_wildcards_does_not_overwrite_existing_arm(self):
        arm = "arm/%s" % factory.make_name("armsub")
        armhf = "armhf/%s" % factory.make_name("armhfsub")
        self.assertEqual(
            {"arm": frozenset([arm]), "armhf": frozenset([armhf])},
            get_architecture_wildcards([arm, armhf]),
        )

    def test_parse_legacy_tags(self):
        self.assertEqual([], parse_legacy_tags([]))
        self.assertEqual(["a", "b"], parse_legacy_tags(["a", "b"]))
        self.assertEqual(["a", "b"], parse_legacy_tags(["a b"]))
        self.assertEqual(["a", "b"], parse_legacy_tags(["a, b"]))
        self.assertEqual(["a", "b", "c"], parse_legacy_tags(["a, b c"]))
        self.assertEqual(["a", "b"], parse_legacy_tags(["a,b"]))
        self.assertEqual(
            ["a", "b", "c", "d"], parse_legacy_tags(["a,b", "c d"])
        )

    def test_JUJU_ACQUIRE_FORM_FIELDS_MAPPING_fields(self):
        self.assertGreaterEqual(
            set(AcquireNodeForm().fields),
            set(JUJU_ACQUIRE_FORM_FIELDS_MAPPING),
        )

    def test_detect_nonexistent_names_returns_empty_if_no_names(self):
        self.assertEqual([], detect_nonexistent_names(Zone, []))

    def test_detect_nonexistent_names_returns_empty_if_all_OK(self):
        zones = [factory.make_Zone() for _ in range(3)]
        self.assertEqual(
            [], detect_nonexistent_names(Zone, [zone.name for zone in zones])
        )

    def test_detect_nonexistent_names_reports_unknown_names(self):
        non_zone = factory.make_name("nonzone")
        self.assertEqual(
            [non_zone], detect_nonexistent_names(Zone, [non_zone])
        )

    def test_detect_nonexistent_names_is_consistent(self):
        names = [factory.make_name("nonzone") for _ in range(3)]
        self.assertEqual(
            detect_nonexistent_names(Zone, names),
            detect_nonexistent_names(Zone, names),
        )

    def test_detect_nonexistent_names_combines_good_and_bad_names(self):
        zone = factory.make_Zone().name
        non_zone = factory.make_name("nonzone")
        self.assertEqual(
            [non_zone], detect_nonexistent_names(Zone, [zone, non_zone])
        )

    def test_detect_nonexistent_names_asserts_parameter_type(self):
        self.assertRaises(
            AssertionError, detect_nonexistent_names, Zone, "text"
        )

    def test_get_storage_constraints_from_string_returns_None_for_empty(self):
        self.assertIsNone(get_storage_constraints_from_string(""))

    def test_get_storage_constraints_from_string_None_for_empty_tags(self):
        self.assertEqual(
            [None, None, None],
            [
                tags
                for _, _, tags in get_storage_constraints_from_string("0,0,0")
            ],
        )

    def test_get_storage_constraints_from_string_returns_size_in_bytes(self):
        self.assertEqual(
            [int(1.5 * (1000**3)), 3 * (1000**3), int(6.75 * (1000**3))],
            [
                size
                for _, size, _ in get_storage_constraints_from_string(
                    "1.5,3,6.75"
                )
            ],
        )

    def test_get_storage_constraints_from_string_sorts_more_tags_first(self):
        """Ensure first tag set remains first, all others are sorted"""
        self.assertEqual(
            [["ssd"], ["ssd", "sata", "removable"], ["ssd", "sata"], ["ssd"]],
            [
                tags
                for _, _, tags in get_storage_constraints_from_string(
                    "0(ssd),0(ssd,sata),0(ssd),0(ssd,sata,removable)"
                )
            ],
        )

    def test_nodes_by_storage_returns_None_when_storage_string_is_empty(self):
        self.assertIsNone(nodes_by_storage(""))


class FilterConstraintsMixin:
    form_class = None  # set in subclasses

    def assertConstrainedNodes(self, nodes, data):
        form = self.form_class(data=data)
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, storage, interfaces = form.filter_nodes(
            Machine.objects.all()
        )
        self.assertCountEqual(nodes, filtered_nodes)
        return (filtered_nodes, storage, interfaces)


def create_unique_node_device_needle(needle_name, needle_factory):
    needles = NodeDevice.objects.all().values_list(needle_name, flat=True)
    unique_needle = needle_factory()
    while unique_needle in needles:
        unique_needle = needle_factory()
    return unique_needle


class TestFilterNodeForm(MAASServerTestCase, FilterConstraintsMixin):
    form_class = FilterNodeForm

    def set_usable_arch(self):
        """Produce an arbitrary, valid, architecture name."""
        arch = "{}/{}".format(
            factory.make_name("arch"), factory.make_name("sub")
        )
        patch_usable_architectures(self, [arch])
        return arch

    def create_node_on_subnets(self, subnets):
        node = factory.make_Node()
        for subnet in subnets:
            nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip="",
                interface=nic,
                subnet=subnet,
            )
        return node

    def test_strict_form_checks_unknown_constraints(self):
        data = {"unknown_constraint": "boo"}
        form = FilterNodeForm.Strict(data=data)
        self.assertEqual(
            (False, {"unknown_constraint": ["No such constraint."]}),
            (form.is_valid(), form.errors),
        )

    def test_not_strict_check_unknown_constraints(self):
        data = {"unknown_constraint": "boo"}
        form = FilterNodeForm(data=data)
        self.assertFalse(form.is_valid())

    def test_no_constraints(self):
        nodes = [factory.make_Node() for _ in range(3)]
        form = FilterNodeForm(data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertCountEqual(nodes, Machine.objects.all())

    def test_subnets_filters_by_name(self):
        subnets = [factory.make_Subnet() for _ in range(3)]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        # Filter for this subnet.  Take one in the middle to avoid
        # coincidental success based on ordering.
        pick = 1
        self.assertConstrainedNodes(
            {nodes[pick]}, {"subnets": [subnets[pick].name]}
        )

    def test_rejects_space_not_connected_to_anything(self):
        space1 = factory.make_Space("foo")
        factory.make_Space("bar")
        v1 = factory.make_VLAN(space=space1)
        s1 = factory.make_Subnet(vlan=v1, space=None)
        factory.make_Node_with_Interface_on_Subnet(subnet=s1)
        form = FilterNodeForm(data={"subnets": "space:bar"})
        self.assertFalse(form.is_valid(), dict(form.errors))

    def test_subnets_filters_by_space(self):
        subnets = [factory.make_Subnet(space=RANDOM) for _ in range(3)]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        # Filter for this subnet.  Take one in the middle to avoid
        # coincidental success based on ordering.
        pick = 1
        self.assertConstrainedNodes(
            {nodes[pick]}, {"subnets": ["space:%s" % subnets[pick].space.name]}
        )

    def test_subnets_filters_by_multiple_not_space_arguments(self):
        # Create 3 different subnets (will be on 3 random spaces)
        subnets = [factory.make_Subnet(space=RANDOM) for _ in range(3)]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        expected_selection = random.randint(0, len(subnets) - 1)
        expected_node = nodes[expected_selection]
        # Remove the expected subnet from the list of subnets; we'll use the
        # remaining subnets to filter the list.
        del subnets[expected_selection]
        self.assertConstrainedNodes(
            {expected_node},
            {
                "not_subnets": [
                    "space:%s" % subnet.space.name for subnet in subnets
                ]
            },
        )

    def test_vlans_filters_by_space(self):
        vlans = [factory.make_VLAN(space=RANDOM) for _ in range(3)]
        subnets = [factory.make_Subnet(vlan=vlan) for vlan in vlans]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        # Filter for this subnet.  Take one in the middle to avoid
        # coincidental success based on ordering.
        pick = 1
        self.assertConstrainedNodes(
            {nodes[pick]}, {"vlans": ["space:%s" % vlans[pick].space.name]}
        )

    def test_vlans_filters_by_multiple_not_space_arguments(self):
        # Create 3 different VLANs (will be on 3 random spaces)
        vlans = [factory.make_VLAN(space=RANDOM) for _ in range(3)]
        subnets = [factory.make_Subnet(vlan=vlan) for vlan in vlans]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        expected_selection = random.randint(0, len(vlans) - 1)
        expected_node = nodes[expected_selection]
        # Remove the expected subnet from the list of subnets; we'll use the
        # remaining subnets to filter the list.
        del vlans[expected_selection]
        self.assertConstrainedNodes(
            {expected_node},
            {"not_vlans": ["space:%s" % vlan.space.name for vlan in vlans]},
        )

    def test_fails_validation_for_no_matching_vlans(self):
        form = FilterNodeForm(data={"vlans": ["space:foo"]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["No matching VLANs found."], dict(form.errors)["vlans"]
        )

    def test_fails_validation_for_no_matching_not_vlans(self):
        form = FilterNodeForm(data={"not_vlans": ["space:foo"]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["No matching VLANs found."],
            dict(form.errors)["not_vlans"],
        )

    def test_fails_validation_for_no_matching_subnets(self):
        form = FilterNodeForm(data={"subnets": ["foo"]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["No matching subnets found."],
            dict(form.errors)["subnets"],
        )

    def test_fails_validation_for_no_matching_not_subnets(self):
        form = FilterNodeForm(data={"not_subnets": ["foo"]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            ["No matching subnets found."],
            dict(form.errors)["not_subnets"],
        )

    def test_subnets_filters_by_ip(self):
        subnets = [factory.make_Subnet() for _ in range(3)]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        # Filter for this subnet.  Take one in the middle to avoid
        # coincidental success based on ordering.
        pick = 1
        self.assertConstrainedNodes(
            {nodes[pick]},
            {
                "subnets": [
                    "ip:%s"
                    % factory.pick_ip_in_network(subnets[pick].get_ipnetwork())
                ]
            },
        )

    def test_subnets_filters_by_vlan_tag(self):
        vlan_tags = list(range(1, 6))
        subnets = [
            factory.make_Subnet(vlan=factory.make_VLAN(vid=tag))
            for tag in vlan_tags
        ]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(
                status=NODE_STATUS.READY, subnet=subnet
            )
            for subnet in subnets
        ]
        # Filter for this network.  Take one in the middle to avoid
        # coincidental success based on ordering.
        pick = 1
        self.assertConstrainedNodes(
            {nodes[pick]}, {"subnets": ["vlan:%d" % vlan_tags[pick]]}
        )

    def test_subnets_filter_ignores_macs_on_other_subnets(self):
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        factory.make_Node_with_Interface_on_Subnet()
        self.assertConstrainedNodes({node}, {"subnets": [subnet.name]})

    def test_subnets_filter_ignores_other_subnets_on_mac(self):
        subnets = [factory.make_Subnet() for _ in range(3)]
        node = factory.make_Node()
        for subnet in subnets:
            nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
            factory.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DHCP,
                ip="",
                interface=nic,
                subnet=subnet,
            )
        self.assertConstrainedNodes({node}, {"subnets": [subnets[1].name]})

    def test_invalid_subnets(self):
        form = FilterNodeForm(data={"subnets": "ip:10.0.0.0"})
        self.assertEqual(
            (
                False,
                {
                    "subnets": [
                        "Invalid parameter: "
                        "list of subnet specifiers required."
                    ]
                },
            ),
            (form.is_valid(), form.errors),
        )

        # The validator is unit-tested separately.  This just verifies that it
        # is being consulted.
        form = FilterNodeForm(data={"subnets": ["vlan:-1"]})
        self.assertEqual(
            (
                False,
                {
                    "subnets": [
                        "VLAN tag (VID) out of range (0-4094; 0 for untagged.)"
                    ]
                },
            ),
            (form.is_valid(), form.errors),
        )

    def test_subnets_combines_filters(self):
        subnets = [factory.make_Subnet() for _ in range(3)]
        [subnet_by_name, subnet_by_ip, subnet_by_vlan] = subnets

        self.create_node_on_subnets([subnet_by_name, subnet_by_ip])
        self.create_node_on_subnets([subnet_by_name, subnet_by_vlan])
        node = self.create_node_on_subnets(
            [subnet_by_name, subnet_by_ip, subnet_by_vlan]
        )
        self.create_node_on_subnets([subnet_by_ip, subnet_by_vlan])
        self.create_node_on_subnets([])

        self.assertConstrainedNodes(
            {node},
            {
                "subnets": [
                    subnet_by_name.name,
                    "ip:%s"
                    % factory.pick_ip_in_network(subnet_by_ip.get_ipnetwork()),
                    "vlan:%d" % subnet_by_vlan.vlan.vid,
                ]
            },
        )

    def test_subnets_ignores_other_subnets(self):
        [this_subnet, other_subnet] = [factory.make_Subnet() for _ in range(2)]
        node = self.create_node_on_subnets([this_subnet, other_subnet])
        self.assertConstrainedNodes([node], {"subnets": [this_subnet.name]})

    def test_not_subnets_filters_by_name(self):
        [subnet, not_subnet] = [factory.make_Subnet() for _ in range(2)]
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        self.assertConstrainedNodes({node}, {"not_subnets": [not_subnet.name]})

    def test_not_subnets_filters_by_ip(self):
        [subnet, not_subnet] = [factory.make_Subnet() for _ in range(2)]
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        self.assertConstrainedNodes(
            {node},
            {
                "not_subnets": [
                    "ip:%s"
                    % factory.pick_ip_in_network(not_subnet.get_ipnetwork())
                ]
            },
        )

    def test_not_subnets_filters_by_vlan_tag(self):
        vlan_tags = list(range(1, 3))
        subnets = [
            factory.make_Subnet(vlan=factory.make_VLAN(vid=tag))
            for tag in vlan_tags
        ]
        nodes = [
            factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
            for subnet in subnets
        ]
        self.assertConstrainedNodes(
            {nodes[0]}, {"not_subnets": ["vlan:%d" % vlan_tags[1]]}
        )

    def test_not_subnets_accepts_nodes_without_subnet_connections(self):
        interfaceless_node = factory.make_Node()
        unconnected_node = factory.make_Node()
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=unconnected_node)
        self.assertConstrainedNodes(
            {interfaceless_node, unconnected_node},
            {"not_subnets": [factory.make_Subnet().name]},
        )

    def test_not_subnets_exclude_node_with_any_interface(self):
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        other_subnet = factory.make_Subnet()
        other_nic = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            interface=other_nic,
            subnet=other_subnet,
        )
        self.assertConstrainedNodes([], {"not_subnets": [subnet.name]})

    def test_not_subnets_excludes_node_with_interface_on_any_not_subnet(self):
        factory.make_Subnet()
        not_subnet = factory.make_Subnet()
        factory.make_Node_with_Interface_on_Subnet(subnet=not_subnet)
        self.assertConstrainedNodes([], {"not_subnets": [not_subnet.name]})

    def test_invalid_not_subnets(self):
        form = FilterNodeForm(data={"not_subnets": "ip:10.0.0.0"})
        self.assertEqual(
            (
                False,
                {
                    "not_subnets": [
                        "Invalid parameter: "
                        "list of subnet specifiers required."
                    ]
                },
            ),
            (form.is_valid(), form.errors),
        )

        # The validator is unit-tested separately.  This just verifies that it
        # is being consulted.
        form = FilterNodeForm(data={"not_subnets": ["vlan:-1"]})
        self.assertEqual(
            (
                False,
                {
                    "not_subnets": [
                        "VLAN tag (VID) out of range (0-4094; 0 for untagged.)"
                    ]
                },
            ),
            (form.is_valid(), form.errors),
        )

    def test_not_subnets_combines_filters(self):
        subnets = [factory.make_Subnet() for _ in range(5)]
        [
            subnet_by_name,
            subnet_by_ip,
            subnet_by_vlan,
            other_subnet,
            remaining_subnet,
        ] = subnets

        self.create_node_on_subnets([subnet_by_name])
        self.create_node_on_subnets([subnet_by_name, subnet_by_ip])
        self.create_node_on_subnets([subnet_by_name, subnet_by_vlan])
        self.create_node_on_subnets([subnet_by_vlan])
        self.create_node_on_subnets([subnet_by_vlan, other_subnet])
        node = self.create_node_on_subnets([remaining_subnet])

        self.assertConstrainedNodes(
            {node},
            {
                "not_subnets": [
                    subnet_by_name.name,
                    "ip:%s"
                    % factory.pick_ip_in_network(subnet_by_ip.get_ipnetwork()),
                    "vlan:%d" % subnet_by_vlan.vlan.vid,
                ]
            },
        )

    def test_link_speed(self):
        node1 = factory.make_Node_with_Interface_on_Subnet(
            interface_speed=1000, link_speed=100
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            interface_speed=1000, link_speed=1000
        )
        nodes = [node1, node2]
        self.assertConstrainedNodes(nodes, {"link_speed": "0"})
        self.assertConstrainedNodes(nodes, {"link_speed": "100"})
        self.assertConstrainedNodes([node2], {"link_speed": "1000"})
        self.assertConstrainedNodes([], {"link_speed": "10000"})

    def test_invalid_link_speed(self):
        form = FilterNodeForm(data={"link_speed": "invalid"})
        self.assertEqual(
            (False, {"link_speed": ["Invalid link speed: number required."]}),
            (form.is_valid(), form.errors),
        )

    def test_zone(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        node3 = factory.make_Node()
        zone1 = factory.make_Zone(nodes=[node1, node2])
        zone2 = factory.make_Zone()

        self.assertConstrainedNodes([node1, node2], {"zone": zone1.name})
        self.assertConstrainedNodes([node1, node2, node3], {"zone": ""})
        self.assertConstrainedNodes([node1, node2, node3], {})
        self.assertConstrainedNodes([], {"zone": zone2.name})

    def test_invalid_zone(self):
        form = FilterNodeForm(data={"zone": "unknown"})
        self.assertEqual(
            (False, {"zone": ["No such zone(s): unknown."]}),
            (form.is_valid(), form.errors),
        )

    def test_not_in_zone_excludes_given_zones(self):
        bad_zone = factory.make_Zone()
        good_zone = factory.make_Zone()
        ineligible_nodes = [factory.make_Node(zone=bad_zone) for _ in range(2)]
        eligible_nodes = [factory.make_Node(zone=good_zone) for _ in range(2)]
        self.assertConstrainedNodes(
            eligible_nodes,
            {"not_in_zone": [node.zone.name for node in ineligible_nodes]},
        )

    def test_not_in_zone_with_required_zone_yields_no_nodes(self):
        zone = factory.make_Zone()
        factory.make_Node(zone=zone)
        self.assertConstrainedNodes([], {"zone": zone, "not_in_zone": [zone]})

    def test_validates_not_in_zone(self):
        bad_zone_name = "#$&*!"
        form = FilterNodeForm(data={"not_in_zone": [bad_zone_name]})
        self.assertFalse(form.is_valid())
        self.assertEqual(["not_in_zone"], list(form.errors.keys()))

    def test_not_in_zone_must_be_zone_name(self):
        non_zone = factory.make_name("nonzone")
        form = FilterNodeForm(data={"not_in_zone": [non_zone]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"not_in_zone": ["No such zone(s): %s." % non_zone]}, form.errors
        )

    def test_not_in_zone_can_exclude_multiple_zones(self):
        # Three nodes, all in different physical zones.  If we say we don't
        # want the first node's zone or the second node's zone, we get the node
        # in the remaining zone.
        nodes = [factory.make_Node(zone=factory.make_Zone()) for _ in range(3)]
        self.assertConstrainedNodes(
            [nodes[2]],
            {"not_in_zone": [nodes[0].zone.name, nodes[1].zone.name]},
        )

    def test_pool(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        node3 = factory.make_Node()

        pool1 = factory.make_ResourcePool(nodes=[node1, node2])
        pool2 = factory.make_ResourcePool()

        self.assertConstrainedNodes([node1, node2], {"pool": pool1.name})
        self.assertConstrainedNodes([node1, node2, node3], {"pool": ""})
        self.assertConstrainedNodes([node1, node2, node3], {})
        self.assertConstrainedNodes([], {"pool": pool2.name})

    def test_invalid_pool(self):
        form = FilterNodeForm(data={"pool": "unknown"})
        self.assertEqual(
            (False, {"pool": ["No such pool(s): unknown."]}),
            (form.is_valid(), form.errors),
        )

    def test_not_in_pool_excludes_given_pools(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        node3 = factory.make_Node()
        node4 = factory.make_Node()

        factory.make_ResourcePool(nodes=[node1, node2])
        pool2 = factory.make_ResourcePool(nodes=[node3, node4])
        self.assertConstrainedNodes(
            [node1, node2], {"not_in_pool": [pool2.name]}
        )

    def test_not_in_pool_with_required_pool_yields_no_nodes(self):
        node = factory.make_Node()
        pool = factory.make_ResourcePool(nodes=[node])
        self.assertConstrainedNodes(
            [], {"pool": pool.name, "not_in_pool": [pool.name]}
        )

    def test_validates_not_in_pool(self):
        bad_pool_name = "#$&*!"
        form = FilterNodeForm(data={"not_in_pool": [bad_pool_name]})
        self.assertFalse(form.is_valid())
        self.assertEqual(["not_in_pool"], list(form.errors.keys()))

    def test_not_in_pool_must_be_pool_name(self):
        non_pool = factory.make_name("nonpool")
        form = FilterNodeForm(data={"not_in_pool": [non_pool]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"not_in_pool": ["No such pool(s): %s." % non_pool]}, form.errors
        )

    def test_not_in_pool_can_exclude_multiple_pool(self):
        # Three nodes, all in different pools.  If we say we don't
        # want the first node's pool or the second node's pool, we get the node
        # in the remaining pool.
        node1 = factory.make_Node()
        pool1 = factory.make_ResourcePool(nodes=[node1])
        node2 = factory.make_Node()
        pool2 = factory.make_ResourcePool(nodes=[node2])
        node3 = factory.make_Node()
        factory.make_ResourcePool(nodes=[node3])

        self.assertConstrainedNodes(
            [node3], {"not_in_pool": [pool1.name, pool2.name]}
        )

    def test_tags(self):
        tag_big = factory.make_Tag(name="big")
        tag_burly = factory.make_Tag(name="burly")
        node_big = factory.make_Node()
        node_big.tags.add(tag_big)
        node_burly = factory.make_Node()
        node_burly.tags.add(tag_burly)
        node_bignburly = factory.make_Node()
        node_bignburly.tags.add(tag_big)
        node_bignburly.tags.add(tag_burly)
        self.assertConstrainedNodes(
            [node_big, node_bignburly], {"tags": ["big"]}
        )
        self.assertConstrainedNodes(
            [node_burly, node_bignburly], {"tags": ["burly"]}
        )
        self.assertConstrainedNodes(
            [node_bignburly], {"tags": ["big", "burly"]}
        )

    def test_not_tags_negates_individual_tags(self):
        tag = factory.make_Tag()
        tagged_node = factory.make_Node()
        tagged_node.tags.add(tag)
        untagged_node = factory.make_Node()

        self.assertConstrainedNodes([untagged_node], {"not_tags": [tag.name]})

    def test_not_tags_negates_multiple_tags(self):
        tagged_node = factory.make_Node()
        tags = [
            factory.make_Tag("spam"),
            factory.make_Tag("eggs"),
            factory.make_Tag("ham"),
        ]
        tagged_node.tags.set(tags)
        partially_tagged_node = factory.make_Node()
        partially_tagged_node.tags.add(tags[0])

        self.assertConstrainedNodes(
            [partially_tagged_node], {"not_tags": ["eggs", "ham"]}
        )

    def test_invalid_tags(self):
        form = FilterNodeForm(data={"tags": ["big", "unknown"]})
        self.assertFalse(form.is_valid())
        tags_error = form.errors.get("tags")
        self.assertIn(
            tags_error,
            (
                [("No such tag(s): 'big', 'unknown'.")],
                [("No such tag(s): 'unknown', 'big'.")],
            ),
        )

    def test_storage_invalid_constraint(self):
        form = FilterNodeForm(data={"storage": "10(ssd,20"})
        self.assertEqual(
            (
                False,
                {"storage": ['Malformed storage constraint, "10(ssd,20".']},
            ),
            (form.is_valid(), form.errors),
        )

    def test_storage_invalid_size_constraint(self):
        form = FilterNodeForm(data={"storage": "abc"})
        self.assertEqual(
            (False, {"storage": ['Malformed storage constraint, "abc".']}),
            (form.is_valid(), form.errors),
        )

    def test_storage_matches_disk_with_root_mount_on_disk(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node1, bootable=True)
        block_device = factory.make_PhysicalBlockDevice(node=node1)
        factory.make_Filesystem(mount_point="/", block_device=block_device)
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node2, bootable=True)
        self.assertConstrainedNodes([node1], {"storage": "0"})

    def test_storage_matches_disk_with_root_mount_on_partition(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, formatted_root=True, bootable=True
        )
        node2 = factory.make_Node(with_boot_disk=False)
        block_device = factory.make_PhysicalBlockDevice(
            node=node2, bootable=True
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(mount_point="/srv", partition=partition)
        self.assertConstrainedNodes([node1], {"storage": "0"})

    def test_storage_matches_partition_with_root_mount(self):
        node1 = factory.make_Node(with_boot_disk=False)
        block_device = factory.make_PhysicalBlockDevice(
            node=node1, bootable=True
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        factory.make_Filesystem(mount_point="/", partition=partition)
        node2 = factory.make_Node(with_boot_disk=False)
        block_device2 = factory.make_PhysicalBlockDevice(
            node=node2, bootable=True
        )
        partition_table2 = factory.make_PartitionTable(
            block_device=block_device2
        )
        partition2 = factory.make_Partition(partition_table=partition_table2)
        factory.make_Filesystem(mount_point="/srv", partition=partition2)
        _, storage, _ = self.assertConstrainedNodes(
            [node1], {"storage": "part:0(partition)"}
        )
        self.assertEqual(
            {node1.id: {"partition:%d" % partition.id: "part"}}, storage
        )

    def test_storage_single_contraint_matches_all_sizes_larger(self):
        node1 = factory.make_Node(with_boot_disk=False)
        # 1gb block device
        factory.make_PhysicalBlockDevice(
            node=node1, size=1 * (1000**3), formatted_root=True
        )
        node2 = factory.make_Node(with_boot_disk=False)
        # 4gb block device
        factory.make_PhysicalBlockDevice(
            node=node2, size=4 * (1000**3), formatted_root=True
        )
        node3 = factory.make_Node(with_boot_disk=False)
        # 8gb block device
        factory.make_PhysicalBlockDevice(
            node=node3, size=8 * (1000**3), formatted_root=True
        )
        # all nodes with physical devices larger than 2gb
        self.assertConstrainedNodes([node2, node3], {"storage": "2"})

    def test_storage_single_contraint_matches_on_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, tags=["ssd"], formatted_root=True, bootable=True
        )
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node2, tags=["rotary"], formatted_root=True, bootable=True
        )
        self.assertConstrainedNodes([node1], {"storage": "0(ssd)"})

    def test_storage_single_constraint_matches_with_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        block_device = factory.make_PhysicalBlockDevice(
            node=node1, bootable=True
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(
            partition_table=partition_table, tags=["ssd-part"]
        )
        factory.make_Filesystem(mount_point="/", partition=partition)
        node2 = factory.make_Node(with_boot_disk=False)
        block_device2 = factory.make_PhysicalBlockDevice(
            node=node2, bootable=True
        )
        partition_table2 = factory.make_PartitionTable(
            block_device=block_device2
        )
        partition2 = factory.make_Partition(
            partition_table=partition_table2, tags=["rotary-part"]
        )
        factory.make_Filesystem(mount_point="/", partition=partition2)
        _, storage, _ = self.assertConstrainedNodes(
            [node1], {"storage": "part:0(partition,ssd-part)"}
        )
        self.assertEqual(
            {node1.id: {"partition:%d" % partition.id: "part"}}, storage
        )

    def test_storage_single_contraint_matches_decimal_size(self):
        node1 = factory.make_Node(with_boot_disk=False)
        # 2gb, 4gb block device
        factory.make_PhysicalBlockDevice(node=node1, size=2 * (1000**3))
        factory.make_PhysicalBlockDevice(
            node=node1, size=4 * (1000**3), formatted_root=True
        )
        node2 = factory.make_Node(with_boot_disk=False)
        # 1gb block device
        factory.make_PhysicalBlockDevice(
            node=node2, size=1 * (1000**3), formatted_root=True
        )
        self.assertConstrainedNodes([node1], {"storage": "1.5"})

    def test_storage_single_contraint_allows_root_on_virtual(self):
        node1 = factory.make_Node(with_boot_disk=False)
        physical = factory.make_PhysicalBlockDevice(
            node=node1, size=(6 * (1000**3))
        )
        partition_table = factory.make_PartitionTable(block_device=physical)
        partition = factory.make_Partition(
            partition_table=partition_table, size=5 * (1000**3)
        )
        pv = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition
        )
        vg = factory.make_FilesystemGroup(
            filesystems=[pv], group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        virtual = factory.make_VirtualBlockDevice(
            filesystem_group=vg, node=node1
        )
        factory.make_Filesystem(mount_point="/", block_device=virtual)
        self.assertConstrainedNodes([node1], {"storage": "0"})

    def test_storage_single_contraint_size_on_virtual(self):
        node1 = factory.make_Node(with_boot_disk=False)
        physical = factory.make_PhysicalBlockDevice(
            node=node1, size=(6 * (1000**3))
        )
        partition_table = factory.make_PartitionTable(block_device=physical)
        partition = factory.make_Partition(
            partition_table=partition_table, size=(5.5 * (1000**3))
        )
        pv = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition
        )
        vg = factory.make_FilesystemGroup(
            filesystems=[pv], group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        virtual = factory.make_VirtualBlockDevice(
            filesystem_group=vg, node=node1, size=(5 * (1000**3))
        )
        factory.make_Filesystem(mount_point="/", block_device=virtual)
        self.assertConstrainedNodes([node1], {"storage": "4"})

    def test_storage_multi_contraint_matches_physical_and_unused(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, formatted_root=True, bootable=True
        )
        # 1gb, 2gb, 3gb block device
        factory.make_PhysicalBlockDevice(node=node1, size=1 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node1, size=2 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node1, size=3 * (1000**3))
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node2, formatted_root=True)
        # 5gb, 6gb, 7gb block device
        factory.make_PhysicalBlockDevice(node=node2, size=5 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node2, size=6 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node2, size=7 * (1000**3))
        node3 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node3, formatted_root=True)
        # 8gb, 9gb, 10gb block device
        factory.make_PhysicalBlockDevice(node=node3, size=8 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node3, size=9 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node3, size=10 * (1000**3))
        # all nodes with physical devices larger than 2gb
        self.assertConstrainedNodes([node2, node3], {"storage": "0,4,4,4"})

    def test_storage_multi_contraint_matches_virtual_and_unused(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, formatted_root=True, bootable=True
        )
        # 1gb, 2gb, 3gb block device
        factory.make_VirtualBlockDevice(node=node1, size=1 * (1000**3))
        factory.make_VirtualBlockDevice(node=node1, size=2 * (1000**3))
        factory.make_VirtualBlockDevice(node=node1, size=3 * (1000**3))
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node2, formatted_root=True, bootable=True
        )
        # 5gb, 6gb, 7gb block device
        factory.make_VirtualBlockDevice(node=node2, size=5 * (1000**3))
        factory.make_VirtualBlockDevice(node=node2, size=6 * (1000**3))
        factory.make_VirtualBlockDevice(node=node2, size=7 * (1000**3))
        node3 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node3, formatted_root=True, bootable=True
        )
        # 8gb, 9gb, 10gb block device
        factory.make_VirtualBlockDevice(node=node3, size=8 * (1000**3))
        factory.make_VirtualBlockDevice(node=node3, size=9 * (1000**3))
        factory.make_VirtualBlockDevice(node=node3, size=10 * (1000**3))
        # all nodes with physical devices larger than 2gb
        self.assertConstrainedNodes([node2, node3], {"storage": "0,4,4,4"})

    def test_storage_multi_contraint_matches_partition_unused(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, formatted_root=True, bootable=True
        )
        # 1gb, 2gb, 3gb block device
        factory.make_PhysicalBlockDevice(node=node1, size=1 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node1, size=2 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node1, size=3 * (1000**3))
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node2, formatted_root=True, bootable=True
        )
        # 5gb, 6gb, 7gb block device
        factory.make_PhysicalBlockDevice(node=node2, size=5 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node2, size=6 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node2, size=7 * (1000**3))
        # node2: used partition on block device
        used_partition = factory.make_Partition(
            partition_table=factory.make_PartitionTable(
                block_device=factory.make_PhysicalBlockDevice(node=node2)
            )
        )
        factory.make_Filesystem(mount_point="/srv", partition=used_partition)
        node3 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node3, formatted_root=True, bootable=True
        )
        # 8gb, 9gb, 10gb block device
        factory.make_PhysicalBlockDevice(node=node3, size=8 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node3, size=9 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node3, size=10 * (1000**3))
        # node3: un-used partition on block device
        block_device = factory.make_PhysicalBlockDevice(
            node=node3, bootable=True
        )
        partition_table = factory.make_PartitionTable(
            block_device=block_device
        )
        partition = factory.make_Partition(partition_table=partition_table)
        # all nodes with physical devices larger than 2gb
        _, storage, _ = self.assertConstrainedNodes(
            [node3], {"storage": "0,4,4,4,part:0(partition)"}
        )
        self.assertEqual(
            {node3.id: {"partition:%d" % partition.id: "part"}}, storage
        )

    def test_storage_multi_contraint_matches_on_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, tags=["ssd"], formatted_root=True, bootable=True
        )
        factory.make_PhysicalBlockDevice(node=node1, tags=["ssd", "removable"])
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node2, tags=["ssd"], formatted_root=True
        )
        factory.make_PhysicalBlockDevice(node=node2, tags=["ssd", "sata"])
        self.assertConstrainedNodes(
            [node1], {"storage": "0(ssd),0(ssd,removable)"}
        )

    def test_storage_multi_contraint_matches_on_size_and_tags(self):
        node1 = factory.make_Node(with_boot_disk=False)
        # 1gb, 2gb block device
        factory.make_PhysicalBlockDevice(
            node=node1, size=1 * (1000**3), tags=["ssd"], formatted_root=True
        )
        factory.make_PhysicalBlockDevice(
            node=node1, size=2 * (1000**3), tags=["ssd"]
        )
        node2 = factory.make_Node(with_boot_disk=False)
        # 4gb, 5gb block device
        factory.make_PhysicalBlockDevice(
            node=node2, size=4 * (1000**3), tags=["ssd"], formatted_root=True
        )
        factory.make_PhysicalBlockDevice(
            node=node2, size=5 * (1000**3), tags=["ssd"]
        )
        self.assertConstrainedNodes([node2], {"storage": "3(ssd),3(ssd)"})

    def test_storage_first_constraint_matches_blockdevice_with_root(self):
        """
        Make sure a constraint like 10(ssd),5,20 will match a node with a
        11(ssd) first device, a 21 second device and a 10 third device,
        but not a 5/20/10(ssd) node
        """
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node1, size=21 * (1000**3))
        factory.make_PhysicalBlockDevice(
            node=node1, size=11 * (1000**3), tags=["ssd"]
        )
        factory.make_PhysicalBlockDevice(
            node=node1, size=6 * (1000**3), formatted_root=True
        )
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(node=node2, size=6 * (1000**3))
        factory.make_PhysicalBlockDevice(node=node2, size=21 * (1000**3))
        factory.make_PhysicalBlockDevice(
            node=node2,
            size=11 * (1000**3),
            tags=["ssd"],
            formatted_root=True,
        )
        self.assertConstrainedNodes([node2], {"storage": "10(ssd),5,20"})

    def test_storage_multi_contraint_matches_large_disk_count(self):
        node1 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node1, formatted_root=True, bootable=True
        )
        for _ in range(10):
            factory.make_PhysicalBlockDevice(node=node1)
        node2 = factory.make_Node(with_boot_disk=False)
        factory.make_PhysicalBlockDevice(
            node=node2, formatted_root=True, bootable=True
        )
        for _ in range(5):
            factory.make_PhysicalBlockDevice(node=node2)
        self.assertConstrainedNodes(
            [node1], {"storage": "0,0,0,0,0,0,0,0,0,0"}
        )

    def test_storage_with_named_constraints(self):
        node1 = factory.make_Node(with_boot_disk=False)
        physical = factory.make_PhysicalBlockDevice(
            node=node1, size=11 * (1000**3)
        )
        partition_table = factory.make_PartitionTable(block_device=physical)
        partition = factory.make_Partition(
            partition_table=partition_table, size=10 * (1000**3)
        )
        pv = factory.make_Filesystem(
            fstype=FILESYSTEM_TYPE.LVM_PV, partition=partition
        )
        vg = factory.make_FilesystemGroup(
            filesystems=[pv], group_type=FILESYSTEM_GROUP_TYPE.LVM_VG
        )
        virtual = factory.make_VirtualBlockDevice(
            filesystem_group=vg, node=node1, size=9 * (1000**3), tags=["lvm"]
        )
        factory.make_Filesystem(mount_point="/", block_device=virtual)
        physical = factory.make_PhysicalBlockDevice(
            node=node1, size=6 * (1000**3), tags=["rotary", "5400rpm"]
        )
        other = factory.make_PhysicalBlockDevice(
            node=node1, size=21 * (1000**3)
        )
        form = FilterNodeForm(
            {"storage": "root:8(lvm),physical:5(rotary,5400rpm),other:20"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        filtered_nodes, constraint_map, _ = form.filter_nodes(
            Machine.objects.all()
        )
        node = filtered_nodes[0]
        constraints = {
            value: key for key, value in constraint_map[node.id].items()
        }
        disk0 = node.current_config.blockdevice_set.get(id=constraints["root"])
        self.assertEqual(virtual.id, disk0.id)
        disk1 = node.current_config.blockdevice_set.get(
            id=constraints["physical"]
        )
        self.assertEqual(physical.id, disk1.id)
        disk2 = node.current_config.blockdevice_set.get(
            id=constraints["other"]
        )
        self.assertEqual(other.id, disk2.id)

    def test_fabrics_constraint(self):
        fabric1 = factory.make_Fabric(name="fabric1")
        fabric2 = factory.make_Fabric(name="fabric2")
        factory.make_Node_with_Interface_on_Subnet(fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(fabric=fabric2)
        form = FilterNodeForm({"fabrics": ["fabric2"]})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_not_fabrics_constraint(self):
        fabric1 = factory.make_Fabric(name="fabric1")
        fabric2 = factory.make_Fabric(name="fabric2")
        factory.make_Node_with_Interface_on_Subnet(fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(fabric=fabric2)
        form = FilterNodeForm({"not_fabrics": ["fabric1"]})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_fabric_classes_constraint(self):
        fabric1 = factory.make_Fabric(class_type="10g")
        fabric2 = factory.make_Fabric(class_type="1g")
        factory.make_Node_with_Interface_on_Subnet(fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(fabric=fabric2)
        form = FilterNodeForm({"fabric_classes": ["1g"]})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_not_fabric_classes_constraint(self):
        fabric1 = factory.make_Fabric(class_type="10g")
        fabric2 = factory.make_Fabric(class_type="1g")
        factory.make_Node_with_Interface_on_Subnet(fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(fabric=fabric2)
        form = FilterNodeForm({"not_fabric_classes": ["10g"]})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_interfaces_constraint_rejected_if_syntax_is_invalid(self):
        factory.make_Node_with_Interface_on_Subnet()
        form = FilterNodeForm({"interfaces": "label:x"})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertIn("interfaces", form.errors)

    def test_interfaces_constraint_rejected_if_key_is_invalid(self):
        factory.make_Node_with_Interface_on_Subnet()
        form = FilterNodeForm(
            {"interfaces": "label:chirp_chirp_thing=silenced"}
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertIn("interfaces", form.errors)

    def test_interfaces_constraint_validated(self):
        factory.make_Node_with_Interface_on_Subnet()
        form = FilterNodeForm({"interfaces": "label:fabric=fabric-0"})
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_interfaces_constraint_works_with_object_form(self):
        factory.make_Node_with_Interface_on_Subnet()
        form = FilterNodeForm(
            {"interfaces": LabeledConstraintMap("label:fabric=fabric-0")}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_interfaces_constraint_works_for_subnet(self):
        subnet = factory.make_Subnet()
        factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        form = FilterNodeForm(
            {
                "interfaces": LabeledConstraintMap(
                    "eth0:subnet=%s" % subnet.cidr
                )
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_interfaces_constraint_works_for_ip_address(self):
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(interface=node.get_boot_interface())
        form = FilterNodeForm(
            {"interfaces": LabeledConstraintMap("eth0:ip=%s" % str(ip.ip))}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_not_preconfig_interfaces_constraint_works_for_unconfigured(self):
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        iface = node.get_boot_interface()
        ip = factory.make_StaticIPAddress(interface=iface)
        lcm = LabeledConstraintMap("eth0:ip=%s,mode=unconfigured" % str(ip.ip))
        result = nodes_by_interface(lcm, preconfigured=False)
        self.assertEqual("unconfigured", result.ip_modes["eth0"])
        # The mode should have been removed after being placed in the result.
        self.assertNotIn("mode", lcm)

    def test_interfaces_constraint_with_multiple_labels_and_values_validated(
        self,
    ):
        factory.make_Node_with_Interface_on_Subnet()
        form = FilterNodeForm(
            {
                "interfaces": "label:fabric=fabric-0,fabric=fabric-1,space=default;"
                "label2:fabric=fabric-3,fabric=fabric-4,space=foo"
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_interfaces_filters_by_fabric_class(self):
        fabric1 = factory.make_Fabric(class_type="1g")
        fabric2 = factory.make_Fabric(class_type="10g")
        node1 = factory.make_Node_with_Interface_on_Subnet(fabric=fabric1)
        node2 = factory.make_Node_with_Interface_on_Subnet(fabric=fabric2)

        form = FilterNodeForm({"interfaces": "label:fabric_class=10g"})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

        form = FilterNodeForm({"interfaces": "label:fabric_class=1g"})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node1], filtered_nodes)

    def test_interfaces_filters_work_with_multiple_labels(self):
        fabric1 = factory.make_Fabric(class_type="1g")
        fabric2 = factory.make_Fabric(class_type="10g")
        vlan1 = factory.make_VLAN(vid=1, fabric=fabric1)
        vlan2 = factory.make_VLAN(vid=2, fabric=fabric2)
        node1 = factory.make_Node_with_Interface_on_Subnet(
            fabric=fabric1, vlan=vlan1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            fabric=fabric2, vlan=vlan2
        )

        form = FilterNodeForm(
            {"interfaces": "fabric:fabric_class=1g;vlan:vid=1"}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node1], filtered_nodes)

        form = FilterNodeForm(
            {"interfaces": "label:fabric_class=10g;vlan:vid=2"}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_interfaces_filters_same_key_treated_as_OR_operation(self):
        fabric1 = factory.make_Fabric(class_type="1g")
        fabric2 = factory.make_Fabric(class_type="10g")
        vlan1 = factory.make_VLAN(vid=1, fabric=fabric1)
        vlan2 = factory.make_VLAN(vid=2, fabric=fabric2)
        node1 = factory.make_Node_with_Interface_on_Subnet(
            fabric=fabric1, vlan=vlan1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            fabric=fabric2, vlan=vlan2
        )

        form = FilterNodeForm(
            {
                "interfaces": "fabric:fabric_class=1g,fabric_class=10g;vlan:vid=1"
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node1], filtered_nodes)

        form = FilterNodeForm(
            {"interfaces": "label:fabric_class=10g,fabric_class=1g;vlan:vid=2"}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_interfaces_filters_different_key_treated_as_AND_operation(self):
        fabric1 = factory.make_Fabric(class_type="1g")
        fabric2 = factory.make_Fabric(class_type="10g")
        vlan1 = factory.make_VLAN(vid=1, fabric=fabric1)
        vlan2 = factory.make_VLAN(vid=2, fabric=fabric2)
        node1 = factory.make_Node_with_Interface_on_Subnet(
            fabric=fabric1, vlan=vlan1
        )
        node2 = factory.make_Node_with_Interface_on_Subnet(
            fabric=fabric2, vlan=vlan2
        )

        form = FilterNodeForm({"interfaces": "none:fabric_class=1g,vid=2"})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([], filtered_nodes)

        form = FilterNodeForm(
            {"interfaces": "any:fabric_class=10g,fabric_class=1g,vid=1,vid=2"}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node1, node2], filtered_nodes)

    def test_owner(self):
        user1 = factory.make_User()
        user2 = factory.make_User()
        factory.make_Node(owner=user1)
        node2 = factory.make_Node(owner=user2)
        form = FilterNodeForm({"owner": user2.username})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_power_state(self):
        factory.make_Node(power_state=POWER_STATE.OFF)
        node2 = factory.make_Node(power_state=POWER_STATE.ON)
        form = FilterNodeForm({"power_state": POWER_STATE.ON})
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects)
        self.assertCountEqual([node2], filtered_nodes)

    def test_combined_constraints(self):
        tag_big = factory.make_Tag(name="big")
        arch = "%s/generic" % factory.make_name("arch")
        wrong_arch = "%s/generic" % factory.make_name("arch")
        patch_usable_architectures(self, [arch, wrong_arch])
        node_big = factory.make_Node(architecture=arch)
        node_big.tags.add(tag_big)
        factory.make_Node(architecture=arch)
        node_big_other_arch = factory.make_Node(architecture=wrong_arch)
        node_big_other_arch.tags.add(tag_big)
        self.assertConstrainedNodes(
            [node_big, node_big_other_arch], {"tags": ["big"]}
        )
        self.assertConstrainedNodes(
            [node_big], {"arch": arch, "tags": ["big"]}
        )

    def test_wildcard_arch_constraint(self):
        patch_usable_architectures(self, ["foo/bar", "foo/baz"])
        form = FilterNodeForm(data={"arch": "foo"})
        self.assertTrue(form.is_valid())

    def test_invalid_combined_constraints(self):
        form = FilterNodeForm(data={"tags": ["unknown"], "arch": "invalid"})
        self.assertEqual(
            (
                False,
                {
                    "arch": ["Architecture not recognised."],
                    "tags": ["No such tag(s): 'unknown'."],
                },
            ),
            (form.is_valid(), form.errors),
        )

    def test_returns_distinct_nodes(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        nic1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            interface=nic1,
            subnet=subnet,
        )
        nic2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DHCP,
            ip="",
            interface=nic2,
            subnet=subnet,
        )
        self.assertConstrainedNodes({node}, {"subnets": [subnet.name]})

    def test_describe_constraints_returns_empty_if_no_constraints(self):
        form = FilterNodeForm(data={})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual("", form.describe_constraints())

    def test_describe_constraints_shows_arch_as_special_case(self):
        # The "arch" field is technically a single-valued string field
        # on the form, but its "cleaning" produces a list of strings.
        arch = self.set_usable_arch()
        form = FilterNodeForm(data={"arch": arch})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual("arch=%s" % arch, form.describe_constraints())

    def test_describe_constraints_shows_multi_constraint(self):
        tag = factory.make_Tag()
        form = FilterNodeForm(data={"tags": [tag.name]})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual("tags=%s" % tag.name, form.describe_constraints())

    def test_describe_constraints_sorts_constraints(self):
        zone = factory.make_Zone()
        pool = factory.make_ResourcePool()
        form = FilterNodeForm(data={"pool": pool, "zone": zone})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            f"pool={pool} zone={zone}", form.describe_constraints()
        )

    def test_describe_constraints_combines_constraint_values(self):
        tag1 = factory.make_Tag()
        tag2 = factory.make_Tag()
        form = FilterNodeForm(data={"tags": [tag1.name, tag2.name]})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            "tags=%s,%s" % tuple(sorted([tag1.name, tag2.name])),
            form.describe_constraints(),
        )

    def test_describe_constraints_shows_all_constraints(self):
        arch = self.set_usable_arch()
        constraints = {
            "arch": arch,
            "not_arch": arch,
            "system_id": "asfghc",
            "cpu_count": random.randint(1, 32),
            "cpu_speed": random.randint(1, 32),
            "devices": "vendor_id=8086",
            "mem": random.randint(1024, 256 * 1024),
            "tags": [factory.make_Tag().name],
            "not_tags": [factory.make_Tag().name],
            "subnets": [factory.make_Subnet().name],
            "not_subnets": [factory.make_Subnet().name],
            "link_speed": random.randint(100, 10000),
            "vlans": ["name:" + factory.make_VLAN(name=RANDOM).name],
            "not_vlans": ["name:" + factory.make_VLAN(name=RANDOM).name],
            "zone": factory.make_Zone(),
            "not_in_zone": [factory.make_Zone().name],
            "pool": factory.make_ResourcePool(),
            "not_in_pool": [factory.make_ResourcePool().name],
            "pod": factory.make_name(),
            "not_pod": factory.make_name(),
            "pod_type": factory.make_name(),
            "not_pod_type": factory.make_name(),
            "storage": "0(ssd),10(ssd)",
            "interfaces": "label:fabric=fabric-0",
            "fabrics": [factory.make_Fabric().name],
            "not_fabrics": [factory.make_Fabric().name],
            "fabric_classes": [
                factory.make_Fabric(class_type="10g").class_type
            ],
            "not_fabric_classes": [
                factory.make_Fabric(class_type="1g").class_type
            ],
            "owner": factory.make_User().username,
            "not_owner": factory.make_User().username,
            "power_state": POWER_STATE.ON,
            "not_power_state": POWER_STATE.OFF,
            "deployment_target": DEPLOYMENT_TARGET.MEMORY,
            "not_deployment_target": DEPLOYMENT_TARGET.DISK,
        }
        form = FilterNodeForm(data=constraints)
        self.assertTrue(form.is_valid(), form.errors)
        # Check first: we didn't forget to test any attributes.  When we add
        # a constraint to the form, we'll have to add it here as well.
        self.assertEqual(form.fields.keys(), constraints.keys())

        described_constraints = {
            constraint.split("=", 1)[0]
            for constraint in form.describe_constraints().split()
        }

        self.assertEqual(constraints.keys(), described_constraints)


class TestFreeTextFilterNodeForm(MAASServerTestCase):
    form_class = FreeTextFilterNodeForm

    def setUp(self):
        from maasserver.websockets.handlers.machine import MachineHandler

        super().setUp()
        self._owner = factory.make_User()
        self._handler = MachineHandler(self._owner, {}, None)

    def get_queryset(self):
        return self._handler.get_queryset(for_list=True)

    def assertConstrainedNodes(self, nodes, data):
        form = self.form_class(data=data)
        self.assertTrue(form.is_valid(), dict(form.errors))
        filtered_nodes, storage, interfaces = form.filter_nodes(
            self.get_queryset()
        )
        self.assertCountEqual(nodes, filtered_nodes)
        return (filtered_nodes, storage, interfaces)

    def test_simple_status(self):
        node1 = factory.make_Node(status=NODE_STATUS.NEW)
        node2 = factory.make_Node(status=NODE_STATUS.FAILED_DEPLOYMENT)
        node3 = factory.make_Node(status=NODE_STATUS.NEW)
        node4 = factory.make_Node(status=NODE_STATUS.FAILED_RELEASING)
        self.assertConstrainedNodes([node1, node3], {"simple_status": "new"})
        self.assertConstrainedNodes(
            [node2, node4], {"simple_status": "failed"}
        )

    def test_match_none(self):
        node1 = factory.make_Node()
        factory.make_Node(owner=factory.make_User())
        self.assertConstrainedNodes([node1], {"owner": [None]})

    def test_substring_filter_one_substring(self):
        name = factory.make_name("hostname")
        node1 = factory.make_Node(hostname=name)
        factory.make_Node()
        self.assertConstrainedNodes(
            [node1],
            {
                "hostname": name[len("hostname-") + 1 :].swapcase(),
            },
        )

    def test_substring_filter_exact_match(self):
        name = factory.make_name("hostname")
        node1 = factory.make_Node(hostname=name)
        factory.make_Node()
        self.assertConstrainedNodes([node1], {"hostname": f"={name}"})
        self.assertConstrainedNodes([], {"hostname": f"={name.upper()}"})

    def test_substring_arch_filter(self):
        architecture = factory.make_name("arch")
        subarch = factory.make_name()
        arch = "/".join([architecture, subarch])
        factory.make_usable_boot_resource(architecture=arch)
        node1 = factory.make_Node(architecture=arch)
        factory.make_Node()
        constraints = {
            "arch": arch[:3],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_tag_filter(self):
        tags = [
            factory.make_Tag(name=factory.make_name("tag")) for _ in range(3)
        ]
        node1 = factory.make_Node()
        factory.make_Node()
        [node1.tags.add(tag) for tag in tags]
        constraints = {
            "tags": [tag.name[len("tag-") + 1 :] for tag in tags],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_system_id_filter(self):
        system_id = factory.make_name("abcdef")
        node1 = factory.make_Node(system_id=system_id)
        factory.make_Node()
        constraints = {
            "system_id": system_id[:6],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_zone_filter(self):
        zone = factory.make_Zone()
        node1 = factory.make_Node(zone=zone)
        factory.make_Node()
        constraints = {
            "zone": zone.name[:3],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_not_in_zone_filter(self):
        zone = factory.make_Zone()
        factory.make_Node(zone=zone)
        other = factory.make_Node()
        constraints = {
            "not_in_zone": [zone.name[:3]],
        }
        self.assertConstrainedNodes([other], constraints)

    def test_substring_pool_filter(self):
        pool = factory.make_ResourcePool()
        node1 = factory.make_Node(pool=pool)
        factory.make_Node()
        constraints = {
            "pool": pool.name[len("resourcepool-") + 1 :],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_not_in_pool_filter(self):
        pool = factory.make_ResourcePool()
        factory.make_Node(pool=pool)
        other = factory.make_Node()
        constraints = {
            "not_in_pool": [pool.name[len("resourcepool-") + 1 :]],
        }
        self.assertConstrainedNodes([other], constraints)

    def test_substring_pod_filter(self):
        pod = factory.make_Pod(name=factory.make_name(prefix="pod"))
        node1 = factory.make_Node(bmc=pod.as_bmc())
        factory.make_Node()
        constraints = {"pod": pod.name[len("pod-") + 1 :]}
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_fabrics_filter(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, vlan=vlan)
        factory.make_Node()
        constraints = {
            "fabrics": [fabric.name[:3]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_fabric_classes_filter(self):
        fabric_class = factory.make_name()
        fabric = factory.make_Fabric(class_type=fabric_class)
        vlan = factory.make_VLAN(fabric=fabric)
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, vlan=vlan)
        factory.make_Node()
        constraints = {
            "fabric_classes": [fabric_class[:3]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_vlans_filter(self):
        vlan = factory.make_VLAN(name=factory.make_name())
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, vlan=vlan)
        factory.make_Node()
        constraints = {
            "vlans": [vlan.name[:3]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_parent_filter(self):
        node = factory.make_Machine()
        child = factory.make_Machine(parent=node)
        factory.make_Node()
        constraints = {
            "parent": [node.system_id],
        }
        self.assertConstrainedNodes([child], constraints)

    def test_substring_no_parent_filter(self):
        node = factory.make_Machine()
        factory.make_Machine(parent=node)
        other = factory.make_Machine()
        constraints = {
            "parent": [None],
        }
        self.assertConstrainedNodes([node, other], constraints)

    def test_substring_spaces_filter(self):
        space = factory.make_Space()
        vlan = factory.make_VLAN(name=factory.make_name(), space=space)
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, vlan=vlan)
        factory.make_Node()
        constraints = {
            "spaces": [space.name[:3]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_workload_filter(self):
        key = factory.make_string(prefix="key")
        val = factory.make_string(prefix="value")
        node1 = factory.make_Node(owner_data={key: val})
        factory.make_Node()
        constraints = {
            "workloads": [f"{key}:={val}"],
        }
        self.assertConstrainedNodes([node1], constraints)
        constraints = {
            "workloads": [f"{key}:{val[2:]}"],
        }
        self.assertConstrainedNodes([node1], constraints)
        constraints = {
            "workloads": [f"{val[2:]}"],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_subnet_filter(self):
        subnet = factory.make_Subnet()
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, subnet=subnet)
        factory.make_Node()
        constraints = {
            "subnets": [str(subnet.cidr)[:3]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_ip_addresses_filter(self):
        subnet = factory.make_Subnet()
        ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
        node1 = factory.make_Node()
        factory.make_Interface(node=node1, subnet=subnet, ip=ip)
        factory.make_Node()
        constraints = {
            "ip_addresses": [str(subnet.cidr)[:3]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_interfaces_filter(self):
        subnet = factory.make_Subnet()
        ips = []
        for _ in range(3):
            ips.append(
                factory.pick_ip_in_network(subnet.get_ipnetwork(), but_not=ips)
            )
        tags = [factory.make_name("tag") for _ in range(3)]
        nodes = [factory.make_Machine() for _ in range(3)]
        ifaces = [
            factory.make_Interface(node=nodes[i], tags=[tags[i]], ip=ips[i])
            for i in range(3)
        ]
        self.assertConstrainedNodes(
            [nodes[0]], {"interfaces": f"name={ifaces[0].name}"}
        )
        self.assertConstrainedNodes(
            [nodes[1]], {"interfaces": f"tag={tags[1]}"}
        )
        self.assertConstrainedNodes(
            [nodes[0], nodes[1]],
            {
                "interfaces": [f"name={ifaces[0].name}", f"tag={tags[1]}"],
            },
        )

    def test_substring_devices_filter(self):
        nodes = [factory.make_Node() for _ in range(3)]
        node_devices = [
            factory.make_NodeDevice(
                node=node,
                vendor_id=create_unique_node_device_needle(
                    "vendor_id", partial(factory.make_hex_string, size=4)
                ),
            )
            for node in nodes
        ]
        self.assertConstrainedNodes(
            [nodes[0]], {"devices": f"vendor_id={node_devices[0].vendor_id}"}
        )

    def test_substring_storage_filters(self):
        GIB = 1000**3
        nodes = [factory.make_Node(with_boot_disk=False) for _ in range(3)]
        dev_tags = [
            factory.make_Tag(name=factory.make_name("dev")) for _ in range(3)
        ]
        part_tags = [
            factory.make_Tag(name=factory.make_name("part")) for _ in range(3)
        ]
        for i in range(3):
            disk = factory.make_PhysicalBlockDevice(
                node=nodes[i], size=(3 - i) * 10 * GIB, tags=[dev_tags[i]]
            )
            ptable = factory.make_PartitionTable(block_device=disk)
            factory.make_Partition(
                partition_table=ptable, size=(i + 3) * GIB, tags=[part_tags[i]]
            )
        self.assertConstrainedNodes(nodes, {"storage": "0"})
        self.assertConstrainedNodes([nodes[0]], {"storage": "30"})
        self.assertConstrainedNodes(
            [nodes[0]], {"storage": f"0({dev_tags[0]})"}
        )
        self.assertConstrainedNodes(
            [nodes[0]], {"storage": f"0(partition,{part_tags[0]})"}
        )
        self.assertConstrainedNodes(
            nodes,
            {
                "storage": [
                    f"0(partition,{part_tags[2]})",
                    f"0({dev_tags[1]})",
                    "30",
                ]
            },
        )

    def test_substring_hostnames_filter(self):
        hostname = factory.make_name()
        node1 = factory.make_Node(hostname=hostname)
        name2 = factory.make_name_avoiding_collision(hostname)
        factory.make_Node(hostname=name2)
        constraints = {
            "hostname": [hostname[:4]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_fqdn_filter(self):
        hostname = factory.make_name()
        node1 = factory.make_Node(hostname=hostname)
        name2 = factory.make_name_avoiding_collision(hostname)
        factory.make_Node(hostname=name2)
        constraints = {
            "fqdn": [f"{hostname[3:]}.{node1.domain.name[:3]}"],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_mac_addresses_filter(self):
        mac_address = factory.make_mac_address()
        node1 = factory.make_Node()
        factory.make_Interface(mac_address=mac_address, node=node1)
        factory.make_Node()
        constraints = {
            "mac_address": [str(mac_address)[:4]],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_agent_name_filter(self):
        name = factory.make_name()
        node1 = factory.make_Node(agent_name=name)
        factory.make_Node()
        constraints = {
            "agent_name": name,
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_description_filter(self):
        desc = factory.make_unicode_string(size=30, spaces=True)
        node1 = factory.make_Node(description=desc)
        factory.make_Node()
        constraints = {
            "description": desc.split()[0],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_error_description_filter(self):
        desc = factory.make_unicode_string(size=30, spaces=True)
        node1 = factory.make_Node(error_description=desc)
        factory.make_Node()
        constraints = {
            "error_description": desc.split()[0],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_distro_filter(self):
        osystem, releases = make_usable_osystem(self)
        series = releases[0]
        node1 = factory.make_Node(
            osystem=osystem,
            distro_series=series,
        )
        factory.make_Node()
        constraints = {
            "distro_series": series[1:],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_substring_osystem_filter(self):
        osystem, releases = make_usable_osystem(self)
        node1 = factory.make_Node(
            osystem=osystem,
            distro_series=releases[0],
        )
        factory.make_Node()
        constraints = {
            "osystem": osystem[1:],
        }
        self.assertConstrainedNodes([node1], constraints)

    def test_free_text_filter(self):
        hostname = factory.make_name("hostname")
        mac_address = factory.make_mac_address()
        pool = factory.make_ResourcePool()
        agent_name = factory.make_name()
        desc = factory.make_unicode_string(size=30, spaces=True)
        err_desc = factory.make_unicode_string(size=30, spaces=True)
        osystem, releases = make_usable_osystem(self)
        space = factory.make_Space()
        subnet = factory.make_Subnet(space=space)
        zone = factory.make_Zone()
        pod = factory.make_Pod()
        fabric_class = factory.make_name()
        fabric = factory.make_Fabric(class_type=fabric_class)
        vlan1 = factory.make_VLAN(fabric=fabric)
        vlan2 = factory.make_VLAN(name=factory.make_name(), space=space)
        key = factory.make_string(prefix="key")
        val = factory.make_string(prefix="value")
        node1 = factory.make_Node_with_Interface_on_Subnet(
            bmc=pod.as_bmc(),
            hostname=hostname,
            agent_name=agent_name,
            osystem=osystem,
            distro_series=releases[0],
            description=desc,
            error_description=err_desc,
            owner_data={key: val},
            pool=pool,
            zone=zone,
            owner=self._owner,
            subnet=subnet,
        )
        tags = [
            factory.make_Tag(name=factory.make_name("tag")) for _ in range(3)
        ]
        [node1.tags.add(tag) for tag in tags]
        factory.make_Interface(node=node1, mac_address=mac_address, vlan=vlan2)
        factory.make_Interface(node=node1, vlan=vlan1)
        factory.make_Node()
        for expr in [
            hostname,
            node1.fqdn,
            pool.name,
            osystem,
            releases[0],
            val,
            space.name,
            zone.name,
            pod.name,
            tags[1].name,
            node1.get_boot_interface().vlan.fabric.name,
        ]:
            self.assertConstrainedNodes([node1], {"free_text": expr})


class TestAcquireNodeForm(MAASServerTestCase, FilterConstraintsMixin):
    form_class = AcquireNodeForm

    def set_usable_arch(self):
        """Produce an arbitrary, valid, architecture name."""
        arch = "{}/{}".format(
            factory.make_name("arch"), factory.make_name("sub")
        )
        patch_usable_architectures(self, [arch])
        return arch

    def test_hostname(self):
        nodes = [factory.make_Node() for _ in range(3)]
        self.assertConstrainedNodes([nodes[0]], {"name": nodes[0].hostname})
        self.assertConstrainedNodes([], {"name": "unknown-name"})

    def test_hostname_with_domain_part(self):
        Domain.objects.get_or_create(name="mydomain", authoritative=True)
        nodes = [
            factory.make_Node(domain=factory.make_Domain()) for _ in range(3)
        ]
        self.assertConstrainedNodes(
            [nodes[0]],
            {"name": f"{nodes[0].hostname}.{nodes[0].domain.name}"},
        )
        self.assertConstrainedNodes(
            [], {"name": "{}.{}".format(nodes[0].hostname, "unknown-domain")}
        )
        self.assertConstrainedNodes(
            [], {"name": f"{nodes[0].hostname}.{nodes[1].domain.name}"}
        )
        node = factory.make_Node(hostname="host21.mydomain")
        self.assertConstrainedNodes([node], {"name": "host21.mydomain"})

        self.assertConstrainedNodes(
            [node], {"name": "host21.%s" % node.domain.name}
        )

    def test_cpu_count(self):
        node1 = factory.make_Node(cpu_count=1)
        node2 = factory.make_Node(cpu_count=2)
        nodes = [node1, node2]
        self.assertConstrainedNodes(nodes, {"cpu_count": "0"})
        self.assertConstrainedNodes(nodes, {"cpu_count": "1.0"})
        self.assertConstrainedNodes([node2], {"cpu_count": "2"})
        self.assertConstrainedNodes([], {"cpu_count": "4"})

    def test_invalid_cpu_count(self):
        form = AcquireNodeForm(data={"cpu_count": "invalid"})
        self.assertEqual(
            (False, {"cpu_count": ["Invalid CPU count: number required."]}),
            (form.is_valid(), form.errors),
        )

    def test_memory(self):
        node1 = factory.make_Node(memory=1024)
        node2 = factory.make_Node(memory=4096)
        self.assertConstrainedNodes([node1, node2], {"mem": "512"})
        self.assertConstrainedNodes([node1, node2], {"mem": "1024"})
        self.assertConstrainedNodes([node2], {"mem": "2048"})
        self.assertConstrainedNodes([node2], {"mem": "4096"})
        self.assertConstrainedNodes([], {"mem": "8192"})
        self.assertConstrainedNodes([node2], {"mem": "4096.0"})

    def test_invalid_memory(self):
        form = AcquireNodeForm(data={"mem": "invalid"})
        self.assertEqual(
            (False, {"mem": ["Invalid memory: number of MiB required."]}),
            (form.is_valid(), form.errors),
        )

    def test_describe_constraints_shows_simple_constraint(self):
        form = AcquireNodeForm(data={"cpu_count": "10"})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual("cpu_count=10.0", form.describe_constraints())

    def test_describe_constraints_shows_all_constraints(self):
        arch = self.set_usable_arch()
        constraints = {
            "name": factory.make_name("host"),
            "system_id": factory.make_name("system_id"),
            "arch": arch,
            "not_arch": arch,
            "cpu_count": random.randint(1, 32),
            "cpu_speed": random.randint(1, 32),
            "devices": "vendor_id=8086",
            "mem": random.randint(1024, 256 * 1024),
            "tags": [factory.make_Tag().name],
            "not_tags": [factory.make_Tag().name],
            "subnets": [factory.make_Subnet().name],
            "not_subnets": [factory.make_Subnet().name],
            "link_speed": random.randint(100, 10000),
            "vlans": ["name:" + factory.make_VLAN(name=RANDOM).name],
            "not_vlans": ["name:" + factory.make_VLAN(name=RANDOM).name],
            "zone": factory.make_Zone(),
            "not_in_zone": [factory.make_Zone().name],
            "pool": factory.make_ResourcePool(),
            "not_in_pool": [factory.make_ResourcePool().name],
            "pod": factory.make_name(),
            "not_pod": factory.make_name(),
            "pod_type": factory.make_name(),
            "not_pod_type": factory.make_name(),
            "storage": "0(ssd),10(ssd)",
            "interfaces": "label:fabric=fabric-0",
            "fabrics": [factory.make_Fabric().name],
            "not_fabrics": [factory.make_Fabric().name],
            "fabric_classes": [
                factory.make_Fabric(class_type="10g").class_type
            ],
            "not_fabric_classes": [
                factory.make_Fabric(class_type="1g").class_type
            ],
            "owner": factory.make_User().username,
            "not_owner": factory.make_User().username,
            "power_state": POWER_STATE.ON,
            "not_power_state": POWER_STATE.OFF,
            "deployment_target": DEPLOYMENT_TARGET.MEMORY,
            "not_deployment_target": DEPLOYMENT_TARGET.DISK,
        }
        form = AcquireNodeForm(data=constraints)
        self.assertTrue(form.is_valid(), form.errors)
        # Check first: we didn't forget to test any attributes.  When we add
        # a constraint to the form, we'll have to add it here as well.
        self.assertCountEqual(form.fields.keys(), constraints.keys())

        described_constraints = {
            constraint.split("=", 1)[0]
            for constraint in form.describe_constraints().split()
        }
        self.assertCountEqual(constraints.keys(), described_constraints)

    def test_pod_not_pod_pod_type_or_not_pod_type_for_pod(self):
        node1 = factory.make_Node(
            power_type="virsh",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod1 = factory.make_Pod(pod_type=node1.power_type, name="pod1")
        node2 = factory.make_Node(
            power_type="lxd",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod2 = factory.make_Pod(pod_type=node2.power_type, name="pod2")
        node1.bmc = pod1
        node1.save()
        node2.bmc = pod2
        node2.save()
        self.assertConstrainedNodes([node1], {"pod": pod1.name})
        self.assertConstrainedNodes([node2], {"pod": pod2.name})
        self.assertConstrainedNodes([], {"pod": factory.make_name("pod")})

    def test_pod_not_pod_pod_type_or_not_pod_type_for_not_pod(self):
        node1 = factory.make_Node(
            power_type="virsh",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod1 = factory.make_Pod(pod_type=node1.power_type, name="pod1")
        node2 = factory.make_Node(
            power_type="lxd",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod2 = factory.make_Pod(pod_type=node2.power_type, name="pod2")
        node1.bmc = pod1
        node1.save()
        node2.bmc = pod2
        node2.save()
        self.assertConstrainedNodes([node2], {"not_pod": pod1.name})
        self.assertConstrainedNodes([node1], {"not_pod": pod2.name})
        self.assertConstrainedNodes(
            [node1, node2], {"not_pod": factory.make_name("not_pod")}
        )

    def test_pod_not_pod_pod_type_or_not_pod_type_for_pod_type(self):
        node1 = factory.make_Node(
            power_type="virsh",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod1 = factory.make_Pod(pod_type=node1.power_type)
        node2 = factory.make_Node(
            power_type="lxd",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod2 = factory.make_Pod(pod_type=node2.power_type)
        node1.bmc = pod1
        node1.save()
        node2.bmc = pod2
        node2.save()
        self.assertConstrainedNodes([node1], {"pod_type": pod1.power_type})
        self.assertConstrainedNodes([node2], {"pod_type": pod2.power_type})
        self.assertConstrainedNodes(
            [], {"pod_type": factory.make_name("pod_type")}
        )

    def test_pod_not_pod_pod_type_or_not_pod_type_for_not_pod_type(self):
        node1 = factory.make_Node(
            power_type="virsh",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod1 = factory.make_Pod(pod_type=node1.power_type)
        node2 = factory.make_Node(
            power_type="lxd",
            power_parameters={"power_address": factory.make_ip_address()},
        )
        pod2 = factory.make_Pod(pod_type=node2.power_type)
        node1.bmc = pod1
        node1.save()
        node2.bmc = pod2
        node2.save()
        self.assertConstrainedNodes([node2], {"not_pod_type": pod1.power_type})
        self.assertConstrainedNodes([node1], {"not_pod_type": pod2.power_type})
        self.assertConstrainedNodes(
            [node1, node2], {"not_pod_type": factory.make_name("not_pod_type")}
        )

    def test_device_filter_by_vendor_id(self):
        node = random.choice([factory.make_Node() for _ in range(3)])
        node_device = factory.make_NodeDevice(
            node=node,
            vendor_id=create_unique_node_device_needle(
                "vendor_id", partial(factory.make_hex_string, size=4)
            ),
        )
        self.assertConstrainedNodes(
            [node], {"devices": f"vendor_id={node_device.vendor_id}"}
        )

    def test_device_filter_by_product_id(self):
        node = random.choice([factory.make_Node() for _ in range(3)])
        node_device = factory.make_NodeDevice(
            node=node,
            product_id=create_unique_node_device_needle(
                "product_id", partial(factory.make_hex_string, size=4)
            ),
        )
        self.assertConstrainedNodes(
            [node], {"devices": f"product_id={node_device.product_id}"}
        )

    def test_device_filter_by_vendor_name(self):
        node = random.choice([factory.make_Node() for _ in range(3)])
        node_device = factory.make_NodeDevice(
            node=node,
            vendor_name=create_unique_node_device_needle(
                "vendor_name", partial(factory.make_name, "vendor_name")
            ),
        )
        self.assertConstrainedNodes(
            [node], {"devices": f"vendor_name={node_device.vendor_name}"}
        )

    def test_device_filter_by_product_name(self):
        node = random.choice([factory.make_Node() for _ in range(3)])
        node_device = factory.make_NodeDevice(
            node=node,
            product_name=create_unique_node_device_needle(
                "product_name", partial(factory.make_name, "product_name")
            ),
        )
        self.assertConstrainedNodes(
            [node], {"devices": f"product_name={node_device.product_name}"}
        )

    def test_device_filter_by_commissioning_driver(self):
        node = random.choice([factory.make_Node() for _ in range(3)])
        node_device = factory.make_NodeDevice(
            node=node,
            commissioning_driver=create_unique_node_device_needle(
                "commissioning_driver",
                partial(factory.make_name, "commissioning_driver"),
            ),
        )
        self.assertConstrainedNodes(
            [node],
            {
                "devices": f"commissioning_driver={node_device.commissioning_driver}"
            },
        )

    def test_device_filter_by_multiple_keys(self):
        vendor_id = factory.make_hex_string(size=4)
        commissioning_driver = factory.make_name("commissioning_driver")
        factory.make_Node()
        node1 = factory.make_Node()
        factory.make_NodeDevice(node=node1, vendor_id=vendor_id)
        node2 = factory.make_Node()
        factory.make_NodeDevice(
            node=node2,
            vendor_id=vendor_id,
            commissioning_driver=commissioning_driver,
        )
        node3 = factory.make_Node()
        factory.make_NodeDevice(
            node=node3,
            vendor_id=vendor_id,
            commissioning_driver=commissioning_driver,
        )
        self.assertConstrainedNodes(
            [node2, node3],
            {
                "devices": f"vendor_id={vendor_id},commissioning_driver={commissioning_driver}"
            },
        )


class TestAcquireNodeFormOrdersResults(MAASServerTestCase):
    def test_describe_constraints_orders_based_on_cost(self):
        nodes = [
            factory.make_Node(
                cpu_count=random.randint(5, 32),
                memory=random.randint(1024, 256 * 1024),
            )
            for _ in range(4)
        ]
        sorted_nodes = sorted(
            nodes, key=lambda n: n.cpu_count + n.memory / 1024
        )
        # The form should select all the nodes.  All we're interested
        # in here is the ordering.
        form = AcquireNodeForm(data={"cpu_count": 4})
        self.assertTrue(form.is_valid(), form.errors)
        filtered_nodes, _, _ = form.filter_nodes(Machine.objects.all())
        self.assertEqual(sorted_nodes, list(filtered_nodes))


class TestReadNodesForm(MAASServerTestCase, FilterConstraintsMixin):
    form_class = ReadNodesForm

    def test_system_ids(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        factory.make_Node()
        self.assertConstrainedNodes(
            [node1, node2], {"id": [node1.system_id, node2.system_id]}
        )

    def test_hostnames(self):
        node1 = factory.make_Node()
        node2 = factory.make_Node()
        factory.make_Node()
        self.assertConstrainedNodes(
            [node1, node2], {"hostname": [node1.hostname, node2.hostname]}
        )

    def test_domain(self):
        domain1 = factory.make_Domain()
        domain2 = factory.make_Domain()
        node1 = factory.make_Node(domain=domain1)
        node2 = factory.make_Node(domain=domain2)
        factory.make_Node()
        self.assertConstrainedNodes(
            [node1, node2], {"domain": [domain1.name, domain2.name]}
        )

    def test_mac_addresses(self):
        if1 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        if2 = factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        factory.make_Interface(INTERFACE_TYPE.PHYSICAL)
        self.assertConstrainedNodes(
            [if1.node_config.node, if2.node_config.node],
            {"mac_address": [if1.mac_address, if2.mac_address]},
        )

    def test_mac_addresses_invalid(self):
        form = ReadNodesForm(data={"mac_address": ["AA:BB:CC:DD:EE:XX"]})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors,
            {
                "mac_address": [
                    "'AA:BB:CC:DD:EE:XX' is not a valid MAC address."
                ]
            },
        )

    def test_agent_name(self):
        agent_name = factory.make_name("agent-name")
        node = factory.make_Node(agent_name=agent_name)
        factory.make_Node(agent_name=factory.make_name("agent-name"))
        self.assertConstrainedNodes([node], {"agent_name": agent_name})

    def test_status(self):
        node1 = factory.make_Node(status=NODE_STATUS.NEW)
        node2 = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node3 = factory.make_Node(status=NODE_STATUS.NEW)
        self.assertConstrainedNodes([node1, node3], {"status": "new"})
        self.assertConstrainedNodes([node2], {"status": "deploying"})

    def test_status_with_prefix(self):
        node1 = factory.make_Node(status=NODE_STATUS.NEW)
        node2 = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node3 = factory.make_Node(status=NODE_STATUS.NEW)
        self.assertConstrainedNodes([node1, node3], {"status": "=new"})
        self.assertConstrainedNodes([node2], {"status": "=deploying"})


class TestGetFieldArgumentType(MAASServerTestCase):
    def test_get_IntegerField_type(self):
        field = forms.IntegerField()
        self.assertEqual(get_field_argument_type(field), "int")

    def test_get_ChoiceField_type(self):
        field = forms.ChoiceField()
        self.assertEqual(get_field_argument_type(field), "str")

    def test_get_FloatField_type(self):
        field = forms.FloatField()
        self.assertEqual(get_field_argument_type(field), "float")

    def test_get_CharField_type(self):
        field = forms.CharField()
        self.assertEqual(get_field_argument_type(field), "str")

    def test_get_ValidatorMultipleChoiceField_type(self):
        field = ValidatorMultipleChoiceField(validator=lambda x: True)
        self.assertEqual(get_field_argument_type(field), "list[str]")

    def test_get_UnconstrainedTypedMultipleChoiceField_type(self):
        field = UnconstrainedTypedMultipleChoiceField(coerce=float)
        self.assertEqual(get_field_argument_type(field), "list[float]")

    def test_get_UnconstrainedMultipleChoiceField_type(self):
        field = UnconstrainedMultipleChoiceField()
        self.assertEqual(get_field_argument_type(field), "list[str]")

    def test_get_unknown_type(self):
        field = forms.Field()
        self.assertEqual(get_field_argument_type(field), "str")
