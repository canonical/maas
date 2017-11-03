# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Low-level composition code for preseeds."""

__all__ = [
    'compose_preseed',
    ]

from datetime import timedelta
from urllib.parse import urlencode

from maasserver.clusterrpc.osystems import get_preseed_data
from maasserver.enum import (
    NODE_STATUS,
    POWER_STATE,
    PRESEED_TYPE,
)
from maasserver.models import PackageRepository
from maasserver.models.config import Config
from maasserver.server_address import get_maas_facing_server_host
from maasserver.utils import absolute_reverse
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    NoSuchOperatingSystem,
)
from provisioningserver.utils.url import compose_URL
import yaml

# Default port for RSYSLOG
RSYSLOG_PORT = 514


def get_apt_proxy(rack_controller=None, default_region_ip=None):
    """Return the APT proxy for the `rack_controller`."""
    if Config.objects.get_config("enable_http_proxy"):
        http_proxy = Config.objects.get_config("http_proxy")
        if http_proxy is not None:
            http_proxy = http_proxy.strip()
        use_peer_proxy = Config.objects.get_config("use_peer_proxy")
        if http_proxy and not use_peer_proxy:
            return http_proxy
        else:
            return compose_URL(
                "http://:8000/", get_maas_facing_server_host(
                    rack_controller, default_region_ip=default_region_ip))
    else:
        return None


def make_clean_repo_name(repo):
    # Removeeany special characters
    repo_name = "%s_%s" % (
        repo.name.translate({ord(c): None for c in '\'!@#$[]{}'}), repo.id)
    # Create a repo name that will be used as file name for the apt list
    return repo_name.strip().replace(' ', '_').lower()


def get_archive_config(node, preserve_sources=False, default_region_ip=None):
    arch = node.split_arch()[0]
    archive = PackageRepository.objects.get_default_archive(arch)
    repositories = PackageRepository.objects.get_additional_repositories(arch)
    apt_proxy = get_apt_proxy(
        node.get_boot_rack_controller(), default_region_ip=default_region_ip)

    # Process the default Ubuntu Archives or Mirror.
    archives = {}
    archives['apt'] = {}
    archives['apt']['preserve_sources_list'] = preserve_sources
    # If disabled_components exist, build a custom list of repositories
    if archive.disabled_components:
        urls = ''
        components = archive.KNOWN_COMPONENTS[:]

        for comp in archive.COMPONENTS_TO_DISABLE:
            if comp in archive.disabled_components:
                components.remove(comp)
        urls += 'deb %s $RELEASE %s\n' % (
            archive.url, ' '.join(components))

        for pocket in archive.POCKETS_TO_DISABLE:
            if pocket not in archive.disabled_pockets:
                urls += 'deb %s $RELEASE-%s %s\n' % (
                    archive.url, pocket, ' '.join(components))

        archives['apt']['sources_list'] = urls
    else:
        archives['apt']['primary'] = [
            {
                'arches': ['default'],
                'uri': archive.url
            }
        ]
        archives['apt']['security'] = [
            {
                'arches': ['default'],
                'uri': archive.url
            }
        ]
        if archive.disabled_pockets:
            archives['apt']['disable_suites'] = archive.disabled_pockets
    if apt_proxy:
        archives['apt']['proxy'] = apt_proxy
    if archive.key:
        archives['apt']['sources'] = {
            'archive_key': {
                'key': archive.key
            }
        }

    # Process addtional repositories, including PPA's and custom.
    for repo in repositories:
        if repo.url.startswith('ppa:'):
            url = repo.url
        elif 'ppa.launchpad.net' in repo.url:
            url = 'deb %s $RELEASE main' % (repo.url)
        else:
            components = ''
            if not repo.components:
                components = 'main'
            else:
                for component in repo.components:
                    components += '%s ' % component
            components = components.strip()

            if not repo.distributions:
                url = 'deb %s $RELEASE %s' % (
                    repo.url, components)
            else:
                url = ''
                for dist in repo.distributions:
                    url += 'deb %s %s %s\n' % (repo.url, dist, components)

        if 'sources' not in archives['apt'].keys():
            archives['apt']['sources'] = {}

        repo_name = make_clean_repo_name(repo)

        if repo.key:
            archives['apt']['sources'][repo_name] = {
                'key': repo.key,
                'source': url.strip()
            }
        else:
            archives['apt']['sources'][repo_name] = {
                'source': url.strip()
            }

    return archives


def get_cloud_init_reporting(node, token, base_url, default_region_ip=None):
    """Return the cloud-init metadata to enable reporting"""
    return {
        'reporting': {
            'maas': {
                'type': 'webhook',
                'endpoint': absolute_reverse(
                    'metadata-status', default_region_ip=default_region_ip,
                    args=[node.system_id], base_url=base_url),
                'consumer_key': token.consumer.key,
                'token_key': token.key,
                'token_secret': token.secret,
            }
        }
    }


def get_rsyslog_host_port(node, default_region_ip=None):
    """Return the rsyslog host and port to use."""
    host = get_maas_facing_server_host(
        node.get_boot_rack_controller(), default_region_ip=default_region_ip)
    return "%s:%d" % (host, RSYSLOG_PORT)


def get_system_info():
    """Return the system info which includes the APT mirror information."""
    return {
        "system_info": {
            "package_mirrors": [
                {
                    "arches": ["i386", "amd64"],
                    "search": {
                        "primary": [
                            PackageRepository.get_main_archive().url],
                        "security": [
                            PackageRepository.get_main_archive().url],
                    },
                    "failsafe": {
                        "primary": "http://archive.ubuntu.com/ubuntu",
                        "security": "http://security.ubuntu.com/ubuntu",
                    }
                },
                {
                    "arches": ["default"],
                    "search": {
                        "primary": [
                            PackageRepository.get_ports_archive().url],
                        "security": [
                            PackageRepository.get_ports_archive().url],
                    },
                    "failsafe": {
                        "primary": "http://ports.ubuntu.com/ubuntu-ports",
                        "security": "http://ports.ubuntu.com/ubuntu-ports",
                    }
                },
            ]
        }
    }


def compose_cloud_init_preseed(
        node, token, base_url='', default_region_ip=None):
    """Compose the preseed value for a node in any state but Commissioning.

    Returns cloud-config that's preseeded to cloud-init via debconf (It only
    configures cloud-init in Ubuntu Classic systems. Ubuntu Core does not
    have debconf as it is not Debian based.
    """
    credentials = urlencode({
        'oauth_consumer_key': token.consumer.key,
        'oauth_token_key': token.key,
        'oauth_token_secret': token.secret,
        })

    config = {
        # Do not let cloud-init override /etc/hosts/: use the default
        # behavior which means running `dns_resolve(hostname)` on a node
        # will query the DNS server (and not return 127.0.0.1).
        # See bug 1087183 for details.
        "manage_etc_hosts": False,
        "apt_preserve_sources_list": True,
        # Prevent the node from requesting cloud-init data on every reboot.
        # This is done so a machine does not need to contact MAAS every time
        # it reboots.
        "manual_cache_clean": True,
    }
    # This is used as preseed for a node that's been installed.
    # This will allow cloud-init to be configured with reporting for
    # a node that has already been installed.
    config.update(
        get_cloud_init_reporting(
            node=node, token=token, base_url=base_url,
            default_region_ip=default_region_ip))
    # Add the system configuration information.
    config.update(get_system_info())
    apt_proxy = get_apt_proxy(
        node.get_boot_rack_controller(), default_region_ip=default_region_ip)
    if apt_proxy:
        config['apt_proxy'] = apt_proxy
    # Add APT configuration for new cloud-init (>= 0.7.7-17)
    config.update(
        get_archive_config(
            node=node, preserve_sources=False,
            default_region_ip=default_region_ip))

    local_config_yaml = yaml.safe_dump(config)
    # this is debconf escaping
    local_config = local_config_yaml.replace("\\", "\\\\").replace("\n", "\\n")

    # Preseed data to send to cloud-init.  We set this as MAAS_PRESEED in
    # ks_meta, and it gets fed straight into debconf.
    preseed_items = [
        ('datasources', 'multiselect', 'MAAS'),
        ('maas-metadata-url', 'string', absolute_reverse(
            'metadata', default_region_ip=default_region_ip,
            base_url=base_url)),
        ('maas-metadata-credentials', 'string', credentials),
        ('local-cloud-config', 'string', local_config)
        ]

    return '\n'.join(
        "cloud-init   cloud-init/%s  %s %s" % (
            item_name,
            item_type,
            item_value,
            )
        for item_name, item_type, item_value in preseed_items)


def compose_commissioning_preseed(
        node, token, base_url='', default_region_ip=None):
    """Compose the preseed value for a Commissioning node."""
    metadata_url = absolute_reverse(
        'metadata', default_region_ip=default_region_ip, base_url=base_url)
    if node.status == NODE_STATUS.DISK_ERASING:
        poweroff_timeout = timedelta(days=7).total_seconds()  # 1 week
    else:
        poweroff_timeout = timedelta(hours=1).total_seconds()  # 1 hour
    return _compose_cloud_init_preseed(
        node, token, metadata_url, base_url=base_url,
        poweroff_timeout=int(poweroff_timeout),
        default_region_ip=default_region_ip)


def compose_curtin_preseed(node, token, base_url='', default_region_ip=None):
    """Compose the preseed value for a node being installed with curtin."""
    metadata_url = absolute_reverse(
        'curtin-metadata', default_region_ip=default_region_ip,
        base_url=base_url)
    return _compose_cloud_init_preseed(
        node, token, metadata_url, base_url=base_url,
        default_region_ip=default_region_ip)


def _compose_cloud_init_preseed(
        node, token, metadata_url, base_url, poweroff_timeout=3600,
        reboot_timeout=1800, default_region_ip=None):
    cloud_config = {
        'datasource': {
            'MAAS': {
                'metadata_url': metadata_url,
                'consumer_key': token.consumer.key,
                'token_key': token.key,
                'token_secret': token.secret,
            }
        },
        # This configure rsyslog for the ephemeral environment
        'rsyslog': {
            'remotes': {
                'maas': get_rsyslog_host_port(
                    node, default_region_ip=default_region_ip),
            }
        },
        # The ephemeral environment doesn't have a domain search path set which
        # cases sudo to fail to resolve itself and print out a warning message.
        # These messages are caught when logging during commissioning and
        # testing. Allow /etc/hosts to be managed by cloud-init so the lookup
        # works. This may cause 1087183 to come back if anyone tries to JuJu
        # deploy in an ephemeral environment.
        'manage_etc_hosts': True,
    }
    # This configures reporting for the ephemeral environment
    cloud_config.update(
        get_cloud_init_reporting(
            node=node, token=token, base_url=base_url,
            default_region_ip=default_region_ip))
    # Add the system configuration information.
    cloud_config.update(get_system_info())
    apt_proxy = get_apt_proxy(
        node.get_boot_rack_controller(), default_region_ip=default_region_ip)
    if apt_proxy:
        cloud_config['apt_proxy'] = apt_proxy
    # Add APT configuration for new cloud-init (>= 0.7.7-17)
    cloud_config.update(get_archive_config(
        node=node, preserve_sources=False,
        default_region_ip=default_region_ip))

    enable_ssh = (node.status in {
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.TESTING,
        } and node.enable_ssh)
    if node.status != NODE_STATUS.ENTERING_RESCUE_MODE and not enable_ssh:
        testing_reboot = False
        if node.status == NODE_STATUS.TESTING:
            script_set = node.current_testing_script_set
            if script_set.power_state_before_transition == POWER_STATE.ON:
                testing_reboot = True
        if node.status == NODE_STATUS.DEPLOYING or testing_reboot:
            cloud_config['power_state'] = {
                'delay': 'now',
                'mode': 'reboot',
                'timeout': reboot_timeout,
                'condition': 'test ! -e /tmp/block-reboot',
            }
        else:
            cloud_config['power_state'] = {
                'delay': 'now',
                'mode': 'poweroff',
                'timeout': poweroff_timeout,
                'condition': 'test ! -e /tmp/block-poweroff',
            }

    return "#cloud-config\n%s" % yaml.safe_dump(cloud_config)


def _get_metadata_url(preseed_type, base_url, default_region_ip=None):
    if preseed_type == PRESEED_TYPE.CURTIN:
        return absolute_reverse(
            'curtin-metadata', default_region_ip=default_region_ip,
            base_url=base_url)
    else:
        return absolute_reverse(
            'metadata', default_region_ip=default_region_ip, base_url=base_url)


def compose_preseed(preseed_type, node, default_region_ip=None):
    """Put together preseed data for `node`.

    This produces preseed data for the node in different formats depending
    on the preseed_type.

    :param preseed_type: The type of preseed to compose.
    :type preseed_type: string
    :param node: The node to compose preseed data for.
    :type node: Node
    :param default_region_ip: The default IP address to use for the region
        controller (for example, when constructing URLs).
    :return: Preseed data containing the information the node needs in order
        to access the metadata service: its URL and auth token.
    """
    # Circular import.
    from metadataserver.models import NodeKey

    token = NodeKey.objects.get_token_for_node(node)
    rack_controller = node.get_boot_rack_controller()
    base_url = rack_controller.url

    if preseed_type == PRESEED_TYPE.COMMISSIONING:
        return compose_commissioning_preseed(
            node, token, base_url, default_region_ip=default_region_ip)
    else:
        metadata_url = _get_metadata_url(
            preseed_type, base_url, default_region_ip=default_region_ip)

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
            return compose_curtin_preseed(
                node, token, base_url, default_region_ip=default_region_ip)
        else:
            return compose_cloud_init_preseed(
                node, token, base_url, default_region_ip=default_region_ip)
