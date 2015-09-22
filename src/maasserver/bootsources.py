# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
    "cache_boot_sources",
    "ensure_boot_source_definition",
    "get_boot_sources",
    "get_os_info_from_boot_sources",
]

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
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.auth import get_maas_user_gpghome
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
                    for spec in descriptions.mapping:
                        BootSourceCache.objects.create(
                            boot_source=bootsource, os=spec.os,
                            arch=spec.arch, subarch=spec.subarch,
                            release=spec.release, label=spec.label)
                maaslog.debug(
                    "Image descriptions for %s have been updated.",
                    source["url"])
            else:
                maaslog.debug(
                    "Image descriptions for %s are outdated; discarding.",
                    source["url"])

    # FIXME: This modifies the environment of the entire process, which is Not
    # Cool. We should integrate with simplestreams in a more Pythonic manner.
    yield deferToDatabase(set_simplestreams_env)

    errors = []
    sources = yield deferToDatabase(get_sources)
    for source in sources:
        with tempdir("keyrings") as keyrings_path:
            [source] = write_all_keyrings(keyrings_path, [source])
            try:
                descriptions = download_all_image_descriptions([source])
            except (IOError, ConnectionError) as error:
                errors.append(
                    "Failed to import images from boot source "
                    "%s: %s" % (source["url"], error))
            else:
                yield deferToDatabase(update_cache, source, descriptions)

    maaslog.info("Updated boot sources cache.")

    component = COMPONENT.REGION_IMAGE_IMPORT
    if len(errors) > 0:
        yield deferToDatabase(
            register_persistent_error, component, "\n".join(errors))
    else:
        yield deferToDatabase(
            discard_persistent_error, component)
