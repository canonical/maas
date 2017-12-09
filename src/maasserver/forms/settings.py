# Copyright 2013-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items definition and utilities."""

__all__ = [
    'CONFIG_ITEMS',
    'CONFIG_ITEMS_KEYS',
    'get_config_field',
    'get_config_form',
    'validate_config_name',
    ]

from datetime import timedelta
import re
from socket import gethostname

from django import forms
from django.core.exceptions import ValidationError
from maasserver.bootresources import IMPORT_RESOURCES_SERVICE_PERIOD
from maasserver.fields import (
    HostListFormField,
    IPListFormField,
)
from maasserver.models import BootResource
from maasserver.models.config import (
    ACTIVE_DISCOVERY_INTERVAL_CHOICES,
    Config,
    DEFAULT_OS,
    DNSSEC_VALIDATION_CHOICES,
    NETWORK_DISCOVERY_CHOICES,
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
from provisioningserver.utils.text import normalise_whitespace


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
    """Build and return the dnssec_validation field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS['dnssec_validation']['default'],
        choices=DNSSEC_VALIDATION_CHOICES,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'dnssec_validation', DNSSEC_VALIDATION_CHOICES)
        },
        **kwargs)
    return field


def make_network_discovery_field(*args, **kwargs):
    """Build and return the network_discovery field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS['network_discovery']['default'],
        choices=NETWORK_DISCOVERY_CHOICES,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'network_discovery', NETWORK_DISCOVERY_CHOICES)
        },
        **kwargs)
    return field


def make_active_discovery_interval_field(*args, **kwargs):
    """Build and return the network_discovery field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS['active_discovery_interval']['default'],
        choices=ACTIVE_DISCOVERY_INTERVAL_CHOICES,
        error_messages={
            'invalid_choice': compose_invalid_choice_text(
                'active_discovery_interval', ACTIVE_DISCOVERY_INTERVAL_CHOICES)
        },
        **kwargs)
    return field


CONFIG_ITEMS = {
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
    'enable_http_proxy': {
        'default': True,
        'form': forms.BooleanField,
        'form_kwargs': {
            'label': "Enable the use of an APT and HTTP/HTTPS proxy",
            'required': False,
            'help_text': (
                "Provision nodes to use the built-in HTTP proxy (or "
                "user specified proxy) for APT. MAAS also uses the proxy for "
                "downloading boot images.")
        }
    },
    'use_peer_proxy': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'label': "Use the built-in proxy with an external proxy as a peer",
            'required': False,
            'help_text': (
                "If enable_http_proxy is set, the built-in proxy will be "
                "configured to use http_proxy as a peer proxy. The deployed "
                "machines will be configured to use the built-in proxy.")
        }
    },
    'http_proxy': {
        'default': None,
        'form': forms.URLField,
        'form_kwargs': {
            'label': "Proxy for APT and HTTP/HTTPS",
            'required': False,
            'help_text': (
                "This will be passed onto provisioned nodes to use as a "
                "proxy for APT traffic. MAAS also uses the proxy for "
                "downloading boot images. If no URL is provided, the built-in "
                "MAAS proxy will be used.")
        }
    },
    'default_dns_ttl': {
        'default': 30,
        'form': forms.IntegerField,
        'form_kwargs': {
            'label': "Default Time-To-Live for the DNS",
            'required': False,
            'help_text': (
                "If no TTL value is specified at a more specific point "
                "this is how long DNS responses are valid, in seconds.")
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
    'ntp_servers': {
        'default': None,
        'form': HostListFormField,
        'form_kwargs': {
            'label': "Addresses of NTP servers",
            'required': False,
            'help_text': normalise_whitespace("""\
                NTP servers, specified as IP addresses or hostnames delimited
                by commas and/or spaces, to be used as time references for
                MAAS itself, the machines MAAS deploys, and devices that make
                use of MAAS's DHCP services.
            """),
        }
    },
    'ntp_external_only': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'label': "Use external NTP servers only",
            'required': False,
            'help_text': normalise_whitespace("""\
                Configure all region controller hosts, rack controller hosts,
                and subsequently deployed machines to refer directly to the
                configured external NTP servers. Otherwise only region
                controller hosts will be configured to use those external NTP
                servers, rack contoller hosts will in turn refer to the
                regions' NTP servers, and deployed machines will refer to the
                racks' NTP servers.
            """),
        }
    },
    'network_discovery': {
        'default': 'enabled',
        'form': make_network_discovery_field,
        'form_kwargs': {
            'label': "",
            'required': False,
            'help_text': (
                "When enabled, MAAS will use passive techniques (such as "
                "listening to ARP requests and mDNS advertisements) to "
                "observe networks attached to rack controllers. Active "
                "subnet mapping will also be available to be enabled on the "
                "configured subnets."
            )
        }
    },
    'active_discovery_interval': {
        'default': int(timedelta(hours=3).total_seconds()),
        'form': make_active_discovery_interval_field,
        'form_kwargs': {
            'label': (
                "Active subnet mapping interval"),
            'required': False,
            'help_text': (
                "When enabled, each rack will scan subnets enabled for active "
                "mapping. This helps ensure discovery information is accurate "
                "and complete."
            )
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
                "Storage layout that is applied to a node when it is "
                "commissioned."
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
            'label': "Erase nodes' disks prior to releasing",
            'help_text': (
                "Forces users to always erase disks when releasing.")
        }
    },
    'disk_erase_with_secure_erase': {
        'default': True,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': "Use secure erase by default when erasing disks",
            'help_text': (
                "Will only be used on devices that support secure erase.  "
                "Other devices will fall back to full wipe or quick erase "
                "depending on the selected options.")
        }
    },
    'disk_erase_with_quick_erase': {
        'default': False,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': "Use quick erase by default when erasing disks.",
            'help_text': (
                "This is not a secure erase; it wipes only the beginning and "
                "end of each disk.")
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
                "provides more detail in the installation logs")
        }
    },
    'enable_analytics': {
        'default': True,
        'form': forms.BooleanField,
        'form_kwargs': {
            'required': False,
            'label': (
                "Enable Google Analytics in MAAS UI to shape improvements "
                "in user experience")
        }
    },
    'completed_intro': {
        'default': True,
        'form': forms.BooleanField,
        'form_kwargs': {
            'label': "Marks if the initial intro has been completed",
            'required': False
        }
    },
    'max_node_commissioning_results': {
        'default': 10,
        'form': forms.IntegerField,
        'form_kwargs': {
            'required': False,
            'label': (
                "The maximum number of commissioning results runs which are "
                "stored"),
            'min_value': 1,
        },
    },
    'max_node_testing_results': {
        'default': 10,
        'form': forms.IntegerField,
        'form_kwargs': {
            'required': False,
            'label': (
                "The maximum number of testing results runs which are "
                "stored"),
            'min_value': 1,
        },
    },
    'max_node_installation_results': {
        'default': 3,
        'form': forms.IntegerField,
        'form_kwargs': {
            'required': False,
            'label': (
                "The maximum number of installation result runs which are "
                "stored"),
            'min_value': 1,
        },
    },
    'subnet_ip_exhaustion_threshold_count': {
        'default': 16,
        'form': forms.IntegerField,
        'form_kwargs': {
            'required': False,
            'label': (
                "If the number of free IP addresses on a subnet becomes less "
                "than or equal to this threshold, an IP exhaustion warning "
                "will appear for that subnet"),
            'min_value': 1,
        },
    },
}


CONFIG_ITEMS_KEYS = frozenset(CONFIG_ITEMS)


INVALID_SETTING_MSG_TEMPLATE = (
    "%s is not a valid config setting (valid settings are: " +
    "%s)." % ', '.join(CONFIG_ITEMS))


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
    for config_name, config_details in sorted(CONFIG_ITEMS.items()):
        form_details = config_details['form_kwargs']
        doc.append(":" + config_name + ": " + form_details['label'] + ". ")
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
    return re.sub('\ +$', '', full_text, flags=re.MULTILINE)
