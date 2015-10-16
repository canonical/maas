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
# is tested (end-to-end testing) in test_listener.  We test it there because
# the asynchronous nature of the PG events makes it easier to test in
# test_listener where all the Twisted infrastructure is already in place.


# Procedure that is called when a tag is added or removed from a node/device.
# Sends a notify message for node_update or device_update depending on if the
# node is installable.
NODE_TAG_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      SELECT system_id, installable, parent_id INTO node
      FROM maasserver_node
      WHERE id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
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
      pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT
          maasserver_node.system_id,
          maasserver_node.installable,
          maasserver_node.parent_id
        FROM maasserver_node_tags, maasserver_node
        WHERE maasserver_node_tags.tag_id = NEW.id
        AND maasserver_node_tags.node_id = maasserver_node.id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
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
      pnode RECORD;
    BEGIN
      SELECT system_id, installable, parent_id INTO node
      FROM maasserver_node
      WHERE id = NEW.node_id;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
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


# Procedure that is called when a Subnet related to a NodeGroupInterface is
# updated. Sends a notify message for nodegroup_update.
SUBNET_NODEGROUP_INTERFACE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION subnet_update_nodegroup_notify()
    RETURNS trigger AS $$
    DECLARE
      nodegroup RECORD;
    BEGIN
      FOR nodegroup IN (
        SELECT ng.id
        FROM
          maasserver_nodegroup ng,
          maasserver_nodegroupinterface ngi,
          maasserver_subnet subnet
        WHERE subnet.id = ngi.subnet_id AND ngi.nodegroup_id = ng.id)
      LOOP
        PERFORM pg_notify('nodegroup_update',CAST(nodegroup.id AS text));
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a static ip address is linked or unlinked to
# an Interface. Sends a notify message for node_update or device_update
# depending on if the node is installable.
INTERFACE_IP_ADDRESS_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      SELECT system_id, installable, parent_id INTO node
      FROM maasserver_node, maasserver_interface
      WHERE maasserver_node.id = maasserver_interface.node_id
      AND maasserver_interface.id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a Interface address updated. Will send
# node_update or device_update when the Interface is moved from another node
# to a new node. Sends a notify message for node_update or device_update
# depending on if the node is installable, both for the old node and the
# new node.
INTERFACE_UPDATE_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION nd_interface_update_notify()
    RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      IF OLD.node_id != NEW.node_id THEN
        SELECT system_id, installable, parent_id INTO node
        FROM maasserver_node
        WHERE id = OLD.node_id;

        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END IF;

      SELECT system_id, installable, parent_id INTO node
      FROM maasserver_node
      WHERE id = NEW.node_id;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when a physical or virtual block device is updated.
# Sends a notify message for node_update or device_update depending on if the
# node is installable.
PHYSICAL_OR_VIRTUAL_BLOCK_DEVICE_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node, maasserver_blockdevice
      WHERE maasserver_node.id = maasserver_blockdevice.node_id
      AND maasserver_blockdevice.id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when the partition table on a block device is
# updated.
PARTITIONTABLE_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS TRIGGER AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node, maasserver_blockdevice
        WHERE maasserver_node.id = maasserver_blockdevice.node_id
        AND maasserver_blockdevice.id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when the partition on a partition table is updated.
PARTITION_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partitiontable
      WHERE maasserver_node.id = maasserver_blockdevice.node_id
      AND maasserver_blockdevice.id = maasserver_partitiontable.block_device_id
      AND maasserver_partitiontable.id = %s;

      IF node.installable THEN
        PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when the filesystem on a partition is updated.
FILESYSTEM_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partition,
           maasserver_partitiontable
      WHERE maasserver_node.id = maasserver_blockdevice.node_id
      AND (
        maasserver_blockdevice.id = %s
        OR (
          maasserver_blockdevice.id =
              maasserver_partitiontable.block_device_id
          AND maasserver_partitiontable.id =
              maasserver_partition.partition_table_id
          AND maasserver_partition.id = %s));

      IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when the filesystemgroup is updated.
FILESYSTEMGROUP_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partition,
           maasserver_partitiontable,
           maasserver_filesystem
      WHERE maasserver_node.id = maasserver_blockdevice.node_id
      AND maasserver_blockdevice.id = maasserver_partitiontable.block_device_id
      AND maasserver_partitiontable.id =
          maasserver_partition.partition_table_id
      AND maasserver_partition.id = maasserver_filesystem.partition_id
      AND (maasserver_filesystem.filesystem_group_id = %s
          OR maasserver_filesystem.cache_set_id = %s);

      IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when the cacheset is updated.
CACHESET_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, installable INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partition,
           maasserver_partitiontable,
           maasserver_filesystem
      WHERE maasserver_node.id = maasserver_blockdevice.node_id
      AND maasserver_blockdevice.id = maasserver_partitiontable.block_device_id
      AND maasserver_partitiontable.id =
          maasserver_partition.partition_table_id
      AND maasserver_partition.id = maasserver_filesystem.partition_id
      AND maasserver_filesystem.cache_set_id = %s;

      IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Procedure that is called when the subnet is updated.
SUBNET_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, installable, parent_id
        FROM
          maasserver_node,
          maasserver_subnet,
          maasserver_interface,
          maasserver_interface_ip_addresses AS ip_link,
          maasserver_staticipaddress
        WHERE maasserver_subnet.id = %s
        AND maasserver_staticipaddress.subnet_id = maasserver_subnet.id
        AND ip_link.staticipaddress_id = maasserver_staticipaddress.id
        AND ip_link.interface_id = maasserver_interface.id
        AND maasserver_node.id = maasserver_interface.node_id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when fabric is updated.
FABRIC_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, installable, parent_id
        FROM
          maasserver_node,
          maasserver_fabric,
          maasserver_interface,
          maasserver_vlan
        WHERE maasserver_fabric.id = %s
        AND maasserver_vlan.fabric_id = maasserver_fabric.id
        AND maasserver_node.id = maasserver_interface.node_id
        AND maasserver_vlan.id = maasserver_interface.vlan_id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when space is updated.
SPACE_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, installable, parent_id
        FROM
          maasserver_node,
          maasserver_space,
          maasserver_subnet,
          maasserver_interface,
          maasserver_interface_ip_addresses AS ip_link,
          maasserver_staticipaddress
        WHERE maasserver_space.id = %s
        AND maasserver_subnet.space_id = maasserver_space.id
        AND maasserver_staticipaddress.subnet_id = maasserver_subnet.id
        AND ip_link.staticipaddress_id = maasserver_staticipaddress.id
        AND ip_link.interface_id = maasserver_interface.id
        AND maasserver_node.id = maasserver_interface.node_id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when vlan is updated.
VLAN_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, installable, parent_id
        FROM maasserver_node, maasserver_interface, maasserver_vlan
        WHERE maasserver_vlan.id = %s
        AND maasserver_node.id = maasserver_interface.node_id
        AND maasserver_vlan.id = maasserver_interface.vlan_id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


# Procedure that is called when an IP address is updated to update the related
# node.
STATIC_IP_ADDRESS_NODE_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, installable, parent_id
        FROM
          maasserver_node,
          maasserver_interface,
          maasserver_interface_ip_addresses AS ip_link
        WHERE ip_link.staticipaddress_id = %s
        AND ip_link.interface_id = maasserver_interface.id
        AND maasserver_node.id = maasserver_interface.node_id)
      LOOP
        IF node.installable THEN
          PERFORM pg_notify('node_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Procedure that is called when an IP address is updated to update its related
# subnet.
STATIC_IP_ADDRESS_SUBNET_NOTIFY = dedent("""\
    CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
    BEGIN
      IF OLD.subnet_id != NEW.subnet_id THEN
        IF OLD.subnet_id IS NOT NULL THEN
          PERFORM pg_notify('subnet_update',CAST(OLD.subnet_id AS text));
        END IF;
      END IF;
      IF NEW.subnet_id IS NOT NULL THEN
        PERFORM pg_notify('subnet_update',CAST(NEW.subnet_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


def render_notification_procedure(proc_name, event_name, cast):
    return dedent("""\
        CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
        DECLARE
        BEGIN
          PERFORM pg_notify('%s',CAST(%s AS text));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """ % (proc_name, event_name, cast))


def render_device_notification_procedure(proc_name, event_name, obj):
    return dedent("""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
          pnode RECORD;
        BEGIN
          IF {obj}.parent_id IS NOT NULL THEN
            SELECT system_id INTO pnode
            FROM maasserver_node
            WHERE id = {obj}.parent_id;
            PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
          ELSE
            PERFORM pg_notify('{event_name}',CAST({obj}.system_id AS text));
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """.format(proc_name=proc_name, event_name=event_name, obj=obj))


def render_node_related_notification_procedure(proc_name, node_id_relation):
    return dedent("""\
        CREATE OR REPLACE FUNCTION %s() RETURNS trigger AS $$
        DECLARE
          node RECORD;
          pnode RECORD;
        BEGIN
          SELECT system_id, installable, parent_id INTO node
          FROM maasserver_node
          WHERE id = %s;

          IF node.installable THEN
            PERFORM pg_notify('node_update',CAST(node.system_id AS text));
          ELSIF node.parent_id IS NOT NULL THEN
            SELECT system_id INTO pnode
            FROM maasserver_node
            WHERE id = node.parent_id;
            PERFORM pg_notify('node_update',CAST(pnode.system_id AS text));
          ELSE
            PERFORM pg_notify('device_update',CAST(node.system_id AS text));
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """ % (proc_name, node_id_relation))


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
        render_notification_procedure(
            'node_create_notify', 'node_create', 'NEW.system_id'))
    register_procedure(
        render_notification_procedure(
            'node_update_notify', 'node_update', 'NEW.system_id'))
    register_procedure(
        render_notification_procedure(
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
        render_device_notification_procedure(
            'device_create_notify', 'device_create', 'NEW'))
    register_procedure(
        render_device_notification_procedure(
            'device_update_notify', 'device_update', 'NEW'))
    register_procedure(
        render_device_notification_procedure(
            'device_delete_notify', 'device_delete', 'OLD'))
    register_trigger(
        "maasserver_node", "device_create_notify", "insert",
        {'NEW.installable': False})
    register_trigger(
        "maasserver_node", "device_update_notify", "update",
        {'NEW.installable': False})
    register_trigger(
        "maasserver_node", "device_delete_notify", "delete",
        {'OLD.installable': False})

    # VLAN table
    register_procedure(
        render_notification_procedure(
            'vlan_create_notify', 'vlan_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'vlan_update_notify', 'vlan_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'vlan_delete_notify', 'vlan_delete', 'OLD.id'))
    register_trigger(
        "maasserver_vlan", "vlan_create_notify", "insert")
    register_trigger(
        "maasserver_vlan", "vlan_update_notify", "update")
    register_trigger(
        "maasserver_vlan", "vlan_delete_notify", "delete")

    # Fabric table
    register_procedure(
        render_notification_procedure(
            'fabric_create_notify', 'fabric_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'fabric_update_notify', 'fabric_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'fabric_delete_notify', 'fabric_delete', 'OLD.id'))
    register_trigger(
        "maasserver_fabric", "fabric_create_notify", "insert")
    register_trigger(
        "maasserver_fabric", "fabric_update_notify", "update")
    register_trigger(
        "maasserver_fabric", "fabric_delete_notify", "delete")

    # Space table
    register_procedure(
        render_notification_procedure(
            'space_create_notify', 'space_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'space_update_notify', 'space_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'space_delete_notify', 'space_delete', 'OLD.id'))
    register_trigger(
        "maasserver_space", "space_create_notify", "insert")
    register_trigger(
        "maasserver_space", "space_update_notify", "update")
    register_trigger(
        "maasserver_space", "space_delete_notify", "delete")

    # Subnet table
    register_procedure(
        render_notification_procedure(
            'subnet_create_notify', 'subnet_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'subnet_update_notify', 'subnet_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'subnet_delete_notify', 'subnet_delete', 'OLD.id'))
    register_trigger(
        "maasserver_subnet", "subnet_create_notify", "insert")
    register_trigger(
        "maasserver_subnet", "subnet_update_notify", "update")
    register_trigger(
        "maasserver_subnet", "subnet_delete_notify", "delete")

    # Nodegroup table
    register_procedure(
        render_notification_procedure(
            'nodegroup_create_notify', 'nodegroup_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'nodegroup_update_notify', 'nodegroup_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
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

    register_procedure(SUBNET_NODEGROUP_INTERFACE_NOTIFY)
    register_trigger(
        "maasserver_subnet", "subnet_update_nodegroup_notify", "update")

    # Subnet node notifications
    register_procedure(
        SUBNET_NODE_NOTIFY % ('subnet_node_update_notify', 'NEW.id',))
    register_trigger(
        "maasserver_subnet",
        "subnet_node_update_notify", "update")

    # Fabric node notifications
    register_procedure(
        FABRIC_NODE_NOTIFY % ('fabric_node_update_notify', 'NEW.id',))
    register_trigger(
        "maasserver_fabric",
        "fabric_node_update_notify", "update")

    # Space node notifications
    register_procedure(
        SPACE_NODE_NOTIFY % ('space_node_update_notify', 'NEW.id',))
    register_trigger(
        "maasserver_space",
        "space_node_update_notify", "update")

    # VLAN node notifications
    register_procedure(
        VLAN_NODE_NOTIFY % ('vlan_node_update_notify', 'NEW.id',))
    register_trigger(
        "maasserver_vlan",
        "vlan_node_update_notify", "update")

    # IP address node notifications
    register_procedure(
        STATIC_IP_ADDRESS_NODE_NOTIFY % (
            'ipaddress_node_update_notify', 'NEW.id',))
    register_trigger(
        "maasserver_staticipaddress",
        "ipaddress_node_update_notify", "update")

    # IP address subnet notifications
    register_procedure(
        STATIC_IP_ADDRESS_SUBNET_NOTIFY % 'ipaddress_subnet_update_notify')
    register_trigger(
        "maasserver_staticipaddress",
        "ipaddress_subnet_update_notify", "update")

    # Zone table
    register_procedure(
        render_notification_procedure(
            'zone_create_notify', 'zone_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'zone_update_notify', 'zone_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'zone_delete_notify', 'zone_delete', 'OLD.id'))
    register_trigger(
        "maasserver_zone", "zone_create_notify", "insert")
    register_trigger(
        "maasserver_zone", "zone_update_notify", "update")
    register_trigger(
        "maasserver_zone", "zone_delete_notify", "delete")

    # Tag table
    register_procedure(
        render_notification_procedure(
            'tag_create_notify', 'tag_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'tag_update_notify', 'tag_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'tag_delete_notify', 'tag_delete', 'OLD.id'))
    register_trigger(
        "maasserver_tag", "tag_create_notify", "insert")
    register_trigger(
        "maasserver_tag", "tag_update_notify", "update")
    register_trigger(
        "maasserver_tag", "tag_delete_notify", "delete")

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
        render_notification_procedure(
            'user_create_notify', 'user_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'user_update_notify', 'user_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'user_delete_notify', 'user_delete', 'OLD.id'))
    register_trigger(
        "auth_user", "user_create_notify", "insert")
    register_trigger(
        "auth_user", "user_update_notify", "update")
    register_trigger(
        "auth_user", "user_delete_notify", "delete")

    # Events table
    register_procedure(
        render_notification_procedure(
            'event_create_notify', 'event_create', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
            'event_update_notify', 'event_update', 'NEW.id'))
    register_procedure(
        render_notification_procedure(
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
        INTERFACE_IP_ADDRESS_NODE_NOTIFY % (
            'nd_sipaddress_link_notify',
            'NEW.interface_id',
            ))
    register_procedure(
        INTERFACE_IP_ADDRESS_NODE_NOTIFY % (
            'nd_sipaddress_unlink_notify',
            'OLD.interface_id',
            ))
    register_trigger(
        "maasserver_interface_ip_addresses",
        "nd_sipaddress_link_notify", "insert")
    register_trigger(
        "maasserver_interface_ip_addresses",
        "nd_sipaddress_unlink_notify", "delete")

    # Node result table, update to linked node.
    register_procedure(
        render_node_related_notification_procedure(
            'nd_noderesult_link_notify', 'NEW.node_id'))
    register_procedure(
        render_node_related_notification_procedure(
            'nd_noderesult_unlink_notify', 'OLD.node_id'))
    register_trigger(
        "metadataserver_noderesult",
        "nd_noderesult_link_notify", "insert")
    register_trigger(
        "metadataserver_noderesult",
        "nd_noderesult_unlink_notify", "delete")

    # Interface address table, update to linked node.
    register_procedure(
        render_node_related_notification_procedure(
            'nd_interface_link_notify', 'NEW.node_id'))
    register_procedure(
        render_node_related_notification_procedure(
            'nd_interface_unlink_notify', 'OLD.node_id'))
    register_procedure(INTERFACE_UPDATE_NODE_NOTIFY)
    register_trigger(
        "maasserver_interface",
        "nd_interface_link_notify", "insert")
    register_trigger(
        "maasserver_interface",
        "nd_interface_unlink_notify", "delete")
    register_trigger(
        "maasserver_interface",
        "nd_interface_update_notify", "update")

    # Block device table, update to linked node.
    register_procedure(
        render_node_related_notification_procedure(
            'nd_blockdevice_link_notify', 'NEW.node_id'))
    register_procedure(
        render_node_related_notification_procedure(
            'nd_blockdevice_update_notify', 'NEW.node_id'))
    register_procedure(
        render_node_related_notification_procedure(
            'nd_blockdevice_unlink_notify', 'OLD.node_id'))
    register_procedure(
        PHYSICAL_OR_VIRTUAL_BLOCK_DEVICE_NODE_NOTIFY % (
            'nd_physblockdevice_update_notify', 'NEW.blockdevice_ptr_id'))
    register_procedure(
        PHYSICAL_OR_VIRTUAL_BLOCK_DEVICE_NODE_NOTIFY % (
            'nd_virtblockdevice_update_notify', 'NEW.blockdevice_ptr_id'))
    register_trigger(
        "maasserver_blockdevice",
        "nd_blockdevice_link_notify", "insert")
    register_trigger(
        "maasserver_blockdevice",
        "nd_blockdevice_update_notify", "update")
    register_trigger(
        "maasserver_blockdevice",
        "nd_blockdevice_unlink_notify", "delete")
    register_trigger(
        "maasserver_physicalblockdevice",
        "nd_physblockdevice_update_notify", "update")
    register_trigger(
        "maasserver_virtualblockdevice",
        "nd_virtblockdevice_update_notify", "update")

    # Partition table, update to linked user.
    register_procedure(
        PARTITIONTABLE_NODE_NOTIFY % (
            'nd_partitiontable_link_notify', 'NEW.block_device_id'))
    register_procedure(
        PARTITIONTABLE_NODE_NOTIFY % (
            'nd_partitiontable_update_notify', 'NEW.block_device_id'))
    register_procedure(
        PARTITIONTABLE_NODE_NOTIFY % (
            'nd_partitiontable_unlink_notify', 'OLD.block_device_id'))
    register_trigger(
        "maasserver_partitiontable",
        "nd_partitiontable_link_notify", "insert")
    register_trigger(
        "maasserver_partitiontable",
        "nd_partitiontable_update_notify", "update")
    register_trigger(
        "maasserver_partitiontable",
        "nd_partitiontable_unlink_notify", "delete")

    # Partition, update to linked user.
    register_procedure(
        PARTITION_NODE_NOTIFY % (
            'nd_partition_link_notify', 'NEW.partition_table_id'))
    register_procedure(
        PARTITION_NODE_NOTIFY % (
            'nd_partition_update_notify', 'NEW.partition_table_id'))
    register_procedure(
        PARTITION_NODE_NOTIFY % (
            'nd_partition_unlink_notify', 'OLD.partition_table_id'))
    register_trigger(
        "maasserver_partition",
        "nd_partition_link_notify", "insert")
    register_trigger(
        "maasserver_partition",
        "nd_partition_update_notify", "update")
    register_trigger(
        "maasserver_partition",
        "nd_partition_unlink_notify", "delete")

    # Filesystem, update to linked user.
    register_procedure(
        FILESYSTEM_NODE_NOTIFY % (
            'nd_filesystem_link_notify', 'NEW.block_device_id',
            'NEW.partition_id'))
    register_procedure(
        FILESYSTEM_NODE_NOTIFY % (
            'nd_filesystem_update_notify', 'NEW.block_device_id',
            'NEW.partition_id'))
    register_procedure(
        FILESYSTEM_NODE_NOTIFY % (
            'nd_filesystem_unlink_notify', 'OLD.block_device_id',
            'OLD.partition_id'))
    register_trigger(
        "maasserver_filesystem",
        "nd_filesystem_link_notify", "insert")
    register_trigger(
        "maasserver_filesystem",
        "nd_filesystem_update_notify", "update")
    register_trigger(
        "maasserver_filesystem",
        "nd_filesystem_unlink_notify", "delete")

    # Filesystemgroup, update to linked user.
    register_procedure(
        FILESYSTEMGROUP_NODE_NOTIFY % (
            'nd_filesystemgroup_link_notify', 'NEW.id', 'NEW.cache_set_id'))
    register_procedure(
        FILESYSTEMGROUP_NODE_NOTIFY % (
            'nd_filesystemgroup_update_notify', 'NEW.id', 'NEW.cache_set_id'))
    register_procedure(
        FILESYSTEMGROUP_NODE_NOTIFY % (
            'nd_filesystemgroup_unlink_notify', 'OLD.id', 'OLD.cache_set_id'))
    register_trigger(
        "maasserver_filesystemgroup",
        "nd_filesystemgroup_link_notify", "insert")
    register_trigger(
        "maasserver_filesystemgroup",
        "nd_filesystemgroup_update_notify", "update")
    register_trigger(
        "maasserver_filesystemgroup",
        "nd_filesystemgroup_unlink_notify", "delete")

    # Cacheset, update to linked user.
    register_procedure(
        CACHESET_NODE_NOTIFY % (
            'nd_cacheset_link_notify', 'NEW.id'))
    register_procedure(
        CACHESET_NODE_NOTIFY % (
            'nd_cacheset_update_notify', 'NEW.id'))
    register_procedure(
        CACHESET_NODE_NOTIFY % (
            'nd_cacheset_unlink_notify', 'OLD.id'))
    register_trigger(
        "maasserver_cacheset",
        "nd_cacheset_link_notify", "insert")
    register_trigger(
        "maasserver_cacheset",
        "nd_cacheset_update_notify", "update")
    register_trigger(
        "maasserver_cacheset",
        "nd_cacheset_unlink_notify", "delete")

    # SSH key table, update to linked user.
    register_procedure(
        render_notification_procedure(
            'user_sshkey_link_notify', 'user_update', 'NEW.user_id'))
    register_procedure(
        render_notification_procedure(
            'user_sshkey_unlink_notify', 'user_update', 'OLD.user_id'))
    register_trigger(
        "maasserver_sshkey", "user_sshkey_link_notify", "insert")
    register_trigger(
        "maasserver_sshkey", "user_sshkey_unlink_notify", "delete")

    # SSL key table, update to linked user.
    register_procedure(
        render_notification_procedure(
            'user_sslkey_link_notify', 'user_update', 'NEW.user_id'))
    register_procedure(
        render_notification_procedure(
            'user_sslkey_unlink_notify', 'user_update', 'OLD.user_id'))
    register_trigger(
        "maasserver_sslkey", "user_sslkey_link_notify", "insert")
    register_trigger(
        "maasserver_sslkey", "user_sslkey_unlink_notify", "delete")
