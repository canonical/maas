# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Keyring management functions for the import boot images job and script."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
import tempfile
from urlparse import urlsplit

from provisioningserver.import_images.helpers import logger


def write_keyring(keyring_path, keyring_data):
    """Write a keyring blob to a file.

    :param path: The path to the keyring file.
    :param keyring_data: The data to write to the keyring_file, as a
        base64-encoded string.
    """
    logger.debug("Writing keyring %s to disk.", keyring_path)
    with open(keyring_path, 'wb') as keyring_file:
        keyring_file.write(keyring_data)


def calculate_keyring_name(source_url):
    """Return a name for a keyring based on a URL."""
    split_url = urlsplit(source_url)
    cleaned_path = split_url.path.strip('/').replace('/', '-')
    keyring_name = "%s-%s.gpg" % (split_url.netloc, cleaned_path)
    return keyring_name


def write_all_keyrings(sources):
    """For a given set of `sources`, write the keyrings to disk.

    :param sources: An iterable of the sources whose keyrings need to be
        written.
    :return: The sources iterable, with each source whose keyring has
        been written now having a "keyring" value set, pointing to the file
        on disk.
    """
    keyring_dir = tempfile.mkdtemp("maas-keyrings")
    for source in sources:
        source_url = source.get('url')
        keyring_file = source.get('keyring')
        keyring_data = source.get('keyring_data')

        if keyring_file is not None and keyring_data is not None:
            logger.warning(
                "Both a keyring file and keyring data were specified; "
                "ignoring the keyring file.")

        if keyring_data is not None:
            keyring_file = os.path.join(
                keyring_dir, calculate_keyring_name(source_url))
            write_keyring(keyring_file, keyring_data)
            source['keyring'] = keyring_file
    return sources
