# Copyright 2013-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items definition and utilities."""

__all__ = [
    "CONFIG_ITEMS",
    "CONFIG_ITEMS_KEYS",
    "get_config_field",
    "get_config_form",
    "validate_config_name",
]

import re

from django import forms
from django.core.exceptions import ValidationError

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
from maasservicelayer.models.configurations import (
    ActiveDiscoveryIntervalConfig,
    AutoVlanCreationConfig,
    BootImagesAutoImportConfig,
    BootImagesNoProxyConfig,
    CommissioningDistroSeriesConfig,
    CompletedIntroConfig,
    CurtinVerboseConfig,
    DEFAULT_OS,
    DefaultBootInterfaceLinkTypeConfig,
    DefaultDistroSeriesConfig,
    DefaultDnsTtlConfig,
    DefaultMinHweKernelConfig,
    DefaultOSystemConfig,
    DefaultStorageLayoutConfig,
    DiskEraseWithQuickEraseConfig,
    DiskEraseWithSecureEraseConfig,
    DNSSECValidationConfig,
    DNSTrustedAclConfig,
    EnableAnalyticsConfig,
    EnableDiskErasingOnReleaseConfig,
    EnableHttpProxyConfig,
    EnableKernelCrashDumpConfig,
    EnableThirdPartyDriversConfig,
    EnlistCommissioningConfig,
    ForceV1NetworkYamlConfig,
    HardwareSyncIntervalConfig,
    HttpProxyConfig,
    KernelOptsConfig,
    MAASAutoIPMICipherSuiteIDConfig,
    MAASAutoIPMIKGBmcKeyConfig,
    MAASAutoIPMIUserConfig,
    MAASAutoIPMIUserPrivilegeLevelConfig,
    MAASAutoIPMIWorkaroundFlagsConfig,
    MAASInternalDomainConfig,
    MAASNameConfig,
    MAASProxyPortConfig,
    MAASSyslogPortConfig,
    MaxNodeCommissioningResultsConfig,
    MaxNodeInstallationResultsConfig,
    MaxNodeReleaseResultsConfig,
    MaxNodeTestingResultsConfig,
    NetworkDiscoveryConfig,
    NodeTimeoutConfig,
    NTPExternalOnlyConfig,
    NTPServersConfig,
    PreferV4ProxyConfig,
    PrometheusEnabledConfig,
    PrometheusPushGatewayConfig,
    PrometheusPushIntervalConfig,
    PromtailEnabledConfig,
    PromtailPortConfig,
    ReleaseNotificationsConfig,
    RemoteSyslogConfig,
    SessionLengthConfig,
    SubnetIPExhaustionThresholdCountConfig,
    ThemeConfig,
    TlsCertExpirationNotificationEnabledConfig,
    TLSCertExpirationNotificationIntervalConfig,
    UpstreamDnsConfig,
    UsePeerProxyConfig,
    UseRackProxyConfig,
    VCenterDatacenterConfig,
    VCenterPasswordConfig,
    VCenterServerConfig,
    VCenterUsernameConfig,
    WindowsKmsHostConfig,
)
from provisioningserver.drivers.power.ipmi import (
    IPMI_CIPHER_SUITE_ID_CHOICES,
    IPMI_PRIVILEGE_LEVEL_CHOICES,
    IPMI_WORKAROUND_FLAG_CHOICES,
)

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


def validate_proxy_port(port: int):
    try:
        return MAASProxyPortConfig.validate_port(port)
    except ValueError as e:
        raise ValidationError(str(e)) from e


def make_maas_proxy_port_field(*args, **kwargs):
    """Build and return the maas_proxy_port field."""
    return forms.IntegerField(validators=[validate_proxy_port], **kwargs)


def validate_syslog_port(port: int):
    try:
        return MAASSyslogPortConfig.validate_port(port)
    except ValueError as e:
        raise ValidationError(str(e)) from e


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


def validate_ipmi_k_g(value):
    """
    Ensure that the provided IPMI k_g value is valid. This validator is used to
    test both for valid encoding (regular or hexadecimal) and to ensure input
    is 20 characters long (or 40 in hexadecimal plus '0x' prefix).
    """
    try:
        return MAASAutoIPMIKGBmcKeyConfig.validate_value(value)
    except ValueError as e:
        raise ValidationError(str(e)) from e


def make_ipmi_k_g_field(*args, **kwargs):
    field = forms.CharField(
        validators=[validate_ipmi_k_g],
        **kwargs,
    )
    return field


class RemoteSyslogField(forms.CharField):
    """
    A `CharField` that formats the input into the expected value for syslog.
    """

    def clean(self, value):
        value = super().clean(value)
        return RemoteSyslogConfig.validate_value(value)


CONFIG_ITEMS = {
    MAASNameConfig.name: {
        "default": MAASNameConfig.default,
        "form": forms.CharField,
        "form_kwargs": {"label": MAASNameConfig.description},
    },
    ThemeConfig.name: {
        "default": ThemeConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": ThemeConfig.description,
            "required": False,
        },
    },
    KernelOptsConfig.name: {
        "default": KernelOptsConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": KernelOptsConfig.description,
            "required": False,
        },
    },
    EnableHttpProxyConfig.name: {
        "default": EnableHttpProxyConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": EnableHttpProxyConfig.description,
            "required": False,
            "help_text": EnableHttpProxyConfig.help_text,
        },
    },
    MAASProxyPortConfig.name: {
        "default": MAASProxyPortConfig.default,
        "form": make_maas_proxy_port_field,
        "form_kwargs": {
            "label": MAASProxyPortConfig.description,
            "required": False,
            "help_text": MAASProxyPortConfig.help_text,
        },
    },
    UsePeerProxyConfig.name: {
        "default": UsePeerProxyConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": UsePeerProxyConfig.description,
            "required": False,
            "help_text": UsePeerProxyConfig.help_text,
        },
    },
    PreferV4ProxyConfig.name: {
        "default": PreferV4ProxyConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": PreferV4ProxyConfig.description,
            "required": False,
            "help_text": PreferV4ProxyConfig.help_text,
        },
    },
    HttpProxyConfig.name: {
        "default": HttpProxyConfig.default,
        "form": forms.URLField,
        "form_kwargs": {
            "label": HttpProxyConfig.description,
            "required": False,
            "help_text": HttpProxyConfig.help_text,
        },
    },
    DefaultDnsTtlConfig.name: {
        "default": DefaultDnsTtlConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": DefaultDnsTtlConfig.description,
            "required": False,
            "help_text": DefaultDnsTtlConfig.help_text,
        },
    },
    UpstreamDnsConfig.name: {
        "default": UpstreamDnsConfig.default,
        "form": IPListFormField,
        "form_kwargs": {
            "label": UpstreamDnsConfig.description,
            "required": False,
            "help_text": UpstreamDnsConfig.help_text,
        },
    },
    DNSSECValidationConfig.name: {
        "default": DNSSECValidationConfig.default,
        "form": make_dnssec_validation_field,
        "form_kwargs": {
            "label": DNSSECValidationConfig.description,
            "required": False,
            "help_text": DNSSECValidationConfig.help_text,
        },
    },
    MAASInternalDomainConfig.name: {
        "default": MAASInternalDomainConfig.default,
        "form": make_maas_internal_domain_field,
        "form_kwargs": {
            "label": MAASInternalDomainConfig.description,
            "required": False,
            "help_text": MAASInternalDomainConfig.help_text,
        },
    },
    DNSTrustedAclConfig.name: {
        "default": DNSTrustedAclConfig.default,
        "form": SubnetListFormField,
        "form_kwargs": {
            "label": DNSTrustedAclConfig.description,
            "required": False,
            "help_text": DNSTrustedAclConfig.help_text,
        },
    },
    NTPServersConfig.name: {
        "default": NTPServersConfig.default,
        "form": HostListFormField,
        "form_kwargs": {
            "label": NTPServersConfig.description,
            "required": False,
            "help_text": NTPServersConfig.help_text,
        },
    },
    NTPExternalOnlyConfig.name: {
        "default": NTPExternalOnlyConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": NTPExternalOnlyConfig.description,
            "required": False,
            "help_text": NTPExternalOnlyConfig.help_text,
        },
    },
    RemoteSyslogConfig.name: {
        "default": RemoteSyslogConfig.default,
        "form": RemoteSyslogField,
        "form_kwargs": {
            "label": RemoteSyslogConfig.description,
            "required": False,
            "help_text": RemoteSyslogConfig.help_text,
        },
    },
    MAASSyslogPortConfig.name: {
        "default": MAASSyslogPortConfig.default,
        "form": make_maas_syslog_port_field,
        "form_kwargs": {
            "label": MAASSyslogPortConfig.description,
            "required": False,
            "help_text": MAASSyslogPortConfig.help_text,
        },
    },
    NetworkDiscoveryConfig.name: {
        "default": NetworkDiscoveryConfig.default,
        "form": make_network_discovery_field,
        "form_kwargs": {
            "label": NetworkDiscoveryConfig.description,
            "required": False,
            "help_text": NetworkDiscoveryConfig.help_text,
        },
    },
    ActiveDiscoveryIntervalConfig.name: {
        "default": ActiveDiscoveryIntervalConfig.default,
        "form": make_active_discovery_interval_field,
        "form_kwargs": {
            "label": ActiveDiscoveryIntervalConfig.description,
            "required": False,
            "help_text": ActiveDiscoveryIntervalConfig.help_text,
        },
    },
    DefaultBootInterfaceLinkTypeConfig.name: {
        "default": DefaultBootInterfaceLinkTypeConfig.default,
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": DefaultBootInterfaceLinkTypeConfig.description,
            "choices": INTERFACE_LINK_TYPE_CHOICES,
            "help_text": DefaultBootInterfaceLinkTypeConfig.help_text,
        },
    },
    DefaultOSystemConfig.name: {
        "form": make_default_osystem_field,
        "form_kwargs": {
            "label": DefaultOSystemConfig.description,
            "required": False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        },
    },
    DefaultDistroSeriesConfig.name: {
        "form": make_default_distro_series_field,
        "form_kwargs": {
            "label": DefaultDistroSeriesConfig.description,
            "required": False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        },
    },
    DefaultMinHweKernelConfig.name: {
        "default": DefaultMinHweKernelConfig.default,
        "form": make_default_min_hwe_kernel_field,
        "form_kwargs": {
            "label": DefaultMinHweKernelConfig.description,
            "required": False,
            "help_text": DefaultMinHweKernelConfig.help_text,
        },
    },
    EnableKernelCrashDumpConfig.name: {
        "default": EnableKernelCrashDumpConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": EnableKernelCrashDumpConfig.description,
            "help_text": EnableKernelCrashDumpConfig.help_text,
        },
    },
    DefaultStorageLayoutConfig.name: {
        "default": DefaultStorageLayoutConfig.default,
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": DefaultStorageLayoutConfig.description,
            "choices": STORAGE_LAYOUT_CHOICES,
            "help_text": DefaultStorageLayoutConfig.help_text,
        },
    },
    CommissioningDistroSeriesConfig.name: {
        "default": DEFAULT_OS.get_default_commissioning_release(),
        "form": make_commissioning_distro_series_field,
        "form_kwargs": {
            "label": CommissioningDistroSeriesConfig.description,
            "required": False,
            # This field's `choices` and `error_messages` are populated
            # at run-time to avoid a race condition.
        },
    },
    EnableThirdPartyDriversConfig.name: {
        "default": EnableThirdPartyDriversConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": EnableThirdPartyDriversConfig.description,
        },
    },
    WindowsKmsHostConfig.name: {
        "default": WindowsKmsHostConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "required": False,
            "label": WindowsKmsHostConfig.description,
            "help_text": WindowsKmsHostConfig.help_text,
        },
    },
    EnableDiskErasingOnReleaseConfig.name: {
        "default": EnableDiskErasingOnReleaseConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": EnableDiskErasingOnReleaseConfig.description,
            "help_text": EnableDiskErasingOnReleaseConfig.help_text,
        },
    },
    DiskEraseWithSecureEraseConfig.name: {
        "default": DiskEraseWithSecureEraseConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": DiskEraseWithSecureEraseConfig.description,
            "help_text": DiskEraseWithSecureEraseConfig.help_text,
        },
    },
    DiskEraseWithQuickEraseConfig.name: {
        "default": DiskEraseWithQuickEraseConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": DiskEraseWithQuickEraseConfig.description,
            "help_text": DiskEraseWithQuickEraseConfig.help_text,
        },
    },
    BootImagesAutoImportConfig.name: {
        "default": BootImagesAutoImportConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": BootImagesAutoImportConfig.description,
        },
    },
    BootImagesNoProxyConfig.name: {
        "default": BootImagesNoProxyConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": BootImagesNoProxyConfig.description,
            "help_text": BootImagesNoProxyConfig.help_text,
        },
    },
    CurtinVerboseConfig.name: {
        "default": CurtinVerboseConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": CurtinVerboseConfig.description,
        },
    },
    ForceV1NetworkYamlConfig.name: {
        "default": ForceV1NetworkYamlConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": ForceV1NetworkYamlConfig.description,
        },
    },
    EnableAnalyticsConfig.name: {
        "default": EnableAnalyticsConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": EnableAnalyticsConfig.description,
        },
    },
    CompletedIntroConfig.name: {
        "default": CompletedIntroConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": CompletedIntroConfig.description,
            "required": False,
        },
    },
    MaxNodeCommissioningResultsConfig.name: {
        "default": MaxNodeCommissioningResultsConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": MaxNodeCommissioningResultsConfig.description,
            "min_value": 1,
        },
    },
    MaxNodeTestingResultsConfig.name: {
        "default": MaxNodeTestingResultsConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": MaxNodeTestingResultsConfig.description,
            "min_value": 1,
        },
    },
    MaxNodeInstallationResultsConfig.name: {
        "default": MaxNodeInstallationResultsConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": MaxNodeInstallationResultsConfig.description,
            "min_value": 1,
        },
    },
    MaxNodeReleaseResultsConfig.name: {
        "default": MaxNodeReleaseResultsConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": MaxNodeReleaseResultsConfig.description,
            "min_value": 1,
        },
    },
    SubnetIPExhaustionThresholdCountConfig.name: {
        "default": SubnetIPExhaustionThresholdCountConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": SubnetIPExhaustionThresholdCountConfig.description,
            "min_value": 1,
        },
    },
    ReleaseNotificationsConfig.name: {
        "default": ReleaseNotificationsConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "required": False,
            "label": ReleaseNotificationsConfig.description,
        },
    },
    UseRackProxyConfig.name: {
        "default": UseRackProxyConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": UseRackProxyConfig.description,
            "required": False,
            "help_text": UseRackProxyConfig.help_text,
        },
    },
    NodeTimeoutConfig.name: {
        "default": NodeTimeoutConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "required": False,
            "label": NodeTimeoutConfig.description,
            "help_text": NodeTimeoutConfig.help_text,
            "min_value": 1,
        },
    },
    PrometheusEnabledConfig.name: {
        "default": PrometheusEnabledConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": PrometheusEnabledConfig.description,
            "required": False,
            "help_text": PrometheusEnabledConfig.help_text,
        },
    },
    PrometheusPushGatewayConfig.name: {
        "default": PrometheusPushGatewayConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": PrometheusPushGatewayConfig.description,
            "required": False,
            "help_text": PrometheusPushGatewayConfig.help_text,
        },
    },
    PrometheusPushIntervalConfig.name: {
        "default": PrometheusPushIntervalConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": PrometheusPushIntervalConfig.description,
            "required": False,
            "help_text": PrometheusPushIntervalConfig.help_text,
        },
    },
    PromtailEnabledConfig.name: {
        "default": PromtailEnabledConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": PromtailEnabledConfig.description,
            "required": False,
            "help_text": PromtailEnabledConfig.help_text,
        },
    },
    PromtailPortConfig.name: {
        "default": PromtailPortConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": PromtailPortConfig.description,
            "required": False,
            "help_text": PromtailPortConfig.help_text,
        },
    },
    EnlistCommissioningConfig.name: {
        "default": EnlistCommissioningConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": EnlistCommissioningConfig.description,
            "required": False,
            "help_text": EnlistCommissioningConfig.help_text,
        },
    },
    MAASAutoIPMIUserConfig.name: {
        "default": MAASAutoIPMIUserConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": MAASAutoIPMIUserConfig.description,
            "required": False,
            "max_length": 20,
            "help_text": MAASAutoIPMIUserConfig.help_text,
        },
    },
    MAASAutoIPMIUserPrivilegeLevelConfig.name: {
        "default": MAASAutoIPMIUserPrivilegeLevelConfig.default,
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": MAASAutoIPMIUserPrivilegeLevelConfig.description,
            "required": False,
            "choices": IPMI_PRIVILEGE_LEVEL_CHOICES,
            "error_messages": {
                "invalid_choice": "Valid choices are ADMIN, OPERATOR, or USER",
            },
            "help_text": MAASAutoIPMIUserPrivilegeLevelConfig.help_text,
        },
    },
    MAASAutoIPMIKGBmcKeyConfig.name: {
        "default": MAASAutoIPMIKGBmcKeyConfig.default,
        "form": make_ipmi_k_g_field,
        "form_kwargs": {
            "label": MAASAutoIPMIKGBmcKeyConfig.description,
            "required": False,
            "help_text": MAASAutoIPMIKGBmcKeyConfig.help_text,
        },
    },
    MAASAutoIPMICipherSuiteIDConfig.name: {
        "default": MAASAutoIPMICipherSuiteIDConfig.default,
        "form": forms.ChoiceField,
        "form_kwargs": {
            "label": MAASAutoIPMICipherSuiteIDConfig.description,
            "required": False,
            "choices": IPMI_CIPHER_SUITE_ID_CHOICES,
            "error_messages": {
                "invalid_choice": "Valid choices are {}".format(
                    ",".join(
                        choice[0] for choice in IPMI_CIPHER_SUITE_ID_CHOICES
                    )
                ),
            },
            "help_text": MAASAutoIPMICipherSuiteIDConfig.help_text,
        },
    },
    MAASAutoIPMIWorkaroundFlagsConfig.name: {
        "default": MAASAutoIPMIWorkaroundFlagsConfig.default,
        "form": forms.MultipleChoiceField,
        "form_kwargs": {
            "label": MAASAutoIPMIWorkaroundFlagsConfig.description,
            "required": False,
            "choices": IPMI_WORKAROUND_FLAG_CHOICES,
            "error_messages": {
                "invalid_choice": "Valid choices are {}".format(
                    ", ".join(
                        choice[0] for choice in IPMI_WORKAROUND_FLAG_CHOICES
                    )
                ),
            },
            "help_text": MAASAutoIPMIWorkaroundFlagsConfig.help_text,
        },
    },
    VCenterServerConfig.name: {
        "default": VCenterServerConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": VCenterServerConfig.description,
            "required": False,
            "help_text": VCenterServerConfig.help_text,
        },
    },
    VCenterUsernameConfig.name: {
        "default": VCenterUsernameConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": VCenterUsernameConfig.description,
            "required": False,
            "help_text": VCenterUsernameConfig.help_text,
        },
    },
    VCenterPasswordConfig.name: {
        "default": VCenterPasswordConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": VCenterPasswordConfig.description,
            "required": False,
            "help_text": VCenterPasswordConfig.help_text,
        },
    },
    VCenterDatacenterConfig.name: {
        "default": VCenterDatacenterConfig.default,
        "form": forms.CharField,
        "form_kwargs": {
            "label": VCenterDatacenterConfig.description,
            "required": False,
            "help_text": VCenterDatacenterConfig.help_text,
        },
    },
    HardwareSyncIntervalConfig.name: {
        "default": HardwareSyncIntervalConfig.default,
        "form": SystemdIntervalField,
        "form_kwargs": {
            "label": HardwareSyncIntervalConfig.description,
            "required": False,
            "help_text": HardwareSyncIntervalConfig.help_text,
        },
    },
    TlsCertExpirationNotificationEnabledConfig.name: {
        "default": TlsCertExpirationNotificationEnabledConfig.description,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": TlsCertExpirationNotificationEnabledConfig.description,
            "required": False,
            "help_text": TlsCertExpirationNotificationEnabledConfig.help_text,
        },
    },
    TLSCertExpirationNotificationIntervalConfig.name: {
        "default": TLSCertExpirationNotificationIntervalConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": TLSCertExpirationNotificationIntervalConfig.description,
            "required": False,
            "help_text": TLSCertExpirationNotificationIntervalConfig.help_text,
            "min_value": 1,
            "max_value": 90,
        },
    },
    SessionLengthConfig.name: {
        "default": SessionLengthConfig.default,
        "form": forms.IntegerField,
        "form_kwargs": {
            "label": SessionLengthConfig.description,
            "required": False,
            "help_text": SessionLengthConfig.help_text,
            "min_value": 10,
            "max_value": 1209600,
        },
    },
    AutoVlanCreationConfig.name: {
        "default": AutoVlanCreationConfig.default,
        "form": forms.BooleanField,
        "form_kwargs": {
            "label": AutoVlanCreationConfig.description,
            "required": False,
            "help_text": AutoVlanCreationConfig.help_text,
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
