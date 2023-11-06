# Copyright 2017-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_STATUS
from maasserver.forms.parameters import (
    DEFAULTS_FROM_MAAS_CONFIG,
    ParametersForm,
)
from maasserver.models import Config
from maasserver.models.config import get_default_config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from provisioningserver.drivers.power.ipmi import IPMI_PRIVILEGE_LEVEL_CHOICES


class TestParametersForm(MAASServerTestCase):
    def pick_scheme(self):
        return random.choice(
            [
                "icmp",
                "file",
                "ftp",
                "ftps",
                "gopher",
                "http",
                "https",
                "imap",
                "imaps",
                "ldap",
                "ldaps",
                "pop3",
                "pop3s",
                "rtmp",
                "rtsp",
                "scp",
                "sftp",
                "smb",
                "smbs",
                "smtp",
                "smtps",
                "telnet",
                "tftp",
            ]
        )

    def test_validates_parameters_is_dict(self):
        form = ParametersForm(data=[factory.make_name() for _ in range(3)])
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["Must be a dictionary"]}, form.errors
        )

    def test_validates_parameter_is_str(self):
        param = random.randint(0, 1000)
        form = ParametersForm(data={param: {"type": "storage"}})
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["%d: parameter must be a string" % param]},
            form.errors,
        )

    def test_validates_parameter_field_type_is_str(self):
        param_type = random.randint(0, 1000)
        form = ParametersForm(
            data={"storage": {"type": param_type, "required": False}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["%d: type must be a string" % param_type]},
            form.errors,
        )

    def test_validates_parameter_field_min_is_int(self):
        param_min = factory.make_name("min")
        form = ParametersForm(
            data={"runtime": {"type": "runtime", "min": param_min}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["%s: min must be an integer" % param_min]},
            form.errors,
        )

    def test_validates_parameter_field_max_is_int(self):
        param_max = factory.make_name("max")
        form = ParametersForm(
            data={"runtime": {"type": "runtime", "max": param_max}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["%s: max must be an integer" % param_max]},
            form.errors,
        )

    def test_validates_parameter_field_title_is_str(self):
        form = ParametersForm(
            data={"storage": {"type": "storage", "title": True}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["True: title must be a string"]}, form.errors
        )

    def test_validates_parameter_field_description_is_str(self):
        form = ParametersForm(
            data={"storage": {"type": "storage", "description": True}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["True: description must be a string"]}, form.errors
        )

    def test_validates_parameter_field_argument_format_is_str(self):
        form = ParametersForm(
            data={"storage": {"type": "storage", "argument_format": []}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["[]: argument_format must be a string"]},
            form.errors,
        )

    def test_validates_parameter_field_argument_format_for_storage_type(self):
        form = ParametersForm(
            data={
                "storage": {
                    "type": "storage",
                    "argument_format": factory.make_name("argument_format"),
                }
            }
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "parameters": [
                    "storage: argument_format must contain one of {input}, "
                    "{name}, {path}, {model}, {serial}"
                ]
            },
            form.errors,
        )

    def test_validates_parameter_field_argument_format_for_interface(self):
        form = ParametersForm(
            data={
                "storage": {
                    "type": "interface",
                    "argument_format": factory.make_name("argument_format"),
                }
            }
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "parameters": [
                    "interface: argument_format must contain one of {input}, "
                    "{name}, {mac}, {vendor}, {product}"
                ]
            },
            form.errors,
        )

    def test_validates_parameter_field_argument_format_non_runtime_type(self):
        form = ParametersForm(
            data={
                "runtime": {
                    "type": "runtime",
                    "argument_format": factory.make_name("argument_format"),
                }
            }
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["runtime: argument_format must contain {input}"]},
            form.errors,
        )

    def test_validates_parameter_field_default_is_str(self):
        param_default = random.randint(0, 1000)
        form = ParametersForm(
            data={"storage": {"type": "storage", "default": param_default}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["%d: default must be a string" % param_default]},
            form.errors,
        )

    def test_validates_parameter_field_required_is_boolean(self):
        param_required = factory.make_name("required")
        form = ParametersForm(
            data={"storage": {"type": "storage", "required": param_required}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "parameters": [
                    "%s: required must be a boolean" % param_required
                ]
            },
            form.errors,
        )

    def test_validates_parameter_field_allow_list_is_boolean(self):
        param_allow_list = factory.make_name("allow_list")
        form = ParametersForm(
            data={"url": {"type": "url", "allow_list": param_allow_list}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "parameters": [
                    "%s: allow_list must be a boolean" % param_allow_list
                ]
            },
            form.errors,
        )

    def test_validates_parameter_field_allow_list_only_for_url(self):
        ptype = random.choice(["storage", "interface", "runtime"])
        form = ParametersForm(
            data={ptype: {"type": ptype, "allow_list": factory.pick_bool()}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["allow_list only supported with the url type."]},
            form.errors,
        )

    def test_checks_for_supported_parameter_types(self):
        form = ParametersForm(
            data={
                "storage": {"type": "storage"},
                "interface": {"type": "interface"},
                "url": {"type": "url"},
                "runtime": {"type": "runtime"},
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_validates_against_unsupported_parameter_types(self):
        unsupported_type = factory.make_name("unsupported")
        form = ParametersForm(data={"storage": {"type": unsupported_type}})
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "parameters": [
                    "%s: type must be either storage, interface, url, "
                    "runtime, string, password, or choice" % unsupported_type
                ]
            },
            form.errors,
        )

    def test_validates_unsupported_parameter_types_if_not_required(self):
        unsupported_type = factory.make_name("unsupported")
        form = ParametersForm(
            data={"storage": {"type": unsupported_type, "required": False}}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_validates_storage_interface_type_has_no_min_or_max(self):
        ptype = random.choice(["storage", "interface"])
        form = ParametersForm(
            data={ptype: {"type": ptype, "min": random.randint(0, 1000)}}
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["Type doesn't support min or max"]}, form.errors
        )

    def test_validates_runtime_type_min_greater_than_zero(self):
        form = ParametersForm(
            data={
                "runtime": {"type": "runtime", "min": random.randint(-100, -1)}
            }
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["runtime minimum must be greater than zero"]},
            form.errors,
        )

    def test_validates_min_less_than_max(self):
        form = ParametersForm(
            data={
                "runtime": {
                    "type": "runtime",
                    "min": random.randint(500, 1000),
                    "max": random.randint(0, 500),
                }
            }
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"parameters": ["min must be less than max"]}, form.errors
        )

    def test_input_errors_on_unknown_paramater(self):
        script = factory.make_Script()
        bad_param = factory.make_name("bad_param")
        form = ParametersForm(
            data={bad_param: factory.make_name("bad_input")},
            script=script,
            node=factory.make_Node(),
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"input": [f"Unknown parameter '{bad_param}' for {script.name}"]},
            form.errors,
        )

    def test_input_runtime(self):
        script = factory.make_Script(
            parameters={"runtime": {"type": "runtime"}}
        )
        value = random.randint(0, 100)
        form = ParametersForm(
            data={"runtime": value}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(1, len(form.cleaned_data["input"]))
        self.assertDictEqual(
            {"runtime": {"type": "runtime", "value": value}},
            form.cleaned_data["input"][0],
        )

    def test_input_runtime_gets_default_from_script_timeout(self):
        script = factory.make_Script(
            parameters={"runtime": {"type": "runtime"}}
        )
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(1, len(form.cleaned_data["input"]))
        self.assertDictEqual(
            {"runtime": {"type": "runtime", "value": script.timeout.seconds}},
            form.cleaned_data["input"][0],
        )

    def test_input_runtime_requires_int(self):
        script = factory.make_Script(
            parameters={"runtime": {"type": "runtime"}}
        )
        form = ParametersForm(
            data={"runtime": factory.make_name("value")},
            script=script,
            node=factory.make_Node(),
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"runtime": ["Must be an int"]}, form.errors)

    def test_input_runtime_validates_required(self):
        script = factory.make_Script(
            parameters={
                "runtime": {
                    "type": "runtime",
                    "required": True,
                    "default": None,
                }
            }
        )
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"runtime": ["Field is required"]}, form.errors)

    def test_input_runtime_validates_min(self):
        min_runtime = random.randint(1, 100)
        script = factory.make_Script(
            parameters={"runtime": {"type": "runtime", "min": min_runtime}}
        )
        value = random.randint(-min_runtime, min_runtime - 1)
        form = ParametersForm(
            data={"runtime": value}, script=script, node=factory.make_Node()
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"runtime": ["Must be greater than %s" % min_runtime]}, form.errors
        )

    def test_input_runtime_validates_max(self):
        max_runtime = random.randint(0, 100)
        script = factory.make_Script(
            parameters={"runtime": {"type": "runtime", "max": max_runtime}}
        )
        value = random.randint(max_runtime + 1, max_runtime + 10)
        form = ParametersForm(
            data={"runtime": value}, script=script, node=factory.make_Node()
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"runtime": ["Must be less than %s" % max_runtime]}, form.errors
        )

    def test_input_storage_validates_required(self):
        script = factory.make_Script(
            parameters={
                "storage": {
                    "type": "storage",
                    "required": True,
                    "default": None,
                }
            }
        )
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"storage": ["Field is required"]}, form.errors)

    def test_input_storage_defaults_all_with_no_disks(self):
        script = factory.make_Script(
            parameters={
                "runtime": {"type": "runtime"},
                "storage": {"type": "storage"},
            }
        )
        form = ParametersForm(
            data={},
            script=script,
            node=factory.make_Node(with_boot_disk=False),
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(1, len(form.cleaned_data["input"]))
        self.assertDictEqual(
            {
                "runtime": {
                    "type": "runtime",
                    "value": script.timeout.seconds,
                },
                "storage": {"type": "storage", "value": "all"},
            },
            form.cleaned_data["input"][0],
        )

    def test_input_storage_all(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(
            parameters={
                "runtime": {"type": "runtime"},
                "storage": {"type": "storage"},
            }
        )
        form = ParametersForm(
            data={"storage": "all"}, script=script, node=node
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(node.physicalblockdevice_set.count(), len(input))
        for bd in node.physicalblockdevice_set:
            for i in input:
                if bd.name == i["storage"]["value"]["name"]:
                    break
            self.assertEqual(script.timeout.seconds, i["runtime"]["value"])
            self.assertDictEqual(
                {
                    "id": bd.id,
                    "name": bd.name,
                    "id_path": bd.id_path,
                    "model": bd.model,
                    "serial": bd.serial,
                    "physical_blockdevice": bd,
                },
                i["storage"]["value"],
            )

    def test_input_storage_id(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(
            parameters={
                "runtime": {"type": "runtime"},
                "storage": {"type": "storage"},
            }
        )
        bd = random.choice(list(node.physicalblockdevice_set.all()))
        form = ParametersForm(
            data={"storage": random.choice([bd.id, str(bd.id)])},
            script=script,
            node=node,
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(1, len(input))
        self.assertEqual(script.timeout.seconds, input[0]["runtime"]["value"])
        self.assertDictEqual(
            {
                "id": bd.id,
                "name": bd.name,
                "id_path": bd.id_path,
                "model": bd.model,
                "serial": bd.serial,
                "physical_blockdevice": bd,
            },
            input[0]["storage"]["value"],
        )

    def test_input_storage_id_errors(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(
            parameters={
                "runtime": {"type": "runtime"},
                "storage": {"type": "storage"},
            }
        )
        form = ParametersForm(
            data={"storage": random.randint(1000, 2000)},
            script=script,
            node=node,
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"storage": ["Physical block id does not exist"]}, form.errors
        )

    def test_input_storage_list(self):
        node = factory.make_Node()
        for _ in range(10):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(
            parameters={
                "runtime": {"type": "runtime"},
                "storage": {"type": "storage"},
            }
        )
        bds = list(node.physicalblockdevice_set.all())
        selected_scripts = {
            bds[0]: f"{bds[0].model}:{bds[0].serial}",
            bds[1]: bds[1].name,
            bds[2]: "/dev/%s" % bds[2].name,
            bds[3]: bds[3].model,
            bds[4]: bds[4].serial,
            bds[5]: random.choice(bds[5].tags),
        }
        form = ParametersForm(
            data={"storage": ",".join(selected_scripts.values())},
            script=script,
            node=node,
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(len(selected_scripts), len(input))
        for bd in selected_scripts.keys():
            for i in input:
                if bd.name == i["storage"]["value"]["name"]:
                    break
            self.assertEqual(script.timeout.seconds, i["runtime"]["value"])
            self.assertDictEqual(
                {
                    "id": bd.id,
                    "name": bd.name,
                    "id_path": bd.id_path,
                    "model": bd.model,
                    "serial": bd.serial,
                    "physical_blockdevice": bd,
                },
                i["storage"]["value"],
            )

    def test_input_storage_name_errors(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(
            parameters={
                "runtime": {"type": "runtime"},
                "storage": {"type": "storage"},
            }
        )
        form = ParametersForm(
            data={"storage": factory.make_name("bad_name")},
            script=script,
            node=node,
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "storage": [
                    "Unknown storage device for %s(%s)"
                    % (node.fqdn, node.system_id)
                ]
            },
            form.errors,
        )

    def test_input_interface_validates_required(self):
        script = factory.make_Script(
            parameters={
                "interface": {
                    "type": "interface",
                    "required": True,
                    "default": None,
                }
            }
        )
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"interface": ["Field is required"]}, form.errors)

    def test_input_interface_defaults_all_with_no_nics(self):
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={}, script=script, node=factory.make_Node(interface=False)
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(1, len(form.cleaned_data["input"]))
        self.assertDictEqual(
            {"interface": {"type": "interface", "value": "all"}},
            form.cleaned_data["input"][0],
        )

    def test_input_interface_defaults_boot_interface_during_commiss(self):
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.COMMISSIONING
        )
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(data={}, script=script, node=node)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(1, len(form.cleaned_data["input"]))
        self.assertDictEqual(
            {
                "id": node.boot_interface.id,
                "name": node.boot_interface.name,
                "mac_address": str(node.boot_interface.mac_address),
                "vendor": node.boot_interface.vendor,
                "product": node.boot_interface.product,
                "interface": node.boot_interface,
            },
            form.cleaned_data["input"][0]["interface"]["value"],
        )

    def test_input_interface_all(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        usable_interfaces = [
            factory.make_Interface(node=node, subnet=subnet) for _ in range(3)
        ]
        # Unconfigured or disabled interfaces
        factory.make_Interface(node=node, enabled=False)
        factory.make_Interface(node=node, link_connected=False)
        discovered = factory.make_Interface(node=node, subnet=subnet)
        discovered_ip = discovered.ip_addresses.first()
        discovered_ip.alloc_type = IPADDRESS_TYPE.DISCOVERED
        discovered_ip.save()
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": "all"}, script=script, node=node
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(len(usable_interfaces), len(input))
        for interface in usable_interfaces:
            for i in input:
                if i["interface"]["value"]["interface"] == interface:
                    break
            self.assertDictEqual(
                {
                    "id": interface.id,
                    "name": interface.name,
                    "mac_address": str(interface.mac_address),
                    "vendor": interface.vendor,
                    "product": interface.product,
                    "interface": interface,
                },
                i["interface"]["value"],
            )

    def test_input_interface_all_only_includes_children(self):
        node = factory.make_Node(interface=False)
        subnet = factory.make_Subnet()
        bond = factory.make_Interface(
            node=node,
            iftype=INTERFACE_TYPE.BOND,
            subnet=subnet,
            parents=[factory.make_Interface(node=node) for _ in range(2)],
        )
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": "all"}, script=script, node=node
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(1, len(input))
        self.assertDictEqual(
            {
                "id": bond.id,
                "name": bond.name,
                "mac_address": str(bond.mac_address),
                "vendor": bond.vendor,
                "product": bond.product,
                "interface": bond,
            },
            input[0]["interface"]["value"],
        )

    def test_input_interface_id(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        for _ in range(3):
            factory.make_Interface(node=node, subnet=subnet)
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        interface = random.choice(
            list(node.current_config.interface_set.all())
        )
        form = ParametersForm(
            data={
                "interface": random.choice([interface.id, str(interface.id)])
            },
            script=script,
            node=node,
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(1, len(input))
        self.assertDictEqual(
            {
                "id": interface.id,
                "name": interface.name,
                "mac_address": str(interface.mac_address),
                "vendor": interface.vendor,
                "product": interface.product,
                "interface": interface,
            },
            input[0]["interface"]["value"],
        )

    def test_input_interface_id_errors(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_Interface(node=node)
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": random.randint(1000, 2000)},
            script=script,
            node=node,
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"interface": ["Interface id does not exist"]}, form.errors
        )

    def test_input_interface_id_errors_on_parent(self):
        node = factory.make_Node(interface=False)
        parents = [factory.make_Interface(node=node) for _ in range(2)]
        factory.make_Interface(
            node=node, iftype=INTERFACE_TYPE.BOND, parents=parents
        )
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": random.choice(parents).id},
            script=script,
            node=node,
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {"interface": ["Interface id does not exist"]}, form.errors
        )

    def test_input_interface_id_errors_on_unconfigured_or_disabled(self):
        node = factory.make_Node()
        bad_interface = random.choice(
            [
                factory.make_Interface(node=node, enabled=False),
                factory.make_Interface(node=node, link_connected=False),
            ]
        )
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": bad_interface.id}, script=script, node=node
        )
        self.assertFalse(form.is_valid())

    def test_input_interface_list(self):
        node = factory.make_Node()
        subnet = factory.make_Subnet()
        for _ in range(10):
            factory.make_Interface(node=node, subnet=subnet)
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        nics = list(node.current_config.interface_set.all())
        selected_scripts = {
            nics[0]: f"{nics[0].vendor}:{nics[0].product}",
            nics[1]: nics[1].name,
            nics[2]: nics[2].vendor,
            nics[3]: nics[3].product,
            nics[4]: str(nics[4].mac_address),
            nics[4]: random.choice(nics[4].tags),
        }
        form = ParametersForm(
            data={"interface": ",".join(selected_scripts.values())},
            script=script,
            node=node,
        )
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data["input"]
        self.assertEqual(len(selected_scripts), len(input))
        for nic in selected_scripts.keys():
            for i in input:
                if (
                    str(nic.mac_address)
                    == i["interface"]["value"]["mac_address"]
                ):
                    break
            self.assertDictEqual(
                {
                    "id": nic.id,
                    "name": nic.name,
                    "mac_address": str(nic.mac_address),
                    "vendor": nic.vendor,
                    "product": nic.product,
                    "interface": nic,
                },
                i["interface"]["value"],
            )

    def test_input_interface_name_errors(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_Interface(node=node)
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": factory.make_name("bad_name")},
            script=script,
            node=node,
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "interface": [
                    "Unknown interface for %s(%s)"
                    % (node.fqdn, node.system_id)
                ]
            },
            form.errors,
        )

    def test_input_interface_name_errors_on_parent(self):
        node = factory.make_Node(interface=False)
        parents = [factory.make_Interface(node=node) for _ in range(2)]
        factory.make_Interface(
            node=node, iftype=INTERFACE_TYPE.BOND, parents=parents
        )
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": random.choice(parents).name},
            script=script,
            node=node,
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                "interface": [
                    "Unknown interface for %s(%s)"
                    % (node.fqdn, node.system_id)
                ]
            },
            form.errors,
        )

    def test_input_interface_name_errors_on_unconfigured_or_disabled(self):
        node = factory.make_Node()
        bad_interface = random.choice(
            [
                factory.make_Interface(node=node, enabled=False),
                factory.make_Interface(node=node, link_connected=False),
            ]
        )
        script = factory.make_Script(
            parameters={"interface": {"type": "interface"}}
        )
        form = ParametersForm(
            data={"interface": bad_interface.name}, script=script, node=node
        )
        self.assertFalse(form.is_valid())

    def test_input_url_validates_required(self):
        script = factory.make_Script(
            parameters={"url": {"type": "url", "required": True}}
        )
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"url": ["Field is required"]}, form.errors)

    def test_input_url_defaults_empty_with_no_input(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual({}, form.cleaned_data["input"][0])

    def test_input_url_allows_ipv4(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        input = factory.make_ipv4_address()
        form = ParametersForm(
            data={"url": input}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "value": input}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_allows_ipv4_url(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        input = "%s://%s:%d/%s" % (
            self.pick_scheme(),
            factory.make_ipv4_address(),
            random.randint(0, 65535),
            factory.make_name(),
        )
        form = ParametersForm(
            data={"url": input}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "value": input}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_allows_ipv6(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        input = factory.make_ipv6_address()
        form = ParametersForm(
            data={"url": input}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "value": input}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_allows_ipv6_url(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        input = "%s://[%s]:%d/%s" % (
            self.pick_scheme(),
            factory.make_ipv6_address(),
            random.randint(0, 65535),
            factory.make_name(),
        )
        form = ParametersForm(
            data={"url": input}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "value": input}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_allows_hostname(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        input = factory.make_hostname()
        form = ParametersForm(
            data={"url": input}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "value": input}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_allows_hostname_url(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        input = factory.make_url(scheme=self.pick_scheme())
        form = ParametersForm(
            data={"url": input}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "value": input}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_allows_list(self):
        script = factory.make_Script(
            parameters={"url": {"type": "url", "allow_list": True}}
        )
        inputs = ",".join(
            [
                factory.make_ipv4_address(),
                "%s://%s:%d/%s"
                % (
                    self.pick_scheme(),
                    factory.make_ipv4_address(),
                    random.randint(0, 65535),
                    factory.make_name(),
                ),
                factory.make_ipv6_address(),
                "%s://[%s]:%d/%s"
                % (
                    self.pick_scheme(),
                    factory.make_ipv6_address(),
                    random.randint(0, 65535),
                    factory.make_name(),
                ),
                factory.make_hostname(),
                factory.make_url(scheme=self.pick_scheme()),
            ]
        )
        form = ParametersForm(
            data={"url": inputs}, script=script, node=factory.make_Node()
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertDictEqual(
            {"url": {"type": "url", "allow_list": True, "value": inputs}},
            form.cleaned_data["input"][0],
        )

    def test_input_url_list_requires_allow_list(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        inputs = ",".join(
            [
                factory.make_ipv4_address(),
                "%s://%s:%d/%s"
                % (
                    self.pick_scheme(),
                    factory.make_ipv4_address(),
                    random.randint(0, 65535),
                    factory.make_name(),
                ),
                factory.make_ipv6_address(),
                "%s://[%s]:%d/%s"
                % (
                    self.pick_scheme(),
                    factory.make_ipv6_address(),
                    random.randint(0, 65535),
                    factory.make_name(),
                ),
                factory.make_hostname(),
                factory.make_url(scheme=self.pick_scheme()),
            ]
        )
        form = ParametersForm(
            data={"url": inputs}, script=script, node=factory.make_Node()
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"url": ["Invalid URL"]}, form.errors)

    def test_input_url_list_errors(self):
        script = factory.make_Script(parameters={"url": {"type": "url"}})
        form = ParametersForm(
            data={"url": factory.make_name("bad!")},
            script=script,
            node=factory.make_Node(),
        )
        self.assertFalse(form.is_valid())
        self.assertDictEqual({"url": ["Invalid URL"]}, form.errors)

    def test_input_string(self):
        # String and password fields are identical from the forms POV.
        param_type = random.choice(["string", "password"])
        script = factory.make_Script(
            parameters={param_type: {"type": param_type}}
        )
        input = factory.make_string()

        form = ParametersForm(
            data={param_type: input}, script=script, node=factory.make_Node()
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            input, form.cleaned_data["input"][0][param_type]["value"]
        )

    def test_input_string_int(self):
        # String and password fields are identical from the forms POV.
        param_type = random.choice(["string", "password"])
        script = factory.make_Script(
            parameters={param_type: {"type": param_type}}
        )
        input = random.randint(0, 100)

        form = ParametersForm(
            data={param_type: input}, script=script, node=factory.make_Node()
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            input, form.cleaned_data["input"][0][param_type]["value"]
        )

    def test_input_string_default(self):
        # String and password fields are identical from the forms POV.
        param_type = random.choice(["string", "password"])
        default = factory.make_string()
        script = factory.make_Script(
            parameters={param_type: {"type": param_type, "default": default}}
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            default, form.cleaned_data["input"][0][param_type]["value"]
        )

    def test_input_string_default_maas_config(self):
        maas_auto_ipmi_user = factory.make_name("maas_auto_ipmi_user")
        Config.objects.set_config("maas_auto_ipmi_user", maas_auto_ipmi_user)
        script = factory.make_Script(
            parameters={"maas_auto_ipmi_user": {"type": "string"}}
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            maas_auto_ipmi_user,
            form.cleaned_data["input"][0]["maas_auto_ipmi_user"]["value"],
        )

    def test_input_password_default_maas_config(self):
        maas_auto_ipmi_k_g_bmc_key = factory.make_name(
            "maas_auto_ipmi_k_g_bmc_key"
        )
        Config.objects.set_config(
            "maas_auto_ipmi_k_g_bmc_key", maas_auto_ipmi_k_g_bmc_key
        )
        script = factory.make_Script(
            parameters={"maas_auto_ipmi_k_g_bmc_key": {"type": "password"}}
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            maas_auto_ipmi_k_g_bmc_key,
            form.cleaned_data["input"][0]["maas_auto_ipmi_k_g_bmc_key"][
                "value"
            ],
        )

    def test_input_string_required(self):
        # String and password fields are identical from the forms POV.
        param_type = random.choice(["string", "password"])
        script = factory.make_Script(
            parameters={param_type: {"type": param_type, "required": True}}
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertFalse(form.is_valid())
        self.assertEqual({param_type: ["Field is required"]}, form.errors)

    def test_input_string_min(self):
        # String and password fields are identical from the forms POV.
        param_type = random.choice(["string", "password"])
        script = factory.make_Script(
            parameters={param_type: {"type": param_type, "min": 30}}
        )

        form = ParametersForm(
            data={param_type: factory.make_string()},
            script=script,
            node=factory.make_Node(),
        )

        self.assertFalse(form.is_valid())
        self.assertEqual({param_type: ["Input too short"]}, form.errors)

    def test_input_string_max(self):
        # String and password fields are identical from the forms POV.
        param_type = random.choice(["string", "password"])
        script = factory.make_Script(
            parameters={param_type: {"type": param_type, "max": 3}}
        )

        form = ParametersForm(
            data={param_type: factory.make_string()},
            script=script,
            node=factory.make_Node(),
        )

        self.assertFalse(form.is_valid())
        self.assertEqual({param_type: ["Input too long"]}, form.errors)

    def test_input_choice(self):
        # Validates a choice parameter can be made using a list of strings.
        choices = [factory.make_name("choice") for _ in range(3)]
        script = factory.make_Script(
            parameters={"choice": {"type": "choice", "choices": choices}}
        )

        choice = random.choice(choices)
        form = ParametersForm(
            data={"choice": choice}, script=script, node=factory.make_Node()
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            choice, form.cleaned_data["input"][0]["choice"]["value"]
        )

    def test_input_choice_django(self):
        # Validates a choice parameter can be made using a Django choice list.
        choices = [
            (factory.make_name("choice"), factory.make_name("pretty_name"))
            for _ in range(3)
        ]
        script = factory.make_Script(
            parameters={"choice": {"type": "choice", "choices": choices}}
        )

        choice = factory.pick_choice(choices)
        form = ParametersForm(
            data={"choice": choice}, script=script, node=factory.make_Node()
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            choice, form.cleaned_data["input"][0]["choice"]["value"]
        )

    def test_input_default(self):
        # Validates a choice parameter can be made using a Django choice list.
        choices = [
            (factory.make_name("choice"), factory.make_name("pretty_name"))
            for _ in range(3)
        ]
        default = factory.pick_choice(choices)
        script = factory.make_Script(
            parameters={
                "choice": {
                    "type": "choice",
                    "choices": choices,
                    "default": default,
                }
            }
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            default, form.cleaned_data["input"][0]["choice"]["value"]
        )

    def test_input_choice_default_maas_config(self):
        maas_auto_ipmi_user_privilege_level = factory.pick_choice(
            IPMI_PRIVILEGE_LEVEL_CHOICES
        )
        Config.objects.set_config(
            "maas_auto_ipmi_user_privilege_level",
            maas_auto_ipmi_user_privilege_level,
        )
        script = factory.make_Script(
            parameters={
                "maas_auto_ipmi_user_privilege_level": {
                    "type": "choice",
                    "choices": IPMI_PRIVILEGE_LEVEL_CHOICES,
                }
            }
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            maas_auto_ipmi_user_privilege_level,
            form.cleaned_data["input"][0][
                "maas_auto_ipmi_user_privilege_level"
            ]["value"],
        )

    def test_input_choice_required(self):
        choices = [factory.make_name("choice") for _ in range(3)]
        script = factory.make_Script(
            parameters={
                "choice": {
                    "type": "choice",
                    "choices": choices,
                    "required": True,
                }
            }
        )

        form = ParametersForm(data={}, script=script, node=factory.make_Node())

        self.assertFalse(form.is_valid())
        self.assertEqual({"choice": ["Field is required"]}, form.errors)

    def test_input_choice_bad(self):
        choices = [factory.make_name("choice") for _ in range(3)]
        script = factory.make_Script(
            parameters={"choice": {"type": "choice", "choices": choices}}
        )
        bad_choice = factory.make_name("bad_choice")

        form = ParametersForm(
            data={"choice": bad_choice},
            script=script,
            node=factory.make_Node(),
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {"choice": [f'Invalid choice "{bad_choice}"']}, form.errors
        )

    def test_input_choice_no_choices(self):
        form = ParametersForm(data={"choice": {"type": "choice"}})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "parameters": [
                    'choices must be given with a "choice" parameter type!'
                ]
            },
            form.errors,
        )

    def test_default_config_keys_exist(self):
        defaults_all = get_default_config().keys()
        self.assertGreaterEqual(defaults_all, DEFAULTS_FROM_MAAS_CONFIG)
