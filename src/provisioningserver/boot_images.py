# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Dealing with boot images.

Most of the lower-level logic is in the `tftppath` module, because it must
correspond closely to the structure of the TFTP filesystem hierarchy.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'report_to_server',
    ]

import json
from logging import getLogger

from apiclient.maas_client import (
    MAASClient,
    MAASDispatcher,
    MAASOAuth,
    )
from provisioningserver.auth import get_recorded_api_credentials
from provisioningserver.cluster_config import (
    get_cluster_uuid,
    get_maas_url,
    )
from provisioningserver.config import Config
from provisioningserver.pxe import tftppath


logger = getLogger(__name__)


def get_cached_knowledge():
    """Return cached items required to report to the server.

    :return: Tuple of cached items: (maas_url, api_credentials).  Either may
        be None if the information has not been received from the server yet.
    """
    maas_url = get_maas_url()
    if maas_url is None:
        logger.debug("Not reporting boot images: don't have API URL yet.")
    api_credentials = get_recorded_api_credentials()
    if api_credentials is None:
        logger.debug("Not reporting boot images: don't have API key yet.")
    return maas_url, api_credentials


def submit(maas_url, api_credentials, images):
    """Submit images to server."""
    MAASClient(MAASOAuth(*api_credentials), MAASDispatcher(), maas_url).post(
        'api/1.0/boot-images/', 'report_boot_images',
        nodegroup=get_cluster_uuid(), images=json.dumps(images))


def report_to_server():
    """For master worker only: report available netboot images."""
    maas_url, api_credentials = get_cached_knowledge()
    if not all([maas_url, api_credentials]):
        return

    images = tftppath.list_boot_images(
        Config.load_from_cache()['tftp']['root'])

    submit(maas_url, api_credentials, images)
