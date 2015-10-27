# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
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

import re
from socket import gethostname

from django import forms
from django.core.exceptions import ValidationError
from maasserver.bootresources import IMPORT_RESOURCES_SERVICE_PERIOD
from maasserver.fields import IPListFormField
from maasserver.models import BootResource
from maasserver.models.config import (
    Config,
    DEFAULT_OS,
    DNSSEC_VALIDATION_CHOICES,
)
from maasserver.storage_layouts import get_storage_layout_choices
from maasserver.utils.forms import compose_invalid_choice_text
from maasserver.utils.osystems import (
    list_all_usable_osystems,
    list_all_usable_releases,
    list_commissioning_choices,
    list_hwe_kernel_choices,
    list_osystem_choices,
    release_a_newer_than_b,
)


INVALID_URL_MESSAGE = "Enter a valid url (e.g. http://host.example.com)."


def validate_missing_boot_images(value):
    """Raise `ValidationError` when the value is equal to '---'. This is
    used when no boot images exist on all clusters, so the config value cannot
    be changed."""
    if value == '---':
        raise ValidationError(
            "Unable to determine supported operating systems, "
            "due to missing boot images.")


def make_default_osystem_field(*args, **kwargs):
    """Build and return the default_osystem field."""
    usable_oses = list_all_usable_osystems()
    os_choices = list_osystem_choices(usable_oses, include_default=False)
    if len(os_choices) == 0:
        os_choices = [('---', '--- No Usable Operating System ---')]
    field = forms.ChoiceField(
        initial=Config.objects.get_config('default_osystem'),
        choices=os_choices,
        validators=[validate_missing_boot_images],
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'osystem', os_choices)
        },
        **kwargs)
    return field


def get_default_usable_osystem(default_osystem):
    """Return the osystem from the clusters that matches the default_osystem.
    """
    usable_oses = list_all_usable_osystems()
    for usable_os in usable_oses:
        if usable_os["name"] == default_osystem:
            return usable_os
    return None


def list_choices_for_releases(releases):
    """List all the release choices."""
    return [
        (release['name'], release['title'])
        for release in releases
    ]


def make_default_distro_series_field(*args, **kwargs):
    """Build and return the default_distro_series field."""
    default_osystem = Config.objects.get_config('default_osystem')
    default_usable_os = get_default_usable_osystem(default_osystem)
    release_choices = [('---', '--- No Usable Release ---')]
    if default_usable_os is not None:
        releases = list_all_usable_releases(
            [default_usable_os])[default_osystem]
        valid_release_choices = list_choices_for_releases(releases)
        if len(valid_release_choices) > 0:
            release_choices = valid_release_choices
    field = forms.ChoiceField(
        initial=Config.objects.get_config('default_distro_series'),
        choices=release_choices,
        validators=[validate_missing_boot_images],
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'release', release_choices)
        },
        **kwargs)
    return field


def make_default_min_hwe_kernel_field(*args, **kwargs):
    """Build and return the default_min_hwe_kernel field."""
    kernel_choices = [('', '--- No minimum kernel ---')]
    # Global choices are limited to the commissioning release as min_hwe_kernel
    # is used during commissioning.
    commissioning_series = Config.objects.get_config(
        'commissioning_distro_series')
    if commissioning_series:
        commissioning_os_release = "ubuntu/" + commissioning_series
        kernel_choices += list_hwe_kernel_choices(
            [kernel
             for kernel in BootResource.objects.get_usable_hwe_kernels(
                 commissioning_os_release)
             if release_a_newer_than_b(kernel, commissioning_series)])
    field = forms.ChoiceField(
        initial=Config.objects.get_config('default_min_hwe_kernel'),
        choices=kernel_choices,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'default_min_hwe_kernel', kernel_choices)
        },
        **kwargs)
    return field


def make_commissioning_distro_series_field(*args, **kwargs):
    """Build and return the commissioning_distro_series field."""
    usable_oses = list_all_usable_osystems()
    commissioning_choices = list_commissioning_choices(usable_oses)
    if len(commissioning_choices) == 0:
        commissioning_choices = [('---', '--- No Usable Release ---')]
    field = forms.ChoiceField(
        initial=Config.objects.get_config('commissioning_distro_series'),
        choices=commissioning_choices,
        validators=[validate_missing_boot_images],
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'commissioning_distro_series', commissioning_choices)
        },
        **kwargs)
    return field


def make_dnssec_validation_field(*args, **kwargs):
    """Build and return the make_dnssec_validation_field field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS['dnssec_validation']['default'],
        choices=DNSSEC_VALIDATION_CHOICES,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'dnssec_validation', DNSSEC_VALIDATION_CHOICES)
        },
        **kwargs)
    return field


CONFIG_ITEMS = {
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
        'form': IPListFormField,
        'form_kwargs': {
            'label': (
                "Upstream DNS used to resolve domains not managed by this "
                "MAAS (space-separated IP addresses)"),
            'required': False,
            'help_text': (
                "Only used when MAAS is running its own DNS server. This "
                "value is used as the value of 'forwarders' in the DNS "
                "server config.")
        }
    },
    'dnssec_validation': {
        'default': 'auto',
        'form': make_dnssec_validation_field,
        'form_kwargs': {
            'label': (
                "Enable DNSSEC validation of upstream zones"),
            'required': False,
            'help_text': (
                "Only used when MAAS is running its own DNS server. This "
                "value is used as the value of 'dnssec_validation' in the DNS "
                "server config.")
        }
    },
    'ntp_server': {
        'default': None,
        'form': forms.CharField,
        'form_kwargs': {
            'label': "Address of NTP server for nodes",
            'required': False,
            'help_text': (
                "NTP server address passed to nodes via a DHCP response. "
                "e.g. ntp.ubuntu.com")
        }
    },
    'default_osystem': {
        'form': make_default_osystem_field,
        'form_kwargs': {
            'label': "Default operating system used for deployment",
            'required': False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        }
    },
    'default_distro_series': {
        'form': make_default_distro_series_field,
        'form_kwargs': {
            'label': "Default OS release used for deployment",
            'required': False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        }
    },
    'default_min_hwe_kernel': {
        'default': None,
        'form': make_default_min_hwe_kernel_field,
        'form_kwargs': {
            'label': "Default Minimum Kernel Version",
            'required': False,
            'help_text': (
                "The default minimum kernel version used on all new and"
                " commissioned nodes."
            )
        }
    },
    'default_storage_layout': {
        'default': 'lvm',
        'form': forms.ChoiceField,
        'form_kwargs': {
            'label': "Default storage layout",
            'choices': get_storage_layout_choices(),
            'help_text': (
                "Storage layout that is applied to a node when it is acquired."
            )
        }
    },
    'commissioning_distro_series': {
        'default': DEFAULT_OS.get_default_commissioning_release(),
        'form': make_commissioning_distro_series_field,
        'form_kwargs': {
            'label': "Default Ubuntu release used for commissioning",
            'required': False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
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
    'windows_kms_host': {
        'default': None,
        'form': forms.CharField,
        'form_kwargs': {
            'required': False,
            'label': "Windows KMS activation host",
            'help_text': (
                "FQDN or IP address of the host that provides the KMS Windows "
                "activation service. (Only needed for Windows deployments "
                "using KMS activation.)")
        }
    },
    'enable_disk_erasing_on_release': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': (
                "Erase nodes' disks prior to releasing.")
        }
    },
    'boot_images_auto_import': {
        'default': True,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': (
                "Automatically import/refresh the boot images "
                "every %d minutes" %
                (IMPORT_RESOURCES_SERVICE_PERIOD.total_seconds() / 60.0))
        }
    },
    'curtin_verbose': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': (
                "Run the fast-path installer with higher verbosity. This "
                "provides more detail in the installation logs.")
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
    full_text = (' ' * indentation).join(doc)
    return re.sub('\s+$', '', full_text, flags=re.MULTILINE)
