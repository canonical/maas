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
    "cache_boot_sources_in_thread",
]

import os

from maasserver import locks
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
    )
from maasserver.enum import COMPONENT
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
from provisioningserver.utils.fs import tempdir
from requests.exceptions import ConnectionError
from twisted.internet import reactor
from twisted.internet.threads import deferToThread


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


def set_simplestreams_env():
    """Set the environment variable simplestreams needs."""
    # We simply set the env variables here as another simplestreams-based
    # import might be running concurrently
    # (bootresources._import_resources) and we don't want to use the
    # environment_variables context manager that would reset the
    # environment variables (they are global to the entire process)
    # while the other import is still running.
    os.environ.update(get_simplestreams_env())


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
def cache_boot_sources():
    """Cache all image information in boot sources."""
    # If the lock is already held, then cache is already running.
    if locks.cache_sources.is_locked():
        return

    source_errors = []

    # Hold the lock while performing the cache
    with locks.cache_sources:
        set_simplestreams_env()
        with tempdir('keyrings') as keyrings_path:
            for source in BootSource.objects.all():
                sources = write_all_keyrings(
                    keyrings_path, [source.to_dict_without_selections()])
                try:
                    image_descriptions = download_all_image_descriptions(
                        sources)
                except (IOError, ConnectionError) as e:
                    source_errors.append(
                        "Failed to import images from boot source %s: %s" % (
                            source.url, unicode(e)))
                    continue

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

        # Update the component errors while still holding the lock.
        if len(source_errors) > 0:
            register_persistent_error(
                COMPONENT.REGION_IMAGE_IMPORT, "\n".join(source_errors))
        else:
            discard_persistent_error(COMPONENT.REGION_IMAGE_IMPORT)


def cache_boot_sources_in_thread():
    """Starts the caching of image information in boot sources.

    Note: This function returns immediately. It only starts the process, it
    doesn't wait for it to be finished.
    """
    # We start the update about 1 second later, or we get a OperationalError.
    # "OperationalError: could not serialize access due to concurrent update"
    # The wait will make sure the transaction that started the update will
    # have finished and been committed.
    reactor.callLater(1, deferToThread, cache_boot_sources)
