# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Postgres Triggers

Triggers are implemented in the database to notify the PostgresListener when
an event occurs. Each trigger should use "CREATE OR REPLACE" so its overrides
its previous trigger. All triggers will be added into the database via the
`start_up` method for regiond.

Each trigger will call a procedure to send the notification. Each procedure
should be named with the table name "maasserver_node" and the action for the
trigger "node_create" followed by "notify".

E.g. "maasserver_node_node_create_notify".
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "register_all_triggers"
    ]

from contextlib import closing
from textwrap import dedent

from django.db import connection
from maasserver.utils.orm import transactional

# Note that the corresponding test module (test_triggers) only tests that the
# triggers and procedures are registered.  The behavior of these procedures
# is tested (end-to-end testing) in test_listeners.  We test it there because
# the asynchronous nature of the PG events makes it easier to test in
# test_listeners where all the Twisted infrastructure is already in place.


# Procedure that is called when a tag is added or removed from a node/device.
# Sends a notify message for node_update or device_update depending on if the
# node is installable.
NODE_TAG_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node
      WHERE id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a tag is updated. This will send the correct
# node_update or device_update notify message for all nodes with this tag.
TAG_NODES_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION tag_update_node_device_notify()
    RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      FOR node IN (
        SELECT maasserver_node.system_id, maasserver_node.installable
        FROM maasserver_node_tags, maasserver_node
        WHERE maasserver_node_tags.tag_id = NEW.id
        AND maasserver_node_tags.node_id = maasserver_node.id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a event is created.
# Sends a notify message for node_update or device_update depending on if the
# link node is installable.
EVENT_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION event_create_node_device_notify()
    RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node
      WHERE id = NEW.node_id;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a NodeGroupInterface is added, updated, or
# deleted from a `NodeGroup`. Sends a notify message for nodegroup_update.
NODEGROUP_INTERFACE_NODEGROUP_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      nodegroup RECORD;
    BEGIN
      PERFORM pg_notify('nodegroup_update',CAST(%s AS text));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a static ip address is linked or unlinked to
# a MAC address. Sends a notify message for node_update or device_update
# depending on if the node is installable.
MACSTATICIPADDRESSLINK_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node, maasserver_macaddress
      WHERE maasserver_node.id = maasserver_macaddress.node_id
      AND maasserver_macaddress.id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a dhcplease is added or removed and it matches
# a MAC address. Sends a notify message for node_update or device_update
# depending on if the node is installable.
DHCPLEASE_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node, maasserver_macaddress
      WHERE maasserver_node.id = maasserver_macaddress.node_id
      AND maasserver_macaddress.mac_address = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a node result is added or removed from a node.
# Sends a notify message for node_update or device_update depending on if the
# node is installable.
NODERESULT_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node
      WHERE id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a MAC address is added or removed from a node.
# Sends a notify message for node_update or device_update depending on if the
# node is installable.
MACADDRESS_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node
      WHERE id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a MAC address updated. Will send node_update
# or device_update when the MAC address is moved from another node to a new
# node. Sends a notify message for node_update or device_update depending on
# if the node is installable, both for the old node and the new node.
MACADDRESS_UPDATE_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION nd_macaddress_update_notify()
    RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      IF OLD.node_id != NEW.node_id THEN
        SELECT system_id, installable INTO node
        FROM maasserver_node
        WHERE id = OLD.node_id;

        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END IF;

      SELECT system_id, installable INTO node
      FROM maasserver_node
      WHERE id = NEW.node_id;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


def get_notification_procedure(proc_name, event_name, cast):
    return dedent("""\
        CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
        DECLARE
        BEGIN
          PERFORM pg_notify('%s',CAST(%s AS text));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """ % (proc_name, event_name, cast))


def register_trigger(table, procedure, event, params=None, when="after"):
    """Register `trigger` on `table` if it doesn't exist."""
    trigger_name = "%s_%s" % (table, procedure)
    if params is not None:
        filter = 'WHEN (' + ''.join(
            [
                "%s = '%s'" % (key, value)
                for key, value in params.items()
            ]) + ')'
    else:
        filter = ''
    trigger_sql = dedent("""\
        DROP TRIGGER IF EXISTS %s ON %s;
        CREATE TRIGGER %s
        %s %s ON %s
        FOR EACH ROW
        %s
        EXECUTE PROCEDURE %s();
        """) % (
        trigger_name,
        table,
        trigger_name,
        when.upper(),
        event.upper(),
        table,
        filter,
        procedure,
        )
    with closing(connection.cursor()) as cursor:
        cursor.execute(trigger_sql)


def register_procedure(procedure):
    """Register the `procedure` SQL."""
    with closing(connection.cursor()) as cursor:
        cursor.execute(procedure)


@transactional
def register_all_triggers():
    """Register all triggers into the database."""
    # Node(installable) table
    register_procedure(
        get_notification_procedure(
            'node_create_notify', 'node_create', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'node_update_notify', 'node_update', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'node_delete_notify', 'node_delete', 'OLD.system_id'))
    register_trigger(
        "maasserver_node", "node_create_notify", "insert",
        {'NEW.installable': True})
    register_trigger(
        "maasserver_node", "node_update_notify", "update",
        {'NEW.installable': True})
    register_trigger(
        "maasserver_node", "node_delete_notify", "delete",
        {'OLD.installable': True})

    # Node(device) table
    register_procedure(
        get_notification_procedure(
            'device_create_notify', 'device_create', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'device_update_notify', 'device_update', 'NEW.system_id'))
    register_procedure(
        get_notification_procedure(
            'device_delete_notify', 'device_delete', 'OLD.system_id'))
    register_trigger(
        "maasserver_node", "device_create_notify", "insert",
        {'NEW.installable': False})
    register_trigger(
        "maasserver_node", "device_update_notify", "update",
        {'NEW.installable': False})
    register_trigger(
        "maasserver_node", "device_delete_notify", "delete",
        {'OLD.installable': False})

    # Nodegroup table
    register_procedure(
        get_notification_procedure(
            'nodegroup_create_notify', 'nodegroup_create', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'nodegroup_update_notify', 'nodegroup_update', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'nodegroup_delete_notify', 'nodegroup_delete', 'OLD.id'))
    register_trigger(
        "maasserver_nodegroup", "nodegroup_create_notify", "insert")
    register_trigger(
        "maasserver_nodegroup", "nodegroup_update_notify", "update")
    register_trigger(
        "maasserver_nodegroup", "nodegroup_delete_notify", "delete")

    # Nodegroup interface table
    register_procedure(
        NODEGROUP_INTERFACE_NODEGROUP_NOTIFY % (
            'nodegroupinterface_create_notify',
            'NEW.nodegroup_id',
            ))
    register_procedure(
        NODEGROUP_INTERFACE_NODEGROUP_NOTIFY % (
            'nodegroupinterface_update_notify',
            'NEW.nodegroup_id',
            ))
    register_procedure(
        NODEGROUP_INTERFACE_NODEGROUP_NOTIFY % (
            'nodegroupinterface_delete_notify',
            'OLD.nodegroup_id',
            ))
    register_trigger(
        "maasserver_nodegroupinterface",
        "nodegroupinterface_create_notify", "insert")
    register_trigger(
        "maasserver_nodegroupinterface",
        "nodegroupinterface_update_notify", "update")
    register_trigger(
        "maasserver_nodegroupinterface",
        "nodegroupinterface_delete_notify", "delete")

    # Zone table
    register_procedure(
        get_notification_procedure(
            'zone_create_notify', 'zone_create', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'zone_update_notify', 'zone_update', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'zone_delete_notify', 'zone_delete', 'OLD.id'))
    register_trigger(
        "maasserver_zone", "zone_create_notify", "insert")
    register_trigger(
        "maasserver_zone", "zone_update_notify", "update")
    register_trigger(
        "maasserver_zone", "zone_delete_notify", "delete")

    # Node tag link table
    register_procedure(
        NODE_TAG_NOTIFY % (
            'node_device_tag_link_notify',
            'NEW.node_id',
            ))
    register_procedure(
        NODE_TAG_NOTIFY % (
            'node_device_tag_unlink_notify',
            'OLD.node_id',
            ))
    register_trigger(
        "maasserver_node_tags", "node_device_tag_link_notify", "insert")
    register_trigger(
        "maasserver_node_tags", "node_device_tag_unlink_notify", "delete")

    # Tag table, update to linked nodes.
    register_procedure(TAG_NODES_NOTIFY)
    register_trigger(
        "maasserver_tag", "tag_update_node_device_notify", "update")

    # User table
    register_procedure(
        get_notification_procedure(
            'user_create_notify', 'user_create', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'user_update_notify', 'user_update', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'user_delete_notify', 'user_delete', 'OLD.id'))
    register_trigger(
        "auth_user", "user_create_notify", "insert")
    register_trigger(
        "auth_user", "user_update_notify", "update")
    register_trigger(
        "auth_user", "user_delete_notify", "delete")

    # Events table
    register_procedure(
        get_notification_procedure(
            'event_create_notify', 'event_create', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'event_update_notify', 'event_update', 'NEW.id'))
    register_procedure(
        get_notification_procedure(
            'event_delete_notify', 'event_delete', 'OLD.id'))
    register_trigger(
        "maasserver_event", "event_create_notify", "insert")
    register_trigger(
        "maasserver_event", "event_update_notify", "update")
    register_trigger(
        "maasserver_event", "event_delete_notify", "delete")

    # Events table, update to linked node.
    register_procedure(EVENT_NODE_NOTIFY)
    register_trigger(
        "maasserver_event", "event_create_node_device_notify", "insert")

    # MAC static ip address table, update to linked node.
    register_procedure(
        MACSTATICIPADDRESSLINK_NODE_NOTIFY % (
            'nd_sipaddress_link_notify',
            'NEW.mac_address_id',
            ))
    register_procedure(
        MACSTATICIPADDRESSLINK_NODE_NOTIFY % (
            'nd_sipaddress_unlink_notify',
            'OLD.mac_address_id',
            ))
    register_trigger(
        "maasserver_macstaticipaddresslink",
        "nd_sipaddress_link_notify", "insert")
    register_trigger(
        "maasserver_macstaticipaddresslink",
        "nd_sipaddress_unlink_notify", "delete")

    # DHCP lease table, update to linked node.
    register_procedure(
        DHCPLEASE_NODE_NOTIFY % (
            'nd_dhcplease_match_notify',
            'NEW.mac',
            ))
    register_procedure(
        DHCPLEASE_NODE_NOTIFY % (
            'nd_dhcplease_unmatch_notify',
            'OLD.mac',
            ))
    register_trigger(
        "maasserver_dhcplease",
        "nd_dhcplease_match_notify", "insert")
    register_trigger(
        "maasserver_dhcplease",
        "nd_dhcplease_unmatch_notify", "delete")

    # Node result table, update to linked node.
    register_procedure(
        NODERESULT_NODE_NOTIFY % (
            'nd_noderesult_link_notify',
            'NEW.node_id',
            ))
    register_procedure(
        NODERESULT_NODE_NOTIFY % (
            'nd_noderesult_unlink_notify',
            'OLD.node_id',
            ))
    register_trigger(
        "metadataserver_noderesult",
        "nd_noderesult_link_notify", "insert")
    register_trigger(
        "metadataserver_noderesult",
        "nd_noderesult_unlink_notify", "delete")

    # MAC address table, update to linked node.
    register_procedure(
        MACADDRESS_NODE_NOTIFY % (
            'nd_macaddress_link_notify',
            'NEW.node_id',
            ))
    register_procedure(
        MACADDRESS_NODE_NOTIFY % (
            'nd_macaddress_unlink_notify',
            'OLD.node_id',
            ))
    register_procedure(MACADDRESS_UPDATE_NODE_NOTIFY)
    register_trigger(
        "maasserver_macaddress",
        "nd_macaddress_link_notify", "insert")
    register_trigger(
        "maasserver_macaddress",
        "nd_macaddress_unlink_notify", "delete")
    register_trigger(
        "maasserver_macaddress",
        "nd_macaddress_update_notify", "update")
