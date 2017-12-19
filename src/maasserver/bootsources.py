# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Boot Sources."""

__all__ = [
    "cache_boot_sources",
    "ensure_boot_source_definition",
    "get_boot_sources",
    "get_os_info_from_boot_sources",
]

import html
import os

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
    Notification,
)
from maasserver.utils import get_maas_user_agent
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.config import (
    DEFAULT_IMAGES_URL,
    DEFAULT_KEYRINGS_PATH,
)
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.import_images.download_descriptions import (
    download_all_image_descriptions,
)
from provisioningserver.import_images.keyrings import write_all_keyrings
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.fs import tempdir
from provisioningserver.utils.twisted import (
    asynchronous,
    FOREVER,
)
from requests.exceptions import ConnectionError
from twisted.internet.defer import inlineCallbacks


maaslog = get_maas_logger("bootsources")


@transactional
def ensure_boot_source_definition():
    """Set default boot source if none is currently defined."""
    if not BootSource.objects.exists():
        source = BootSource.objects.create(
            url=DEFAULT_IMAGES_URL, keyring_filename=DEFAULT_KEYRINGS_PATH)
        # Default is to import newest Ubuntu LTS releases, for only amd64
        # release versions only.
        ubuntu = UbuntuOS()
        BootSourceSelection.objects.create(
            boot_source=source, os=ubuntu.name,
            release=ubuntu.get_default_commissioning_release(),
            arches=['amd64'], subarches=['*'], labels=['*'])
        return True
    else:
        return False


@transactional
def get_boot_sources():
    """Return list of boot sources for the region to import from."""
    return [
        source.to_dict()
        for source in BootSource.objects.all()
        ]


@transactional
def get_simplestreams_env():
    """Get environment that should be used with simplestreams."""
    env = {'GNUPGHOME': get_maas_user_gpghome()}
    if Config.objects.get_config('enable_http_proxy'):
        http_proxy = Config.objects.get_config('http_proxy')
        if http_proxy is not None:
            env['http_proxy'] = http_proxy
            env['https_proxy'] = http_proxy
            # When the proxy environment variables are set they effect the
            # entire process, including controller refresh. When the region
            # needs to refresh itself it sends itself results over HTTP to
            # 127.0.0.1.
            env['no_proxy'] = '127.0.0.1,localhost'
    return env


def set_simplestreams_env():
    """Set the environment that simplestreams needs."""
    # We simply set the env variables here as another simplestreams-based
    # import might be running concurrently (bootresources._import_resources)
    # and we don't want to use the environment_variables context manager that
    # would reset the environment variables (they are global to the entire
    # process) while the other import is still running.
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


def get_product_title(item):
    os_title = item.get('os_title')
    release_title = item.get('release_title')
    gadget_title = item.get('gadget_title')
    if None not in (os_title, release_title, gadget_title):
        return "%s %s %s" % (os_title, release_title, gadget_title)
    elif None not in (os_title, release_title):
        return "%s %s" % (os_title, release_title)
    else:
        return None


@asynchronous(timeout=FOREVER)
@inlineCallbacks
def cache_boot_sources():
    """Cache all image information in boot sources.

    Called from *outside* of a transaction this will:

    1. Retrieve information about all boot sources from the database. The
       transaction is committed before proceeding.

    2. The boot sources are consulted (i.e. there's network IO now) and image
       descriptions downloaded.

    3. Update the boot source cache with the fetched information. If the boot
       source has been modified or deleted during #2 then the results are
       discarded.

    This approach does not require an exclusive lock.

    """
    # Nomenclature herein: `bootsource` is an ORM record for BootSource;
    # `source` is one of those converted to a dict. The former ought not to be
    # used outside of a transactional context.

    @transactional
    def get_sources():
        return list(
            bootsource.to_dict_without_selections()
            for bootsource in BootSource.objects.all()
            # TODO: Only where there are no corresponding BootSourceCache
            # records or the BootSource's updated timestamp is later than any
            # of the BootSourceCache records' timestamps.
        )

    @transactional
    def update_cache(source, descriptions):
        try:
            bootsource = BootSource.objects.get(url=source["url"])
        except BootSource.DoesNotExist:
            # The record was deleted while we were fetching the description.
            maaslog.debug(
                "Image descriptions at %s are no longer needed; discarding.",
                source["url"])
        else:
            if bootsource.compare_dict_without_selections(source):
                # Only delete from the cache once we have the descriptions.
                BootSourceCache.objects.filter(boot_source=bootsource).delete()
                if not descriptions.is_empty():
                    for spec, item in descriptions.mapping.items():
                        title = get_product_title(item)
                        if title is None:
                            extra = {}
                        else:
                            extra = {'title': title}
                        BootSourceCache.objects.create(
                            boot_source=bootsource, os=spec.os,
                            arch=spec.arch, subarch=spec.subarch,
                            kflavor=spec.kflavor,
                            release=spec.release, label=spec.label,
                            release_codename=item.get('release_codename'),
                            release_title=item.get('release_title'),
                            support_eol=item.get('support_eol'),
                            bootloader_type=item.get('bootloader-type'),
                            extra=extra,
                            )
                maaslog.debug(
                    "Image descriptions for %s have been updated.",
                    source["url"])
            else:
                maaslog.debug(
                    "Image descriptions for %s are outdated; discarding.",
                    source["url"])

    @transactional
    def check_commissioning_series_selected():
        commissioning_osystem = Config.objects.get_config(
            name='commissioning_osystem')
        commissioning_series = Config.objects.get_config(
            name='commissioning_distro_series')
        qs = BootSourceSelection.objects.filter(
            os=commissioning_osystem, release=commissioning_series)
        if not qs.exists():
            if not Notification.objects.filter(
                    ident='commissioning_series_unselected').exists():
                Notification.objects.create_error_for_users(
                    '%s %s is configured as the commissioning release but it '
                    'is not selected for download!' % (
                        commissioning_osystem, commissioning_series),
                    ident='commissioning_series_unselected')
        qs = BootSourceCache.objects.filter(
            os=commissioning_osystem, release=commissioning_series)
        if not qs.exists():
            if not Notification.objects.filter(
                    ident='commissioning_series_unavailable').exists():
                Notification.objects.create_error_for_users(
                    '%s %s is configured as the commissioning release but it '
                    'is unavailable in the configured streams!' % (
                        commissioning_osystem, commissioning_series),
                    ident='commissioning_series_unavailable')

    # FIXME: This modifies the environment of the entire process, which is Not
    # Cool. We should integrate with simplestreams in a more Pythonic manner.
    yield deferToDatabase(set_simplestreams_env)

    errors = []
    sources = yield deferToDatabase(get_sources)
    for source in sources:
        with tempdir("keyrings") as keyrings_path:
            [source] = write_all_keyrings(keyrings_path, [source])
            try:
                user_agent = yield deferToDatabase(get_maas_user_agent)
                descriptions = download_all_image_descriptions(
                    [source],
                    user_agent=user_agent)
            except (IOError, ConnectionError) as error:
                errors.append(
                    "Failed to import images from boot source "
                    "%s: %s" % (source["url"], error))
            else:
                yield deferToDatabase(update_cache, source, descriptions)

    yield deferToDatabase(check_commissioning_series_selected)

    maaslog.info("Updated boot sources cache.")

    component = COMPONENT.REGION_IMAGE_IMPORT
    if len(errors) > 0:
        yield deferToDatabase(
            register_persistent_error, component,
            "<br>".join(map(html.escape, errors)))
    else:
        yield deferToDatabase(
            discard_persistent_error, component)
