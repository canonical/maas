# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items definition and utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    'CONFIG_ITEMS',
    'CONFIG_ITEMS_KEYS',
    'get_config_field',
    'get_config_form',
    'validate_config_name',
]

from socket import gethostname

from django import forms
from maasserver.models.config import DEFAULT_OS
from maasserver.utils.forms import compose_invalid_choice_text
from provisioningserver.drivers.osystem import OperatingSystemRegistry


INVALID_URL_MESSAGE = "Enter a valid url (e.g. http://host.example.com)."


def list_osystem_choices():
    osystems = [osystem for _, osystem in OperatingSystemRegistry]
    osystems = sorted(osystems, key=lambda osystem: osystem.title)
    return [
        (osystem.name, osystem.title)
        for osystem in osystems
        ]


def list_release_choices():
    osystems = [osystem for _, osystem in OperatingSystemRegistry]
    choices = []
    for osystem in osystems:
        supported = sorted(osystem.get_supported_releases())
        options = osystem.format_release_choices(supported)
        options = [
            ('%s/%s' % (osystem.name, name), title)
            for name, title in options
            ]
        choices += options
    return choices


def list_commisioning_choices():
    releases = DEFAULT_OS.get_supported_commissioning_releases()
    options = DEFAULT_OS.format_release_choices(releases)
    return list(options)


CONFIG_ITEMS = {
    'check_compatibility': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': "Check component compatibility and certification"
        }
    },
    'main_archive': {
        'default': 'http://archive.ubuntu.com/ubuntu',
        'form': forms.URLField,
        'form_kwargs': {
            'label': "Main archive",
            'error_messages': {'invalid': INVALID_URL_MESSAGE},
            'help_text': (
                "Archive used by nodes to retrieve packages for Intel "
                "architectures. "
                "E.g. http://archive.ubuntu.com/ubuntu."
            )
        }
    },
    'ports_archive': {
        'default': 'http://ports.ubuntu.com/ubuntu-ports',
        'form': forms.URLField,
        'form_kwargs': {
            'label': "Ports archive",
            'error_messages': {'invalid': INVALID_URL_MESSAGE},
            'help_text': (
                "Archive used by nodes to retrieve packages for non-Intel "
                "architectures. "
                "E.g. http://ports.ubuntu.com/ubuntu-ports."
            )
        }
    },
    'maas_name': {
        'default': gethostname(),
        'form': forms.CharField,
        'form_kwargs': {
            'label': "MAAS name",
        }
    },
    'kernel_opts': {
        'default': None,
        'form': forms.CharField,
        'form_kwargs': {
            'label': "Boot parameters to pass to the kernel by default",
            'required': False,
        }
    },
    'enlistment_domain': {
        'default': b'local',
        'form': forms.CharField,
        'form_kwargs': {
            'label': "Default domain for new nodes",
            'required': False,
            'help_text': (
                "If 'local' is chosen, nodes must be using mDNS. Leave "
                "empty to use hostnames without a domain for newly enlisted "
                "nodes.")
        }
    },
    'http_proxy': {
        'detault': None,
        'form': forms.URLField,
        'form_kwargs': {
            'label': "Proxy for HTTP and HTTPS traffic",
            'required': False,
            'help_text': (
                "This is used by the cluster and region controllers for "
                "downloading PXE boot images and other provisioning-related "
                "resources. This will also be passed onto provisioned "
                "nodes instead of the default proxy (the region controller "
                "proxy).")
        }
    },
    'upstream_dns': {
        'default': None,
        'form': forms.GenericIPAddressField,
        'form_kwargs': {
            'label': (
                "Upstream DNS used to resolve domains not managed by this "
                "MAAS"),
            'required': False,
            'help_text': (
                "Only used when MAAS is running its own DNS server. This "
                "value is used as the value of 'forwarders' in the DNS "
                "server config.")
        }
    },
    'ntp_server': {
        'default': None,
        'form': forms.GenericIPAddressField,
        'form_kwargs': {
            'label': "Address of NTP server for nodes",
            'required': False,
            'help_text': (
                "NTP server address passed to nodes via a DHCP response. "
                "e.g. for ntp.ubuntu.com: '91.189.94.4'")
        }
    },
    'default_osystem': {
        'default': DEFAULT_OS.name,
        'form': forms.ChoiceField,
        'form_kwargs': {
            'label': "Default operating system used for deployment",
            'choices': list_osystem_choices(),
            'required': False,
            'error_messages': {
                'invalid_choice': compose_invalid_choice_text(
                    'osystem',
                    list_osystem_choices())},
        }
    },
    'default_distro_series': {
        'default': '%s/%s' % (
            DEFAULT_OS.name,
            DEFAULT_OS.get_default_release()
            ),
        'form': forms.ChoiceField,
        'form_kwargs': {
            'label': "Default OS release used for deployment",
            'choices': list_release_choices(),
            'required': False,
            'error_messages': {
                'invalid_choice': compose_invalid_choice_text(
                    'distro_series',
                    list_release_choices())},
        }
    },
    'commissioning_distro_series': {
        'default': DEFAULT_OS.get_default_commissioning_release(),
        'form': forms.ChoiceField,
        'form_kwargs': {
            'label': "Default Ubuntu release used for commissioning",
            'choices': list_commisioning_choices(),
            'required': False,
            'error_messages': {
                'invalid_choice': compose_invalid_choice_text(
                    'commissioning_distro_series',
                    list_commisioning_choices())},
        }
    },
    'enable_third_party_drivers': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': (
                "Enable the installation of proprietary drivers (i.e. HPVSA)")
        }
    },
}


CONFIG_ITEMS_KEYS = CONFIG_ITEMS.keys()


INVALID_SETTING_MSG_TEMPLATE = (
    "%s is not a valid config setting (valid settings are: " +
    "%s)." % ', '.join(CONFIG_ITEMS.keys()))


def validate_config_name(config_name):
    if config_name not in CONFIG_ITEMS_KEYS:
        raise forms.ValidationError(
            {config_name: [INVALID_SETTING_MSG_TEMPLATE % config_name]})


def get_config_field(config_name, **kwargs):
    """Return a configuration field.

    :param config_name: Name of the configuration item.
    :type config_name: unicode
    :return: A configuration field
    :rtype: :class:`django.forms.Field`
    """
    validate_config_name(config_name)
    conf = CONFIG_ITEMS[config_name]
    kwargs.update(conf['form_kwargs'])
    return conf['form'](**kwargs)


def get_config_form(config_name, data=None):
    """Return a ConfigForm with one configuration field.

    :param config_name: Name of the configuration item.
    :type config_name: unicode
    :param data: Dict used to initialize the field of the form.
    :type data: dict
    :return: A configuration form with one field
    :rtype: :class:`maasserver.forms.ConfigForm`
    """
    # Avoid circular imports.
    from maasserver.forms import ConfigForm

    class LocalForm(ConfigForm):
        pass
    if data is None:
        data = {}
    form = LocalForm(data=data)
    form.fields[config_name] = get_config_field(config_name)
    form._load_initials()
    return form


def describe_choices(choices):
    """Describe the items in an enumeration of Django form choices."""
    return ', '.join(
        "'%s' (%s)" % (value, meaning) for value, meaning in choices)


def get_config_doc(indentation=0):
    """Return the documentation about the available configuration settings."""
    doc = ["Available configuration items:\n\n"]
    for config_name, config_details in CONFIG_ITEMS.items():
        form_details = config_details['form_kwargs']
        doc.append("- " + config_name + ": " + form_details['label'] + ". ")
        # Append help text if present.
        help_text = form_details.get('help_text')
        if help_text is not None:
            doc.append(help_text.strip())
        # Append list of possible choices if present.
        choices = form_details.get('choices')
        if choices is not None:
            choice_descr = describe_choices(choices)
            doc.append("Available choices are: %s." % choice_descr)
        doc.append("\n")
    return (' ' * indentation).join(doc)
