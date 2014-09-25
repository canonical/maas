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
]


from maasserver.models import (
    BootSource,
    BootSourceSelection,
    Config,
    )
from provisioningserver.auth import get_maas_user_gpghome
from provisioningserver.import_images.download_descriptions import (
    download_all_image_descriptions,
    )
from provisioningserver.import_images.keyrings import write_all_keyrings
from provisioningserver.utils.env import environment_variables
from provisioningserver.utils.fs import tempdir


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
    for the given operating system from the `BootSource`'s."""
    os_sources = []
    releases = set()
    arches = set()
    env = get_simplestreams_env()
    with environment_variables(env), tempdir('keyrings') as keyrings_path:
        for source in BootSource.objects.all():
            sources = write_all_keyrings(
                keyrings_path, [source.to_dict_without_selections()])
            image_descriptions = download_all_image_descriptions(sources)
            if not image_descriptions.is_empty():
                os_specs = [
                    image_spec
                    for image_spec in image_descriptions.mapping.keys()
                    if image_spec.os == os
                    ]
                if len(os_specs) > 0:
                    os_sources.append(source)
                for image_spec in os_specs:
                    releases.add(image_spec.release)
                    arches.add(image_spec.arch)
    return os_sources, releases, arches
