# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from netaddr import IPAddress

from maascommon.utils.network import MAASIPRange
from maasservicelayer.db.mappers.base import StorageRow


class SubnetUtilizationRangeMapper:
    """Hydrate non-Pydantic IP ranges from utilization query projections."""

    @staticmethod
    def to_domain(row: StorageRow) -> MAASIPRange:
        return MAASIPRange(
            start=IPAddress(str(row["start_ip"])),
            end=IPAddress(str(row["end_ip"])),
            purpose=set(row["purpose"]),
        )
