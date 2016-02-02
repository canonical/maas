# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.triggers.system`."""

__all__ = []

from contextlib import closing

from django.db import connection
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers.system import register_system_triggers
from maasserver.utils.orm import psql_array


class TestTriggers(MAASServerTestCase):

    def test_register_system_triggers(self):
        register_system_triggers()
        triggers = [
            "maasserver_vlan_sys_dhcp_vlan_update",
            "maasserver_subnet_sys_dhcp_subnet_update",
            "maasserver_subnet_sys_dhcp_subnet_delete",
            "maasserver_iprange_sys_dhcp_iprange_insert",
            "maasserver_iprange_sys_dhcp_iprange_update",
            "maasserver_iprange_sys_dhcp_iprange_delete",
            ]
        sql, args = psql_array(triggers, sql_type="text")
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT tgname::text FROM pg_trigger WHERE "
                "tgname::text = ANY(%s) "
                "OR tgname::text SIMILAR TO 'maasserver.*'" % sql, args)
            db_triggers = cursor.fetchall()

        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = [trigger[0] for trigger in db_triggers]
        self.assertEqual(
            len(triggers), len(db_triggers),
            "Missing %s triggers in the database. Triggers found: %s" % (
                len(triggers) - len(db_triggers), triggers_found))

        self.assertItemsEqual(
            triggers, triggers_found,
            "Missing triggers in the database. Triggers found: %s" % (
                triggers_found))
