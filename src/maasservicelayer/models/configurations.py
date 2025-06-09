# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import re
from socket import gethostname
from typing import Any, ClassVar, Generic, Optional, Type, TypeVar

from netaddr import AddrFormatError, IPAddress, IPNetwork
from pydantic import AnyHttpUrl, Field, IPvAnyAddress, validator
from pydantic.generics import GenericModel

from maascommon.constants import IMPORT_RESOURCES_SERVICE_PERIOD, NODE_TIMEOUT
from maascommon.enums.discovery import (
    ActiveDiscoveryIntervalEnum,
    NetworkDiscoveryEnum,
)
from maascommon.enums.dns import DNSSECEnumm
from maascommon.enums.interface import InterfaceLinkType
from maascommon.enums.ipmi import (
    IPMICipherSuiteID,
    IPMIPrivilegeLevel,
    IPMIWorkaroundFlags,
)
from maascommon.enums.storage import StorageLayoutEnum
from maascommon.osystem import UbuntuOS
from maascommon.utils.dns import NAMESPEC, validate_hostname
from maascommon.utils.time import systemd_interval_to_seconds
from maascommon.utils.url import splithost
from maasservicelayer.models.base import generate_builder, MaasBaseModel
from maasservicelayer.models.secrets import (
    GlobalSecret,
    MAASAutoIPMIKGBmcKeySecret,
    OMAPIKeySecret,
    RPCSharedSecret,
    VCenterPasswordSecret,
)

T = TypeVar("T")

DEFAULT_OS = UbuntuOS()


@generate_builder()
class DatabaseConfiguration(MaasBaseModel):
    name: str
    value: Any


class Config(GenericModel, Generic[T]):
    name: ClassVar[str]
    description: ClassVar[str]
    help_text: ClassVar[Optional[str]] = None
    default: ClassVar

    # If the config should be exposed to the users via API.
    is_public: ClassVar[bool] = True

    # If the config should be stored as secret.
    stored_as_secret: ClassVar[bool] = False

    # The secret model to use.
    secret_model: ClassVar[Optional[GlobalSecret]] = None
    value: T


class MAASNameConfig(Config[Optional[str]]):
    name: ClassVar[str] = "maas_name"
    default: ClassVar[Optional[str]] = gethostname()
    description: ClassVar[str] = "MAAS name"
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[str] = Field(default=default, description=description)


class ThemeConfig(Config[Optional[str]]):
    name: ClassVar[str] = "theme"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = "MAAS theme"
    value: Optional[str] = Field(default=default, description=description)


class KernelOptsConfig(Config[Optional[str]]):
    name: ClassVar[str] = "kernel_opts"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = (
        "Boot parameters to pass to the kernel by default"
    )
    value: Optional[str] = Field(default=default, description=description)


class EnableHttpProxyConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "enable_http_proxy"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Enable the use of an APT or YUM and HTTP/HTTPS proxy"
    )
    help_text: ClassVar[Optional[str]] = (
        "Provision nodes to use the built-in HTTP proxy (or user specified proxy) for APT or YUM. MAAS also uses the proxy for downloading boot images."
    )
    value: Optional[bool] = Field(default=default, description=description)


class MAASProxyPortConfig(Config[Optional[int]]):
    name: ClassVar[str] = "maas_proxy_port"
    default: ClassVar[Optional[int]] = 8000
    description: ClassVar[str] = (
        "Port to bind the MAAS built-in proxy (default: 8000)"
    )
    help_text: ClassVar[Optional[str]] = (
        "Defines the port used to bind the built-in proxy. The default port is 8000."
    )
    value: Optional[int] = Field(default=default, description=description)

    @validator("value")
    def validate_port(cls, value):
        if value is None:
            return None
        if value > 65535 or value <= 0:
            raise ValueError(
                "Unable to change port number. Port number is not between 0 - 65535."
            )
        if value >= 0 and value <= 1023:
            raise ValueError(
                "Unable to change port number. Port number is reserved for system services."
            )
        # 5239-5240 -> reserved for region HTTP.
        # 5241 - 4247 -> reserved for other MAAS services.
        # 5248 -> reserved for rack HTTP.
        # 5250 - 5270 -> reserved for region workers (RPC).
        # 5271 - 5274 -> reserved for communication between Rack Controller (specifically maas-agent) and Region Controller.
        # 5281 - 5284 -> Region Controller Temporal cluster membership gossip communication.
        if value >= 5239 and value <= 5284:
            raise ValueError(
                "Unable to change port number. Port number is reserved for MAAS services."
            )
        return value


class UsePeerProxyConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "use_peer_proxy"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = (
        "Use the built-in proxy with an external proxy as a peer"
    )
    help_text: ClassVar[Optional[str]] = (
        "If enable_http_proxy is set, the built-in proxy will be configured to use http_proxy as a peer proxy. The deployed machines will be configured to use the built-in proxy."
    )
    value: Optional[bool] = Field(default=default, description=description)


class PreferV4ProxyConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "prefer_v4_proxy"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = "Sets IPv4 DNS resolution before IPv6"
    help_text: ClassVar[Optional[str]] = (
        "If prefer_v4_proxy is set, the proxy will be set to prefer IPv4 DNS resolution before it attempts to perform IPv6 DNS resolution."
    )
    value: Optional[bool] = Field(default=default, description=description)


class HttpProxyConfig(Config[Optional[AnyHttpUrl]]):
    name: ClassVar[str] = "http_proxy"
    default: ClassVar[Optional[AnyHttpUrl]] = None
    description: ClassVar[str] = "Proxy for APT or YUM and HTTP/HTTPS"
    help_text: ClassVar[Optional[str]] = (
        "This will be passed onto provisioned nodes to use as a proxy for APT or YUM traffic. MAAS also uses the proxy for downloading boot images. If no URL is provided, the built-in MAAS proxy will be used."
    )
    value: Optional[AnyHttpUrl] = Field(
        default=default, description=description
    )


class DefaultDnsTtlConfig(Config[Optional[int]]):
    name: ClassVar[str] = "default_dns_ttl"
    default: ClassVar[Optional[int]] = 30
    description: ClassVar[str] = "Default Time-To-Live for the DNS"
    help_text: ClassVar[Optional[str]] = (
        "If no TTL value is specified at a more specific point this is how long DNS responses are valid, in seconds."
    )
    value: Optional[int] = Field(default=default, description=description)


class UpstreamDnsConfig(Config[Optional[list[IPvAnyAddress]]]):
    name: ClassVar[str] = "upstream_dns"
    default: ClassVar[Optional[list[IPvAnyAddress]]] = None
    description: ClassVar[str] = (
        "Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses)"
    )
    help_text: ClassVar[Optional[str]] = (
        "Only used when MAAS is running its own DNS server. This value is used as the value of 'forwarders' in the DNS server config."
    )
    value: Optional[list[IPvAnyAddress]] = Field(
        default=default, description=description
    )


class DNSSECValidationConfig(Config[Optional[DNSSECEnumm]]):
    name: ClassVar[str] = "dnssec_validation"
    default: ClassVar[Optional[DNSSECEnumm]] = DNSSECEnumm.AUTO
    description: ClassVar[str] = "Enable DNSSEC validation of upstream zones"
    help_text: ClassVar[Optional[str]] = (
        "Only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config."
    )
    value: Optional[DNSSECEnumm] = Field(
        default=default, description=description
    )


class MAASInternalDomainConfig(Config[Optional[str]]):
    name: ClassVar[str] = "maas_internal_domain"
    default: ClassVar[Optional[str]] = "maas-internal"
    description: ClassVar[str] = (
        "Domain name used by MAAS for internal mapping of MAAS provided services."
    )
    help_text: ClassVar[Optional[str]] = (
        "This domain should not collide with an upstream domain provided by the set upstream DNS."
    )
    value: Optional[str] = Field(default=default, description=description)

    @validator("value")
    def validate_value(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        namespec = re.compile("^%s$" % NAMESPEC)
        if not namespec.search(value) or len(value) > 255:
            raise ValueError("Invalid domain name: %s." % value)
        return value


class DNSTrustedAclConfig(Config[Optional[str]]):
    """Accepts a space/comma separated list of hostnames, Subnets or IPs.

    This field normalizes the list to a space-separated list.
    """

    _separators = re.compile(r"[,\s]+")
    _pt_ipv4 = r"(?:\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    _pt_ipv6 = r"(?:([0-9A-Fa-f]{1,4})?[:]([0-9A-Fa-f]{1,4})?[:](.*))"
    _pt_ip = re.compile(rf"^({_pt_ipv4}|{_pt_ipv6})$", re.VERBOSE)
    _pt_subnet = re.compile(rf"^({_pt_ipv4}|{_pt_ipv6})/\d+$", re.VERBOSE)

    name: ClassVar[str] = "dns_trusted_acl"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = (
        "List of external networks (not previously known), that will be allowed to use MAAS for DNS resolution."
    )
    help_text: ClassVar[Optional[str]] = (
        "MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows to add extra networks (not previously known) to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names."
    )
    value: Optional[str] = Field(default=default, description=description)

    @validator("value")
    def validate_value(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        values = map(str.strip, cls._separators.split(value))
        values = (value for value in values if len(value) != 0)
        values = map(cls._clean_addr_or_host, values)
        return " ".join(values)

    @classmethod
    def _clean_addr_or_host(cls, value: str) -> str:
        if cls._pt_subnet.match(value):  # Looks like subnet
            return cls._clean_subnet(value)
        elif cls._pt_ip.match(value):  # Looks like ip
            return cls._clean_addr(value)
        else:  # Anything else
            return cls._clean_host(value)

    @classmethod
    def _clean_addr(cls, value: str) -> str:
        try:
            return str(IPAddress(value))
        except (ValueError, AddrFormatError) as e:
            raise ValueError(f"Invalid IP address: {value}.") from e

    @classmethod
    def _clean_subnet(cls, value: str) -> str:
        try:
            return str(IPNetwork(value))
        except AddrFormatError as e:
            raise ValueError(f"Invalid network: {value}.") from e

    @classmethod
    def _clean_host(cls, host: str) -> str:
        try:
            validate_hostname(host)
        except ValueError as e:
            raise ValueError(f"Invalid hostname: {str(e)}") from e
        return host


class NTPServersConfig(Config[Optional[str]]):
    """Accepts a space/comma separated list of hostnames or IP addresses.

    This field normalizes the list to a space-separated list.
    """

    _separators = re.compile(r"[,\s]+")

    # Regular expressions to sniff out things that look like IP addresses;
    # additional and more robust validation ought to be done to make sure.
    _pt_ipv4 = r"(?: \d{1,3} [.] \d{1,3} [.] \d{1,3} [.] \d{1,3} )"
    _pt_ipv6 = r"(?: (?: [\da-fA-F]+ :+)+ (?: [\da-fA-F]+ | %s )+ )" % _pt_ipv4
    _pt_ip = re.compile(rf"^ (?: {_pt_ipv4} | {_pt_ipv6} ) $", re.VERBOSE)

    name: ClassVar[str] = "ntp_servers"
    default: ClassVar[Optional[str]] = "ntp.ubuntu.com"
    description: ClassVar[str] = "Addresses of NTP servers"
    help_text: ClassVar[Optional[str]] = (
        "NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS's DHCP services."
    )
    value: Optional[str] = Field(default=default, description=description)

    @validator("value")
    def validate_value(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        else:
            values = map(str.strip, cls._separators.split(value))
            values = (value for value in values if len(value) != 0)
            values = map(cls._clean_addr_or_host, values)
            return " ".join(values)

    @classmethod
    def _clean_addr_or_host(cls, value):
        looks_like_ip = cls._pt_ip.match(value) is not None
        if looks_like_ip:
            return cls._clean_addr(value)
        elif ":" in value:
            # This is probably an IPv6 address. It's definitely not a
            # hostname.
            return cls._clean_addr(value)
        else:
            return cls._clean_host(value)

    @classmethod
    def _clean_addr(cls, addr):
        try:
            addr = IPAddress(addr)
        except AddrFormatError as error:
            message = str(error)  # netaddr has good messages.
            message = message[:1].upper() + message[1:] + "."
            raise ValueError(message)  # noqa: B904
        else:
            return str(addr)

    @classmethod
    def _clean_host(cls, host):
        try:
            validate_hostname(host)
        except ValueError as error:
            raise ValueError(f"Invalid hostname: {str(error)}")  # noqa: B904
        else:
            return host


class NTPExternalOnlyConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "ntp_external_only"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = "Use external NTP servers only"
    help_text: ClassVar[Optional[str]] = (
        "Configure all region controller hosts, rack controller hosts, and subsequently deployed machines to refer directly to the configured external NTP servers. Otherwise only region controller hosts will be configured to use those external NTP servers, rack contoller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers."
    )
    value: Optional[bool] = Field(default=default, description=description)


class RemoteSyslogConfig(Config[Optional[str]]):
    name: ClassVar[str] = "remote_syslog"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = "Remote syslog server to forward machine logs"
    help_text: ClassVar[Optional[str]] = (
        "A remote syslog server that MAAS will set on enlisting, commissioning, testing, and deploying machines to send all log messages. Clearing this value will restore the default behaviour of forwarding syslog to MAAS."
    )
    value: Optional[str] = Field(default=default, description=description)

    @validator("value")
    def validate_value(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        host, port = splithost(value)
        if not port:
            port = 514
        return "%s:%d" % (host, port)


class MAASSyslogPortConfig(Config[Optional[int]]):
    name: ClassVar[str] = "maas_syslog_port"
    default: ClassVar[Optional[int]] = 5247
    description: ClassVar[str] = (
        "Port to bind the MAAS built-in syslog (default: 5247)"
    )
    help_text: ClassVar[Optional[str]] = (
        "Defines the port used to bind the built-in syslog. The default port is 5247."
    )
    value: Optional[int] = Field(default=default, description=description)

    @validator("value")
    def validate_port(cls, value):
        if value is None:
            return None
        # Allow the internal syslog port
        if value == 5247:
            return value
        if value > 65535 or value <= 0:
            raise ValueError(
                "Unable to change port number. Port number is not between 0 - 65535."
            )
        if value >= 0 and value <= 1023:
            raise ValueError(
                "Unable to change port number. Port number is reserved for system services."
            )
        # 5239-5240 -> reserved for region HTTP.
        # 5241 - 4247 -> reserved for other MAAS services.
        # 5248 -> reserved for rack HTTP.
        # 5250 - 5270 -> reserved for region workers (RPC).
        # 5271 - 5274 -> reserved for communication between Rack Controller (specifically maas-agent) and Region Controller.
        # 5281 - 5284 -> Region Controller Temporal cluster membership gossip communication.
        if value >= 5239 and value <= 5284:
            raise ValueError(
                "Unable to change port number. Port number is reserved for MAAS services."
            )
        return value


class NetworkDiscoveryConfig(Config[Optional[NetworkDiscoveryEnum]]):
    name: ClassVar[str] = "network_discovery"
    default: ClassVar[Optional[NetworkDiscoveryEnum]] = (
        NetworkDiscoveryEnum.ENABLED
    )
    description: ClassVar[str] = ""
    help_text: ClassVar[Optional[str]] = (
        "When enabled, MAAS will use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets."
    )
    value: Optional[NetworkDiscoveryEnum] = Field(
        default=default, description=description
    )


class ActiveDiscoveryIntervalConfig(
    Config[Optional[ActiveDiscoveryIntervalEnum]]
):
    name: ClassVar[str] = "active_discovery_interval"
    default: ClassVar[Optional[ActiveDiscoveryIntervalEnum]] = (
        ActiveDiscoveryIntervalEnum.EVERY_3_HOURS
    )
    description: ClassVar[str] = "Active subnet mapping interval"
    help_text: ClassVar[Optional[str]] = (
        "When enabled, each rack will scan subnets enabled for active mapping. This helps ensure discovery information is accurate and complete."
    )
    value: Optional[ActiveDiscoveryIntervalEnum] = Field(
        default=default, description=description
    )


class DefaultBootInterfaceLinkTypeConfig(Config[Optional[InterfaceLinkType]]):
    name: ClassVar[str] = "default_boot_interface_link_type"
    default: ClassVar[Optional[InterfaceLinkType]] = InterfaceLinkType.AUTO
    description: ClassVar[str] = "Default boot interface IP Mode"
    help_text: ClassVar[Optional[str]] = (
        "IP Mode that is applied to the boot interface on a node when it is commissioned."
    )
    value: Optional[InterfaceLinkType] = Field(
        default=default, description=description
    )


class DefaultOSystemConfig(Config[Optional[str]]):
    name: ClassVar[str] = "default_osystem"
    default: ClassVar[Optional[str]] = DEFAULT_OS.name
    description: ClassVar[str] = "Default operating system used for deployment"
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[str] = Field(default=default, description=description)

    # TODO ADD VALIDATION


class DefaultDistroSeriesConfig(Config[Optional[str]]):
    name: ClassVar[str] = "default_distro_series"
    default: ClassVar[Optional[str]] = DEFAULT_OS.get_default_release()
    description: ClassVar[str] = "Default OS release used for deployment"
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[str] = Field(default=default, description=description)

    # TODO ADD VALIDATION


class DefaultMinHweKernelConfig(Config[Optional[str]]):
    name: ClassVar[str] = "default_min_hwe_kernel"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = "Default Minimum Kernel Version"
    help_text: ClassVar[Optional[str]] = (
        "The default minimum kernel version used on all new and commissioned nodes."
    )
    value: Optional[str] = Field(default=default, description=description)

    # TODO ADD VALIDATION


class EnableKernelCrashDumpConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "enable_kernel_crash_dump"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = (
        "Enable the kernel crash dump feature in deployed machines."
    )
    help_text: ClassVar[Optional[str]] = (
        "Enable the collection of kernel crash dump when a machine is deployed."
    )
    value: Optional[bool] = Field(default=default, description=description)


class DefaultStorageLayoutConfig(Config[Optional[StorageLayoutEnum]]):
    name: ClassVar[str] = "default_storage_layout"
    default: ClassVar[Optional[StorageLayoutEnum]] = StorageLayoutEnum.FLAT
    description: ClassVar[str] = "Default storage layout"
    help_text: ClassVar[Optional[str]] = (
        "Storage layout that is applied to a node when it is commissioned."
    )
    value: Optional[StorageLayoutEnum] = Field(
        default=default, description=description
    )


class CommissioningDistroSeriesConfig(Config[Optional[str]]):
    name: ClassVar[str] = "commissioning_distro_series"
    default: ClassVar[Optional[str]] = (
        DEFAULT_OS.get_default_commissioning_release()
    )
    description: ClassVar[str] = (
        "Default Ubuntu release used for commissioning"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[str] = Field(default=default, description=description)

    # TODO ADD VALIDATION


class EnableThirdPartyDriversConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "enable_third_party_drivers"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Enable the installation of proprietary drivers (i.e. HPVSA)"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class WindowsKmsHostConfig(Config[Optional[str]]):
    name: ClassVar[str] = "windows_kms_host"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = "Windows KMS activation host"
    help_text: ClassVar[Optional[str]] = (
        "FQDN or IP address of the host that provides the KMS Windows activation service. (Only needed for Windows deployments using KMS activation.)"
    )
    value: Optional[str] = Field(default=default, description=description)


class EnableDiskErasingOnReleaseConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "enable_disk_erasing_on_release"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = "Erase nodes' disks prior to releasing"
    help_text: ClassVar[Optional[str]] = (
        "Forces users to always erase disks when releasing."
    )
    value: Optional[bool] = Field(default=default, description=description)


class DiskEraseWithSecureEraseConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "disk_erase_with_secure_erase"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Use secure erase by default when erasing disks"
    )
    help_text: ClassVar[Optional[str]] = (
        "Will only be used on devices that support secure erase.  Other devices will fall back to full wipe or quick erase depending on the selected options."
    )
    value: Optional[bool] = Field(default=default, description=description)


class DiskEraseWithQuickEraseConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "disk_erase_with_quick_erase"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = (
        "Use quick erase by default when erasing disks."
    )
    help_text: ClassVar[Optional[str]] = (
        "This is not a secure erase; it wipes only the beginning and end of each disk."
    )
    value: Optional[bool] = Field(default=default, description=description)


class BootImagesAutoImportConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "boot_images_auto_import"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        f"Automatically import/refresh the boot images every {IMPORT_RESOURCES_SERVICE_PERIOD.total_seconds() / 60.0} minutes"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class BootImagesNoProxyConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "boot_images_no_proxy"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = (
        "Set no_proxy with the image repository address when MAAS is behind (or set with) a proxy."
    )
    help_text: ClassVar[Optional[str]] = (
        "By default, when MAAS is behind (and set with) a proxy, it is used to download images from the image repository. In some situations (e.g. when using a local image repository) it doesn't make sense for MAAS to use the proxy to download images because it can access them directly. Setting this option allows MAAS to access the (local) image repository directly by setting the no_proxy variable for the MAAS env with the address of the image repository."
    )
    value: Optional[bool] = Field(default=default, description=description)


class CurtinVerboseConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "curtin_verbose"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Run the fast-path installer with higher verbosity. This provides more detail in the installation logs"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class ForceV1NetworkYamlConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "force_v1_network_yaml"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = (
        "Always use the legacy v1 YAML (rather than Netplan format, also known as v2 YAML) when composing the network configuration for a machine."
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class EnableAnalyticsConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "enable_analytics"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Enable Google Analytics in MAAS UI to shape improvements in user experience"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class CompletedIntroConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "completed_intro"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = (
        "Marks if the initial intro has been completed"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class MaxNodeCommissioningResultsConfig(Config[Optional[int]]):
    name: ClassVar[str] = "max_node_commissioning_results"
    default: ClassVar[Optional[int]] = 10
    description: ClassVar[str] = (
        "The maximum number of commissioning results runs which are stored"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[int] = Field(
        default=default, description=description, ge=1
    )


class MaxNodeTestingResultsConfig(Config[Optional[int]]):
    name: ClassVar[str] = "max_node_testing_results"
    default: ClassVar[Optional[int]] = 10
    description: ClassVar[str] = (
        "The maximum number of testing results runs which are stored"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[int] = Field(
        default=default, description=description, ge=1
    )


class MaxNodeInstallationResultsConfig(Config[Optional[int]]):
    name: ClassVar[str] = "max_node_installation_results"
    default: ClassVar[Optional[int]] = 3
    description: ClassVar[str] = (
        "The maximum number of installation result runs which are stored"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[int] = Field(
        default=default, description=description, ge=1
    )


class MaxNodeReleaseResultsConfig(Config[Optional[int]]):
    name: ClassVar[str] = "max_node_release_results"
    default: ClassVar[Optional[int]] = 3
    description: ClassVar[str] = (
        "The maximum number of release result runs which are stored"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[int] = Field(
        default=default, description=description, ge=1
    )


class SubnetIPExhaustionThresholdCountConfig(Config[Optional[int]]):
    name: ClassVar[str] = "subnet_ip_exhaustion_threshold_count"
    default: ClassVar[Optional[int]] = 16
    description: ClassVar[str] = (
        "If the number of free IP addresses on a subnet becomes less than or equal to this threshold, an IP exhaustion warning will appear for that subnet"
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[int] = Field(
        default=default, description=description, ge=1
    )


class ReleaseNotificationsConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "release_notifications"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Enable or disable notifications for new MAAS releases."
    )
    help_text: ClassVar[Optional[str]] = ""
    value: Optional[bool] = Field(default=default, description=description)


class UseRackProxyConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "use_rack_proxy"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Use DNS and HTTP metadata proxy on the rack controllers when a machine is booted."
    )
    help_text: ClassVar[Optional[str]] = (
        "All DNS and HTTP metadata traffic will flow through the rack controller that a machine is booting from. This isolated region controllers from machines."
    )
    value: Optional[bool] = Field(default=default, description=description)


class NodeTimeoutConfig(Config[Optional[int]]):
    name: ClassVar[str] = "node_timeout"
    default: ClassVar[Optional[int]] = NODE_TIMEOUT
    description: ClassVar[str] = (
        "Time, in minutes, until the node times out during commissioning, testing, deploying, or entering rescue mode."
    )
    help_text: ClassVar[Optional[str]] = (
        "Commissioning, testing, deploying, and entering rescue mode all set a timeout when beginning. If MAAS does not hear from the node within the specified number of minutes the node is powered off and set into a failed status."
    )
    value: Optional[int] = Field(
        default=default, description=description, ge=1
    )


class PrometheusEnabledConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "prometheus_enabled"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = "Enable Prometheus exporter"
    help_text: ClassVar[Optional[str]] = (
        "Whether to enable Prometheus exporter functions, including Cluster metrics endpoint and Push gateway (if configured)."
    )
    value: Optional[bool] = Field(default=default, description=description)


class PrometheusPushGatewayConfig(Config[Optional[str]]):
    name: ClassVar[str] = "prometheus_push_gateway"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = (
        "Address or hostname of the Prometheus push gateway."
    )
    help_text: ClassVar[Optional[str]] = (
        "Defines the address or hostname of the Prometheus push gateway where MAAS will send data to."
    )
    value: Optional[str] = Field(default=default, description=description)


class PrometheusPushIntervalConfig(Config[Optional[int]]):
    name: ClassVar[str] = "prometheus_push_interval"
    default: ClassVar[Optional[int]] = 60
    description: ClassVar[str] = (
        "Interval of how often to send data to Prometheus (default: to 60 minutes)."
    )
    help_text: ClassVar[Optional[str]] = (
        "The internal of how often MAAS will send stats to Prometheus in minutes."
    )
    value: Optional[int] = Field(default=default, description=description)


class PromtailEnabledConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "promtail_enabled"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = "Enable streaming logs to Promtail."
    help_text: ClassVar[Optional[str]] = "Whether to stream logs to Promtail"
    value: Optional[bool] = Field(default=default, description=description)


class PromtailPortConfig(Config[Optional[int]]):
    name: ClassVar[str] = "promtail_port"
    default: ClassVar[Optional[int]] = 5238
    description: ClassVar[str] = "TCP port of the Promtail Push API."
    help_text: ClassVar[Optional[str]] = (
        "Defines the TCP port of the Promtail push API where MAAS will stream logs to."
    )
    value: Optional[int] = Field(default=default, description=description)


class EnlistCommissioningConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "enlist_commissioning"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Whether to run commissioning during enlistment."
    )
    help_text: ClassVar[Optional[str]] = (
        "Enables running all built-in commissioning scripts during enlistment."
    )
    value: Optional[bool] = Field(default=default, description=description)


class MAASAutoIPMIUserConfig(Config[Optional[str]]):
    name: ClassVar[str] = "maas_auto_ipmi_user"
    default: ClassVar[Optional[str]] = "maas"
    description: ClassVar[str] = "MAAS IPMI user."
    help_text: ClassVar[Optional[str]] = (
        "The name of the IPMI user that MAAS automatically creates during enlistment/commissioning."
    )
    value: Optional[str] = Field(default=default, description=description)


class MAASAutoIPMIUserPrivilegeLevelConfig(
    Config[Optional[IPMIPrivilegeLevel]]
):
    name: ClassVar[str] = "maas_auto_ipmi_user_privilege_level"
    default: ClassVar[Optional[IPMIPrivilegeLevel]] = IPMIPrivilegeLevel.ADMIN
    description: ClassVar[str] = "MAAS IPMI privilege level"
    help_text: ClassVar[Optional[str]] = (
        "The default IPMI privilege level to use when creating the MAAS user and talking IPMI BMCs"
    )
    value: Optional[IPMIPrivilegeLevel] = Field(
        default=default, description=description
    )


class MAASAutoIPMIKGBmcKeyConfig(Config[Optional[str]]):
    stored_as_secret: ClassVar[bool] = True
    secret_model: ClassVar[Optional[GlobalSecret]] = (
        MAASAutoIPMIKGBmcKeySecret()
    )
    name: ClassVar[str] = "maas_auto_ipmi_k_g_bmc_key"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = (
        "The IPMI K_g key to set during BMC configuration."
    )
    help_text: ClassVar[Optional[str]] = (
        "This IPMI K_g BMC key is used to encrypt all IPMI traffic to a BMC. Once set, all clients will REQUIRE this key upon being commissioned. Any current machines that were previously commissioned will not require this key until they are recommissioned."
    )
    value: Optional[str] = Field(default=default, description=description)

    @validator("value")
    def validate_value(cls, value: Optional[str]) -> Optional[str]:
        """
        Ensure that the provided IPMI k_g value is valid. This validator is used to
        test both for valid encoding (regular or hexadecimal) and to ensure input
        is 20 characters long (or 40 in hexadecimal plus '0x' prefix).
        """
        if value is None:
            return None

        if value == "":
            return ""

        valid_k_g_match = re.search(r"^(0x[a-fA-F0-9]{40}|[\w\W]{20})$", value)
        if not valid_k_g_match:
            raise ValueError(
                (
                    "Error: K_g must either be 20 characters in length, or "
                    '40 hexadecimal characters prefixed with "0x" (current '
                    "length is %d)."
                )
                % len(value)
            )
        return value


class MAASAutoIPMICipherSuiteIDConfig(Config[Optional[IPMICipherSuiteID]]):
    name: ClassVar[str] = "maas_auto_ipmi_cipher_suite_id"
    default: ClassVar[Optional[IPMICipherSuiteID]] = IPMICipherSuiteID.SUITE_3
    description: ClassVar[str] = "MAAS IPMI Default Cipher Suite ID"
    help_text: ClassVar[Optional[str]] = (
        "The default IPMI cipher suite ID to use when connecting to the BMC via ipmitools"
    )
    value: Optional[IPMICipherSuiteID] = Field(
        default=default, description=description
    )


class MAASAutoIPMIWorkaroundFlagsConfig(
    Config[Optional[list[IPMIWorkaroundFlags]]]
):
    name: ClassVar[str] = "maas_auto_ipmi_workaround_flags"
    default: ClassVar[Optional[list[IPMIWorkaroundFlags]]] = None
    description: ClassVar[str] = "IPMI Workaround Flags"
    help_text: ClassVar[Optional[str]] = (
        "The default workaround flag (-W options) to use for ipmipower commands"
    )
    value: Optional[list[IPMIWorkaroundFlags]] = Field(
        default=default, description=description
    )


class VCenterServerConfig(Config[Optional[str]]):
    name: ClassVar[str] = "vcenter_server"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = "VMware vCenter server FQDN or IP address"
    help_text: ClassVar[Optional[str]] = (
        "VMware vCenter server FQDN or IP address which is passed to a deployed VMware ESXi host."
    )
    value: Optional[str] = Field(default=default, description=description)


class VCenterUsernameConfig(Config[Optional[str]]):
    name: ClassVar[str] = "vcenter_username"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = "VMware vCenter username"
    help_text: ClassVar[Optional[str]] = (
        "VMware vCenter server username which is passed to a deployed VMware ESXi host."
    )
    value: Optional[str] = Field(default=default, description=description)


class VCenterPasswordConfig(Config[Optional[str]]):
    stored_as_secret: ClassVar[bool] = True
    secret_model: ClassVar[Optional[GlobalSecret]] = VCenterPasswordSecret()
    name: ClassVar[str] = "vcenter_password"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = "VMware vCenter password"
    help_text: ClassVar[Optional[str]] = (
        "VMware vCenter server password which is passed to a deployed VMware ESXi host."
    )
    value: Optional[str] = Field(default=default, description=description)


class VCenterDatacenterConfig(Config[Optional[str]]):
    name: ClassVar[str] = "vcenter_datacenter"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = "VMware vCenter datacenter"
    help_text: ClassVar[Optional[str]] = (
        "VMware vCenter datacenter which is passed to a deployed VMware ESXi host."
    )
    value: Optional[str] = Field(default=default, description=description)


class HardwareSyncIntervalConfig(Config[Optional[str]]):
    name: ClassVar[str] = "hardware_sync_interval"
    default: ClassVar[Optional[str]] = "15m"
    description: ClassVar[str] = "Hardware Sync Interval"
    help_text: ClassVar[Optional[str]] = (
        "The interval to send hardware info to MAAS fromhardware sync enabled machines, in systemd time span syntax."
    )
    value: Optional[str] = Field(default=default, description=description)

    @validator("value")
    def validate_systemd_interval(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        # try to parse the interval.
        systemd_interval_to_seconds(value)
        return value


class TlsCertExpirationNotificationEnabledConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "tls_cert_expiration_notification_enabled"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = "Notify when the certificate is due to expire"
    help_text: ClassVar[Optional[str]] = (
        "Enable/Disable notification about certificate expiration."
    )
    value: Optional[bool] = Field(default=default, description=description)


class TLSCertExpirationNotificationIntervalConfig(Config[Optional[int]]):
    name: ClassVar[str] = "tls_cert_expiration_notification_interval"
    default: ClassVar[Optional[int]] = 30
    description: ClassVar[str] = "Certificate expiration reminder (days)"
    help_text: ClassVar[Optional[str]] = (
        "Configure notification when certificate is due to expire in (days)."
    )
    value: Optional[int] = Field(
        default=default, description=description, ge=1, le=90
    )


class SessionLengthConfig(Config[Optional[int]]):
    name: ClassVar[str] = "session_length"
    default: ClassVar[Optional[int]] = 1209600
    description: ClassVar[str] = "Session timeout (seconds)"
    help_text: ClassVar[Optional[str]] = (
        "Configure timeout of session (seconds). Minimum 10s, maximum 2 weeks (1209600s)."
    )
    value: Optional[int] = Field(
        default=default, description=description, ge=10, le=1209600
    )


class AutoVlanCreationConfig(Config[Optional[bool]]):
    name: ClassVar[str] = "auto_vlan_creation"
    default: ClassVar[Optional[bool]] = True
    description: ClassVar[str] = (
        "Automatically create VLANs and Fabrics for interfaces"
    )
    help_text: ClassVar[Optional[str]] = (
        "Enables the creation of a default VLAN and Fabric for discovered network interfaces when MAAS cannot connect it to an existing one. When disabled, the interface is left disconnected in these cases."
    )
    value: Optional[bool] = Field(default=default, description=description)


# Private configs
class ActiveDiscoveryLastScanConfig(Config[Optional[int]]):
    is_public: ClassVar[bool] = False
    name: ClassVar[str] = "active_discovery_last_scan"
    default: ClassVar[Optional[int]] = 0
    description: ClassVar[str] = ""
    value: Optional[int] = Field(default=default, description=description)


class CommissioningOSystemConfig(Config[Optional[str]]):
    is_public: ClassVar[bool] = False
    name: ClassVar[str] = "commissioning_osystem"
    default: ClassVar[Optional[str]] = DEFAULT_OS.name
    description: ClassVar[str] = ""
    value: Optional[str] = Field(default=default, description=description)


class MAASUrlConfig(Config[Optional[str]]):
    is_public: ClassVar[bool] = False
    name: ClassVar[str] = "maas_url"
    default: ClassVar[Optional[str]] = "http://localhost:5240/MAAS"
    description: ClassVar[str] = ""
    value: Optional[str] = Field(default=default, description=description)


class OMAPIKeyConfig(Config[Optional[str]]):
    is_public: ClassVar[bool] = False
    stored_as_secret: ClassVar[bool] = True
    secret_model: ClassVar[Optional[GlobalSecret]] = OMAPIKeySecret()
    name: ClassVar[str] = "omapi_key"
    default: ClassVar[Optional[str]] = ""
    description: ClassVar[str] = ""
    value: Optional[str] = Field(default=default, description=description)


class RPCSharedSecretConfig(Config[Optional[str]]):
    is_public: ClassVar[bool] = False
    stored_as_secret: ClassVar[bool] = True
    secret_model: ClassVar[Optional[GlobalSecret]] = RPCSharedSecret()
    name: ClassVar[str] = "rpc_shared_secret"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = ""
    value: Optional[str] = Field(default=default, description=description)


class TLSPortConfig(Config[Optional[int]]):
    is_public: ClassVar[bool] = False
    name: ClassVar[str] = "tls_port"
    default: ClassVar[Optional[int]] = None
    description: ClassVar[str] = ""
    value: Optional[int] = Field(default=default, description=description)


class UUIDConfig(Config[Optional[str]]):
    is_public: ClassVar[bool] = False
    name: ClassVar[str] = "uuid"
    default: ClassVar[Optional[str]] = None
    description: ClassVar[str] = ""
    value: Optional[str] = Field(default=default, description=description)


class VaultEnabledConfig(Config[Optional[bool]]):
    is_public: ClassVar[bool] = False
    name: ClassVar[str] = "vault_enabled"
    default: ClassVar[Optional[bool]] = False
    description: ClassVar[str] = ""
    value: Optional[bool] = Field(default=default, description=description)


class ConfigFactory:
    ALL_CONFIGS: dict[str, Type[Config]] = {
        MAASNameConfig.name: MAASNameConfig,
        ThemeConfig.name: ThemeConfig,
        KernelOptsConfig.name: KernelOptsConfig,
        EnableHttpProxyConfig.name: EnableHttpProxyConfig,
        MAASProxyPortConfig.name: MAASProxyPortConfig,
        UsePeerProxyConfig.name: UsePeerProxyConfig,
        PreferV4ProxyConfig.name: PreferV4ProxyConfig,
        HttpProxyConfig.name: HttpProxyConfig,
        DefaultDnsTtlConfig.name: DefaultDnsTtlConfig,
        UpstreamDnsConfig.name: UpstreamDnsConfig,
        DNSSECValidationConfig.name: DNSSECValidationConfig,
        MAASInternalDomainConfig.name: MAASInternalDomainConfig,
        DNSTrustedAclConfig.name: DNSTrustedAclConfig,
        NTPServersConfig.name: NTPServersConfig,
        NTPExternalOnlyConfig.name: NTPExternalOnlyConfig,
        RemoteSyslogConfig.name: RemoteSyslogConfig,
        MAASSyslogPortConfig.name: MAASSyslogPortConfig,
        NetworkDiscoveryConfig.name: NetworkDiscoveryConfig,
        ActiveDiscoveryIntervalConfig.name: ActiveDiscoveryIntervalConfig,
        DefaultBootInterfaceLinkTypeConfig.name: DefaultBootInterfaceLinkTypeConfig,
        DefaultOSystemConfig.name: DefaultOSystemConfig,
        DefaultDistroSeriesConfig.name: DefaultDistroSeriesConfig,
        DefaultMinHweKernelConfig.name: DefaultMinHweKernelConfig,
        EnableKernelCrashDumpConfig.name: EnableKernelCrashDumpConfig,
        DefaultStorageLayoutConfig.name: DefaultStorageLayoutConfig,
        CommissioningDistroSeriesConfig.name: CommissioningDistroSeriesConfig,
        EnableThirdPartyDriversConfig.name: EnableThirdPartyDriversConfig,
        WindowsKmsHostConfig.name: WindowsKmsHostConfig,
        EnableDiskErasingOnReleaseConfig.name: EnableDiskErasingOnReleaseConfig,
        DiskEraseWithSecureEraseConfig.name: DiskEraseWithSecureEraseConfig,
        DiskEraseWithQuickEraseConfig.name: DiskEraseWithQuickEraseConfig,
        BootImagesAutoImportConfig.name: BootImagesAutoImportConfig,
        BootImagesNoProxyConfig.name: BootImagesNoProxyConfig,
        CurtinVerboseConfig.name: CurtinVerboseConfig,
        ForceV1NetworkYamlConfig.name: ForceV1NetworkYamlConfig,
        EnableAnalyticsConfig.name: EnableAnalyticsConfig,
        CompletedIntroConfig.name: CompletedIntroConfig,
        MaxNodeCommissioningResultsConfig.name: MaxNodeCommissioningResultsConfig,
        MaxNodeTestingResultsConfig.name: MaxNodeTestingResultsConfig,
        MaxNodeInstallationResultsConfig.name: MaxNodeInstallationResultsConfig,
        MaxNodeReleaseResultsConfig.name: MaxNodeReleaseResultsConfig,
        SubnetIPExhaustionThresholdCountConfig.name: SubnetIPExhaustionThresholdCountConfig,
        ReleaseNotificationsConfig.name: ReleaseNotificationsConfig,
        UseRackProxyConfig.name: UseRackProxyConfig,
        NodeTimeoutConfig.name: NodeTimeoutConfig,
        PrometheusEnabledConfig.name: PrometheusEnabledConfig,
        PrometheusPushGatewayConfig.name: PrometheusPushGatewayConfig,
        PrometheusPushIntervalConfig.name: PrometheusPushIntervalConfig,
        PromtailEnabledConfig.name: PromtailEnabledConfig,
        PromtailPortConfig.name: PromtailPortConfig,
        EnlistCommissioningConfig.name: EnlistCommissioningConfig,
        MAASAutoIPMIUserConfig.name: MAASAutoIPMIUserConfig,
        MAASAutoIPMIUserPrivilegeLevelConfig.name: MAASAutoIPMIUserPrivilegeLevelConfig,
        MAASAutoIPMIKGBmcKeyConfig.name: MAASAutoIPMIKGBmcKeyConfig,
        MAASAutoIPMICipherSuiteIDConfig.name: MAASAutoIPMICipherSuiteIDConfig,
        MAASAutoIPMIWorkaroundFlagsConfig.name: MAASAutoIPMIWorkaroundFlagsConfig,
        VCenterServerConfig.name: VCenterServerConfig,
        VCenterUsernameConfig.name: VCenterUsernameConfig,
        VCenterPasswordConfig.name: VCenterPasswordConfig,
        VCenterDatacenterConfig.name: VCenterDatacenterConfig,
        HardwareSyncIntervalConfig.name: HardwareSyncIntervalConfig,
        TlsCertExpirationNotificationEnabledConfig.name: TlsCertExpirationNotificationEnabledConfig,
        TLSCertExpirationNotificationIntervalConfig.name: TLSCertExpirationNotificationIntervalConfig,
        SessionLengthConfig.name: SessionLengthConfig,
        AutoVlanCreationConfig.name: AutoVlanCreationConfig,
        # Private configs.
        ActiveDiscoveryLastScanConfig.name: ActiveDiscoveryLastScanConfig,
        CommissioningOSystemConfig.name: CommissioningOSystemConfig,
        MAASUrlConfig.name: MAASUrlConfig,
        OMAPIKeyConfig.name: OMAPIKeyConfig,
        RPCSharedSecretConfig.name: RPCSharedSecretConfig,
        TLSPortConfig.name: TLSPortConfig,
        UUIDConfig.name: UUIDConfig,
        VaultEnabledConfig.name: VaultEnabledConfig,
    }

    PUBLIC_CONFIGS = {
        config_name: config_model
        for config_name, config_model in ALL_CONFIGS.items()
        if config_model.is_public
    }

    @classmethod
    def parse(cls, name: str, value: Any) -> Config:
        """
        Parses and returns a configuration object for the given name.

        This method retrieves the appropriate configuration model (either public or private)
        and initializes it with the provided value.

        Args:
            name (str): The name of the configuration key.
            value (Any): The value to be assigned to the configuration.

        Returns:
            Config: An instance of the corresponding configuration model.

        Raises:
            ValueError: If the configuration name is not recognized.
        """
        model = cls.get_config_model(name)
        return model(value=value)

    @classmethod
    def get_config_model(cls, name: str) -> Type[Config]:
        """
        Retrieves the configuration model associated with the given name.

        This method checks both public and private configurations and returns the corresponding
        configuration model type.

        Args:
            name (str): The name of the configuration key.

        Returns:
            Type[Config]: The corresponding configuration model class.

        Raises:
            ValueError: If the configuration name is not found in either public or private configurations.
        """
        model = cls.ALL_CONFIGS.get(name)
        if model:
            return model
        raise ValueError(f"The configuration '{name}' is unknown.")
