# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level composition code for preseeds."""


from datetime import timedelta
from ipaddress import ip_address
from urllib.parse import urlencode

from django.urls import reverse
import yaml

from maasserver.clusterrpc.osystems import get_preseed_data
from maasserver.dns.config import get_resource_name_for_subnet
from maasserver.enum import NODE_STATUS, POWER_STATE, PRESEED_TYPE
from maasserver.models import PackageRepository
from maasserver.models.config import Config
from maasserver.models.subnet import get_boot_rackcontroller_ips, Subnet
from maasserver.node_status import COMMISSIONING_LIKE_STATUSES
from maasserver.server_address import get_maas_facing_server_host
from maasserver.utils import get_default_region_ip, get_remote_ip
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
)
from provisioningserver.utils.url import compose_URL

# Default port for RSYSLOG
RSYSLOG_PORT = 5247

# Default port for rack controller proxy
RACK_CONTROLLER_PORT = 5248


def _subnet_uses_dns(subnet):
    return (
        subnet is not None
        and subnet.allow_dns
        and not subnet.dns_servers
        and (subnet.vlan.dhcp_on or subnet.vlan.relay_vlan_id is not None)
    )


def _wrap_ipv6_address(ip):
    return str(ip) if ip_address(ip).version == 4 else f"[{ip}]"


def _get_rack_host(request):
    machine_ip = get_remote_ip(request)
    if machine_ip:
        machine_subnet = Subnet.objects.get_best_subnet_for_ip(machine_ip)
        rackcontroller_ips = get_boot_rackcontroller_ips(machine_subnet)
        if rackcontroller_ips:
            boot_ip = rackcontroller_ips[0]
            boot_subnet = Subnet.objects.get_best_subnet_for_ip(boot_ip)
            if _subnet_uses_dns(machine_subnet):
                internal_domain = Config.objects.get_config(
                    "maas_internal_domain"
                )
                return f"{get_resource_name_for_subnet(boot_subnet)}.{internal_domain}"
            else:
                return _wrap_ipv6_address(boot_ip)
    return None


def _get_rackcontroller_host(request, node=None):
    if node and node.boot_cluster_ip:
        return _wrap_ipv6_address(node.boot_cluster_ip)
    else:
        return _get_rack_host(request)


def build_metadata_url(request, route, rack_controller, node=None, extra=""):
    host = _get_rackcontroller_host(request, node=node)
    if host is None and rack_controller is not None:
        host = rack_controller.fqdn
    return (
        request.build_absolute_uri(route) + extra
        if not host
        else f"{request.scheme}://{host}:{RACK_CONTROLLER_PORT}{route}{extra}"
    )


def get_apt_proxy(request, rack_controller=None, node=None):
    """Return the APT proxy for the `rack_controller`."""
    config = Config.objects.get_configs(
        [
            "enable_http_proxy",
            "http_proxy",
            "use_peer_proxy",
            "maas_proxy_port",
            "maas_internal_domain",
            "use_rack_proxy",
        ]
    )
    if config["enable_http_proxy"]:
        http_proxy = config["http_proxy"]
        if http_proxy is not None:
            http_proxy = http_proxy.strip()
        use_peer_proxy = config["use_peer_proxy"]
        if http_proxy and not use_peer_proxy:
            return http_proxy
        else:
            # Ensure the proxy port is the default if not set.
            maas_proxy_port = config["maas_proxy_port"]
            if not maas_proxy_port:
                maas_proxy_port = 8000
            # Use the client requesting the preseed to determine how they
            # should access the APT proxy.
            if config["use_rack_proxy"]:
                host = _get_rackcontroller_host(request, node=node)
                if host:
                    return f"http://{host}:{maas_proxy_port}/"
            # Fallback to sending the APT directly to the
            # region controller.
            region_ip = get_default_region_ip(request)
            url = f"http://:{maas_proxy_port}/"
            return compose_URL(
                url,
                get_maas_facing_server_host(
                    rack_controller, default_region_ip=region_ip
                ),
            )
    else:
        return None


def make_clean_repo_name(repo):
    # Removeeany special characters
    repo_name = "{}_{}".format(
        repo.name.translate({ord(c): None for c in "'!@#$[]{}"}),
        repo.id,
    )
    # Create a repo name that will be used as file name for the apt list
    return repo_name.strip().replace(" ", "_").lower()


# LP: #1743966 - If the archive is resigned and has a key, then work around
# this by creating an apt_source that includes the key.
def get_cloud_init_legacy_apt_config_to_inject_key_to_archive(node):
    arch = node.split_arch()[0]
    archive = PackageRepository.objects.get_default_archive(arch)
    apt_sources = {}
    apt_sources["apt_sources"] = []

    if archive.key:
        apt_sources["apt_sources"].append(
            {
                "key": archive.key,
                "source": "deb %s $RELEASE main" % (archive.url),
                "filename": "lp1743966.list",
            }
        )

    return apt_sources


def get_archive_config(request, node, preserve_sources=False):
    arch = node.split_arch()[0]
    archive = PackageRepository.objects.get_default_archive(arch)
    repositories = PackageRepository.objects.get_additional_repositories(arch)
    apt_proxy = get_apt_proxy(request, node.get_boot_rack_controller(), node)

    # Process the default Ubuntu Archives or Mirror.
    archives = {}
    archives["apt"] = {}
    archives["apt"]["preserve_sources_list"] = preserve_sources
    # Always generate a custom list of repositories. deb-src is enabled in the
    # ephemeral environment due to the cloud-init template having it enabled.
    # It is disabled in a deployed environment due to the Curtin template
    # having it enabled.
    urls = ""
    components = set(archive.KNOWN_COMPONENTS)

    if archive.disabled_components:
        for comp in archive.COMPONENTS_TO_DISABLE:
            if comp in archive.disabled_components:
                components.remove(comp)

    urls += "deb {} $RELEASE {}\n".format(archive.url, " ".join(components))
    if archive.disable_sources:
        urls += "# "
    urls += "deb-src {} $RELEASE {}\n".format(
        archive.url, " ".join(components)
    )

    for pocket in archive.POCKETS_TO_DISABLE:
        if (
            not archive.disabled_pockets
            or pocket not in archive.disabled_pockets
        ):
            urls += "deb {} $RELEASE-{} {}\n".format(
                archive.url,
                pocket,
                " ".join(components),
            )
            if archive.disable_sources:
                urls += "# "
            urls += "deb-src {} $RELEASE-{} {}\n".format(
                archive.url,
                pocket,
                " ".join(components),
            )

    archives["apt"]["sources_list"] = urls

    if apt_proxy:
        archives["apt"]["proxy"] = apt_proxy
    if archive.key:
        archives["apt"]["sources"] = {"archive_key": {"key": archive.key}}

    # Process addtional repositories, including PPA's and custom.
    for repo in repositories:
        if repo.url.startswith("ppa:"):
            url = repo.url
        elif "ppa.launchpad.net" in repo.url:
            url = "deb %s $RELEASE main" % (repo.url)
        else:
            components = ""
            if not repo.components:
                components = "main"
            else:
                for component in repo.components:
                    components += "%s " % component
            components = components.strip()

            if not repo.distributions:
                url = f"deb {repo.url} $RELEASE {components}"
            else:
                url = ""
                for dist in repo.distributions:
                    url += f"deb {repo.url} {dist} {components}\n"

        if "sources" not in archives["apt"].keys():
            archives["apt"]["sources"] = {}

        repo_name = make_clean_repo_name(repo)

        if repo.key:
            archives["apt"]["sources"][repo_name] = {
                "key": repo.key,
                "source": url.strip(),
            }
        else:
            archives["apt"]["sources"][repo_name] = {"source": url.strip()}

    return archives


def get_enlist_archive_config(apt_proxy=None):
    default = PackageRepository.get_main_archive()
    ports = PackageRepository.get_ports_archive()
    # Process the default Ubuntu Archives or Mirror.
    archives = {
        "apt": {
            "preserve_sources_list": False,
            "primary": [
                {"arches": ["amd64", "i386"], "uri": default.url},
                {"arches": ["default"], "uri": ports.url},
            ],
            "security": [
                {"arches": ["amd64", "i386"], "uri": default.url},
                {"arches": ["default"], "uri": ports.url},
            ],
        }
    }
    if apt_proxy:
        archives["apt"]["proxy"] = apt_proxy
    if default.key:
        archives["apt"]["sources"] = {"default_key": {"key": default.key}}
    if ports.key:
        archives["apt"]["sources"] = {"ports_key": {"key": ports.key}}

    # Collect the list of all things to disable. Since we do not know the
    # architecture during enlistment if a suite or component is disabled on
    # default or ports it will be disabled on both during enlistment.
    disabled_suites = set()
    disabled_components = set()
    disable_sources = default.disable_sources or ports.disable_sources
    for repo in [default, ports]:
        disabled_suites = disabled_suites.union(repo.disabled_pockets)
        disabled_components = disabled_components.union(
            repo.disabled_components
        )

    components = " ".join(
        disabled_components.symmetric_difference(default.KNOWN_COMPONENTS)
    )
    archives["apt"]["sources_list"] = "deb $PRIMARY $RELEASE %s\n" % components
    if disable_sources:
        archives["apt"]["sources_list"] += "# "
    archives["apt"]["sources_list"] += (
        "deb-src $PRIMARY $RELEASE %s\n" % components
    )
    for suite in ["updates", "backports"]:
        if suite not in disabled_suites:
            archives["apt"][
                "sources_list"
            ] += f"deb $PRIMARY $RELEASE-{suite} {components}\n"
            if disable_sources:
                archives["apt"]["sources_list"] += "# "
            archives["apt"][
                "sources_list"
            ] += f"deb-src $PRIMARY $RELEASE-{suite} {components}\n"
    if "security" not in disabled_suites:
        archives["apt"]["sources_list"] += (
            "deb $SECURITY $RELEASE-security %s\n" % components
        )
        if disable_sources:
            archives["apt"]["sources_list"] += "# "
        archives["apt"]["sources_list"] += (
            "deb-src $SECURITY $RELEASE-security %s\n" % components
        )

    return archives


def get_cloud_init_reporting(request, node, token):
    """Return the cloud-init metadata to enable reporting"""
    route = reverse("metadata-status", args=[node.system_id])
    return {
        "reporting": {
            "maas": {
                "type": "webhook",
                "endpoint": build_metadata_url(
                    request, route, node.get_boot_rack_controller(), node=node
                ),
                "consumer_key": token.consumer.key,
                "token_key": token.key,
                "token_secret": token.secret,
            }
        }
    }


def get_snap_config(request, node):
    """Return the cloud-init snap configuration."""
    proxy = get_apt_proxy(request, node.get_boot_rack_controller(), node)
    if not proxy:
        return {}
    return {
        "snap": {
            "commands": [
                f'snap set system proxy.http="{proxy}" proxy.https="{proxy}"',
            ],
        },
    }


def get_rsyslog_host_port(request, node):
    """Return the rsyslog host and port to use."""
    configs = Config.objects.get_configs(["remote_syslog", "maas_syslog_port"])
    if configs["remote_syslog"]:
        return configs["remote_syslog"]
    else:
        port = configs["maas_syslog_port"]
        if not port:
            port = RSYSLOG_PORT
        return "%s:%d" % (node.boot_cluster_ip, port)


def get_old_archive_config():
    """Return the system info which includes the APT mirror information."""
    # Deprecated in cloud-init 0.7.8 in favor of the apt configuration format
    # generated by get_archive_config. This is still provided as old releases
    # (Precise, Trusty) have an older version of cloud-init which only reads
    # this format.
    return {
        "system_info": {
            "package_mirrors": [
                {
                    "arches": ["i386", "amd64"],
                    "search": {
                        "primary": [PackageRepository.get_main_archive().url],
                        "security": [PackageRepository.get_main_archive().url],
                    },
                    "failsafe": {
                        "primary": "http://archive.ubuntu.com/ubuntu",
                        "security": "http://security.ubuntu.com/ubuntu",
                    },
                },
                {
                    "arches": ["default"],
                    "search": {
                        "primary": [PackageRepository.get_ports_archive().url],
                        "security": [
                            PackageRepository.get_ports_archive().url
                        ],
                    },
                    "failsafe": {
                        "primary": "http://ports.ubuntu.com/ubuntu-ports",
                        "security": "http://ports.ubuntu.com/ubuntu-ports",
                    },
                },
            ]
        }
    }


def get_base_preseed(node=None):
    """Return the base preseed config used by all ephemeral environments."""
    cloud_config = {
        # The ephemeral environment doesn't have a domain search path set which
        # causes sudo to fail to resolve itself and print out a warning
        # message. These messages are caught when logging during commissioning
        # and testing. Allow /etc/hosts to be managed by cloud-init so the
        # lookup works. This may cause LP:1087183 to come back if anyone tries
        # to JuJu deploy in an ephemeral environment.
        "manage_etc_hosts": True
    }

    if node is None or node.status in COMMISSIONING_LIKE_STATUSES:
        # All other ephemeral environments use the MAAS script runner or
        # signaler to send MAAS information about process status. cloud-init
        # downloads the preseed from MAAS which contains the OAUTH keys and the
        # metadata server URL. python3-yaml is used to read the preseed and
        # python3-oauthlib is used to return the results. Both packages are
        # currently dependencies of cloud-init but are included incase those
        # dependencies are ever removed.  cloud-init is smart enough to not run
        # apt if the requested packages are already installed.
        cloud_config["packages"] = ["python3-yaml", "python3-oauthlib"]
        # On disk erasing, we need nvme-cli
        if node is not None and node.status == NODE_STATUS.DISK_ERASING:
            cloud_config["packages"] += ["nvme-cli"]

    return cloud_config


def compose_debconf_cloud_init_preseed(request, node, token):
    """Compose the preseed value for a node in any state but Commissioning.

    Returns cloud-config that's preseeded to cloud-init via debconf (It only
    configures cloud-init in Ubuntu Classic systems. Ubuntu Core does not
    have debconf as it is not Debian based.)

    Note that this was originally for systems that installed via
    debian-installer, but it is used to ensure full backwards compatibility.
    """
    credentials = urlencode(
        {
            "oauth_consumer_key": token.consumer.key,
            "oauth_token_key": token.key,
            "oauth_token_secret": token.secret,
        }
    )

    config = get_base_preseed(node)
    config.update(
        {
            # Prevent the node from requesting cloud-init data on every reboot.
            # This is done so a machine does not need to contact MAAS every time
            # it reboots.
            "manual_cache_clean": True
        }
    )
    # This is used as preseed for a node that's been installed.
    # This will allow cloud-init to be configured with reporting for
    # a node that has already been installed.
    config.update(get_cloud_init_reporting(request, node, token))

    local_config_yaml = yaml.safe_dump(config)
    # this is debconf escaping
    local_config = local_config_yaml.replace("\\", "\\\\").replace("\n", "\\n")

    route = reverse("metadata")

    # Preseed data to send to cloud-init.  We set this as MAAS_PRESEED in
    # ks_meta, and it gets fed straight into debconf.
    preseed_items = [
        ("datasources", "multiselect", "MAAS"),
        (
            "maas-metadata-url",
            "string",
            build_metadata_url(
                request, route, node.get_boot_rack_controller(), node=node
            ),
        ),
        ("maas-metadata-credentials", "string", credentials),
        ("local-cloud-config", "string", local_config),
    ]

    return "\n".join(
        "cloud-init   cloud-init/%s  %s %s"
        % (item_name, item_type, item_value)
        for item_name, item_type, item_value in preseed_items
    )


def compose_commissioning_preseed(request, node, token):
    """Compose the preseed value for a Commissioning node."""
    route = reverse("metadata")
    metadata_url = build_metadata_url(
        request, route, node.get_boot_rack_controller(), node=node
    )
    if node.status == NODE_STATUS.DISK_ERASING:
        poweroff_timeout = timedelta(days=7).total_seconds()  # 1 week
    else:
        poweroff_timeout = timedelta(hours=1).total_seconds()  # 1 hour
    return _compose_cloud_init_preseed(
        request,
        node,
        token,
        metadata_url,
        poweroff_timeout=int(poweroff_timeout),
    )


def compose_curtin_preseed(request, node, token):
    """Compose the preseed value for a node being installed with curtin."""
    route = reverse("curtin-metadata")
    metadata_url = build_metadata_url(
        request, route, node.get_boot_rack_controller(), node=node
    )
    return _compose_cloud_init_preseed(request, node, token, metadata_url)


def _compose_cloud_init_preseed(
    request,
    node,
    token,
    metadata_url,
    poweroff_timeout=3600,
    reboot_timeout=1800,
):
    cloud_config = get_base_preseed(node)
    cloud_config.update(
        {
            "datasource": {
                "MAAS": {
                    "metadata_url": metadata_url,
                    "consumer_key": token.consumer.key,
                    "token_key": token.key,
                    "token_secret": token.secret,
                }
            },
            # This configure rsyslog for the ephemeral environment
            "rsyslog": {
                "remotes": {"maas": get_rsyslog_host_port(request, node)}
            },
        }
    )
    # This configures reporting for the ephemeral environment
    cloud_config.update(get_cloud_init_reporting(request, node, token))
    # Add legacy APT configuration for cloud-init in case the ephemeral
    # is an older version of maas. Since precise is now deployed using
    # the commissioning enviroment (which will either be Xenial or Bionic)
    # then we only need the legacy config for trusty.
    if node.distro_series == "trusty":
        cloud_config.update(get_old_archive_config())
        # apt_proxy is deprecated in the cloud-init source code in favor of
        # what get_archive_config does.
        apt_proxy = get_apt_proxy(
            request, node.get_boot_rack_controller(), node
        )
        if apt_proxy:
            cloud_config["apt_proxy"] = apt_proxy
        # LP: #1743966 - If a custom archive is being used with a custom key,
        # create a work around to inject it in legacy format.
        cloud_config.update(
            get_cloud_init_legacy_apt_config_to_inject_key_to_archive(node)
        )
    # Add APT configuration for new cloud-init (>= 0.7.7-17)
    cloud_config.update(
        get_archive_config(request, node, preserve_sources=False)
    )
    # Add snaps configuration
    cloud_config.update(get_snap_config(request, node))

    enable_ssh = (
        node.status in {NODE_STATUS.COMMISSIONING, NODE_STATUS.TESTING}
        and node.enable_ssh
    )
    if (
        node.status != NODE_STATUS.ENTERING_RESCUE_MODE
        and not enable_ssh
        and not node.ephemeral_deploy
    ):
        testing_reboot = False
        if node.status == NODE_STATUS.TESTING:
            script_set = node.current_testing_script_set
            if script_set.power_state_before_transition == POWER_STATE.ON:
                testing_reboot = True
        if node.status == NODE_STATUS.DEPLOYING or testing_reboot:
            cloud_config["power_state"] = {
                "delay": "now",
                "mode": "reboot",
                "timeout": reboot_timeout,
                "condition": "test ! -e /tmp/block-reboot",
            }
        else:
            cloud_config["power_state"] = {
                "delay": "now",
                "mode": "poweroff",
                "timeout": poweroff_timeout,
                "condition": "test ! -e /tmp/block-poweroff",
            }

    return "#cloud-config\n%s" % yaml.safe_dump(cloud_config)


def _get_metadata_url(request, preseed_type, node):
    route = reverse("metadata")
    if preseed_type == PRESEED_TYPE.CURTIN:
        route = reverse("curtin-metadata")
    return build_metadata_url(
        request, route, node.get_boot_rack_controller(), node=node
    )


def compose_preseed(request, preseed_type, node):
    """Put together preseed data for `node`.

    This produces preseed data for the node in different formats depending
    on the preseed_type.

    :param preseed_type: The type of preseed to compose.
    :type preseed_type: string
    :param node: The node to compose preseed data for.
    :type node: Node
    :return: Preseed data containing the information the node needs in order
        to access the metadata service: its URL and auth token.
    """
    from maasserver.models import NodeKey

    token = NodeKey.objects.get_token_for_node(node)
    if preseed_type == PRESEED_TYPE.COMMISSIONING:
        return compose_commissioning_preseed(request, node, token)
    else:
        metadata_url = _get_metadata_url(request, preseed_type, node)
        try:
            return get_preseed_data(preseed_type, node, token, metadata_url)
        except NotImplementedError:
            # This is fine; it indicates that the OS does not specify
            # any special preseed data for this type of preseed.
            pass
        except NoSuchOperatingSystem:
            # Let a caller handle this. If rendered for presentation in the
            # UI, an explanatory error message could be displayed. If rendered
            # via the API, in response to cloud-init for example, the prudent
            # course of action might be to turn the node's power off, mark it
            # as broken, and notify the user.
            raise
        except NoConnectionsAvailable:
            # This means that the region is not in contact with the node's
            # cluster controller. In the UI this could be shown as an error
            # message. This is, however, a show-stopping problem when booting
            # or installing a node. A caller cannot turn the node's power off
            # via the usual methods because they rely on a connection to the
            # cluster. This /could/ generate a preseed that aborts the boot or
            # installation. The caller /could/ mark the node as broken. For
            # now, let the caller make the decision, which might be to retry.
            raise

        # There is no OS-specific preseed data.
        if preseed_type == PRESEED_TYPE.CURTIN:
            return compose_curtin_preseed(request, node, token)
        else:
            return compose_debconf_cloud_init_preseed(request, node, token)


def compose_enlistment_preseed(request, rack_controller, context):
    """Put together preseed data for a new `node` being enlisted.

    :param rack_controller: The RackController the request came from.
    :param context: The output of get_preseed_context
    :return: Preseed data containing the information the node needs in order
        to access the metadata service: its URL and auth token.
    """
    cloud_config = get_base_preseed()
    route = reverse("metadata")
    cloud_config.update(
        {
            "datasource": {
                "MAAS": {
                    "metadata_url": build_metadata_url(
                        request, route, rack_controller
                    ),
                },
            },
            "rsyslog": {"remotes": {"maas": context["syslog_host_port"]}},
            "power_state": {
                "delay": "now",
                "mode": "poweroff",
                "timeout": 1800,
                "condition": "test ! -e /tmp/block-poweroff",
            },
            **get_enlist_archive_config(
                get_apt_proxy(request, rack_controller)
            ),
        }
    )

    return "#cloud-config\n%s" % yaml.safe_dump(cloud_config)
