# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass

CONFIGURE_DNS_WORKFLOW_NAME = "configure-dns"


class InvalidDNSUpdateError(Exception):
    pass


@dataclass
class ConfigureDNSParam:
    need_full_reload: bool


def merge_configure_dns_params(
    old: ConfigureDNSParam, new: ConfigureDNSParam
) -> ConfigureDNSParam:
    return old if old.need_full_reload else new
