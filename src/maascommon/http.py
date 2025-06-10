# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

from maascommon.path import get_maas_data_path

REGIOND_SOCKET_PATH = os.getenv(
    "MAAS_HTTP_SOCKET_WORKER_BASE_PATH",
    get_maas_data_path("maas-regiond-webapp.sock"),
)
