# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import hashlib
import os
from typing import Any, Dict, List

from structlog import getLogger

logger = getLogger()


def write_keyring(keyring_path: str, keyring_data: bytes) -> None:
    """Write a keyring blob to a file.

    :param keyring_path: The path to the keyring file.
    :param keyring_data: The data to write to the keyring_file, as a
        base64-encoded string.
    """
    logger.debug(f"Writing keyring {keyring_path} to disk.")
    with open(keyring_path, "wb") as keyring_file:
        keyring_file.write(keyring_data)


def calculate_keyring_name(source_url: str) -> str:
    """Return a name for a keyring based on a URL.

    :param source_url: The URL of the source with which to calculate the keyring name.
    :return: A hexadecimal digest of the MD5 hash of the source URL.
    """
    return hashlib.md5(source_url.encode("utf8")).hexdigest()


def write_all_keyrings(
    directory: str, sources: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """For a given set of `sources`, write the keyrings to disk.

    :param directory: A directory where the key files should be written.  Use
        a dedicated temporary directory for this, and clean it up when done.
    :param sources: An iterable of the sources whose keyrings need to be
        written.
    :return: The sources iterable, with each source whose keyring has
        been written now having a "keyring" value set, pointing to the file
        on disk.
    """
    for source in sources:
        source_url = source.get("url")
        keyring_file = source.get("keyring")
        keyring_data = source.get("keyring_data")

        if keyring_file is not None and keyring_data is not None:
            logger.warning(
                "Both a keyring file and keyring data were specified; "
                "ignoring the keyring file."
            )

        if keyring_data is not None:
            keyring_file = os.path.join(
                directory,
                calculate_keyring_name(source_url),  # pyright: ignore[reportArgumentType]
            )
            write_keyring(keyring_file, keyring_data)
            source["keyring"] = keyring_file
    return sources
