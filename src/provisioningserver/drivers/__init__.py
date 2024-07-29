# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Drivers."""


from jsonschema import validate

from provisioningserver.utils.registry import Registry


class IP_EXTRACTOR_PATTERNS:
    """Commonly used patterns IP extractor patterns."""

    # Use the entire string as the value.
    IDENTITY = "^(?P<address>.+?)$"

    # The typical URL pattern. Extracts address field as the value.
    # The given URL has an address component that is one of:
    # (1) an IPv6 IP address surrounded by []
    # (2) an IPv4 IP address (no [])
    # (3) a name
    # (4) the empty string.
    # Cases 2 and 3 are processed in the regex by excluding all []/: from the
    # allowed values.  The need to verify the [] around the IPv6 IP address
    # introduces a goodly amount of complexity due to looking forward/backward
    # to determine if [] is ok/expected.
    # The resulting address is simply the IP address (v6 or v4), or a hostname.
    URL = (
        r"^"
        r"((?P<schema>.+?)://)?"
        r"((?P<user>.+?)(:(?P<password>.*?))?@)?"
        r"(?:\[(?=[0-9a-fA-F]*:[0-9a-fA-F.:]+\]))?"
        r"(?P<address>(?:(?:[^\[\]/:]*(?!\]))|"
        r"(?:(?<=\[)[0-9a-fA-F:.]+(?=\]))))\]?"
        r"(:(?P<port>\d+?))?"
        r"(?P<path>/.*?)?"
        r"(?P<query>[?].*?)?"
        r"$"
    )


# Python REGEX pattern for extracting IP address from parameter field.
# The field_name tells the extractor which power_parameter field to use.
# Name the address field 'address' in your Python regex pattern.
# The pattern will be used as in 're.match(pattern, field_value)'.
IP_EXTRACTOR_SCHEMA = {
    "title": "IP Extractor Configuration",
    "type": "object",
    "properties": {
        "field_name": {"type": "string"},
        "pattern": {"type": "string"},
    },
    "dependencies": {"field_name": ["pattern"], "pattern": ["field_name"]},
}

# JSON schema representing the Django choices format as JSON; an array of
# 2-item arrays.
CHOICE_FIELD_SCHEMA = {
    "type": "array",
    "items": {
        "title": "Setting parameter field choice",
        "type": "array",
        "minItems": 2,
        "maxItems": 2,
        "uniqueItems": True,
        "items": {"type": "string"},
    },
}

# JSON schema for what a settings field should look like.
SETTING_PARAMETER_FIELD_SCHEMA = {
    "title": "Setting parameter field",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "field_type": {"type": "string"},
        "label": {"type": "string"},
        "required": {"type": "boolean"},
        # 'bmc' or 'node': Whether value lives on bmc (global) or node/device.
        "scope": {"type": "string"},
        "choices": CHOICE_FIELD_SCHEMA,
        "default": {"type": "string"},
    },
    "required": ["field_type", "label", "required"],
}


MULTIPLE_CHOICE_SETTING_PARAMETER_FIELD_SCHEMA = {
    "title": "Multiple choice setting parameter field",
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "field_type": {"type": "string"},
        "label": {"type": "string"},
        "required": {"type": "boolean"},
        "scope": {"type": "string"},
        "choices": CHOICE_FIELD_SCHEMA,
        "default": {"type": "array"},
    },
    "required": ["field_type", "label", "required"],
}


def make_ip_extractor(field_name, pattern=IP_EXTRACTOR_PATTERNS.IDENTITY):
    return {"field_name": field_name, "pattern": pattern}


class SETTING_SCOPE:
    BMC = "bmc"
    NODE = "node"


def make_setting_field(
    name,
    label,
    field_type=None,
    choices=None,
    default=None,
    required=False,
    scope=SETTING_SCOPE.BMC,
    secret=False,
):
    """Helper function for building a JSON setting parameters field.

    :param name: The name of the field.
    :type name: string
    :param label: The label to be presented to the user for this field.
    :type label: string
    :param field_type: The type of field to create. Can be one of
        (string, choice, multiple_choice, password, ip_address, mac_address).
        Defaults to string.
    :type field_type: string.
    :param choices: The collection of choices to present to the user.
        Needs to be structured as a list of lists, otherwise
        make_setting_field() will raise a ValidationError.
    :type list:
    :param default: The default value for the field.
    :type default: string
    :param required: Whether or not a value for the field is required.
    :type required: boolean
    :param scope: 'bmc' or 'node' - Whether value is bmc or node specific.
        Defaults to 'bmc'.
    :type scope: string
    :param secret: True or False - Whether value should be stored securely.
        Defaults to False
    :type secret: boolean
    """
    if field_type not in (
        "string",
        "mac_address",
        "choice",
        "multiple_choice",
        "password",
        "ip_address",
        "virsh_address",
        "lxd_address",
    ):
        field_type = "string"
    if choices is None:
        choices = []
    validate(choices, CHOICE_FIELD_SCHEMA)
    if default is None:
        default = [] if field_type == "multiple_choice" else ""
    if scope not in (SETTING_SCOPE.BMC, SETTING_SCOPE.NODE):
        scope = SETTING_SCOPE.BMC
    return {
        "name": name,
        "label": label,
        "required": required,
        "field_type": field_type,
        "choices": choices,
        "default": default,
        "scope": scope,
        "secret": secret,
    }


class Architecture:
    def __init__(
        self, name, description, pxealiases=None, kernel_options=None
    ):
        """Represents an architecture in the driver context.

        :param name: The architecture name as used in MAAS.
            arch/subarch or just arch.
        :param description: The human-readable description for the
            architecture.
        :param pxealiases: The optional list of names used if the
            hardware uses a different name when requesting its bootloader.
        :param kernel_options: The optional list of kernel options for this
            architecture.  Anything supplied here supplements the options
            provided by MAAS core.
        """
        if pxealiases is None:
            pxealiases = ()
        self.name = name
        self.description = description
        self.pxealiases = pxealiases
        self.kernel_options = kernel_options


class ArchitectureRegistry(Registry):
    """Registry for architecture classes."""

    @classmethod
    def get_by_pxealias(cls, alias: str):
        for _, arch in cls:
            if alias in arch.pxealiases:
                return arch
        return None


builtin_architectures = [
    Architecture(name="i386/generic", description="i386"),
    Architecture(name="amd64/generic", description="amd64"),
    Architecture(
        name="arm64/generic", description="arm64/generic", pxealiases=["arm"]
    ),
    Architecture(
        name="arm64/xgene-uboot",
        description="arm64/xgene-uboot",
        pxealiases=["arm"],
    ),
    Architecture(
        name="arm64/xgene-uboot-mustang",
        description="arm64/xgene-uboot-mustang",
        pxealiases=["arm"],
    ),
    Architecture(
        name="armhf/highbank",
        description="armhf/highbank",
        pxealiases=["arm"],
        kernel_options=["console=ttyAMA0"],
    ),
    Architecture(
        name="armhf/generic",
        description="armhf/generic",
        pxealiases=["arm"],
        kernel_options=["console=ttyAMA0"],
    ),
    Architecture(
        name="armhf/keystone", description="armhf/keystone", pxealiases=["arm"]
    ),
    # PPC64EL needs a rootdelay for PowerNV. The disk controller
    # in the hardware, takes a little bit longer to come up then
    # the initrd wants to wait. Set this to 60 seconds, just to
    # give the booting machine enough time. This doesn't slow down
    # the booting process, it just increases the timeout.
    Architecture(
        name="ppc64el/generic",
        description="ppc64el",
        kernel_options=["rootdelay=60"],
    ),
]
for arch in builtin_architectures:
    ArchitectureRegistry.register_item(arch.name, arch)
