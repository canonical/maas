# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

"""Tests for `maasserver.triggers`."""

str = None

__metaclass__ = type
__all__ = []

from contextlib import closing

from django.db import connection
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers import (
    register_all_triggers,
    register_procedure,
    register_trigger,
    render_notification_procedure,
)
from maasserver.utils.orm import psql_array


class TestTriggers(MAASServerTestCase):

    def test_register_trigger_doesnt_create_trigger_if_already_exists(self):
        NODE_CREATE_PROCEDURE = render_notification_procedure(
            'node_create_notify', 'node_create', 'NEW.system_id')
        register_procedure(NODE_CREATE_PROCEDURE)
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "DROP TRIGGER IF EXISTS maasserver_node_node_create_notify ON "
                "maasserver_node;"
                "CREATE TRIGGER maasserver_node_node_create_notify "
                "AFTER INSERT ON maasserver_node "
                "FOR EACH ROW EXECUTE PROCEDURE node_create_notify();")

        # Will raise an OperationError if trigger already exists.
        register_trigger("maasserver_node", "node_create_notify", "insert")

    def test_register_trigger_creates_missing_trigger(self):
        NODE_CREATE_PROCEDURE = render_notification_procedure(
            'node_create_notify', 'node_create', 'NEW.system_id')
        register_procedure(NODE_CREATE_PROCEDURE)
        register_trigger("maasserver_node", "node_create_notify", "insert")

        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM pg_trigger WHERE "
                "tgname = 'maasserver_node_node_create_notify'")
            triggers = cursor.fetchall()

        self.assertEquals(1, len(triggers), "Trigger was not created.")

    def test_register_all_triggers(self):
        register_all_triggers()
        triggers = [
            "maasserver_node_node_create_notify",
            "maasserver_node_node_update_notify",
            "maasserver_node_node_delete_notify",
            "maasserver_node_device_create_notify",
            "maasserver_node_device_update_notify",
            "maasserver_node_device_delete_notify",
            "maasserver_nodegroup_nodegroup_create_notify",
            "maasserver_nodegroup_nodegroup_update_notify",
            "maasserver_nodegroup_nodegroup_delete_notify",
            "maasserver_zone_zone_create_notify",
            "maasserver_zone_zone_update_notify",
            "maasserver_zone_zone_delete_notify",
            "maasserver_tag_tag_create_notify",
            "maasserver_tag_tag_update_notify",
            "maasserver_tag_tag_delete_notify",
            "maasserver_node_tags_node_device_tag_link_notify",
            "maasserver_node_tags_node_device_tag_unlink_notify",
            "maasserver_tag_tag_update_node_device_notify",
            "auth_user_user_create_notify",
            "auth_user_user_update_notify",
            "auth_user_user_delete_notify",
            "maasserver_event_event_create_notify",
            "maasserver_event_event_update_notify",
            "maasserver_event_event_delete_notify",
            "maasserver_event_event_create_node_device_notify",
            "maasserver_nodegroupinterface_nodegroupinterface_create_notify",
            "maasserver_nodegroupinterface_nodegroupinterface_update_notify",
            "maasserver_nodegroupinterface_nodegroupinterface_delete_notify",
            "maasserver_macstaticipaddresslink_nd_sipaddress_link_notify",
            "maasserver_macstaticipaddresslink_nd_sipaddress_unlink_notify",
            "maasserver_dhcplease_nd_dhcplease_match_notify",
            "maasserver_dhcplease_nd_dhcplease_unmatch_notify",
            "metadataserver_noderesult_nd_noderesult_link_notify",
            "metadataserver_noderesult_nd_noderesult_unlink_notify",
            "maasserver_macaddress_nd_macaddress_link_notify",
            "maasserver_macaddress_nd_macaddress_unlink_notify",
            "maasserver_macaddress_nd_macaddress_update_notify",
            "maasserver_blockdevice_nd_blockdevice_link_notify",
            "maasserver_blockdevice_nd_blockdevice_unlink_notify",
            "maasserver_physicalblockdevice_nd_physblockdevice_update_notify",
            "maasserver_virtualblockdevice_nd_virtblockdevice_update_notify",
            "maasserver_sshkey_user_sshkey_link_notify",
            "maasserver_sshkey_user_sshkey_unlink_notify",
            "maasserver_sslkey_user_sslkey_link_notify",
            "maasserver_sslkey_user_sslkey_unlink_notify",
            ]
        sql, args = psql_array(triggers, sql_type="text")
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "SELECT * FROM pg_trigger WHERE "
                "tgname::text = ANY(%s)" % sql, args)
            db_triggers = cursor.fetchall()

        self.assertEquals(
            len(triggers), len(db_triggers),
            "Missing %s triggers in the database." % (
                len(triggers) - len(db_triggers)))
