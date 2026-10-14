# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Django command: Perform a preflight check to ensure MAAS can be safely upgraded.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connections, DEFAULT_DB_ALIAS


class Command(BaseCommand):
    help = (
        "Perform a preflight check to ensure that MAAS can be safely upgraded."
    )

    def handle(self, *args, **options):
        conn = connections[DEFAULT_DB_ALIAS]
        conn.ensure_connection()
        with conn.cursor() as cursor:
            cursor.execute("""
                        SELECT name, primary_rack_id, secondary_rack_id
                        FROM maasserver_vlan
                        WHERE dhcp_on = true;
                """)
            vlans = cursor.fetchall()

            primaries = defaultdict(list)
            secondaries = defaultdict(list)

            for name, primary, secondary in vlans:
                if primary:
                    primaries[primary].append(name)
                if secondary:
                    secondaries[secondary].append(name)

            overlap = set(primaries.keys()).intersection(secondaries.keys())

            if not overlap:
                return

            err_msg = "ERROR: The following racks are the primary and secondary rack for different VLANs\n"
            err_msg += "primaries (rack ID -> VLAN names):\n"
            err_msg += str({i: primaries[i] for i in overlap})
            err_msg += "secondaries (rack ID -> VLAN names):"
            err_msg += str({i: secondaries[i] for i in overlap})
            raise AssertionError(err_msg)
