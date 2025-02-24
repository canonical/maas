#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta

SYSTEM_CA_FILE = "/etc/ssl/certs/ca-certificates.crt"

# Time, in minutes, until the node times out during commissioning, testing,
# deploying, or entering rescue mode…
NODE_TIMEOUT = 30

# How often the import service runs.
IMPORT_RESOURCES_SERVICE_PERIOD = timedelta(hours=1)
