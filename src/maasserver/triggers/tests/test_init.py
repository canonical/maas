# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.triggers`."""

__all__ = []

from contextlib import closing

from django.db import connection
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.triggers import (
    register_procedure,
    register_trigger,
)
from maasserver.triggers.websocket import render_notification_procedure


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

        self.assertEqual(1, len(triggers), "Trigger was not created.")
