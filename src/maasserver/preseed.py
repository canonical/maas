# Copyright 2012-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preseed generation."""

__all__ = [
    'CURTIN_INSTALL_LOG',
    'compose_enlistment_preseed_url',
    'compose_preseed_url',
    'curtin_supports_webhook_events',
    'get_curtin_userdata',
    'get_enlist_preseed',
    'get_preseed',
    'get_preseed_context',
    'OS_WITH_IPv6_SUPPORT',
    ]

from collections import namedtuple
import json
import os.path
from pipes import quote
from urllib.parse import (
    urlencode,
    urlparse,
)

from crochet import TimeoutError
from curtin.config import merge_config
from curtin.pack import pack_install
from django.conf import settings
from maasserver import logger
from maasserver.clusterrpc.boot_images import get_boot_images_for
from maasserver.compose_preseed import (
    compose_cloud_init_preseed,
    compose_preseed,
    get_apt_proxy,
    get_archive_config,
    get_cloud_init_reporting,
    get_system_info,
    RSYSLOG_PORT,
)
from maasserver.enum import (
    FILESYSTEM_TYPE,
    PRESEED_TYPE,
    USERDATA_TYPE,
)
from maasserver.exceptions import (
    ClusterUnavailable,
    MissingBootImage,
)
from maasserver.models import (
    BootResource,
    Config,
    PackageRepository,
)
from maasserver.models.filesystem import Filesystem
from maasserver.node_status import COMMISSIONING_LIKE_STATUSES
from maasserver.preseed_network import compose_curtin_network_config
from maasserver.preseed_storage import compose_curtin_storage_config
from maasserver.server_address import get_maas_facing_server_host
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils import absolute_reverse
from maasserver.utils.curtin import (
    curtin_supports_custom_storage,
    curtin_supports_custom_storage_for_dd,
    curtin_supports_webhook_events,
)
from metadataserver.models import NodeKey
from metadataserver.user_data.snippets import get_snippet_context
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.logger import (
    get_maas_logger,
    LegacyLogger,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils import typed
from provisioningserver.utils.url import compose_URL
import tempita
import yaml


maaslog = get_maas_logger("preseed")

log = LegacyLogger()

GENERIC_FILENAME = 'generic'


# Node operating systems which we can deploy with IPv6 networking.
OS_WITH_IPv6_SUPPORT = ['ubuntu']


# The path to the Curtin installation log. Curtin uploads this file to MAAS
# with its full path once the deployment is finished.
CURTIN_INSTALL_LOG = "/tmp/install.log"


def get_enlist_preseed(rack_controller=None, default_region_ip=None):
    """Return the enlistment preseed.

    :param rack_controller: The rack controller used to generate the preseed.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    return render_enlistment_preseed(
        PRESEED_TYPE.ENLIST, rack_controller=rack_controller,
        default_region_ip=default_region_ip)


def get_enlist_userdata(rack_controller=None, default_region_ip=None):
    """Return the enlistment preseed.

    :param rack_controller: The rack controller used to generate the preseed.
    :return: The rendered enlistment user-data string.
    :rtype: unicode.
    """
    http_proxy = get_apt_proxy(
        rack_controller=rack_controller, default_region_ip=default_region_ip)
    enlist_userdata = render_enlistment_preseed(
        USERDATA_TYPE.ENLIST, rack_controller=rack_controller)
    config = get_system_info()
    config.update({'apt_proxy': http_proxy})
    config.update(get_enlist_archive_config(http_proxy))
    return enlist_userdata + yaml.safe_dump(config).encode('utf-8')


def get_enlist_archive_config(apt_proxy=None):
    default = PackageRepository.get_main_archive()
    ports = PackageRepository.get_ports_archive()
    # Process the default Ubuntu Archives or Mirror.
    archives = {
        'apt': {
            'preserve_sources_list': False,
            'primary': [
                {
                    'arches': ['amd64', 'i386'],
                    'uri': default.url
                },
                {
                    'arches': ['default'],
                    'uri': ports.url
                },
            ],
            'security': [
                {
                    'arches': ['amd64', 'i386'],
                    'uri': default.url
                },
                {
                    'arches': ['default'],
                    'uri': ports.url
                },
            ],
        },
    }
    if apt_proxy:
        archives['apt']['proxy'] = apt_proxy
    if default.key:
        archives['apt']['sources'] = {
            'default_key': {
                'key': default.key
            }
        }
    if ports.key:
        archives['apt']['sources'] = {
            'ports_key': {
                'key': ports.key
            }
        }

    return archives


def curtin_maas_reporter(node, events_support=True):
    token = NodeKey.objects.get_token_for_node(node)
    rack_controller = node.get_boot_rack_controller()
    base_url = rack_controller.url
    if events_support:
        return {
            'reporting': {
                'maas': {
                    'type': 'webhook',
                    'endpoint': absolute_reverse(
                        'metadata-status', args=[node.system_id],
                        base_url=base_url),
                    'consumer_key': token.consumer.key,
                    'token_key': token.key,
                    'token_secret': token.secret,
                },
            },
            'install': {
                'log_file': CURTIN_INSTALL_LOG,
                'post_files': [CURTIN_INSTALL_LOG]
            }
        }
    else:
        version = 'latest'
        return {
            'reporter': {
                'maas': {
                    'url': absolute_reverse(
                        'curtin-metadata-version', args=[version],
                        query={'op': 'signal'}, base_url=base_url),
                    'consumer_key': token.consumer.key,
                    'token_key': token.key,
                    'token_secret': token.secret,
                }
            }
        }


def compose_curtin_maas_reporter(node):
    """Return a list of curtin preseeds for using the MAASReporter in curtin.

    This enables the ability for curtin to talk back to MAAS through a backend
    that matches what the locally installed Curtin uses.
    """
    reporter = curtin_maas_reporter(node, curtin_supports_webhook_events())
    return [yaml.safe_dump(reporter)]


def get_curtin_cloud_config(node):
    """Compose the curtin cloud-config, which is only applied to
       Ubuntu core (by curtin)."""
    token = NodeKey.objects.get_token_for_node(node)
    rack_controller = node.get_boot_rack_controller()
    base_url = rack_controller.url
    datasource = {
        'datasource': {
            'MAAS': {
                'consumer_key': token.consumer.key,
                'token_key': token.key,
                'token_secret': token.secret,
                'metadata_url': absolute_reverse(
                    'metadata', base_url=base_url),
            }
        }
    }
    config = {
        'maas-datasource': {
            'path': '/etc/cloud/cloud.cfg.d/90_maas_datasource.cfg',
            'content': 'datasource_list: [ MAAS ]',
        },
        'maas-cloud-config': {
            'path': '/etc/cloud/cloud.cfg.d/90_maas_cloud_config.cfg',
            'content': "#cloud-config\n%s" % yaml.safe_dump(datasource)
        },
    }
    # Add the Ubuntu SSO email if its set on the user.
    if node.owner is not None and node.owner.email:
        config['maas-ubuntu-sso'] = {
            'path': '/etc/cloud/cloud.cfg.d/90_maas_ubuntu_sso.cfg',
            'content': "#cloud-config\n%s" % yaml.safe_dump({
                'snappy': {
                    'email': node.owner.email
                }
            })
        }
    config['maas-reporting'] = {
        'path': '/etc/cloud/cloud.cfg.d/90_maas_cloud_init_reporting.cfg',
        'content': '#cloud-config\n%s' % yaml.safe_dump(
            get_cloud_init_reporting(
                node=node, token=token, base_url=base_url))
    }
    return {
        'cloudconfig': config
    }


def compose_curtin_cloud_config(node):
    config = get_curtin_cloud_config(node)
    return [yaml.safe_dump(config)]


def compose_curtin_archive_config(node):
    """Return the curtin preseed for configuring a node's apt sources.

    If a node's deployed OS is Ubuntu (or a Custom Ubuntu), we pass this
    configuration along, provided that repositories are only available
    for Ubuntu.
    """
    if node.osystem in ['ubuntu', 'custom']:
        archives = get_archive_config(node)
        return [yaml.safe_dump(archives)]
    return []


def compose_curtin_swap_preseed(node):
    """Return the curtin preseed for configuring a node's swap space.

    These can then be appended to the main Curtin configuration.  The preseeds
    are returned as a list of strings, each holding a YAML section.

    If a node's swap space is unconfigured but swap has been configured on a
    block device or partition, this will suppress the creation of a swap file.
    """
    if node.swap_size is None:
        swap_filesystems = (
            Filesystem.objects.filter_by_node(node).filter(
                fstype=FILESYSTEM_TYPE.SWAP))
        if swap_filesystems.exists():
            # Suppress creation of a swap file.
            swap_config = {'swap': {'size': '0B'}}
            return [yaml.safe_dump(swap_config)]
        else:
            # Leave the decision up to Curtin.
            return []
    else:
        # Make a swap file of `swap_size` bytes.
        swap_config = {'swap': {'size': '%dB' % node.swap_size}}
        return [yaml.safe_dump(swap_config)]


def compose_curtin_kernel_preseed(node):
    """Return the curtin preseed for installing a kernel other than default.

    The BootResourceFile table contains a mapping between hwe kernels and
    Ubuntu package names. If this mapping is missing we fall back to letting
    Curtin figure out which kernel should be installed"""
    kpackage = BootResource.objects.get_kpackage_for_node(node)
    if kpackage:
        kernel_config = {
            'kernel': {
                'package': kpackage,
                'mapping': {},
                },
            }
        return [yaml.safe_dump(kernel_config)]
    return []


def compose_curtin_verbose_preseed():
    """Return the curtin options for the preseed that will tell curtin
    to run with high verbosity.
    """
    if Config.objects.get_config("curtin_verbose"):
        return [yaml.safe_dump({
            "verbosity": 3,
            "showtrace": True,
            })]
    else:
        return []


def get_curtin_yaml_config(node, default_region_ip=None):
    """Return the curtin configration for the node."""
    main_config = get_curtin_config(node)
    cloud_config = compose_curtin_cloud_config(node)
    archive_config = compose_curtin_archive_config(node)
    reporter_config = compose_curtin_maas_reporter(node)
    swap_config = compose_curtin_swap_preseed(node)
    kernel_config = compose_curtin_kernel_preseed(node)
    verbose_config = compose_curtin_verbose_preseed()

    supports_custom_storage = True
    # Get the storage configration if curtin supports custom storage.
    if not curtin_supports_custom_storage():
        maaslog.error(
            "%s: cannot deploy with custom storage config; missing support "
            "from curtin." % node.hostname)
        supports_custom_storage = False

    network_config = compose_curtin_network_config(node)

    if node.osystem != "ubuntu":
        maaslog.info(
            "%s: custom storage options are only supported on "
            "Ubuntu. Using flat storage layout."
            % node.hostname)
        supports_custom_storage = False
        if (node.osystem == "windows" and
           curtin_supports_custom_storage_for_dd()):
            # Windows does not support custom storage, however we still pass
            # the storage config to ensure that curtin correctly selects the
            # boot device as the root device.
            #
            # This also requires curtin support. See (LP:1640301).
            supports_custom_storage = True

    if node.osystem == "custom":
        maaslog.info(
            "%s: deploying custom image '%s' with custom networking options. "
            "Please verify that this image supports custom network "
            "configuration." % (node.hostname, node.distro_series))

    if supports_custom_storage:
        storage_config = compose_curtin_storage_config(node)
    else:
        storage_config = []

    return (
        storage_config + [main_config] + archive_config + reporter_config +
        network_config + swap_config + kernel_config + verbose_config +
        cloud_config)


def get_curtin_merged_config(node):
    """Return the merged curtin configuration for the node."""
    yaml_config = get_curtin_yaml_config(node)
    config = {}
    for cfg in yaml_config:
        merge_config(config, yaml.safe_load(cfg))
    return config


def get_curtin_userdata(node, default_region_ip=None):
    """Return the curtin user-data.

    :param node: The node for which to generate the user-data.
    :return: The rendered user-data string.
    :rtype: unicode.
    """
    # Pack the curtin and the configuration into a script to execute on the
    # deploying node.
    return pack_install(
        configs=get_curtin_yaml_config(node, default_region_ip),
        args=[get_curtin_installer_url(node)])


def get_curtin_image(node):
    """Return boot image that supports 'xinstall' for the given node."""
    osystem = node.get_osystem()
    series = node.get_distro_series()
    arch, subarch = node.split_arch()
    rack_controller = node.get_boot_rack_controller()
    try:
        images = get_boot_images_for(
            rack_controller, osystem, arch, subarch, series)
    except (NoConnectionsAvailable, TimeoutError):
        logger.error(
            "Unable to get RPC connection for rack controller '%s' (%s)",
            rack_controller.hostname, rack_controller.system_id)
        raise ClusterUnavailable(
            "Unable to get RPC connection for rack controller '%s' (%s)" %
            (rack_controller.hostname, rack_controller.system_id))
    for image in images:
        if image['purpose'] == 'xinstall':
            return image
    raise MissingBootImage(
        "Error generating the URL of curtin's image file.  "
        "No image could be found for the given selection: "
        "os=%s, arch=%s, subarch=%s, series=%s, purpose=xinstall." % (
            osystem,
            arch,
            subarch,
            series,
        ))


def get_curtin_installer_url(node):
    """Return the URL where curtin on the node can download its installer."""
    osystem = node.get_osystem()
    series = node.get_distro_series()
    arch, subarch = node.architecture.split('/')
    # XXX rvb(?): The path shouldn't be hardcoded like this, but rather synced
    # somehow with the content of contrib/maas-cluster-http.conf.
    # Per etc/services cluster is opening port 5248 to serve images via HTTP
    image = get_curtin_image(node)
    if image['xinstall_type'] == 'squashfs':
        # XXX: roaksoax LP: #1739761 - Since the switch to squashfs (and drop
        # of iscsi), precise is no longer deployable. To address a squashfs
        # image is made available allowing it to be deployed in the
        # commissioning ephemeral environment.
        if series == 'precise':
            url_prepend = "fsimage:"
        else:
            return 'cp:///media/root-ro'
    elif image['xinstall_type'] == 'tgz':
        url_prepend = ''
    else:
        url_prepend = '%s:' % image['xinstall_type']
    dyn_uri = '/'.join([
        osystem,
        arch,
        subarch,
        series,
        image['label'],
        image['xinstall_path'],
        ])
    url = compose_URL(
        'http://:5248/images/%s' % dyn_uri, str(node.boot_cluster_ip))
    return url_prepend + url


def get_curtin_config(node, default_region_ip=None):
    """Return the curtin configuration to be used by curtin.pack_install.

    :param node: The node for which to generate the configuration.
    :rtype: unicode.
    """
    osystem = node.get_osystem()
    series = node.get_distro_series()
    template = load_preseed_template(
        node, USERDATA_TYPE.CURTIN, osystem, series)
    rack_controller = node.get_boot_rack_controller()
    context = get_preseed_context(
        osystem, series, rack_controller=rack_controller,
        default_region_ip=default_region_ip)
    context.update(
        get_node_preseed_context(
            node, osystem, series, rack_controller=rack_controller,
            default_region_ip=default_region_ip))
    context.update(
        get_curtin_context(
            node, rack_controller=rack_controller,
            default_region_ip=default_region_ip))
    deprecated_context_variables = [
        'main_archive_hostname', 'main_archive_directory',
        'ports_archive_hostname', 'ports_archive_directory',
        'enable_http_proxy', 'http_proxy']
    deprecated_config_variables = []
    for var in deprecated_context_variables:
        if var not in context:
            deprecated_context_variables.remove(var)
    context.update(get_node_deprecated_preseed_context())
    config = yaml.safe_load(template.substitute(**context))
    # Remove deprecated config from the curtin preseed.
    if 'power_state' in config:
        del config['power_state']
        deprecated_config_variables.append('power_state')
    if 'apt_proxy' in config:
        deprecated_config_variables.append('apt_proxy')
        del config['apt_proxy']
    if 'apt_mirrors' in config:
        deprecated_config_variables.append('apt_mirrors')
        del config['apt_mirrors']
    if deprecated_context_variables:
        log.warn(
            "WARNING: '%s' contains deprecated preseed "
            "variables. Please remove: %s" % (
                template.name, ", ".join(deprecated_context_variables)))
    if deprecated_config_variables:
        log.warn(
            "WARNING: '%s' contains deprecated preseed "
            "configuration. Please remove: %s" % (
                template.name, ", ".join(deprecated_config_variables)))
    # Precise does not support cloud-init performing the reboot, so curtin
    # must have this statement.
    if node.distro_series == "precise":
        config['power_state'] = {'mode': 'reboot'}
    # Ensure we always set debconf_selections for grub to ensure it doesn't
    # overwrite the config sent by MAAS. See LP: #1642298
    grub2_debconf = {'grub2': 'grub2   grub2/update_nvram  boolean false'}
    if 'debconf_selections' in config:
        config['debconf_selections'].update(grub2_debconf)
    else:
        config['debconf_selections'] = grub2_debconf
    return yaml.safe_dump(config)


def get_curtin_context(node, rack_controller=None, default_region_ip=None):
    """Return the curtin-specific context dictionary to be used to render
    user-data templates.

    :param node: The node for which to generate the user-data.
    :rtype: dict.
    """
    token = NodeKey.objects.get_token_for_node(node)
    if rack_controller is None:
        rack_controller = node.get_boot_rack_controller()
    base_url = rack_controller.url
    return {
        'curtin_preseed': compose_cloud_init_preseed(
            node, token, base_url, default_region_ip=default_region_ip)
    }


def get_preseed_type_for(node):
    """Returns the preseed type for the node.

    If the node is in a commissioning like status then the commissioning
    preseed will be used. Otherwise the node will use the curtin installer.
    """
    is_commissioning_preseed = (
        node.status in COMMISSIONING_LIKE_STATUSES or
        node.get_boot_purpose() == 'poweroff'
        )
    if is_commissioning_preseed:
        return PRESEED_TYPE.COMMISSIONING
    else:
        return PRESEED_TYPE.CURTIN


@typed
def get_preseed(node, default_region_ip=None) -> bytes:
    """Return the preseed for a given node. Depending on the node's
    status this will be a commissioning preseed (if the node is
    commissioning or disk erasing) or an install preseed (normal
    installation preseed or curtin preseed).

    :param node: The node to return preseed for.
    :type node: :class:`maasserver.models.Node`
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    if node.status in COMMISSIONING_LIKE_STATUSES:
        return render_preseed(
            node, PRESEED_TYPE.COMMISSIONING,
            osystem=Config.objects.get_config('commissioning_osystem'),
            release=Config.objects.get_config('commissioning_distro_series'),
            default_region_ip=default_region_ip)
    else:
        return render_preseed(
            node, get_preseed_type_for(node),
            osystem=node.get_osystem(), release=node.get_distro_series(),
            default_region_ip=default_region_ip)


UBUNTU_NAME = UbuntuOS().name


def get_preseed_filenames(node, prefix='', osystem='', release='',
                          default=False):
    """List possible preseed template filenames for the given node.

    :param node: The node to return template preseed filenames for.
    :type node: :class:`maasserver.models.Node`
    :param prefix: At the top level, this is the preseed type (will be used as
        a prefix in the template filenames).  Usually one of {'', 'enlist',
        'commissioning'}.
    :type prefix: unicode
    :param osystem: The operating system to be used.
    :type osystem: unicode
    :param release: The os release to be used.
    :type release: unicode
    :param default: Should we return the default ('generic') template as a
        last resort template?
    :type default: boolean

    Returns a list of possible preseed template filenames using the following
    lookup order:
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}_{node_name}
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}
    {prefix}_{osystem}_{node_arch}_{node_subarch}
    {prefix}_{osystem}_{node_arch}
    {prefix}_{osystem}
    {prefix}
    'generic'

    Note: in order to be backward-compatible with earlier versions of MAAS that
    only supported the Ubuntu OS, if the node OS is Ubuntu paths without the
    {osystem} are also tried:
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}_{node_name}
    {prefix}_{node_arch}_{node_subarch}_{release}_{node_name}
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}
    {prefix}_{node_arch}_{node_subarch}_{release}
    {prefix}_{osystem}_{node_arch}_{node_subarch}
    {prefix}_{node_arch}_{node_subarch}
    {prefix}_{osystem}_{node_arch}
    {prefix}_{node_arch}
    {prefix}_{osystem}
    {prefix}
    'generic'
    """
    elements = []
    # Add prefix.
    if prefix != '':
        elements.append(prefix)
        has_prefix = True
    else:
        has_prefix = False
    # Add osystem
    elements.append(osystem)
    # Add architecture/sub-architecture.
    if node is not None:
        arch = split_subarch(node.architecture)
        elements.extend(arch)
    # Add release.
    elements.append(release)
    # Add hostname.
    if node is not None:
        elements.append(node.hostname)
    while elements:
        yield compose_filename(elements)
        # Backward-compatibility fix for 1439366: also generate a filename
        # with the 'osystem' omitted when deploying with Ubuntu.
        if osystem == UBUNTU_NAME:
            should_emit = (
                (not has_prefix and len(elements) > 1) or
                (has_prefix and len(elements) > 2))
            if should_emit:
                cutoff = 1 if has_prefix else 0
                yield compose_filename(
                    elements[:cutoff] + elements[cutoff + 1:])
        elements.pop()
    if default:
        yield GENERIC_FILENAME


def split_subarch(architecture):
    """Split the architecture and the subarchitecture."""
    return architecture.split('/')


def compose_filename(elements):
    """Create a preseed filename from a list of elements."""
    return '_'.join(elements)


def get_preseed_template(filenames):
    """Get the path and content for the first template found.

    :param filenames: An iterable of relative filenames.
    """
    assert not isinstance(filenames, (bytes, str))
    assert all(isinstance(filename, str) for filename in filenames)
    for location in settings.PRESEED_TEMPLATE_LOCATIONS:
        for filename in filenames:
            filepath = os.path.join(location, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as stream:
                    content = stream.read()
            except IOError:
                pass  # Ignore.
            else:
                return filepath, content
    else:
        return None, None


def get_escape_singleton():
    """Return a singleton containing methods to escape various formats used in
    the preseed templates.
    """
    # Bug#1642996: We need to keep escape.shell in 2.X, for backwards
    # compatibility.  Any bugs filed about how it doesn't work should be marked
    # as a dup of Bug#1643595, and the user told to change to escape.json.
    Escape = namedtuple('Escape', ['json', 'shell'])
    return Escape(json=json.dumps, shell=quote)


class PreseedTemplate(tempita.Template):
    """A Tempita template specialised for preseed rendering.

    It provides a filter named 'escape' which contains methods to escape
    various formats used in the template."""

    default_namespace = dict(
        tempita.Template.default_namespace,
        escape=get_escape_singleton())


class TemplateNotFoundError(Exception):
    """The template has not been found."""

    def __init__(self, name):
        super(TemplateNotFoundError, self).__init__(name)
        self.name = name


def load_preseed_template(node, prefix, osystem='', release=''):
    """Find and load a `PreseedTemplate` for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    """

    def get_template(name, from_template, default=False):
        """A Tempita hook used to load the templates files.

        It is defined to preserve the context (node, name, release, default)
        since this will be called (by Tempita) called out of scope.
        """
        filenames = list(get_preseed_filenames(
            node, name, osystem, release, default))
        filepath, content = get_preseed_template(filenames)
        if filepath is None:
            raise TemplateNotFoundError(name)
        # This is where the closure happens: pass `get_template` when
        # instanciating PreseedTemplate.
        return PreseedTemplate(
            content, name=filepath, get_template=get_template)

    return get_template(prefix, None, default=True)


def get_netloc_and_path(url):
    """Return a tuple of the netloc and the hierarchical path from a url.

    The netloc, the "Network location part", is composed of the hostname
    and, optionally, the port.
    """
    parsed_url = urlparse(url)
    return parsed_url.netloc, parsed_url.path.lstrip("/")


def get_preseed_context(
        osystem='', release='', rack_controller=None, default_region_ip=None):
    """Return the node-independent context dictionary to be used to render
    preseed templates.

    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :param rack_controller: The rack controller used to generate the preseed.
    :return: The context dictionary.
    :rtype: dict.
    """
    server_host = get_maas_facing_server_host(
        rack_controller=rack_controller, default_region_ip=default_region_ip)
    if rack_controller is None:
        base_url = None
    else:
        base_url = rack_controller.url

    return {
        'osystem': osystem,
        'release': release,
        'server_host': server_host,
        'server_url': absolute_reverse(
            'machines_handler', default_region_ip=default_region_ip,
            base_url=base_url),
        'syslog_host_port': '%s:%d' % (server_host, RSYSLOG_PORT),
        'metadata_enlist_url': absolute_reverse(
            'enlist', default_region_ip=default_region_ip, base_url=base_url),
        }


def get_node_preseed_context(
        node, osystem='', release='', rack_controller=None,
        default_region_ip=None):
    """Return the node-dependent context dictionary to be used to render
    preseed templates.

    :param node: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The context dictionary.
    :rtype: dict.
    """
    if rack_controller is None:
        rack_controller = node.get_boot_rack_controller()
    # Create the url and the url-data (POST parameters) used to turn off
    # PXE booting once the install of the node is finished.
    node_disable_pxe_url = absolute_reverse(
        'metadata-node-by-id', default_region_ip=default_region_ip,
        args=['latest', node.system_id], base_url=rack_controller.url)
    node_disable_pxe_data = urlencode({'op': 'netboot_off'})
    driver = get_third_party_driver(node)
    return {
        'third_party_drivers': (
            Config.objects.get_config('enable_third_party_drivers')),
        'driver': driver,
        'driver_package': driver.get('package', ''),
        'node': node,
        'preseed_data': compose_preseed(
            get_preseed_type_for(node), node,
            default_region_ip=default_region_ip),
        'node_disable_pxe_url': node_disable_pxe_url,
        'node_disable_pxe_data': node_disable_pxe_data,
        'license_key': node.get_effective_license_key(),
    }


def get_node_deprecated_preseed_context():
    """Return the node-dependent context dictionary to be used to render
    preseed template. This includes all the context variables that have
    been deprecated, but allows for backwards compatibility for those
    preseeds that still contain old variables.

    :return: The context dictionary.
    :rtype: dict.
    """
    main_archive_hostname, main_archive_directory = get_netloc_and_path(
        PackageRepository.get_main_archive().url)
    ports_archive_hostname, ports_archive_directory = get_netloc_and_path(
        PackageRepository.get_ports_archive().url)

    return {
        'main_archive_hostname': main_archive_hostname,
        'main_archive_directory': main_archive_directory,
        'ports_archive_hostname': ports_archive_hostname,
        'ports_archive_directory': ports_archive_directory,
        'enable_http_proxy': Config.objects.get_config('enable_http_proxy'),
        'http_proxy': Config.objects.get_config('http_proxy'),
    }


def render_enlistment_preseed(
        prefix, osystem='', release='', rack_controller=None,
        default_region_ip=None):
    """Return the enlistment preseed.

    :param prefix: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :param rack_controller: The rack controller used to generate the preseed.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    template = load_preseed_template(None, prefix, osystem, release)
    context = get_preseed_context(
        osystem, release, rack_controller=rack_controller,
        default_region_ip=default_region_ip)
    # Render the snippets in the main template.
    snippets = get_snippet_context()
    snippets.update(context)
    return template.substitute(**snippets).encode("utf-8")


def render_preseed(
        node, prefix, osystem='', release='', default_region_ip=None):
    """Return the preseed for the given node.

    :param node: See `get_preseed_filenames`.
    :param prefix: See `get_preseed_filenames`.
    :param osystem: See `get_preseed_filenames`.
    :param release: See `get_preseed_filenames`.
    :return: The rendered preseed string.
    :rtype: unicode.
    """
    template = load_preseed_template(node, prefix, osystem, release)
    rack_controller = node.get_boot_rack_controller()
    context = get_preseed_context(
        osystem, release, rack_controller=rack_controller,
        default_region_ip=default_region_ip)
    context.update(
        get_node_preseed_context(
            node, osystem, release, rack_controller=rack_controller,
            default_region_ip=default_region_ip))
    return template.substitute(**context).encode("utf-8")


def compose_enlistment_preseed_url(
        rack_controller=None, default_region_ip=None):
    """Compose enlistment preseed URL.

    :param rack_controller: The rack controller used to generate the preseed.
    :param default_region_ip: The preferred IP address this region should
        communicate on.
    """
    # Always uses the latest version of the metadata API.
    base_url = (
        rack_controller.url
        if rack_controller is not None
        else None)
    version = 'latest'
    return absolute_reverse(
        'metadata-enlist-preseed', default_region_ip=default_region_ip,
        args=[version], query={'op': 'get_enlist_preseed'}, base_url=base_url)


def compose_preseed_url(node, rack_controller, default_region_ip=None):
    """Compose a metadata URL for `node`'s preseed data."""
    # Always uses the latest version of the metadata API.
    version = 'latest'
    return absolute_reverse(
        'metadata-node-by-id', default_region_ip=default_region_ip,
        args=[version, node.system_id], query={'op': 'get_preseed'},
        base_url=rack_controller.url)
