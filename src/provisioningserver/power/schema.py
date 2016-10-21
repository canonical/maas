# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Define json schema for power parameters."""

__all__ = [
    "JSON_POWER_TYPE_PARAMETERS",
    "JSON_POWER_TYPE_SCHEMA",
    "POWER_TYPE_PARAMETER_FIELD_SCHEMA",
    ]


from jsonschema import validate

# We specifically declare this here so that a node not knowing its own
# powertype won't fail to enlist. However, we don't want it in the list
# of power types since setting a node's power type to "I don't know"
# from another type doens't make any sense.
UNKNOWN_POWER_TYPE = ''


class POWER_PARAMETER_SCOPE:
    BMC = "bmc"
    NODE = "node"


# Some commonly used patterns here for convenience and re-use.
class IP_EXTRACTOR_PATTERNS:

    # Use the entire string as the value.
    IDENTITY = '^(?P<address>.+?)$'

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
    URL = (r'^'
           r'((?P<schema>.+?)://)?'
           r'((?P<user>.+?)(:(?P<password>.*?))?@)?'

           r'(?:\[(?=[0-9a-fA-F]*:[0-9a-fA-F.:]+\]))?'
           r'(?P<address>(?:(?:[^\[\]/:]*(?!\]))|'
           r'(?:(?<=\[)[0-9a-fA-F:.]+(?=\]))))\]?'

           r'(:(?P<port>\d+?))?'
           r'(?P<path>/.*?)?'
           r'(?P<query>[?].*?)?'
           r'$'
           )


class IPMI_DRIVER:
    DEFAULT = ''
    LAN = 'LAN'
    LAN_2_0 = 'LAN_2_0'


IPMI_DRIVER_CHOICES = [
    [IPMI_DRIVER.LAN, "LAN [IPMI 1.5]"],
    [IPMI_DRIVER.LAN_2_0, "LAN_2_0 [IPMI 2.0]"],
    ]


# Represent the Django choices format as JSON; an array of 2-item
# arrays.
CHOICE_FIELD_SCHEMA = {
    'type': 'array',
    'items': {
        'title': "Power type parameter field choice",
        'type': 'array',
        'minItems': 2,
        'maxItems': 2,
        'uniqueItems': True,
        'items': {
            'type': 'string',
        }
    },
}


# Python REGEX pattern for extracting IP address from parameter field.
# The field_name tells the extractor which power_parameter field to use.
# Name the address field 'address' in your Python regex pattern.
# The pattern will be used as in 're.match(pattern, field_value)'.
IP_EXTRACTOR_SCHEMA = {
    'title': "IP Extractor Configuration",
    'type': 'object',
    'properties': {
        'field_name': {
            'type': 'string',
        },
        'pattern': {
            'type': 'string',
        },
    },
    "dependencies": {
        "field_name": ["pattern"],
        "pattern": ["field_name"]
    },
}

POWER_TYPE_PARAMETER_FIELD_SCHEMA = {
    'title': "Power type parameter field",
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
        },
        'field_type': {
            'type': 'string',
        },
        'label': {
            'type': 'string',
        },
        'required': {
            'type': 'boolean',
        },
        # 'bmc' or 'node': Whether value lives on bmc (global) or node/device.
        'scope': {
            'type': 'string',
        },
        'choices': CHOICE_FIELD_SCHEMA,
        'default': {
            'type': 'string',
        },
    },
    'required': ['field_type', 'label', 'required'],
}


# A basic JSON schema for what power type parameters should look like.
JSON_POWER_TYPE_SCHEMA = {
    'title': "Power parameters set",
    'type': 'array',
    'items': {
        'title': "Power type parameters",
        'type': 'object',
        'properties': {
            'name': {
                'type': 'string',
            },
            'description': {
                'type': 'string',
            },
            'missing_packages': {
                'type': 'array',
                'items': {
                    'type': 'string',
                },
            },
            'fields': {
                'type': 'array',
                'items': POWER_TYPE_PARAMETER_FIELD_SCHEMA,
            },
            'ip_extractor': IP_EXTRACTOR_SCHEMA,
        },
        'required': ['name', 'description', 'fields'],
    },
}


# Power control choices for sm15k power type
SM15K_POWER_CONTROL_CHOICES = [
    ["ipmi", "IPMI"],
    ["restapi", "REST API v0.9"],
    ["restapi2", "REST API v2.0"],
    ]


def make_ip_extractor(field_name, pattern=IP_EXTRACTOR_PATTERNS.IDENTITY):
    return {
        'field_name': field_name,
        'pattern': pattern,
    }


def make_json_field(
        name, label, field_type=None, choices=None, default=None,
        required=False, scope=POWER_PARAMETER_SCOPE.BMC):
    """Helper function for building a JSON power type parameters field.

    :param name: The name of the field.
    :type name: string
    :param label: The label to be presented to the user for this field.
    :type label: string
    :param field_type: The type of field to create. Can be one of
        (string, choice, mac_address, password). Defaults to string.
    :type field_type: string.
    :param choices: The collection of choices to present to the user.
        Needs to be structured as a list of lists, otherwise
        make_json_field() will raise a ValidationError.
    :type list:
    :param default: The default value for the field.
    :type default: string
    :param required: Whether or not a value for the field is required.
    :type required: boolean
    :param scope: 'bmc' or 'node' - Whether value is bmc or node specific.
        Defaults to 'bmc'.
    :type scope: string
    """
    if field_type not in ('string', 'mac_address', 'choice', 'password'):
        field_type = 'string'
    if choices is None:
        choices = []
    validate(choices, CHOICE_FIELD_SCHEMA)
    if default is None:
        default = ""
    if scope not in (POWER_PARAMETER_SCOPE.BMC, POWER_PARAMETER_SCOPE.NODE):
        scope = POWER_PARAMETER_SCOPE.BMC
    field = {
        'name': name,
        'label': label,
        'required': required,
        'field_type': field_type,
        'choices': choices,
        'default': default,
        'scope': scope,
    }
    return field


# XXX: Each drivers should declare this stuff itself;
# this should not be configured centrally.
JSON_POWER_TYPE_PARAMETERS = [
    {
        'name': 'manual',
        'description': 'Manual',
        'fields': [],
    },
    {
        'name': 'virsh',
        'description': 'Virsh (virtual systems)',
        'fields': [
            make_json_field('power_address', "Power address", required=True),
            make_json_field(
                'power_id', "Power ID", scope=POWER_PARAMETER_SCOPE.NODE,
                required=True),
            make_json_field(
                'power_pass', "Power password (optional)",
                required=False, field_type='password'),
        ],
        'ip_extractor': make_ip_extractor(
            'power_address', IP_EXTRACTOR_PATTERNS.URL),
    },
    {
        'name': 'vmware',
        'description': 'VMWare',
        'fields': [
            make_json_field(
                'power_vm_name', "VM Name (if UUID unknown)", required=False,
                scope=POWER_PARAMETER_SCOPE.NODE),
            make_json_field(
                'power_uuid', "VM UUID (if known)", required=False,
                scope=POWER_PARAMETER_SCOPE.NODE),
            make_json_field('power_address', "VMware hostname", required=True),
            make_json_field('power_user', "VMware username", required=True),
            make_json_field(
                'power_pass', "VMware password", field_type='password',
                required=True),
            make_json_field(
                'power_port', "VMware API port (optional)", required=False),
            make_json_field(
                'power_protocol', "VMware API protocol (optional)",
                required=False),
        ],
    },
    {
        'name': 'fence_cdu',
        'description': 'Sentry Switch CDU',
        'fields': [
            make_json_field('power_address', "Power address", required=True),
            make_json_field(
                'power_id', "Power ID", scope=POWER_PARAMETER_SCOPE.NODE,
                required=True),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'ipmi',
        'description': 'IPMI',
        'fields': [
            make_json_field(
                'power_driver', "Power driver", field_type='choice',
                choices=IPMI_DRIVER_CHOICES, default=IPMI_DRIVER.LAN_2_0,
                required=True),
            make_json_field('power_address', "IP address", required=True),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
            make_json_field(
                'mac_address', "Power MAC", scope=POWER_PARAMETER_SCOPE.NODE)
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'moonshot',
        'description': 'HP Moonshot - iLO4 (IPMI)',
        'fields': [
            make_json_field('power_address', "Power address", required=True),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
            make_json_field(
                'power_hwaddress', "Power hardware address",
                scope=POWER_PARAMETER_SCOPE.NODE, required=True),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'sm15k',
        'description': 'SeaMicro 15000',
        'fields': [
            make_json_field(
                'system_id', "System ID", scope=POWER_PARAMETER_SCOPE.NODE,
                required=True),
            make_json_field('power_address', "Power address", required=True),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
            make_json_field(
                'power_control', "Power control type", field_type='choice',
                choices=SM15K_POWER_CONTROL_CHOICES, default='ipmi',
                required=True),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'amt',
        'description': 'Intel AMT',
        'fields': [
            make_json_field(
                'power_pass', "Power password", field_type='password'),
            make_json_field('power_address', "Power address", required=True)
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'dli',
        'description': 'Digital Loggers, Inc. PDU',
        'fields': [
            make_json_field(
                'outlet_id', "Outlet ID", scope=POWER_PARAMETER_SCOPE.NODE,
                required=True),
            make_json_field('power_address', "Power address", required=True),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'wedge',
        'description': "Facebook's Wedge",
        'fields': [
            make_json_field('power_address', "IP address", required=True),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'ucsm',
        'description': "Cisco UCS Manager",
        'fields': [
            make_json_field(
                'uuid', "Server UUID", scope=POWER_PARAMETER_SCOPE.NODE,
                required=True),
            make_json_field('power_address', "URL for XML API", required=True),
            make_json_field('power_user', "API user"),
            make_json_field(
                'power_pass', "API password", field_type='password'),
        ],
        'ip_extractor': make_ip_extractor(
            'power_address', IP_EXTRACTOR_PATTERNS.URL),
    },
    {
        'name': 'mscm',
        'description': "HP Moonshot - iLO Chassis Manager",
        'fields': [
            make_json_field(
                'power_address', "IP for MSCM CLI API", required=True),
            make_json_field('power_user', "MSCM CLI API user"),
            make_json_field(
                'power_pass', "MSCM CLI API password", field_type='password'),
            make_json_field(
                'node_id',
                "Node ID - Must adhere to cXnY format "
                "(X=cartridge number, Y=node number).",
                scope=POWER_PARAMETER_SCOPE.NODE, required=True),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'msftocs',
        'description': "Microsoft OCS - Chassis Manager",
        'fields': [
            make_json_field('power_address', "Power address", required=True),
            make_json_field('power_port', "Power port"),
            make_json_field('power_user', "Power user"),
            make_json_field(
                'power_pass', "Power password", field_type='password'),
            make_json_field(
                'blade_id', "Blade ID (Typically 1-24)",
                scope=POWER_PARAMETER_SCOPE.NODE, required=True),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'apc',
        'description': "American Power Conversion (APC) PDU",
        'fields': [
            make_json_field('power_address', "IP for APC PDU", required=True),
            make_json_field(
                'node_outlet', "APC PDU node outlet number (1-16)",
                scope=POWER_PARAMETER_SCOPE.NODE, required=True),
            make_json_field(
                'power_on_delay', "Power ON outlet delay (seconds)",
                default='5'),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'hmc',
        'description': "IBM Hardware Management Console (HMC)",
        'fields': [
            make_json_field('power_address', "IP for HMC", required=True),
            make_json_field('power_user', "HMC username"),
            make_json_field(
                'power_pass', "HMC password", field_type='password'),
            make_json_field(
                'server_name', "HMC Managed System server name",
                scope=POWER_PARAMETER_SCOPE.NODE, required=True),
            make_json_field(
                'lpar', "HMC logical partition",
                scope=POWER_PARAMETER_SCOPE.NODE, required=True),
        ],
        'ip_extractor': make_ip_extractor('power_address'),
    },
    {
        'name': 'nova',
        'description': 'OpenStack Nova',
        'fields': [
            make_json_field('nova_id', "Host UUID", required=True),
            make_json_field('os_tenantname', "Tenant name", required=True),
            make_json_field('os_username', "Username", required=True),
            make_json_field(
                'os_password', "Password", field_type='password',
                required=True),
            make_json_field('os_authurl', "Auth URL", required=True),
        ],
    },
]

POWER_TYPE_PARAMETERS_BY_NAME = {
    power_type['name']: power_type
    for power_type in JSON_POWER_TYPE_PARAMETERS
}

POWER_FIELDS_BY_TYPE = {
    power_type['name']: {
        field['name']: field
        for field in power_type['fields']
    }
    for power_type in JSON_POWER_TYPE_PARAMETERS
}
