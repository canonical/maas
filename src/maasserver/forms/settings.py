# Copyright 2013-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items definition and utilities."""

__all__ = [
    "CONFIG_ITEMS",
    "CONFIG_ITEMS_KEYS",
    "get_config_field",
    "get_config_form",
    "validate_config_name",
]

from datetime import timedelta
import re
from socket import gethostname

from django import forms
from django.core.exceptions import ValidationError

from maasserver.bootresources import IMPORT_RESOURCES_SERVICE_PERIOD
from maasserver.enum import INTERFACE_LINK_TYPE_CHOICES
from maasserver.fields import (
    HostListFormField,
    IPListFormField,
    SubnetListFormField,
    SystemdIntervalField,
)
from maasserver.models import BootResource
from maasserver.models.config import (
    ACTIVE_DISCOVERY_INTERVAL_CHOICES,
    Config,
    DEFAULT_OS,
    DNSSEC_VALIDATION_CHOICES,
    NETWORK_DISCOVERY_CHOICES,
)
from maasserver.models.domain import validate_internal_domain_name
from maasserver.storage_layouts import STORAGE_LAYOUT_CHOICES
from maasserver.utils.forms import compose_invalid_choice_text
from maasserver.utils.osystems import (
    list_all_usable_osystems,
    list_commissioning_choices,
    list_hwe_kernel_choices,
    list_osystem_choices,
    release_a_newer_than_b,
)
from provisioningserver.drivers.power.ipmi import (
    IPMI_CIPHER_SUITE_ID_CHOICES,
    IPMI_PRIVILEGE_LEVEL_CHOICES,
    IPMI_WORKAROUND_FLAG_CHOICES,
)
from provisioningserver.utils.text import normalise_whitespace
from provisioningserver.utils.url import splithost

INVALID_URL_MESSAGE = "Enter a valid url (e.g. http://host.example.com)."


def validate_missing_boot_images(value):
    """Raise `ValidationError` when the value is equal to '---'. This is
    used when no boot images exist on all clusters, so the config value cannot
    be changed."""
    if value == "---":
        raise ValidationError(
            "Unable to determine supported operating systems, "
            "due to missing boot images."
        )


def make_default_osystem_field(*args, **kwargs):
    """Build and return the default_osystem field."""
    usable_oses = list_all_usable_osystems()
    os_choices = list_osystem_choices(usable_oses, include_default=False)
    if len(os_choices) == 0:
        os_choices = [("---", "--- No Usable Operating System ---")]
    field = forms.ChoiceField(
        initial=Config.objects.get_config("default_osystem"),
        choices=os_choices,
        validators=[validate_missing_boot_images],
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "osystem", os_choices
            )
        },
        **kwargs,
    )
    return field


def validate_port(value, allow_ports=None):
    """Raise `ValidationError` when the value is set to a port number. that is
    either reserved for known services, or for MAAS services to ensure this
    doesn't break MAAS or other applications."""
    if allow_ports and value in allow_ports:
        # Value is in the allowed ports override.
        return
    msg = "Unable to change port number"
    if value > 65535 or value <= 0:
        raise ValidationError(
            "%s. Port number is not between 0 - 65535." % msg
        )
    if value >= 0 and value <= 1023:
        raise ValidationError(
            "%s. Port number is reserved for system services." % msg
        )
    # 5240 -> reserved for region HTTP.
    # 5241 - 4247 -> reserved for other MAAS services.
    # 5248 -> reserved for rack HTTP.
    # 5250+ -> reserved for region workers (RPC).
    if value >= 5240 and value <= 5270:
        raise ValidationError(
            "%s. Port number is reserved for MAAS services." % msg
        )


def validate_syslog_port(value):
    """A `validate_port` that allows the internal syslog port."""
    return validate_port(value, allow_ports=[5247])


def get_default_usable_osystem(default_osystem):
    """Return the osystem from the clusters that matches the default_osystem."""
    usable_oses = list_all_usable_osystems()
    for usable_os in usable_oses.values():
        if usable_os.name == default_osystem:
            return usable_os
    return None


def list_choices_for_releases(releases):
    """List all the release choices."""
    return [(release.name, release.title) for release in releases]


def make_maas_proxy_port_field(*args, **kwargs):
    """Build and return the maas_proxy_port field."""
    return forms.IntegerField(validators=[validate_port], **kwargs)


def make_maas_syslog_port_field(*args, **kwargs):
    """Build and return the maas_syslog_port field."""
    return forms.IntegerField(validators=[validate_syslog_port], **kwargs)


def make_default_distro_series_field(*args, **kwargs):
    """Build and return the default_distro_series field."""
    default_osystem = Config.objects.get_config("default_osystem")
    default_usable_os = get_default_usable_osystem(default_osystem)
    release_choices = [("---", "--- No Usable Release ---")]
    if default_usable_os is not None:
        releases = default_usable_os.releases.values()
        valid_release_choices = list_choices_for_releases(releases)
        if len(valid_release_choices) > 0:
            release_choices = valid_release_choices
    field = forms.ChoiceField(
        initial=Config.objects.get_config("default_distro_series"),
        choices=release_choices,
        validators=[validate_missing_boot_images],
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "release", release_choices
            )
        },
        **kwargs,
    )
    return field


def make_default_min_hwe_kernel_field(*args, **kwargs):
    """Build and return the default_min_hwe_kernel field."""
    kernel_choices = [("", "--- No minimum kernel ---")]
    # Global choices are limited to the commissioning release as min_hwe_kernel
    # is used during commissioning.
    commissioning_series = Config.objects.get_config(
        "commissioning_distro_series"
    )
    if commissioning_series:
        commissioning_os_release = "ubuntu/" + commissioning_series
        kernel_choices += list_hwe_kernel_choices(
            [
                kernel
                for kernel in BootResource.objects.get_kernels(
                    commissioning_os_release
                )
                if release_a_newer_than_b(kernel, commissioning_series)
            ]
        )
    field = forms.ChoiceField(
        initial=Config.objects.get_config("default_min_hwe_kernel"),
        choices=kernel_choices,
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "default_min_hwe_kernel", kernel_choices
            )
        },
        **kwargs,
    )
    return field


def make_commissioning_distro_series_field(*args, **kwargs):
    """Build and return the commissioning_distro_series field."""
    usable_oses = list_all_usable_osystems()
    commissioning_choices = list_commissioning_choices(usable_oses)
    if len(commissioning_choices) == 0:
        commissioning_choices = [("---", "--- No Usable Release ---")]
    field = forms.ChoiceField(
        initial=Config.objects.get_config("commissioning_distro_series"),
        choices=commissioning_choices,
        validators=[validate_missing_boot_images],
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "commissioning_distro_series", commissioning_choices
            )
        },
        **kwargs,
    )
    return field


def make_dnssec_validation_field(*args, **kwargs):
    """Build and return the dnssec_validation field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS["dnssec_validation"]["default"],
        choices=DNSSEC_VALIDATION_CHOICES,
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "dnssec_validation", DNSSEC_VALIDATION_CHOICES
            )
        },
        **kwargs,
    )
    return field


def make_network_discovery_field(*args, **kwargs):
    """Build and return the network_discovery field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS["network_discovery"]["default"],
        choices=NETWORK_DISCOVERY_CHOICES,
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "network_discovery", NETWORK_DISCOVERY_CHOICES
            )
        },
        **kwargs,
    )
    return field


def make_active_discovery_interval_field(*args, **kwargs):
    """Build and return the network_discovery field."""
    field = forms.ChoiceField(
        initial=CONFIG_ITEMS["active_discovery_interval"]["default"],
        choices=ACTIVE_DISCOVERY_INTERVAL_CHOICES,
        error_messages={
            "invalid_choice": compose_invalid_choice_text(
                "active_discovery_interval", ACTIVE_DISCOVERY_INTERVAL_CHOICES
            )
        },
        **kwargs,
    )
    return field


def make_maas_internal_domain_field(*args, **kwargs):
    """Build and return the maas_internal_domain field."""
    return forms.CharField(
        validators=[validate_internal_domain_name], **kwargs
    )


class RemoteSyslogField(forms.CharField):
    """
    A `CharField` that formats the input into the expected value for syslog.
    """

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return None
        host, port = splithost(value)
        if not port:
            port = 514
        return "%s:%d" % (host, port)


CONFIG_ITEMS = {
    "maas_name": {
        "default": gethostname(),
        "form": forms.CharField,
        "form_kwargs": {"label": "MAAS name"},
    },
    "theme": {
        "default": "",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "MAAS theme",
            "required": False,
        },
    },
    "kernel_opts": {
        "default": None,
        "form": forms.CharField,
        "form_kwargs": {
            "label": "Boot parameters to pass to the kernel by default",
            "required": False,
        },
    },
    "enable_http_proxy": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Enable the use of an APT or YUM and HTTP/HTTPS proxy",
            "required": False,
            "help_text": (
                "Provision nodes to use the built-in HTTP proxy (or "
                "user specified proxy) for APT or YUM. MAAS also uses the "
                "proxy for downloading boot images."
            ),
        },
    },
    "maas_proxy_port": {
        "default": 8000,
        "form": make_maas_proxy_port_field,
        "form_kwargs": {
            "label": "Port to bind the MAAS built-in proxy (default: 8000)",
            "required": False,
            "help_text": (
                "Defines the port used to bind the built-in proxy. The "
                "default port is 8000."
            ),
        },
    },
    "use_peer_proxy": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Use the built-in proxy with an external proxy as a peer",
            "required": False,
            "help_text": (
                "If enable_http_proxy is set, the built-in proxy will be "
                "configured to use http_proxy as a peer proxy. The deployed "
                "machines will be configured to use the built-in proxy."
            ),
        },
    },
    "prefer_v4_proxy": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Sets IPv4 DNS resolution before IPv6",
            "required": False,
            "help_text": (
                "If prefer_v4_proxy is set, the proxy will be set to prefer "
                "IPv4 DNS resolution before it attempts to perform IPv6 DNS "
                "resolution."
            ),
        },
    },
    "http_proxy": {
        "default": None,
        "form": forms.URLField,
        "form_kwargs": {
            "label": "Proxy for APT or YUM and HTTP/HTTPS",
            "required": False,
            "help_text": (
                "This will be passed onto provisioned nodes to use as a "
                "proxy for APT or YUM traffic. MAAS also uses the proxy for "
                "downloading boot images. If no URL is provided, the built-in "
                "MAAS proxy will be used."
            ),
        },
    },
    "default_dns_ttl": {
        "default": 30,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": "Default Time-To-Live for the DNS",
            "required": False,
            "help_text": (
                "If no TTL value is specified at a more specific point "
                "this is how long DNS responses are valid, in seconds."
            ),
        },
    },
    "upstream_dns": {
        "default": None,
        "form": IPListFormField,
        "form_kwargs": {
            "label": (
                "Upstream DNS used to resolve domains not managed by this "
                "MAAS (space-separated IP addresses)"
            ),
            "required": False,
            "help_text": (
                "Only used when MAAS is running its own DNS server. This "
                "value is used as the value of 'forwarders' in the DNS "
                "server config."
            ),
        },
    },
    "dnssec_validation": {
        "default": "auto",
        "form": make_dnssec_validation_field,
        "form_kwargs": {
            "label": "Enable DNSSEC validation of upstream zones",
            "required": False,
            "help_text": (
                "Only used when MAAS is running its own DNS server. This "
                "value is used as the value of 'dnssec_validation' in the DNS "
                "server config."
            ),
        },
    },
    "maas_internal_domain": {
        "default": "_maas_internal",
        "form": make_maas_internal_domain_field,
        "form_kwargs": {
            "label": (
                "Domain name used by MAAS for internal mapping of MAAS "
                "provided services."
            ),
            "required": False,
            "help_text": (
                "This domain should not collide with an upstream domain "
                "provided by the set upstream DNS."
            ),
        },
    },
    "dns_trusted_acl": {
        "default": None,
        "form": SubnetListFormField,
        "form_kwargs": {
            "label": (
                "List of external networks (not previously known), that will "
                "be allowed to use MAAS for DNS resolution."
            ),
            "required": False,
            "help_text": (
                "MAAS keeps a list of networks that are allowed to use MAAS "
                "for DNS resolution. This option allows to add extra "
                "networks (not previously known) to the trusted ACL where "
                "this list of networks is kept. It also supports specifying "
                "IPs or ACL names."
            ),
        },
    },
    "ntp_servers": {
        "default": None,
        "form": HostListFormField,
        "form_kwargs": {
            "label": "Addresses of NTP servers",
            "required": False,
            "help_text": normalise_whitespace(
                """\
                NTP servers, specified as IP addresses or hostnames delimited
                by commas and/or spaces, to be used as time references for
                MAAS itself, the machines MAAS deploys, and devices that make
                use of MAAS's DHCP services.
            """
            ),
        },
    },
    "ntp_external_only": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Use external NTP servers only",
            "required": False,
            "help_text": normalise_whitespace(
                """\
                Configure all region controller hosts, rack controller hosts,
                and subsequently deployed machines to refer directly to the
                configured external NTP servers. Otherwise only region
                controller hosts will be configured to use those external NTP
                servers, rack contoller hosts will in turn refer to the
                regions' NTP servers, and deployed machines will refer to the
                racks' NTP servers.
            """
            ),
        },
    },
    "remote_syslog": {
        "default": None,
        "form": RemoteSyslogField,
        "form_kwargs": {
            "label": "Remote syslog server to forward machine logs",
            "required": False,
            "help_text": normalise_whitespace(
                """\
                A remote syslog server that MAAS will set on enlisting,
                commissioning, testing, and deploying machines to send all
                log messages. Clearing this value will restore the default
                behaviour of forwarding syslog to MAAS.
            """
            ),
        },
    },
    "maas_syslog_port": {
        "default": 5247,
        "form": make_maas_syslog_port_field,
        "form_kwargs": {
            "label": "Port to bind the MAAS built-in syslog (default: 5247)",
            "required": False,
            "help_text": (
                "Defines the port used to bind the built-in syslog. The "
                "default port is 5247."
            ),
        },
    },
    "network_discovery": {
        "default": "enabled",
        "form": make_network_discovery_field,
        "form_kwargs": {
            "label": "",
            "required": False,
            "help_text": (
                "When enabled, MAAS will use passive techniques (such as "
                "listening to ARP requests and mDNS advertisements) to "
                "observe networks attached to rack controllers. Active "
                "subnet mapping will also be available to be enabled on the "
                "configured subnets."
            ),
        },
    },
    "active_discovery_interval": {
        "default": int(timedelta(hours=3).total_seconds()),
        "form": make_active_discovery_interval_field,
        "form_kwargs": {
            "label": "Active subnet mapping interval",
            "required": False,
            "help_text": (
                "When enabled, each rack will scan subnets enabled for active "
                "mapping. This helps ensure discovery information is accurate "
                "and complete."
            ),
        },
    },
    "default_boot_interface_link_type": {
        "default": "auto",
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": "Default boot interface IP Mode",
            "choices": INTERFACE_LINK_TYPE_CHOICES,
            "help_text": (
                "IP Mode that is applied to the boot interface on a node when "
                "it is commissioned."
            ),
        },
    },
    "default_osystem": {
        "form": make_default_osystem_field,
        "form_kwargs": {
            "label": "Default operating system used for deployment",
            "required": False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        },
    },
    "default_distro_series": {
        "form": make_default_distro_series_field,
        "form_kwargs": {
            "label": "Default OS release used for deployment",
            "required": False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        },
    },
    "default_min_hwe_kernel": {
        "default": None,
        "form": make_default_min_hwe_kernel_field,
        "form_kwargs": {
            "label": "Default Minimum Kernel Version",
            "required": False,
            "help_text": (
                "The default minimum kernel version used on all new and"
                " commissioned nodes."
            ),
        },
    },
    "enable_kernel_crash_dump": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": "Enable the kernel crash dump feature in deployed machines.",
            "help_text": "Enable the collection of kernel crash dump when a machine is deployed.",
        },
    },
    "default_storage_layout": {
        "default": "lvm",
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": "Default storage layout",
            "choices": STORAGE_LAYOUT_CHOICES,
            "help_text": (
                "Storage layout that is applied to a node when it is "
                "commissioned."
            ),
        },
    },
    "commissioning_distro_series": {
        "default": DEFAULT_OS.get_default_commissioning_release(),
        "form": make_commissioning_distro_series_field,
        "form_kwargs": {
            "label": "Default Ubuntu release used for commissioning",
            "required": False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        },
    },
    "enable_third_party_drivers": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Enable the installation of proprietary drivers (i.e. HPVSA)"
            ),
        },
    },
    "windows_kms_host": {
        "default": None,
        "form": forms.CharField,
        "form_kwargs": {
            "required": False,
            "label": "Windows KMS activation host",
            "help_text": (
                "FQDN or IP address of the host that provides the KMS Windows "
                "activation service. (Only needed for Windows deployments "
                "using KMS activation.)"
            ),
        },
    },
    "enable_disk_erasing_on_release": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": "Erase nodes' disks prior to releasing",
            "help_text": "Forces users to always erase disks when releasing.",
        },
    },
    "disk_erase_with_secure_erase": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": "Use secure erase by default when erasing disks",
            "help_text": (
                "Will only be used on devices that support secure erase.  "
                "Other devices will fall back to full wipe or quick erase "
                "depending on the selected options."
            ),
        },
    },
    "disk_erase_with_quick_erase": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": "Use quick erase by default when erasing disks.",
            "help_text": (
                "This is not a secure erase; it wipes only the beginning and "
                "end of each disk."
            ),
        },
    },
    "boot_images_auto_import": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Automatically import/refresh the boot images "
                "every %d minutes"
                % (IMPORT_RESOURCES_SERVICE_PERIOD.total_seconds() / 60.0)
            ),
        },
    },
    "boot_images_no_proxy": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Set no_proxy with the image repository address when MAAS "
                "is behind (or set with) a proxy."
            ),
            "help_text": (
                "By default, when MAAS is behind (and set with) a proxy, it "
                "is used to download images from the image repository. In "
                "some situations (e.g. when using a local image repository) "
                "it doesn't make sense for MAAS to use the proxy to download "
                "images because it can access them directly. Setting this "
                "option allows MAAS to access the (local) image repository "
                "directly by setting the no_proxy variable for the MAAS env "
                "with the address of the image repository."
            ),
        },
    },
    "curtin_verbose": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Run the fast-path installer with higher verbosity. This "
                "provides more detail in the installation logs"
            ),
        },
    },
    "force_v1_network_yaml": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Always use the legacy v1 YAML (rather than Netplan format, "
                "also known as v2 YAML) when composing the network "
                "configuration for a machine."
            ),
        },
    },
    "enable_analytics": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Enable Google Analytics in MAAS UI to shape improvements "
                "in user experience"
            ),
        },
    },
    "completed_intro": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Marks if the initial intro has been completed",
            "required": False,
        },
    },
    "max_node_commissioning_results": {
        "default": 10,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": (
                "The maximum number of commissioning results runs which are "
                "stored"
            ),
            "min_value": 1,
        },
    },
    "max_node_testing_results": {
        "default": 10,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": (
                "The maximum number of testing results runs which are "
                "stored"
            ),
            "min_value": 1,
        },
    },
    "max_node_installation_results": {
        "default": 3,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": (
                "The maximum number of installation result runs which are "
                "stored"
            ),
            "min_value": 1,
        },
    },
    "max_node_release_results": {
        "default": 3,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": "The maximum number of release result runs which are stored",
            "min_value": 1,
        },
    },
    "subnet_ip_exhaustion_threshold_count": {
        "default": 16,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": (
                "If the number of free IP addresses on a subnet becomes less "
                "than or equal to this threshold, an IP exhaustion warning "
                "will appear for that subnet"
            ),
            "min_value": 1,
        },
    },
    "release_notifications": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Enable or disable notifications for new MAAS releases."
            ),
        },
    },
    "use_rack_proxy": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": (
                "Use DNS and HTTP metadata proxy on the rack controllers "
                "when a machine is booted."
            ),
            "required": False,
            "help_text": (
                "All DNS and HTTP metadata traffic will flow through the "
                "rack controller that a machine is booting from. This "
                "isolated region controllers from machines."
            ),
        },
    },
    "node_timeout": {
        "default": 30,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": (
                "Time, in minutes, until the node times out during "
                "commissioning, testing, deploying, or entering rescue mode."
            ),
            "help_text": (
                "Commissioning, testing, deploying, and entering rescue mode "
                "all set a timeout when beginning. If MAAS does not hear from "
                "the node within the specified number of minutes the node is "
                "powered off and set into a failed status."
            ),
            "min_value": 1,
        },
    },
    "prometheus_enabled": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Enable Prometheus exporter",
            "required": False,
            "help_text": (
                "Whether to enable Prometheus exporter functions, including "
                "Cluster metrics endpoint and Push gateway (if configured)."
            ),
        },
    },
    "prometheus_push_gateway": {
        "default": None,
        "form": forms.CharField,
        "form_kwargs": {
            "label": "Address or hostname of the Prometheus push gateway.",
            "required": False,
            "help_text": (
                "Defines the address or hostname of the Prometheus push "
                "gateway where MAAS will send data to."
            ),
        },
    },
    "prometheus_push_interval": {
        "default": 60,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": (
                "Interval of how often to send data to Prometheus "
                "(default: to 60 minutes)."
            ),
            "required": False,
            "help_text": (
                "The internal of how often MAAS will send stats to Prometheus "
                "in minutes."
            ),
        },
    },
    "promtail_enabled": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Enable streaming logs to Promtail.",
            "required": False,
            "help_text": ("Whether to stream logs to Promtail"),
        },
    },
    "promtail_port": {
        "default": 5238,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": "TCP port of the Promtail Push API.",
            "required": False,
            "help_text": (
                "Defines the TCP port of the Promtail push "
                "API where MAAS will stream logs to."
            ),
        },
    },
    "enlist_commissioning": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Whether to run commissioning during enlistment.",
            "required": False,
            "help_text": (
                "Enables running all built-in commissioning scripts during "
                "enlistment."
            ),
        },
    },
    "maas_auto_ipmi_user": {
        "default": "maas",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "MAAS IPMI user.",
            "required": False,
            "max_length": 20,
            "help_text": (
                "The name of the IPMI user that MAAS automatically creates "
                "during enlistment/commissioning."
            ),
        },
    },
    "maas_auto_ipmi_user_privilege_level": {
        "default": "ADMIN",
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": "MAAS IPMI privilege level",
            "required": False,
            "choices": IPMI_PRIVILEGE_LEVEL_CHOICES,
            "error_messages": {
                "invalid_choice": "Valid choices are ADMIN, OPERATOR, or USER",
            },
            "help_text": (
                "The default IPMI privilege level to use when creating the "
                "MAAS user and talking IPMI BMCs"
            ),
        },
    },
    "maas_auto_ipmi_k_g_bmc_key": {
        "default": "",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "The IPMI K_g key to set during BMC configuration.",
            "required": False,
            "max_length": 20,
            "help_text": (
                "This IPMI K_g BMC key is used to encrypt all IPMI traffic to "
                "a BMC. Once set, all clients will REQUIRE this key upon being "
                "commissioned. Any current machines that were previously "
                "commissioned will not require this key until they are "
                "recommissioned."
            ),
        },
    },
    "maas_auto_ipmi_cipher_suite_id": {
        "default": "3",
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": "MAAS IPMI Default Cipher Suite ID",
            "required": False,
            "choices": IPMI_CIPHER_SUITE_ID_CHOICES,
            "error_messages": {
                "invalid_choice": "Valid choices are {}".format(
                    ",".join(
                        choice[0] for choice in IPMI_CIPHER_SUITE_ID_CHOICES
                    )
                ),
            },
            "help_text": (
                "The default IPMI cipher suite ID to use when connecting "
                "to the BMC via ipmitools"
            ),
        },
    },
    "maas_auto_ipmi_workaround_flags": {
        "default": ["opensesspriv"],
        "form": forms.MultipleChoiceField,
        "form_kwargs": {
            "label": "IPMI Workaround Flags",
            "required": False,
            "choices": IPMI_WORKAROUND_FLAG_CHOICES,
            "error_messages": {
                "invalid_choice": "Valid choices are {}".format(
                    ", ".join(
                        choice[0] for choice in IPMI_WORKAROUND_FLAG_CHOICES
                    )
                ),
            },
            "help_text": (
                "The default workaround flag (-W options) to use for "
                "ipmipower commands"
            ),
        },
    },
    "vcenter_server": {
        "default": "",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "VMware vCenter server FQDN or IP address",
            "required": False,
            "help_text": (
                "VMware vCenter server FQDN or IP address which is passed "
                "to a deployed VMware ESXi host."
            ),
        },
    },
    "vcenter_username": {
        "default": "",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "VMware vCenter username",
            "required": False,
            "help_text": (
                "VMware vCenter server username which is passed to a deployed "
                "VMware ESXi host."
            ),
        },
    },
    "vcenter_password": {
        "default": "",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "VMware vCenter password",
            "required": False,
            "help_text": (
                "VMware vCenter server password which is passed to a deployed "
                "VMware ESXi host."
            ),
        },
    },
    "vcenter_datacenter": {
        "default": "",
        "form": forms.CharField,
        "form_kwargs": {
            "label": "VMware vCenter datacenter",
            "required": False,
            "help_text": (
                "VMware vCenter datacenter which is passed to a deployed "
                "VMware ESXi host."
            ),
        },
    },
    "hardware_sync_interval": {
        "default": "15m",
        "form": SystemdIntervalField,
        "form_kwargs": {
            "label": "Hardware Sync Interval",
            "required": False,
            "help_text": (
                "The interval to send hardware info to MAAS from"
                "hardware sync enabled machines, in systemd time span syntax."
            ),
        },
    },
    "tls_cert_expiration_notification_enabled": {
        "default": False,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Notify when the certificate is due to expire",
            "required": False,
            "help_text": (
                "Enable/Disable notification about certificate expiration."
            ),
        },
    },
    "tls_cert_expiration_notification_interval": {
        "default": 30,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": "Certificate expiration reminder (days)",
            "required": False,
            "help_text": (
                "Configure notification when certificate is "
                "due to expire in (days)."
            ),
            "min_value": 1,
            "max_value": 90,
        },
    },
    "session_length": {
        "default": 1209600,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": "Session timeout (seconds)",
            "required": False,
            "help_text": (
                "Configure timeout of session (seconds). "
                "Minimum 10s, maximum 2 weeks (1209600s)."
            ),
            "min_value": 10,
            "max_value": 1209600,
        },
    },
    "auto_vlan_creation": {
        "default": True,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": "Automatically create VLANs and Fabrics for interfaces",
            "required": False,
            "help_text": (
                "Enables the creation of a default VLAN and Fabric for "
                "discovered network interfaces when MAAS cannot connect it "
                "to an existing one. When disabled, the interface is left "
                "disconnected in these cases."
            ),
        },
    },
}


CONFIG_ITEMS_KEYS = frozenset(CONFIG_ITEMS)


INVALID_SETTING_MSG_TEMPLATE = (
    "%s is not a valid config setting (valid settings are: "
    + "%s)." % ", ".join(CONFIG_ITEMS)
)


def validate_config_name(config_name):
    if config_name not in CONFIG_ITEMS_KEYS:
        raise forms.ValidationError(
            {config_name: [INVALID_SETTING_MSG_TEMPLATE % config_name]}
        )


def get_config_field(config_name, **kwargs):
    """Return a configuration field.

    :param config_name: Name of the configuration item.
    :type config_name: unicode
    :return: A configuration field
    :rtype: :class:`django.forms.Field`
    """
    validate_config_name(config_name)
    conf = CONFIG_ITEMS[config_name]
    kwargs.update(conf["form_kwargs"])
    return conf["form"](**kwargs)


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


def get_config_doc(config_items=None, indentation=0):
    """Return the documentation about the available configuration settings."""
    if config_items is None:
        config_items = CONFIG_ITEMS
    doc = ["Available configuration items:\n\n"]
    for config_name, config_details in sorted(config_items.items()):
        form_details = config_details["form_kwargs"]
        doc.append(":" + config_name + ": " + form_details["label"] + ". ")
        # Append help text if present.
        help_text = form_details.get("help_text")
        if help_text is not None:
            doc.append(help_text.strip())
        # Append list of possible choices if present.
        choices = form_details.get("choices")
        if choices is not None:
            choice_descr = ", ".join(
                f"'{value}' ({meaning})" for value, meaning in sorted(choices)
            )
            doc.append("Available choices are: %s." % choice_descr)
        doc.append("\n")
    full_text = (" " * indentation).join(doc)
    return re.sub(r"\ +$", "", full_text, flags=re.MULTILINE)
