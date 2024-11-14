# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

CONFIGURE_DNS_WORKFLOW_NAME = "configure-dns"


@dataclass
class ConfigureDNSParam:
    need_full_reload: bool
