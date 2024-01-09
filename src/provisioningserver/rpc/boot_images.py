# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC relating to boot images."""

from urllib.parse import urlparse

from twisted.internet.defer import fail, inlineCallbacks
from twisted.internet.threads import deferToThread

from provisioningserver import concurrency
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.boot import tftppath
from provisioningserver.config import ClusterConfiguration
from provisioningserver.import_images import boot_resources
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc import getRegionClient
from provisioningserver.rpc.region import UpdateLastImageSync
from provisioningserver.utils.env import environment_variables, MAAS_ID
from provisioningserver.utils.twisted import synchronous

log = LegacyLogger()


CACHED_BOOT_IMAGES = None


def list_boot_images():
    """List the boot images that exist on the cluster.

    This return value of this function is cached. This helps reduce the amount
    of IO, as this function is called often. To update the cache call
    `reload_boot_images`.
    """

    global CACHED_BOOT_IMAGES
    if CACHED_BOOT_IMAGES is None:
        with ClusterConfiguration.open() as config:
            tftp_root = config.tftp_root
        CACHED_BOOT_IMAGES = tftppath.list_boot_images(tftp_root)
    return CACHED_BOOT_IMAGES


def reload_boot_images():
    """Update the cached boot images so `list_boot_images` returns the
    most up-to-date boot images list."""
    global CACHED_BOOT_IMAGES
    with ClusterConfiguration.open() as config:
        tftp_root = config.tftp_root
    CACHED_BOOT_IMAGES = tftppath.list_boot_images(tftp_root)


def get_hosts_from_sources(sources):
    """Return set of hosts that are contained in the given sources.

    If the host is an IPv6 address, we also return it in the format
    of [<ipv6-address>] because things like no_proxy (which this
    function is used for), need it that way."""
    hosts = set()
    for source in sources:
        url = urlparse(source["url"])
        if url.hostname is not None:
            hosts.add(url.hostname)
        # If it's the IPv6 address, we add also add it inside []
        if ":" in url.hostname:
            hosts.add("[%s]" % url.hostname)
    return hosts


def fix_sources_for_cluster(sources, maas_url):
    """Return modified sources that use the URL to the region defined in the
    cluster configuration instead of the one the region suggested."""
    sources = list(sources)
    maas_url_parsed = urlparse(maas_url)
    maas_url_path = maas_url_parsed.path.lstrip("/").rstrip("/")
    for source in sources:
        url = urlparse(source["url"])
        source_path = url.path.lstrip("/")
        # Most likely they will both have 'MAAS/' at the start. We can't just
        # append because then the URL would be 'MAAS/MAAS/' which is incorrect.
        # If the initial part of the URL defined in the config matches the
        # beginning of what the region told the cluster to use then strip it
        # out and build the new URL.
        if source_path.startswith(maas_url_path):
            source_path = source_path[len(maas_url_path) :]
        url = maas_url.rstrip("/") + "/" + source_path.lstrip("/")
        source["url"] = url
    return sources


@synchronous
def _run_import(sources, maas_url, http_proxy=None, https_proxy=None):
    """Run the import.

    This is function is synchronous so it must be called with deferToThread.
    """
    # Fix the sources to download from the IP address defined in the cluster
    # configuration, instead of the URL that the region asked it to use.
    sources = fix_sources_for_cluster(sources, maas_url)
    variables = {"GNUPGHOME": get_maas_user_gpghome()}
    if http_proxy is not None:
        variables["http_proxy"] = http_proxy
    if https_proxy is not None:
        variables["https_proxy"] = https_proxy
    # Communication to the sources and loopback should not go through proxy.
    no_proxy_hosts = [
        "localhost",
        "::ffff:127.0.0.1",
        "127.0.0.1",
        "::1",
        "[::ffff:127.0.0.1]",
        "[::1]",
    ]
    no_proxy_hosts += list(get_hosts_from_sources(sources))
    variables["no_proxy"] = ",".join(no_proxy_hosts)
    with environment_variables(variables):
        imported = boot_resources.import_images(sources)

    # Update the boot images cache so `list_boot_images` returns the
    # correct information.
    reload_boot_images()

    # Tell callers if anything happened.
    return imported


def import_boot_images(sources, maas_url, http_proxy=None, https_proxy=None):
    """Imports the boot images from the given sources."""
    lock = concurrency.boot_images
    # This checks if any other defer is already waiting. If nothing is waiting
    # then add the _import again. If its already waiting nothing is added.
    #
    # This is important to how this functions. If the rackd is already
    # importing images and the regiond triggers another import then after the
    # original import another will be fired.
    if not lock.waiting:
        return lock.run(
            _import_boot_images,
            sources,
            maas_url,
            http_proxy=http_proxy,
            https_proxy=https_proxy,
        )


@inlineCallbacks
def _import_boot_images(sources, maas_url, http_proxy=None, https_proxy=None):
    """Import boot images then inform the region.

    Helper for `import_boot_images`.
    """
    proxies = dict(http_proxy=http_proxy, https_proxy=https_proxy)
    yield deferToThread(_run_import, sources, maas_url, **proxies)
    yield touch_last_image_sync_timestamp().addErrback(
        log.err, "Failure touching last image sync timestamp."
    )


def touch_last_image_sync_timestamp():
    """Inform the region that images have just been synchronised.

    :return: :class:`Deferred` that can fail with `NoConnectionsAvailable` or
        any exception arising from an `UpdateLastImageSync` RPC.
    """
    try:
        client = getRegionClient()
    except Exception:
        return fail()
    else:
        return client(UpdateLastImageSync, system_id=MAAS_ID.get())
