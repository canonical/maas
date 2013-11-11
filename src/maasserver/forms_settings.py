# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
    'compose_invalid_choice_text',
    'CONFIG_ITEMS',
    'CONFIG_ITEMS_KEYS',
    'get_config_field',
    'get_config_form',
    'validate_config_name',
]

from socket import gethostname

from django import forms
from maasserver.enum import (
    DISTRO_SERIES,
    DISTRO_SERIES_CHOICES,
    NODE_AFTER_COMMISSIONING_ACTION,
    NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
    )
from provisioningserver.enum import (
    POWER_TYPE,
    POWER_TYPE_CHOICES,
    )


def compose_invalid_choice_text(choice_of_what, valid_choices):
    """Compose an "invalid choice" string for form error messages.

    This returns a template string that is intended to be used as the
    argument to the 'error_messages' parameter in a Django form.

    :param choice_of_what: The name for what the selected item is supposed
        to be, to be inserted into the error string.
    :type choice_of_what: unicode
    :param valid_choices: Valid choices, in Django choices format:
        (name, value).
    :type valid_choices: sequence
    """
    return "%s is not a valid %s.  It should be one of: %s." % (
        "%(value)s",
        choice_of_what,
        ", ".join(name for name, value in valid_choices),
    )


INVALID_URL_MESSAGE = "Enter a valid url (e.g. http://host.example.com)."


INVALID_DISTRO_SERIES_MESSAGE = compose_invalid_choice_text(
    'distro_series', DISTRO_SERIES_CHOICES)


CONFIG_ITEMS = {
    'after_commissioning': {
        'default': NODE_AFTER_COMMISSIONING_ACTION.DEFAULT,
        'form': forms.ChoiceField,
        'form_kwargs': {
            'choices': NODE_AFTER_COMMISSIONING_ACTION_CHOICES,
            'label': "After commissioning action"
        }
    },
    'check_compatibility': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': "Check component compatibility and certification"
        }
    },
    'node_power_type': {
        'default': POWER_TYPE.WAKE_ON_LAN,
        'form': forms.ChoiceField,
        'form_kwargs': {
            'choices': POWER_TYPE_CHOICES,
            'label': "Default node power type"
        }
    },
    #'fallback_master_archive': {},
    #'keep_mirror_list_uptodate': {},
    #'fetch_new_releases': {},
    'main_archive': {
        'default': 'http://archive.ubuntu.com/ubuntu',
        'form': forms.URLField,
        'form_kwargs': {
            'label': "Main archive",
            'error_messages': {'invalid': INVALID_URL_MESSAGE},
            'help_text': (
                "Archive used by nodes to retrieve packages and by cluster "
                "controllers to retrieve boot images (Intel architectures). "
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
                "Archive used by cluster controllers to retrieve boot "
                "images (non-Intel architectures). "
                "E.g. http://ports.ubuntu.com/ubuntu-ports."
            )
        }
    },
    'cloud_images_archive': {
        'default': 'https://maas.ubuntu.com/images',
        'form': forms.URLField,
        'form_kwargs': {
            'label': "Cloud images archive",
            'error_messages': {'invalid': INVALID_URL_MESSAGE},
            'help_text': (
                "Archive used by the nodes to retrieve ephemeral images. "
                "E.g. https://maas.ubuntu.com/images."
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
    'default_distro_series': {
        'default': DISTRO_SERIES.precise,
        'form': forms.ChoiceField,
        'form_kwargs': {
            'label': "Default distro series used for deployment",
            'choices': DISTRO_SERIES_CHOICES,
            'required': False,
            'error_messages': {
                'invalid_choice': INVALID_DISTRO_SERIES_MESSAGE},
        }
    },
    'commissioning_distro_series': {
        'default': DISTRO_SERIES.precise,
        'form': forms.ChoiceField,
        'form_kwargs': {
            'label': "Default distro series used for commissioning",
            'choices': DISTRO_SERIES_CHOICES,
            'required': False,
            'error_messages': {
                'invalid_choice': INVALID_DISTRO_SERIES_MESSAGE},
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
        help_text = form_details.get('help_text', "")
        doc.append(help_text)
        # Append list of possible choices if present.
        choices = form_details.get('choices')
        if choices is not None:
            choice_descr = describe_choices(choices)
            doc.append("Available choices are: %s." % choice_descr)
        doc.append("\n")
    return (' ' * indentation).join(doc)
