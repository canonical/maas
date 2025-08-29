# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from contextlib import closing

from django.db import connection

from maasserver.models.dnspublication import zone_serial
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers.system import register_system_triggers
from maasserver.utils.orm import psql_array
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


class TestTriggers(MAASServerTestCase):
    def test_register_system_triggers(self):
        register_system_triggers()
        triggers = [
            "regionrackrpcconnection_sys_core_rpc_insert",
            "regionrackrpcconnection_sys_core_rpc_delete",
            "subnet_sys_proxy_subnet_insert",
            "subnet_sys_proxy_subnet_update",
            "subnet_sys_proxy_subnet_delete",
            "resourcepool_sys_rbac_rpool_insert",
            "resourcepool_sys_rbac_rpool_update",
            "resourcepool_sys_rbac_rpool_delete",
        ]
        sql, args = psql_array(triggers, sql_type="text")
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT tgname::text FROM pg_trigger WHERE "
                "tgname::text = ANY(%s)" % sql,
                args,
            )
            db_triggers = cursor.fetchall()

        # Note: if this test fails, a trigger may have been added, but not
        # added to the list of expected triggers.
        triggers_found = [trigger[0] for trigger in db_triggers]
        missing_triggers = [
            trigger for trigger in triggers if trigger not in triggers_found
        ]
        self.assertEqual(
            len(triggers),
            len(db_triggers),
            "Missing %s triggers in the database. Triggers missing: %s"
            % (len(triggers) - len(db_triggers), missing_triggers),
        )

    def test_register_system_triggers_ensures_zone_serial(self):
        mock_create = self.patch(zone_serial, "create_if_not_exists")
        register_system_triggers()
        mock_create.assert_called_once_with()
