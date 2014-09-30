# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Sources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ensure_boot_source_definition",
    "get_boot_sources",
    "get_os_info_from_boot_sources",
    "cache_boot_sources",
    "BootSourceCacheService",
]


from maasserver import locks
from maasserver.models import (
    BootSource,
    BootSourceCache,
    BootSourceSelection,
    Config,
    )
from maasserver.utils.async import transactional
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.import_images.download_descriptions import (
    download_all_image_descriptions,
    )
from provisioningserver.import_images.keyrings import write_all_keyrings
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.env import environment_variables
from provisioningserver.utils.fs import tempdir
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.internet.threads import deferToThread
from twisted.python import log


maaslog = get_maas_logger("bootsources")


def ensure_boot_source_definition():
    """Set default boot source if none is currently defined."""
    if not BootSource.objects.exists():
        source = BootSource.objects.create(
            url='http://maas.ubuntu.com/images/ephemeral-v2/releases/',
            keyring_filename=(
                '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'))
        # Default is to import newest Ubuntu LTS releases, for only amd64
        # release versions only.
        BootSourceSelection.objects.create(
            boot_source=source, os='ubuntu', release='trusty',
            arches=['amd64'], subarches=['*'], labels=['release'])


def get_boot_sources():
    """Return list of boot sources for the region to import from."""
    return [
        source.to_dict()
        for source in BootSource.objects.all()
        ]


def get_simplestreams_env():
    """Return environment variables that should be used, when accessing
    simplestreams."""
    env = {
        'GNUPGHOME': get_maas_user_gpghome(),
        }
    http_proxy = Config.objects.get_config('http_proxy')
    if http_proxy is not None:
        env['http_proxy'] = http_proxy
        env['https_proxy'] = http_proxy
    return env


def get_os_info_from_boot_sources(os):
    """Return sources, list of releases, and list of architectures that exists
    for the given operating system from the `BootSource`'s.

    This pulls the information for BootSourceCache.
    """
    os_sources = []
    releases = set()
    arches = set()
    for source in BootSource.objects.all():
        for cache_item in BootSourceCache.objects.filter(
                boot_source=source, os=os):
            if source not in os_sources:
                os_sources.append(source)
            releases.add(cache_item.release)
            arches.add(cache_item.arch)
    return os_sources, releases, arches


@transactional
def _cache_boot_sources():
    """Cache all image information in boot sources."""
    # If the lock is already held, then cache is already running.
    if locks.cache_sources.is_locked():
        return

    # Hold the lock while performing the cache
    with locks.cache_sources:
        env = get_simplestreams_env()
        with environment_variables(env), tempdir('keyrings') as keyrings_path:
            for source in BootSource.objects.all():
                sources = write_all_keyrings(
                    keyrings_path, [source.to_dict_without_selections()])
                image_descriptions = download_all_image_descriptions(sources)

                # We clear the cache once the information has been retrieved,
                # because if an error occurs getting the information then the
                # function will not make it to this point, allowing the items
                # in the cache to remain before it errors.
                BootSourceCache.objects.filter(boot_source=source).delete()
                if not image_descriptions.is_empty():
                    for image_spec in image_descriptions.mapping.keys():
                        BootSourceCache.objects.create(
                            boot_source=source,
                            os=image_spec.os,
                            arch=image_spec.arch,
                            subarch=image_spec.subarch,
                            release=image_spec.release,
                            label=image_spec.label,
                            )
        maaslog.info("Updated boot sources cache.")


def cache_boot_sources():
    """Starts the caching of image information in boot sources.

    Note: This function returns immediately. It only starts the process, it
    doesn't wait for it to be finished.
    """
    # We start the update about 1 second later, or we get a OperationalError.
    # "OperationalError: could not serialize access due to concurrent update"
    # The wait will make sure the transaction that started the update will
    # have finished and been committed.
    reactor.callLater(1, deferToThread, _cache_boot_sources)


class BootSourceCacheService(TimerService, object):
    """Service to periodically cache boot source information.

    This will run immediately when it's started, then once again every hour,
    though the interval can be overridden by passing it to the constructor.
    """

    def __init__(self, interval=(60 * 60)):
        super(BootSourceCacheService, self).__init__(
            interval, self.try_cache_boot_sources)

    def try_cache_boot_sources(self):
        """Attempt to cache boot sources.

        Log errors on failure, but do not propagate them up; that will
        stop the timed loop from running.
        """

        def cache_boot_sources_failed(failure):
            # Log the error in full to the Twisted log.
            log.err(failure)
            # Log something concise to the MAAS log.
            maaslog.error(
                "Failed to update boot source cache: %s",
                failure.getErrorMessage())

        d = deferToThread(_cache_boot_sources)
        d.addErrback(cache_boot_sources_failed)
        return d
