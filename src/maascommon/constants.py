#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import os

SYSTEM_CA_FILE = "/etc/ssl/certs/ca-certificates.crt"

# Time, in minutes, until the node times out during commissioning, testing,
# deploying, or entering rescue mode…
NODE_TIMEOUT = 30

# PISTON3 tokens, consumers and users
GENERIC_CONSUMER = "MAAS consumer"
MAAS_USER_USERNAME = "MAAS"
MAAS_USER_LAST_NAME = "Special user"
MAAS_USER_EMAIL = "maas@localhost"


BOOTLOADERS_DIR = "bootloaders"

KEYRINGS_PATH = (
    "/snap/maas/current/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
    if os.environ.get("SNAP")
    else "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
)


STABLE_IMAGES_STREAM_URL = "http://images.maas.io/ephemeral-v3/stable"
STABLE_IMAGES_STREAM_NAME = "MAAS Stable"

CANDIDATE_IMAGES_STREAM_URL = "http://images.maas.io/ephemeral-v3/candidate"
CANDIDATE_IMAGES_STREAM_NAME = "MAAS Candidate"
