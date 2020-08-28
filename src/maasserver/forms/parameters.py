# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Parameters form."""

__all__ = ["ParametersForm"]

import copy
from ipaddress import ip_address
import os

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q
from django.forms import Field, Form

from maasserver.enum import NODE_STATUS
from maasserver.utils.dns import validate_url
from maasserver.utils.forms import set_form_error
from maasserver.utils.mac import is_mac


class ParametersForm(Form):
    """Parameters forms."""

    parameters = Field(label="Paramaters", required=False, initial={})
    input = Field(label="Input", required=False, initial={})

    def __init__(self, data=None, script=None, node=None):
        if script is not None:
            assert node is not None, "node must be passed with script!"
            data = {"parameters": script.parameters, "input": data}
        else:
            data = {"parameters": data}
        super().__init__(data=data)
        self._node = node
        self._script = script

    def _get_interfaces(self, *args, **kwargs):
        """Return a list of configured interfaces."""
        ifaces = [
            interface
            for interface in self._node.interface_set.filter(
                children_relationships=None, enabled=True, *args, **kwargs
            ).prefetch_related("ip_addresses")
            if interface.is_configured()
        ]
        if (
            not ifaces
            and self._node.status == NODE_STATUS.COMMISSIONING
            and self._node.boot_interface
        ):
            # During commissioning no interface will have a configured IP
            # address if network information wasn't kept. The netplan
            # configuration will use DHCP on the boot_interface. Allow it
            # to be selected for a ScriptResult during commissioning so
            # regeneration works.
            ifaces = [self._node.boot_interface]
        return ifaces

    def clean_parameters(self):
        """Validate the parameters set in the embedded YAML within the script."""
        parameters = self.data.get("parameters")
        if not isinstance(parameters, dict):
            set_form_error(self, "parameters", "Must be a dictionary")
            return

        for param, fields in parameters.items():
            # All parameter values should have a type defined.
            # Only currently supported parameter types are storage and runtime.
            param_type = fields.get("type")
            param_min = fields.get("min")
            param_max = fields.get("max")
            param_title = fields.get("title")
            param_description = fields.get("description")
            param_argument_format = fields.get("argument_format")
            param_default = fields.get("default")
            param_required = fields.get("required", True)
            allow_list = fields.get("allow_list")

            # Check param data type.
            if not isinstance(param, str):
                set_form_error(
                    self,
                    "parameters",
                    "%s: parameter must be a string" % param,
                )
            # Check fields data types.
            if not isinstance(param_type, str):
                set_form_error(
                    self,
                    "parameters",
                    "%s: type must be a string" % param_type,
                )
            if param_min is not None and not isinstance(param_min, int):
                set_form_error(
                    self,
                    "parameters",
                    "%s: min must be an integer" % param_min,
                )
            if param_max is not None and not isinstance(param_max, int):
                set_form_error(
                    self,
                    "parameters",
                    "%s: max must be an integer" % param_max,
                )
            if param_title is not None and not isinstance(param_title, str):
                set_form_error(
                    self,
                    "parameters",
                    "%s: title must be a string" % param_title,
                )
            if param_description is not None and not isinstance(
                param_description, str
            ):
                set_form_error(
                    self,
                    "parameters",
                    "%s: description must be a string" % param_description,
                )
            if param_argument_format is not None and not isinstance(
                param_argument_format, str
            ):
                set_form_error(
                    self,
                    "parameters",
                    "%s: argument_format must be a string"
                    % param_argument_format,
                )
            if param_default is not None and not isinstance(
                param_default, str
            ):
                set_form_error(
                    self,
                    "parameters",
                    "%s: default must be a string" % param_default,
                )
            if param_required is not None and not isinstance(
                param_required, bool
            ):
                set_form_error(
                    self,
                    "parameters",
                    "%s: required must be a boolean" % param_required,
                )
            if allow_list is not None and not isinstance(allow_list, bool):
                set_form_error(
                    self,
                    "parameters",
                    "%s: allow_list must be a boolean" % allow_list,
                )
            if allow_list is not None and param_type != "url":
                set_form_error(
                    self,
                    "parameters",
                    "allow_list only supported with the url type.",
                )

            # Check parameter type is supported and required.
            if (
                param_type not in ("storage", "interface", "url", "runtime")
                and param_required
            ):
                set_form_error(
                    self,
                    "parameters",
                    "%s: type must be either storage, interface, url, or "
                    "runtime" % param_type,
                )
            if param_type in ("storage", "interface", "url") and (
                param_min is not None or param_max is not None
            ):
                set_form_error(
                    self, "parameters", "Type doesn't support min or max"
                )
            if param_type == "runtime" and isinstance(param_min, int):
                if param_min < 0:
                    set_form_error(
                        self,
                        "parameters",
                        "runtime minimum must be greater than zero",
                    )
            if isinstance(param_min, int) and isinstance(param_max, int):
                if param_min > param_max:
                    set_form_error(
                        self, "parameters", "min must be less than max"
                    )
            if isinstance(param_argument_format, str):
                if param_type == "storage":
                    if not any(
                        format in param_argument_format
                        for format in (
                            "{input}",
                            "{name}",
                            "{path}",
                            "{model}",
                            "{serial}",
                        )
                    ):
                        set_form_error(
                            self,
                            "parameters",
                            "%s: argument_format must contain one of {input}, "
                            "{name}, {path}, {model}, {serial}" % param_type,
                        )
                elif param_type == "interface":
                    if not any(
                        format in param_argument_format
                        for format in (
                            "{input}",
                            "{name}",
                            "{mac}",
                            "{vendor}",
                            "{product}",
                        )
                    ):
                        set_form_error(
                            self,
                            "parameters",
                            "%s: argument_format must contain one of {input}, "
                            "{name}, {mac}, {vendor}, {product}" % param_type,
                        )
                else:
                    if "{input}" not in param_argument_format:
                        set_form_error(
                            self,
                            "parameters",
                            "%s: argument_format must contain {input}"
                            % param_type,
                        )

        return parameters

    def _setup_input(self):
        """Split input result and multi_result categories and set defaults.

        Users may specify multiple devices for the storage and interface
        parameters. This results in one ScriptResult per device to allow each
        each device to have its own logs and results. Each ScriptResult
        needs to include values for all parameters. The two lists will be
        combined later so each ScriptResult has a complete set of parameters.

        Any parameter which was not defined will have its default value set,
        if available.
        """
        parameters = self.data.get("parameters", {})
        input = self.data.get("input", {})

        if not isinstance(input, dict):
            set_form_error(self, "input", "Input must be a dictionary")
            return {}, {}

        # Paramaters which map to a single ScriptResult
        result_params = {}
        # Paramaters which may require multiple ScriptResults(storage)
        multi_result_params = {}

        # Split user input into params which need one ScriptResult per
        # param and one which may need multiple ScriptResults per param.
        for param_name, value in input.items():
            if param_name not in parameters:
                set_form_error(
                    self,
                    "input",
                    "Unknown parameter '%s' for %s"
                    % (param_name, self._script.name),
                )
                continue
            if parameters[param_name]["type"] in ("storage", "interface"):
                multi_result_params[param_name] = copy.deepcopy(
                    parameters[param_name]
                )
                multi_result_params[param_name]["value"] = value
            else:
                result_params[param_name] = copy.deepcopy(
                    parameters[param_name]
                )
                result_params[param_name]["value"] = value

        # Check for any paramaters not given which have defaults.
        for param_name, param in parameters.items():
            if (
                param["type"] in ("storage", "interface")
                and param_name not in multi_result_params
            ):
                default = param.get("default", "all")
                if not default and param.get("required", True):
                    set_form_error(self, param_name, "Field is required")
                elif default:
                    multi_result_params[param_name] = copy.deepcopy(param)
                    multi_result_params[param_name]["value"] = default
            elif param_name not in result_params:
                if param["type"] == "runtime":
                    default = param.get(
                        "default", self._script.timeout.seconds
                    )
                    if not isinstance(default, int) and param.get(
                        "required", True
                    ):
                        set_form_error(self, param_name, "Field is required")
                    elif isinstance(default, int):
                        result_params[param_name] = copy.deepcopy(param)
                        result_params[param_name]["value"] = default
                else:
                    default = param.get("default", "")
                    if not default and param.get("required", False):
                        set_form_error(self, param_name, "Field is required")
                    elif default:
                        result_params[param_name] = copy.deepcopy(param)
                        result_params[param_name]["value"] = default

        return result_params, multi_result_params

    def _validate_and_clean_runtime(self, param_name, param):
        """Validate and clean runtime input."""
        value = param["value"]
        min_value = param.get("min", 0)
        max_value = param.get("max")
        if isinstance(value, str) and value.isdigit():
            value = int(value)
        if not isinstance(value, int):
            set_form_error(self, param_name, "Must be an int")
            return
        if value < min_value:
            set_form_error(
                self, param_name, "Must be greater than %s" % min_value
            )
        if max_value is not None and value > max_value:
            set_form_error(
                self, param_name, "Must be less than %s" % max_value
            )

    def _blockdevice_to_dict(self, block_device):
        """Convert a block device to a dictionary with limited fields."""
        return {
            "name": block_device.name,
            "id_path": block_device.id_path,
            "model": block_device.model,
            "serial": block_device.serial,
            "physical_blockdevice": block_device,
        }

    def _validate_and_clean_storage_all(
        self, param_name, param, result_params, ret
    ):
        """Validate and clean storage input when set to all."""
        if len(self._node.physicalblockdevice_set) == 0:
            # Use 'all' as a place holder until the disks get added during
            # commissioning.
            clean_param = copy.deepcopy(result_params)
            clean_param[param_name] = param
            ret.append(clean_param)
        else:
            for bd in self._node.physicalblockdevice_set:
                clean_param = copy.deepcopy(result_params)
                clean_param[param_name] = copy.deepcopy(param)
                clean_param[param_name]["value"] = self._blockdevice_to_dict(
                    bd
                )
                ret.append(clean_param)

    def _validate_and_clean_storage_id(
        self, param_name, param, result_params, ret
    ):
        """Validate and clean storage input when id."""
        try:
            bd = self._node.physicalblockdevice_set.get(id=int(param["value"]))
        except ObjectDoesNotExist:
            set_form_error(
                self, param_name, "Physical block id does not exist"
            )
        else:
            clean_param = copy.deepcopy(result_params)
            clean_param[param_name] = copy.deepcopy(param)
            clean_param[param_name]["value"] = self._blockdevice_to_dict(bd)
            ret.append(clean_param)

    def _validate_and_clean_storage(
        self, param_name, param, result_params, ret
    ):
        """Validate and clean storage input."""
        value = param["value"]
        for i in value.split(","):
            if ":" in i:
                # Allow users to specify a disk using the model and serial.
                model, serial = i.split(":")
                try:
                    bd = self._node.physicalblockdevice_set.get(
                        model=model, serial=serial
                    )
                except ObjectDoesNotExist:
                    pass
                else:
                    clean_param = copy.deepcopy(result_params)
                    clean_param[param_name] = copy.deepcopy(param)
                    clean_param[param_name][
                        "value"
                    ] = self._blockdevice_to_dict(bd)
                    ret.append(clean_param)
                    continue

            qs = self._node.physicalblockdevice_set.filter(
                Q(name=i)
                | Q(name=os.path.basename(i))
                | Q(model=i)
                | Q(serial=i)
                | Q(tags__overlap=[i])
            )
            if len(qs) == 0:
                set_form_error(
                    self,
                    param_name,
                    "Unknown storage device for %s(%s)"
                    % (self._node.fqdn, self._node.system_id),
                )
                continue
            for bd in qs:
                clean_param = copy.deepcopy(result_params)
                clean_param[param_name] = copy.deepcopy(param)
                clean_param[param_name]["value"] = self._blockdevice_to_dict(
                    bd
                )
                ret.append(clean_param)

    def _interface_to_dict(self, interface):
        """Convert an interface to a dictionary with limited fields."""
        return {
            "name": interface.name,
            "mac_address": str(interface.mac_address),
            "vendor": interface.vendor,
            "product": interface.product,
            "interface": interface,
        }

    def _validate_and_clean_interface_all(
        self, param_name, param, result_params, ret
    ):
        """Validate and clean interface input when set to all."""
        interfaces = self._get_interfaces()
        if len(interfaces) == 0:
            # Use 'all' as a place holder until the Interfaces get added during
            # commissioning.
            clean_param = copy.deepcopy(result_params)
            clean_param[param_name] = param
            ret.append(clean_param)
        else:
            for interface in interfaces:
                clean_param = copy.deepcopy(result_params)
                clean_param[param_name] = copy.deepcopy(param)
                clean_param[param_name]["value"] = self._interface_to_dict(
                    interface
                )
                ret.append(clean_param)

    def _validate_and_clean_interface_id(
        self, param_name, param, result_params, ret
    ):
        """Validate and clean interface input when id."""
        interfaces = self._get_interfaces(id=int(param["value"]))
        if len(interfaces) != 1:
            set_form_error(self, param_name, "Interface id does not exist")
        else:
            clean_param = copy.deepcopy(result_params)
            clean_param[param_name] = copy.deepcopy(param)
            clean_param[param_name]["value"] = self._interface_to_dict(
                interfaces[0]
            )
            ret.append(clean_param)

    def _validate_and_clean_interface(
        self, param_name, param, result_params, ret
    ):
        """Validate and clean interface input."""
        value = param["value"]
        for i in value.split(","):
            if ":" in i:
                # Allow users to specify an Interface using the vendor and
                # product.
                vendor, product = i.split(":")
                interfaces = self._get_interfaces(
                    vendor=vendor, product=product
                )
                if len(interfaces) != 0:
                    for interface in interfaces:
                        clean_param = copy.deepcopy(result_params)
                        clean_param[param_name] = copy.deepcopy(param)
                        clean_param[param_name][
                            "value"
                        ] = self._interface_to_dict(interface)
                        ret.append(clean_param)
                    continue

            if is_mac(i):
                interfaces = self._get_interfaces(mac_address=i)
            else:
                interfaces = self._get_interfaces(
                    Q(name=i)
                    | Q(vendor=i)
                    | Q(product=i)
                    | Q(tags__overlap=[i])
                )
            if len(interfaces) == 0:
                set_form_error(
                    self,
                    param_name,
                    "Unknown interface for %s(%s)"
                    % (self._node.fqdn, self._node.system_id),
                )
                continue
            for interface in interfaces:
                clean_param = copy.deepcopy(result_params)
                clean_param[param_name] = copy.deepcopy(param)
                clean_param[param_name]["value"] = self._interface_to_dict(
                    interface
                )
                ret.append(clean_param)

    def _validate_and_clean_url(self, param_name, param):
        """Validate and clean URL input."""
        if param.get("allow_list", False):
            value = param["value"].split(",")
        else:
            value = [param["value"]]

        for url in value:
            # Django's validator requires a protocol but we accept just a
            # hostname or IP address.
            try:
                ip = ip_address(url)
            except ValueError:
                if "://" not in url:
                    url = "http://%s" % url
            else:
                if ip.version == 4:
                    url = "http://%s" % url
                else:
                    url = "http://[%s]" % url
            # Allow all schemes supported by curl(used with the network
            # validation test) + icmp.
            try:
                validate_url(
                    url,
                    schemes=[
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
                    ],
                )
            except ValidationError:
                set_form_error(self, param_name, "Invalid URL")

    def clean_input(self):
        """Validate and clean parameter input.

        Validate that input is correct per the parameter description. Storage
        input will be transformed into a dictionary representing the selected
        storage device from the PhysicalBlockDevice type.

        input will be cleaned to be a list of parameter dicts. Each item in the
        list represents one set of parameters for the script. This allows each
        storage device to be run seperately.
        """
        ret = []
        # Only validating the parameter description, not input. Do nothing.
        if None in (self._script, self._node):
            return ret

        result_params, multi_result_params = self._setup_input()

        # Validate input for single ScriptResult params
        for param_name, param in result_params.items():
            if param["type"] == "runtime":
                self._validate_and_clean_runtime(param_name, param)
            elif param["type"] == "url":
                self._validate_and_clean_url(param_name, param)

        # Validate input for multi ScriptResult params
        for param_name, param in multi_result_params.items():
            value = param["value"]
            if param["type"] == "storage":
                if value == "all":
                    self._validate_and_clean_storage_all(
                        param_name, param, result_params, ret
                    )
                elif isinstance(value, int) or value.isdigit():
                    self._validate_and_clean_storage_id(
                        param_name, param, result_params, ret
                    )
                else:
                    self._validate_and_clean_storage(
                        param_name, param, result_params, ret
                    )
            elif param["type"] == "interface":
                if value == "all":
                    self._validate_and_clean_interface_all(
                        param_name, param, result_params, ret
                    )
                elif isinstance(value, int) or value.isdigit():
                    self._validate_and_clean_interface_id(
                        param_name, param, result_params, ret
                    )
                else:
                    self._validate_and_clean_interface(
                        param_name, param, result_params, ret
                    )

        if ret == []:
            return [result_params]
        else:
            return ret
