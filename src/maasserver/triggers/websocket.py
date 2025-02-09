# Copyright 2015-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Websocket Triggers

Each trigger will call a procedure to send the notification. Each procedure
should be named with the table name "maasserver_node" and the action for the
trigger "node_create" followed by "notify".

E.g. "maasserver_node_node_create_notify".
"""

import logging
from textwrap import dedent

from maasserver.enum import BMC_TYPE, NODE_TYPE
from maasserver.triggers import (
    EVENTS_IUD,
    EVENTS_LU,
    EVENTS_LUU,
    register_procedure,
    register_trigger,
    register_triggers,
)
from maasserver.utils.orm import transactional

# Note that the corresponding test module (test_triggers) only tests that the
# triggers and procedures are registered.  The behavior of these procedures
# is tested (end-to-end testing) in test_listener.  We test it there because
# the asynchronous nature of the PG events makes it easier to test in
# test_listener where all the Twisted infrastructure is already in place.

TYPE_CONTROLLERS = (
    f"({NODE_TYPE.RACK_CONTROLLER}, {NODE_TYPE.REGION_CONTROLLER}, "
    f"{NODE_TYPE.REGION_AND_RACK_CONTROLLER})"
)

# Procedure that is called when a tag is added or removed from a node/device.
# Sends a notify message for machine_update or device_update depending on if
# the node type is node.
NODE_TAG_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      SELECT system_id, node_type, parent_id INTO node
      FROM maasserver_node
      WHERE id = {entry}.node_id;

      IF node.node_type = {type_machine} THEN
        PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      ELSIF node.node_type IN {type_controllers} THEN
        PERFORM pg_notify('controller_update', CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('machine_update', CAST(pnode.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update', CAST(node.system_id AS text));
      END IF;
      PERFORM pg_notify('tag_update', CAST({entry}.tag_id AS text));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a tag is updated. This will send the correct
# machine_update or device_update notify message for all nodes with this tag.
TAG_NODES_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION tag_update_machine_device_notify()
    RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT
          maasserver_node.system_id,
          maasserver_node.node_type,
          maasserver_node.parent_id
        FROM maasserver_node_tags, maasserver_node
        WHERE maasserver_node_tags.tag_id = NEW.id
        AND maasserver_node_tags.node_id = maasserver_node.id)
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a VM cluster is created.
VMCLUSTER_INSERT_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION vmcluster_insert_notify() RETURNS trigger AS $$
    BEGIN
        PERFORM pg_notify('vmcluster_create',CAST(NEW.id AS text));
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a VM cluster is updated
VMCLUSTER_UPDATE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION vmcluster_update_notify() RETURNS trigger AS $$
    BEGIN
        PERFORM pg_notify('vmcluster_update',CAST(NEW.id AS text));
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a VM cluster is deleted
VMCLUSTER_DELETE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION vmcluster_delete_notify() RETURNS trigger AS $$
    BEGIN
        PERFORM pg_notify('vmcluster_delete',CAST(OLD.id as text));
        RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a pod is created.
POD_INSERT_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION pod_insert_notify() RETURNS trigger AS $$
    BEGIN
      IF NEW.bmc_type = {BMC_TYPE.POD} THEN
        PERFORM pg_notify('pod_create',CAST(NEW.id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a pod is updated.
POD_UPDATE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION pod_update_notify() RETURNS trigger AS $$
    BEGIN
      IF OLD.bmc_type = NEW.bmc_type THEN
        IF OLD.bmc_type = {BMC_TYPE.POD} THEN
          PERFORM pg_notify('pod_update',CAST(OLD.id AS text));
        END IF;
      ELSIF OLD.bmc_type = {BMC_TYPE.BMC} AND NEW.bmc_type = {BMC_TYPE.POD} THEN
          PERFORM pg_notify('pod_create',CAST(NEW.id AS text));
      ELSIF OLD.bmc_type = {BMC_TYPE.POD} AND NEW.bmc_type = {BMC_TYPE.BMC} THEN
          PERFORM pg_notify('pod_delete',CAST(OLD.id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a pod is deleted.
POD_DELETE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION pod_delete_notify() RETURNS trigger AS $$
    BEGIN
      IF OLD.bmc_type = {BMC_TYPE.POD} THEN
          PERFORM pg_notify('pod_delete',CAST(OLD.id AS text));
      END IF;
      RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a machine is created to update its
# related VMCluster, if one exists
NODE_VMCLUSTER_INSERT_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_vmcluster_insert_notify() RETURNS trigger AS $$
    DECLARE
      bmc RECORD;
      hints RECORD;
    BEGIN
      IF NEW.bmc_id IS NOT NULL THEN
        SELECT * INTO bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
        IF bmc.bmc_type = {BMC_TYPE.POD} THEN
          SELECT * INTO hints FROM maasserver_podhints WHERE pod_id = bmc.id;
          IF hints IS NOT NULL AND hints.cluster_id IS NOT NULL THEN
            PERFORM pg_notify('vmcluster_update',CAST(hints.cluster_id AS text));
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

NODE_VMCLUSTER_UPDATE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_vmcluster_update_notify() RETURNS trigger AS $$
    DECLARE
      bmc_type INT;
      new_bmc RECORD;
      old_bmc RECORD;
      old_hints RECORD;
      new_hints RECORD;
    BEGIN
      bmc_type = {BMC_TYPE.POD};
      IF OLD.bmc_id IS NOT NULL AND NEW.bmc_id IS NOT NULL THEN
        IF OLD.bmc_id = NEW.bmc_id THEN
          SELECT * INTO new_bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
          IF new_bmc.bmc_type = bmc_type THEN
            SELECT * INTO new_hints FROM maasserver_podhints WHERE pod_id = new_bmc.id;
            IF new_hints IS NOT NULL AND new_hints.cluster_id is NOT NULL THEN
              PERFORM pg_notify('vmcluster_update',CAST(new_hints.cluster_id AS text));
            END IF;
          END IF;
        ELSE
          SELECT * INTO new_bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
          SELECT * INTO old_bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
          IF new_bmc.bmc_type = bmc_type THEN
            SELECT * INTO new_hints FROM maasserver_podhints WHERE pod_id = new_bmc.id;
          END IF;
          IF old_bmc.bmc_type = bmc_type THEN
            SELECT * INTO old_hints FROM maasserver_podhints WHERE pod_id = old_bmc.id;
          END IF;
          IF old_hints IS NOT NULL THEN
            IF old_hints.cluster_id IS NOT NULL THEN
              PERFORM pg_notify('vmcluster_update',CAST(old_hints.cluster_id as text));
            END IF;
            IF new_hints IS NOT NULL THEN
              IF new_hints.cluster_id IS NOT NULL AND new_hints.cluster_id != old_hints.cluster_id THEN
                PERFORM pg_notify('vmcluster_update',CAST(new_hints.cluster_id as text));
              END IF;
            END IF;
          END IF;
          IF new_hints IS NOT NULL THEN
            IF new_hints.cluster_id IS NOT NULL AND old_hints IS NULL THEN
              PERFORM pg_notify('vmcluster_update',CAST(new_hints.cluster_id as text));
            END IF;
          END IF;
        END IF;
      ELSE
        IF OLD.bmc_id IS NOT NULL THEN
          SELECT * INTO old_bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
          IF old_bmc.bmc_type = bmc_type THEN
            SELECT * INTO old_hints FROM maasserver_podhints WHERE pod_id = old_bmc.id;
            IF old_hints IS NOT NULL AND old_hints.cluster_id IS NOT NULL THEN
              PERFORM pg_notify('vmcluster_update',CAST(old_hints.cluster_id as text));
            END IF;
          END IF;
        END IF;
        IF NEW.bmc_id IS NOT NULL THEN
          SELECT * INTO new_bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
          IF new_bmc.bmc_type = bmc_type THEN
            SELECT * INTO new_hints FROM maasserver_podhints WHERE pod_id = new_bmc.id;
            IF new_hints IS NOT NULL AND new_hints.cluster_id IS NOT NULL THEN
              PERFORM pg_notify('vmcluster_update',CAST(new_hints.cluster_id as text));
            END IF;
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

NODE_VMCLUSTER_DELETE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_vmcluster_delete_notify() RETURNS trigger AS $$
    DECLARE
      bmc RECORD;
      hints RECORD;
    BEGIN
      IF OLD.bmc_id IS NOT NULL THEN
        SELECT * INTO bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
        IF bmc.bmc_type = {BMC_TYPE.POD} THEN
          SELECT * INTO hints FROM maasserver_podhints WHERE pod_id = bmc.id;
          IF hints.cluster_id IS NOT NULL THEN
            PERFORM pg_notify('vmcluster_update',CAST(hints.cluster_id AS text));
          END IF;
        END IF;
      END IF;
      RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when a machine is created to update its related
# bmc if bmc_type is pod.
NODE_POD_INSERT_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_pod_insert_notify() RETURNS trigger AS $$
    DECLARE
      bmc RECORD;
    BEGIN
      IF NEW.bmc_id IS NOT NULL THEN
        SELECT * INTO bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
        IF bmc.bmc_type = {BMC_TYPE.POD} THEN
          PERFORM pg_notify('pod_update',CAST(NEW.bmc_id AS text));
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a machine is updated to update its related
# bmc if bmc_type is pod.
NODE_POD_UPDATE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_pod_update_notify() RETURNS trigger AS $$
    DECLARE
      bmc RECORD;
    BEGIN
      IF ((OLD.bmc_id IS NULL and NEW.bmc_id IS NOT NULL) OR
          (OLD.bmc_id IS NOT NULL and NEW.bmc_id IS NULL) OR
          OLD.bmc_id != NEW.bmc_id) THEN
        IF OLD.bmc_id IS NOT NULL THEN
          SELECT * INTO bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
          IF bmc.bmc_type = {BMC_TYPE.POD} THEN
            PERFORM pg_notify('pod_update',CAST(OLD.bmc_id AS text));
          END IF;
        END IF;
      END IF;
      IF NEW.bmc_id IS NOT NULL THEN
        SELECT * INTO bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
        IF bmc.bmc_type = {BMC_TYPE.POD} THEN
          PERFORM pg_notify('pod_update',CAST(NEW.bmc_id AS text));
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a machine is deleted to update its related
# bmc if bmc_type is pod.
NODE_POD_DELETE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_pod_delete_notify() RETURNS trigger AS $$
    DECLARE
      bmc RECORD;
    BEGIN
      IF OLD.bmc_id IS NOT NULL THEN
        SELECT * INTO bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
        IF bmc.bmc_type = {BMC_TYPE.POD} THEN
          PERFORM pg_notify('pod_update',CAST(OLD.bmc_id AS text));
        END IF;
      END IF;
      RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """
)

INTERFACE_POD_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION interface_pod_notify() RETURNS TRIGGER AS $$
    DECLARE
        _node_id BIGINT;
        _pod_id BIGINT;
    BEGIN
        IF TG_OP = 'INSERT' then
            SELECT INTO _pod_id pod_id
            FROM maasserver_podhost
            JOIN maasserver_nodeconfig
              ON maasserver_nodeconfig.node_id = maasserver_podhost.node_id
            WHERE maasserver_nodeconfig.id = NEW.node_config_id;

            IF _pod_id IS NOT NULL then
              PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
            END IF;
        ELSIF TG_OP = 'UPDATE' then
            IF OLD.vlan_id IS NOT DISTINCT FROM NEW.vlan_id
                AND OLD.node_config_id IS NOT DISTINCT FROM NEW.node_config_id then
                -- Nothing relevant changed during interface update.
                RETURN NULL;
            END IF;

            SELECT INTO _pod_id pod_id
            FROM maasserver_podhost
            JOIN maasserver_nodeconfig
              ON maasserver_nodeconfig.node_id = maasserver_podhost.node_id
            WHERE maasserver_nodeconfig.id = NEW.node_config_id;

            IF _pod_id IS NOT NULL then
              PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
            END IF;
            IF OLD.node_config_id != NEW.node_config_id then
              SELECT INTO _pod_id pod_id
              FROM maasserver_podhost
              JOIN maasserver_nodeconfig
                ON maasserver_nodeconfig.node_id = maasserver_podhost.node_id
              WHERE maasserver_nodeconfig.id = OLD.node_config_id;

              IF _pod_id IS NOT NULL then
                PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
              END IF;
            END IF;
        ELSE
            SELECT INTO _pod_id pod_id
            FROM maasserver_podhost
            JOIN maasserver_nodeconfig
              ON maasserver_nodeconfig.node_id = maasserver_podhost.node_id
            WHERE maasserver_nodeconfig.id = OLD.node_config_id;

            IF _pod_id IS NOT NULL then
              PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
            END IF;
        END IF;
        RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when a static ip address is linked or unlinked to
# an Interface. Sends a notify message for domain_update
INTERFACE_IP_ADDRESS_DOMAIN_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      domain RECORD;
    BEGIN
      SELECT maasserver_domain.id INTO domain
      FROM maasserver_interface
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.id = maasserver_interface.node_config_id
      JOIN maasserver_node
        ON maasserver_node.id = maasserver_nodeconfig.node_id
      JOIN maasserver_domain
        ON maasserver_domain.id = maasserver_node.domain_id
      WHERE maasserver_interface.id = {entry}.interface_id;

      IF domain.id IS NOT NULL THEN
        PERFORM pg_notify('domain_update',CAST(domain.id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a static ip address is linked or unlinked to
# an Interface. Sends a notify message for machine_update or device_update
# depending on if the node type is node.
INTERFACE_IP_ADDRESS_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      SELECT system_id, node_type, parent_id INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      JOIN maasserver_interface
        ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
      WHERE maasserver_interface.id = {entry}.interface_id;

      IF node.node_type = {type_machine} THEN
        PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
      ELSIF node.node_type IN {type_controllers} THEN
        PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a Interface address updated. Will send
# machine_update or device_update when the Interface is moved from another node
# to a new node. Sends a notify message for machine_update or device_update
# depending on if the node type is node, both for the old node and the new
# node.
INTERFACE_UPDATE_NODE_NOTIFY = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION nd_interface_update_notify()
    RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      IF OLD.node_config_id != NEW.node_config_id THEN
        SELECT system_id, node_type, parent_id INTO node
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        WHERE maasserver_nodeconfig.id = OLD.node_config_id;

        IF node.node_type = {NODE_TYPE.MACHINE} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {TYPE_CONTROLLERS} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END IF;

      SELECT system_id, node_type, parent_id INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      WHERE maasserver_nodeconfig.id = NEW.node_config_id;

      IF node.node_type = {NODE_TYPE.MACHINE} THEN
        PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
      ELSIF node.node_type IN {TYPE_CONTROLLERS} THEN
        PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
      ELSIF node.parent_id IS NOT NULL THEN
        SELECT system_id INTO pnode
        FROM maasserver_node
        WHERE id = node.parent_id;
        PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
      ELSE
        PERFORM pg_notify('device_update',CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a physical or virtual block device is updated.
# Sends a notify message for machine_update or device_update depending on if
# the node type is node.
PHYSICAL_OR_VIRTUAL_BLOCK_DEVICE_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, node_type INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      JOIN maasserver_blockdevice
        ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
      WHERE maasserver_blockdevice.id = {entry}.blockdevice_ptr_id;

      IF node.node_type = {machine_type} THEN
        PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when the partition table on a block device is
# updated.
PARTITIONTABLE_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS TRIGGER AS $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, node_type INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      JOIN maasserver_blockdevice
        ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
      WHERE maasserver_blockdevice.id = {entry}.block_device_id;

      IF node.node_type = {machine_type} THEN
        PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when the partition on a partition table is updated.
PARTITION_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, node_type INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      JOIN maasserver_blockdevice
        ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
      JOIN maasserver_partitiontable
        ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
      WHERE maasserver_partitiontable.id = {entry}.partition_table_id;

      IF node.node_type = {machine_type} THEN
        PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when the filesystem on a partition is updated.
FILESYSTEM_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      IF {entry}.block_device_id IS NOT NULL
      THEN
        SELECT system_id, node_type INTO node
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_blockdevice
          ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
        WHERE maasserver_blockdevice.id = {entry}.block_device_id;
      ELSIF {entry}.partition_id IS NOT NULL
      THEN
        SELECT system_id, node_type INTO node
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_blockdevice
          ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
        JOIN maasserver_partitiontable
          ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
        JOIN maasserver_partition
          ON maasserver_partition.partition_table_id = maasserver_partitiontable.id
        WHERE maasserver_partition.id = {entry}.partition_id;
      ELSE
        SELECT system_id, node_type INTO node
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        WHERE {entry}.node_config_id = maasserver_nodeconfig.id;
      END IF;

      IF node.node_type = {machine_type} THEN
          PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      END IF;

      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when the filesystemgroup is updated.
FILESYSTEMGROUP_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, node_type INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      JOIN maasserver_blockdevice
        ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
      JOIN maasserver_partitiontable
        ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
      JOIN maasserver_partition
        ON maasserver_partition.partition_table_id = maasserver_partitiontable.id
      JOIN maasserver_filesystem
        ON maasserver_filesystem.partition_id = maasserver_partition.id
      WHERE maasserver_filesystem.filesystem_group_id = {entry}.id
        OR maasserver_filesystem.cache_set_id = {entry}.cache_set_id;

      IF node.node_type = {machine_type} THEN
          PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when the cacheset is updated.
CACHESET_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger as $$
    DECLARE
      node RECORD;
    BEGIN
      SELECT system_id, node_type INTO node
      FROM maasserver_node
      JOIN maasserver_nodeconfig
        ON maasserver_nodeconfig.node_id = maasserver_node.id
      JOIN maasserver_blockdevice
        ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
      JOIN maasserver_partitiontable
        ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
      JOIN maasserver_partition
        ON maasserver_partition.partition_table_id = maasserver_partitiontable.id
      JOIN maasserver_filesystem
        ON maasserver_filesystem.partition_id = maasserver_partition.id
      WHERE maasserver_filesystem.cache_set_id = {entry}.id;

      IF node.node_type = {machine_type} THEN
          PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when the subnet is updated.
SUBNET_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, node_type, parent_id
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_interface
          ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
        JOIN maasserver_interface_ip_addresses
          ON maasserver_interface_ip_addresses.interface_id = maasserver_interface.id
        JOIN maasserver_staticipaddress
          ON maasserver_staticipaddress.id = maasserver_interface_ip_addresses.staticipaddress_id
        WHERE maasserver_staticipaddress.subnet_id = {entry}.id
      )
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when fabric is updated.
FABRIC_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, node_type, parent_id
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_interface
          ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
        JOIN maasserver_vlan
          ON maasserver_vlan.id = maasserver_interface.vlan_id
        JOIN maasserver_fabric
          ON maasserver_vlan.fabric_id = maasserver_fabric.id
        WHERE maasserver_fabric.id = {entry}.id
      )
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when space is updated.
SPACE_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, node_type, parent_id
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_interface
          ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
        JOIN maasserver_interface_ip_addresses
          ON maasserver_interface_ip_addresses.interface_id = maasserver_interface.id
        JOIN maasserver_staticipaddress
          ON maasserver_staticipaddress.id = maasserver_interface_ip_addresses.staticipaddress_id
        JOIN maasserver_subnet
          ON maasserver_staticipaddress.subnet_id = maasserver_subnet.id
        JOIN maasserver_vlan
          ON maasserver_vlan.id = maasserver_subnet.vlan_id
        JOIN maasserver_space
          ON maasserver_vlan.space_id IS NOT DISTINCT FROM maasserver_space.id
        WHERE maasserver_space.id = {entry}.id
      )
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when vlan is updated.
VLAN_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, node_type, parent_id
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_interface
          ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
        WHERE maasserver_interface.vlan_id = {entry}.id
      )
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when BMC is updated
BMC_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      node RECORD;
    BEGIN
      FOR node IN (
        SELECT system_id, node_type
        FROM maasserver_node
        WHERE bmc_id = {entry}.id)
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when en event is created linked to a node. DEBUG
# events do not trigger a notification, event must be >= INFO.
EVENT_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      type RECORD;
      node RECORD;
    BEGIN
      SELECT level INTO type
      FROM maasserver_eventtype
      WHERE maasserver_eventtype.id = {entry}.type_id;
      IF type.level >= {loglevel_info} THEN
        SELECT system_id, node_type INTO node
        FROM maasserver_node
        WHERE maasserver_node.id = {entry}.node_id;

        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when vlan is updated.
VLAN_SUBNET_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        subnet RECORD;
    BEGIN
      FOR subnet IN (
        SELECT DISTINCT maasserver_subnet.id AS id
        FROM maasserver_subnet, maasserver_vlan
        WHERE maasserver_vlan.id = {entry}.id)
      LOOP
        PERFORM pg_notify('subnet_update',CAST(subnet.id AS text));
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when an IP address is updated to update the related
# node.
STATIC_IP_ADDRESS_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        node RECORD;
        pnode RECORD;
    BEGIN
      FOR node IN (
        SELECT DISTINCT ON (maasserver_node.id)
          system_id, node_type, parent_id
        FROM maasserver_node
        JOIN maasserver_nodeconfig
          ON maasserver_nodeconfig.node_id = maasserver_node.id
        JOIN maasserver_interface
          ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
        JOIN maasserver_interface_ip_addresses
          ON maasserver_interface_ip_addresses.interface_id = maasserver_interface.id
        WHERE maasserver_interface_ip_addresses.staticipaddress_id = {entry}.id
      )
      LOOP
        IF node.node_type = {type_machine} THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN {type_controllers} THEN
          PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
        ELSIF node.parent_id IS NOT NULL THEN
          SELECT system_id INTO pnode
          FROM maasserver_node
          WHERE id = node.parent_id;
          PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
        ELSE
          PERFORM pg_notify('device_update',CAST(node.system_id AS text));
        END IF;
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when an IP address is updated to update its related
# subnet.
STATIC_IP_ADDRESS_SUBNET_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    BEGIN
      IF TG_OP = 'INSERT' THEN
        IF NEW.subnet_id IS NOT NULL THEN
          PERFORM pg_notify('subnet_update',CAST(NEW.subnet_id AS text));
        END IF;
        RETURN NEW;
      END IF;
      IF TG_OP = 'DELETE' THEN
        IF OLD.subnet_id IS NOT NULL THEN
          PERFORM pg_notify('subnet_update',CAST(OLD.subnet_id AS text));
        END IF;
        RETURN OLD;
      END IF;
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
    """
)

# Procedure that is called when an IP address is updated, to update its related
# domain.
STATIC_IP_ADDRESS_DOMAIN_UPDATE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION ipaddress_domain_update_notify() RETURNS trigger AS $$
    DECLARE
      dom RECORD;
    BEGIN
      IF ((OLD.ip IS NULL and NEW.ip IS NOT NULL) OR
            (OLD.ip IS NOT NULL and NEW.ip IS NULL) OR
            OLD.ip != NEW.ip) THEN
        FOR dom IN (
          SELECT DISTINCT ON (domain.id)
            domain.id
          FROM maasserver_staticipaddress AS staticipaddress
          LEFT JOIN (
            maasserver_interface_ip_addresses AS iia
            JOIN maasserver_interface AS interface
              ON iia.interface_id = interface.id
            JOIN maasserver_nodeconfig AS nodeconfig
              ON interface.node_config_id = nodeconfig.id
            JOIN maasserver_node AS node
              ON node.id = nodeconfig.node_id) ON
            iia.staticipaddress_id = staticipaddress.id
          LEFT JOIN (
            maasserver_dnsresource_ip_addresses AS dia
            JOIN maasserver_dnsresource AS dnsresource ON
              dia.dnsresource_id = dnsresource.id) ON
            dia.staticipaddress_id = staticipaddress.id
          JOIN maasserver_domain AS domain ON
            domain.id = node.domain_id OR domain.id = dnsresource.domain_id
          WHERE staticipaddress.id = OLD.id OR staticipaddress.id = NEW.id)
        LOOP
          PERFORM pg_notify('domain_update',CAST(dom.id AS text));
        END LOOP;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when an IP address is inserted or deleted, to update
# its related domain.
STATIC_IP_ADDRESS_DOMAIN_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      dom RECORD;
    BEGIN
      FOR dom IN (
        SELECT DISTINCT ON (domain.id)
          domain.id
        FROM maasserver_staticipaddress AS staticipaddress
        LEFT JOIN (
          maasserver_interface_ip_addresses AS iia
          JOIN maasserver_interface AS interface
            ON iia.interface_id = interface.id
          JOIN maasserver_nodeconfig
            ON maasserver_nodeconfig.id = interface.node_config_id
          JOIN maasserver_node AS node
            ON node.id = maasserver_nodeconfig.node_id) ON
          iia.staticipaddress_id = staticipaddress.id
        LEFT JOIN (
          maasserver_dnsresource_ip_addresses AS dia
          JOIN maasserver_dnsresource AS dnsresource ON
            dia.dnsresource_id = dnsresource.id) ON
          dia.staticipaddress_id = staticipaddress.id
        JOIN maasserver_domain AS domain ON
          domain.id = node.domain_id OR domain.id = dnsresource.domain_id
        WHERE staticipaddress.id = {entry}.id)
      LOOP
        PERFORM pg_notify('domain_update',CAST(dom.id AS text));
      END LOOP;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when an IP range is created to update its related
# subnet.
IP_RANGE_SUBNET_INSERT_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION iprange_subnet_insert_notify() RETURNS trigger AS $$
    BEGIN
      IF NEW.subnet_id IS NOT NULL THEN
        PERFORM pg_notify('subnet_update',CAST(NEW.subnet_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when an IP range is updated to update its related
# subnet.
IP_RANGE_SUBNET_UPDATE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION iprange_subnet_update_notify() RETURNS trigger AS $$
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
    """
)

# Procedure that is called when an IP range is deleted to update its related
# subnet.
IP_RANGE_SUBNET_DELETE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION iprange_subnet_delete_notify() RETURNS trigger AS $$
    BEGIN
      IF OLD.subnet_id IS NOT NULL THEN
        PERFORM pg_notify('subnet_update',CAST(OLD.subnet_id AS text));
      END IF;
      RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when a DNSData entry is changed.
DNSDATA_DOMAIN_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        dom RECORD;
    BEGIN
      SELECT DISTINCT ON (domain_id) domain_id INTO dom
      FROM maasserver_dnsresource AS dnsresource
      WHERE dnsresource.id = {match_expr};
      PERFORM pg_notify('domain_update',CAST(dom.domain_id AS text));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when a DNSData entry is inserted/removed.
DNSRESOURCE_DOMAIN_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
        domain RECORD;
    BEGIN
      PERFORM pg_notify('domain_update',CAST({entry}.domain_id AS text));
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Procedure that is called when a DNSData entry is updated.
DNSRESOURCE_DOMAIN_UPDATE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION dnsresource_domain_update_notify() RETURNS trigger AS $$
    DECLARE
        domain RECORD;
    BEGIN
      PERFORM pg_notify('domain_update',CAST(OLD.domain_id AS text));
      IF OLD.domain_id != NEW.domain_id THEN
        PERFORM pg_notify('domain_update',CAST(NEW.domain_id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a static ip address is linked or unlinked to
# an Interface. Sends a notify message for domain_update
DNSRESOURCE_IP_ADDRESS_DOMAIN_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      domain RECORD;
    BEGIN
      SELECT maasserver_domain.id INTO domain
      FROM maasserver_dnsresource, maasserver_domain
      WHERE maasserver_domain.id = maasserver_dnsresource.domain_id
      AND maasserver_dnsresource.id = {entry}.dnsresource_id;

      IF domain.id IS NOT NULL THEN
        PERFORM pg_notify('domain_update',CAST(domain.id AS text));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a domain is updated.  Sends a notify message
# for node_update.
DOMAIN_NODE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {function_name}() RETURNS trigger AS $$
    DECLARE
      node RECORD;
      pnode RECORD;
    BEGIN
      IF OLD.name != NEW.name THEN
        FOR node IN (
          SELECT system_id, node_type, parent_id
          FROM maasserver_node
          WHERE maasserver_node.domain_id = NEW.id)
        LOOP
          IF node.system_id IS NOT NULL THEN
            IF node.node_type = {type_machine} THEN
              PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
            ELSIF node.node_type IN {type_controllers} THEN
              PERFORM pg_notify(
                'controller_update',CAST(node.system_id AS text));
            ELSIF node.parent_id IS NOT NULL THEN
              SELECT system_id INTO pnode
              FROM maasserver_node
              WHERE id = node.parent_id;
              PERFORM
                pg_notify('machine_update',CAST(pnode.system_id AS text));
            ELSE
              PERFORM pg_notify('device_update',CAST(node.system_id AS text));
            END IF;
          END IF;
        END LOOP;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


POOL_NODE_INSERT_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {func_name}() RETURNS trigger AS $$
    BEGIN
      IF {pool_id} IS NOT NULL THEN
        PERFORM pg_notify('resourcepool_update',CAST({pool_id} AS TEXT));
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


POOL_NODE_UPDATE_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {}() RETURNS trigger AS $$
    BEGIN
      IF OLD.pool_id != NEW.pool_id THEN
        IF OLD.pool_id IS NOT NULL THEN
          PERFORM pg_notify('resourcepool_update',CAST(OLD.pool_id AS text));
        END IF;
        IF NEW.pool_id IS NOT NULL THEN
          PERFORM pg_notify('resourcepool_update',CAST(NEW.pool_id AS text));
        END IF;
      ELSIF OLD.node_type != NEW.node_type THEN
        -- NODE_TYPE.MACHINE = 0
        IF OLD.node_type = 0 OR NEW.node_type = 0 THEN
          IF NEW.pool_id IS NOT NULL THEN
            PERFORM pg_notify('resourcepool_update',CAST(NEW.pool_id AS text));
          ELSIF OLD.pool_id IS NOT NULL THEN
            PERFORM pg_notify('resourcepool_update',CAST(OLD.pool_id AS text));
          END IF;
        END IF;
      ELSIF OLD.status != NEW.status THEN
        -- NODE_STATUS.READY = 4
        IF OLD.status = 4 OR NEW.status = 4 THEN
          PERFORM pg_notify('resourcepool_update',CAST(NEW.pool_id AS text));
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure that is called when a consumer is updated triggering a notification
# to the related tokens of the consumer.
CONSUMER_TOKEN_NOTIFY = dedent(
    """\
    CREATE OR REPLACE FUNCTION {}() RETURNS trigger AS $$
    DECLARE
        token RECORD;
    BEGIN
      IF OLD.name != NEW.name THEN
        FOR token IN (
          SELECT id
          FROM piston3_token
          WHERE piston3_token.consumer_id = NEW.id)
        LOOP
          PERFORM pg_notify('token_update',CAST(token.id AS text));
        END LOOP;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


def render_notification_procedure(proc_name, event_name, cast):
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
        BEGIN
          PERFORM pg_notify('{event_name}',CAST({cast} AS text));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def render_device_notification_procedure(proc_name, event_name, obj):
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
          pnode RECORD;
        BEGIN
          IF {obj}.parent_id IS NOT NULL THEN
            SELECT system_id INTO pnode
            FROM maasserver_node
            WHERE id = {obj}.parent_id;
            PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
          ELSE
            PERFORM pg_notify('{event_name}',CAST({obj}.system_id AS text));
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def render_node_related_notification_procedure(proc_name, entry):
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
          node RECORD;
          pnode RECORD;
        BEGIN
          SELECT system_id, node_type, parent_id INTO node
          FROM maasserver_node
          WHERE id = {entry}.node_id;

          IF node.node_type = {NODE_TYPE.MACHINE} THEN
            PERFORM pg_notify(
              'machine_update', CAST(node.system_id AS text)
            );
          ELSIF node.node_type IN {TYPE_CONTROLLERS} THEN
            PERFORM pg_notify(
              'controller_update', CAST(node.system_id AS text)
            );
          ELSIF node.parent_id IS NOT NULL THEN
            SELECT system_id INTO pnode
            FROM maasserver_node
            WHERE id = node.parent_id;

            PERFORM pg_notify(
              'machine_update', CAST(pnode.system_id AS text)
            );
          ELSE
            PERFORM pg_notify(
              'device_update', CAST(node.system_id AS text)
            );
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def render_node_related_notification_procedure_via_config(proc_name, entry):
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
          node RECORD;
          pnode RECORD;
        BEGIN
          SELECT system_id, node_type, parent_id INTO node
          FROM maasserver_node
          JOIN maasserver_nodeconfig
            ON maasserver_nodeconfig.node_id = maasserver_node.id
          WHERE maasserver_nodeconfig.id = {entry}.node_config_id;

          IF node.node_type = {NODE_TYPE.MACHINE} THEN
            PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
          ELSIF node.node_type IN {TYPE_CONTROLLERS} THEN
            PERFORM pg_notify('controller_update',CAST(
              node.system_id AS text));
          ELSIF node.parent_id IS NOT NULL THEN
            SELECT system_id INTO pnode
            FROM maasserver_node
            WHERE id = node.parent_id;
            PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
          ELSE
            PERFORM pg_notify('device_update',CAST(node.system_id AS text));
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


NODE_TYPE_CHANGE = dedent(
    f"""\
    CREATE OR REPLACE FUNCTION node_type_change_notify()
    RETURNS trigger AS $$
    BEGIN
      IF (OLD.node_type != NEW.node_type AND NOT (
          (OLD.node_type IN {TYPE_CONTROLLERS}) AND
          (NEW.node_type IN {TYPE_CONTROLLERS})
         )) THEN
        CASE OLD.node_type
          WHEN {NODE_TYPE.MACHINE} THEN
            PERFORM pg_notify('machine_delete',CAST(
              OLD.system_id AS TEXT));
          WHEN {NODE_TYPE.DEVICE} THEN
            PERFORM pg_notify('device_delete',CAST(
              OLD.system_id AS TEXT));
          WHEN {NODE_TYPE.RACK_CONTROLLER} THEN
            PERFORM pg_notify('controller_delete',CAST(
              OLD.system_id AS TEXT));
          WHEN {NODE_TYPE.REGION_CONTROLLER} THEN
            PERFORM pg_notify('controller_delete',CAST(
              OLD.system_id AS TEXT));
          WHEN {NODE_TYPE.REGION_AND_RACK_CONTROLLER} THEN
            PERFORM pg_notify('controller_delete',CAST(
              OLD.system_id AS TEXT));
        END CASE;
        CASE NEW.node_type
          WHEN {NODE_TYPE.MACHINE} THEN
            PERFORM pg_notify('machine_create',CAST(
              NEW.system_id AS TEXT));
          WHEN {NODE_TYPE.DEVICE} THEN
            PERFORM pg_notify('device_create',CAST(
              NEW.system_id AS TEXT));
          WHEN {NODE_TYPE.RACK_CONTROLLER} THEN
            PERFORM pg_notify('controller_create',CAST(
              NEW.system_id AS TEXT));
          WHEN {NODE_TYPE.REGION_CONTROLLER} THEN
            PERFORM pg_notify('controller_create',CAST(
              NEW.system_id AS TEXT));
          WHEN {NODE_TYPE.REGION_AND_RACK_CONTROLLER} THEN
            PERFORM pg_notify('controller_create',CAST(
              NEW.system_id AS TEXT));
        END CASE;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


def render_script_result_notify(proc_name, script_set_id):
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
          node RECORD;
        BEGIN
          SELECT
            system_id, node_type INTO node
          FROM
            maasserver_node AS nodet,
            maasserver_scriptset AS scriptset
          WHERE
            scriptset.id = {script_set_id} AND
            scriptset.node_id = nodet.id;
          IF node.node_type = {NODE_TYPE.MACHINE} THEN
            PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
          ELSIF node.node_type IN {TYPE_CONTROLLERS} THEN
            PERFORM pg_notify(
              'controller_update',CAST(node.system_id AS text));
          ELSIF node.node_type = {NODE_TYPE.DEVICE} THEN
            PERFORM pg_notify('device_update',CAST(node.system_id AS text));
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """
    )


def render_notification_dismissal_notification_procedure(
    proc_name, event_name
):
    """Send the notification_id and user_id when a notification is dismissed.

    Why not send the surrogate primary key as we do for most/all other models?
    The surrogate primary key exists only because Django won't let us do
    without. It's just not interesting. We only want the notification's ID and
    the user's ID, and we may as well put those in the notification because
    they're really short and it saves an extra trip to the database to load
    the row.
    """
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        DECLARE
        BEGIN
          PERFORM pg_notify(
              '{event_name}', CAST(NEW.notification_id AS text) || ':' ||
              CAST(NEW.user_id AS text));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


# Only trigger updates to the websocket on the node object for fields
# the UI cares about.
node_fields = (
    "architecture",
    "bmc_id",
    "cpu_count",
    "cpu_speed",
    "current_commissioning_script_set_id",
    "current_installation_script_set_id",
    "current_testing_script_set_id",
    "description",
    "distro_series",
    "domain_id",
    "error",
    "hostname",
    "hwe_kernel",
    "instance_power_parameters",
    "last_image_sync",
    "license_key",
    "locked",
    "min_hwe_kernel",
    "osystem",
    "owner_id",
    "parent_id",
    "pool_id",
    "power_state",
    "status",
    "swap_size",
    "zone_id",
)


@transactional
def register_websocket_triggers():
    """Register all websocket triggers into the database."""
    for proc_name_prefix, event_name_prefix, node_type in (
        ("machine", "machine", NODE_TYPE.MACHINE),
        ("rack_controller", "controller", NODE_TYPE.RACK_CONTROLLER),
        ("region_controller", "controller", NODE_TYPE.REGION_CONTROLLER),
        (
            "region_and_rack_controller",
            "controller",
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ),
    ):
        # Non-Device Node types
        register_procedure(
            render_notification_procedure(
                f"{proc_name_prefix}_create_notify",
                f"{event_name_prefix}_create",
                "NEW.system_id",
            )
        )
        register_procedure(
            render_notification_procedure(
                f"{proc_name_prefix}_update_notify",
                f"{event_name_prefix}_update",
                "NEW.system_id",
            )
        )
        register_procedure(
            render_notification_procedure(
                f"{proc_name_prefix}_delete_notify",
                f"{event_name_prefix}_delete",
                "OLD.system_id",
            )
        )
        register_triggers(
            "maasserver_node",
            proc_name_prefix,
            {"node_type": node_type},
            fields=node_fields,
        )

    # ControllerInfo notifications
    register_procedure(
        render_node_related_notification_procedure(
            "controllerinfo_link_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "controllerinfo_update_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "controllerinfo_unlink_notify", "OLD"
        )
    )
    register_triggers(
        "maasserver_controllerinfo",
        "controllerinfo",
        events=EVENTS_LUU,
    )

    # NodeMetadata notifications
    register_procedure(
        render_node_related_notification_procedure(
            "nodemetadata_link_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "nodemetadata_update_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "nodemetadata_unlink_notify", "OLD"
        )
    )
    register_triggers(
        "maasserver_nodemetadata", "nodemetadata", events=EVENTS_LUU
    )

    # workload annotations notifications
    register_procedure(
        render_node_related_notification_procedure(
            "ownerdata_link_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "ownerdata_update_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "ownerdata_unlink_notify", "OLD"
        )
    )
    register_triggers("maasserver_ownerdata", "ownerdata", events=EVENTS_LUU)

    register_procedure(
        POOL_NODE_INSERT_NOTIFY.format(
            func_name="resourcepool_link_notify", pool_id="NEW.pool_id"
        )
    )
    register_procedure(
        POOL_NODE_INSERT_NOTIFY.format(
            func_name="resourcepool_unlink_notify", pool_id="OLD.pool_id"
        )
    )
    register_procedure(
        POOL_NODE_UPDATE_NOTIFY.format("node_resourcepool_update_notify")
    )
    register_triggers("maasserver_node", "resourcepool", events=EVENTS_LU)
    register_trigger(
        "maasserver_node",
        "node_resourcepool_update_notify",
        event="update",
        fields=["pool_id", "status"],
    )

    # Device Node types
    register_procedure(
        render_device_notification_procedure(
            "device_create_notify", "device_create", "NEW"
        )
    )
    register_procedure(
        render_device_notification_procedure(
            "device_update_notify", "device_update", "NEW"
        )
    )
    register_procedure(
        render_device_notification_procedure(
            "device_delete_notify", "device_delete", "OLD"
        )
    )
    register_triggers(
        "maasserver_node",
        "device",
        {"node_type": NODE_TYPE.DEVICE},
        fields=node_fields,
    )

    # VLAN table
    register_procedure(
        render_notification_procedure(
            "vlan_create_notify", "vlan_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "vlan_update_notify", "vlan_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "vlan_delete_notify", "vlan_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_vlan", "vlan")

    # IPRange table
    register_procedure(
        render_notification_procedure(
            "iprange_create_notify", "iprange_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "iprange_update_notify", "iprange_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "iprange_delete_notify", "iprange_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_iprange", "iprange")

    # Neighbour table
    register_procedure(
        render_notification_procedure(
            "neighbour_create_notify", "neighbour_create", "NEW.ip"
        )
    )
    register_procedure(
        render_notification_procedure(
            "neighbour_update_notify", "neighbour_update", "NEW.ip"
        )
    )
    register_procedure(
        render_notification_procedure(
            "neighbour_delete_notify", "neighbour_delete", "OLD.ip"
        )
    )
    register_triggers("maasserver_neighbour", "neighbour")

    # StaticRoute table
    register_procedure(
        render_notification_procedure(
            "staticroute_create_notify", "staticroute_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "staticroute_update_notify", "staticroute_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "staticroute_delete_notify", "staticroute_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_staticroute", "staticroute")

    # Fabric table
    register_procedure(
        render_notification_procedure(
            "fabric_create_notify", "fabric_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "fabric_update_notify", "fabric_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "fabric_delete_notify", "fabric_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_fabric", "fabric")

    # Space table
    register_procedure(
        render_notification_procedure(
            "space_create_notify", "space_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "space_update_notify", "space_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "space_delete_notify", "space_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_space", "space")

    # Subnet table
    register_procedure(
        render_notification_procedure(
            "subnet_create_notify", "subnet_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "subnet_update_notify", "subnet_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "subnet_delete_notify", "subnet_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_subnet", "subnet")

    # Subnet node notifications
    register_procedure(
        SUBNET_NODE_NOTIFY.format(
            function_name="subnet_machine_update_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_subnet", "subnet_machine_update_notify", "update"
    )

    # Fabric node notifications
    register_procedure(
        FABRIC_NODE_NOTIFY.format(
            function_name="fabric_machine_update_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_fabric", "fabric_machine_update_notify", "update"
    )

    # Space node notifications
    register_procedure(
        SPACE_NODE_NOTIFY.format(
            function_name="space_machine_update_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_space", "space_machine_update_notify", "update"
    )

    # VLAN node notifications
    register_procedure(
        VLAN_NODE_NOTIFY.format(
            function_name="vlan_machine_update_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger("maasserver_vlan", "vlan_machine_update_notify", "update")

    # BMC node notifications
    register_procedure(
        BMC_NODE_NOTIFY.format(
            function_name="bmc_machine_update_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger("maasserver_bmc", "bmc_machine_update_notify", "update")

    # Event node notifications
    register_procedure(
        EVENT_NODE_NOTIFY.format(
            function_name="event_machine_update_notify",
            entry="NEW",
            loglevel_info=logging.INFO,
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_event", "event_machine_update_notify", "insert"
    )

    # VLAN subnet notifications
    register_procedure(
        VLAN_SUBNET_NOTIFY.format(
            function_name="vlan_subnet_update_notify",
            entry="NEW",
        )
    )
    register_trigger("maasserver_vlan", "vlan_subnet_update_notify", "update")

    # IP address node notifications
    register_procedure(
        STATIC_IP_ADDRESS_NODE_NOTIFY.format(
            function_name="ipaddress_machine_update_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_staticipaddress",
        "ipaddress_machine_update_notify",
        "update",
    )

    # IP address subnet notifications
    register_procedure(
        STATIC_IP_ADDRESS_SUBNET_NOTIFY.format(
            function_name="ipaddress_subnet_update_notify"
        )
    )
    register_procedure(
        STATIC_IP_ADDRESS_SUBNET_NOTIFY.format(
            function_name="ipaddress_subnet_insert_notify"
        )
    )
    register_procedure(
        STATIC_IP_ADDRESS_SUBNET_NOTIFY.format(
            function_name="ipaddress_subnet_delete_notify"
        )
    )
    register_triggers(
        "maasserver_staticipaddress", "ipaddress_subnet", events=EVENTS_IUD
    )

    # IP address domain notifications
    register_procedure(
        STATIC_IP_ADDRESS_DOMAIN_NOTIFY.format(
            function_name="ipaddress_domain_insert_notify", entry="NEW"
        )
    )
    register_procedure(STATIC_IP_ADDRESS_DOMAIN_UPDATE_NOTIFY)
    register_procedure(
        STATIC_IP_ADDRESS_DOMAIN_NOTIFY.format(
            function_name="ipaddress_domain_delete_notify", entry="OLD"
        )
    )
    register_triggers(
        "maasserver_staticipaddress", "ipaddress_domain", events=EVENTS_IUD
    )

    # IP range subnet notifications
    register_procedure(IP_RANGE_SUBNET_INSERT_NOTIFY)
    register_procedure(IP_RANGE_SUBNET_UPDATE_NOTIFY)
    register_procedure(IP_RANGE_SUBNET_DELETE_NOTIFY)
    register_triggers(
        "maasserver_iprange", "iprange_subnet", events=EVENTS_IUD
    )

    # VMCluster notifications
    register_procedure(VMCLUSTER_INSERT_NOTIFY)
    register_procedure(VMCLUSTER_UPDATE_NOTIFY)
    register_procedure(VMCLUSTER_DELETE_NOTIFY)
    register_triggers("maasserver_vmcluster", "vmcluster", events=EVENTS_IUD)

    # NODE VMCluster notifications
    register_procedure(NODE_VMCLUSTER_INSERT_NOTIFY)
    register_procedure(NODE_VMCLUSTER_UPDATE_NOTIFY)
    register_procedure(NODE_VMCLUSTER_DELETE_NOTIFY)
    register_triggers("maasserver_node", "node_vmcluster", events=EVENTS_IUD)

    # Pod notifications
    register_procedure(POD_INSERT_NOTIFY)
    register_procedure(POD_UPDATE_NOTIFY)
    register_procedure(POD_DELETE_NOTIFY)
    register_triggers("maasserver_bmc", "pod", events=EVENTS_IUD)

    # Node pod notifications
    register_procedure(NODE_POD_INSERT_NOTIFY)
    register_procedure(NODE_POD_UPDATE_NOTIFY)
    register_procedure(NODE_POD_DELETE_NOTIFY)
    register_triggers(
        "maasserver_node", "node_pod", events=EVENTS_IUD, fields=node_fields
    )

    register_procedure(INTERFACE_POD_NOTIFY)
    register_trigger(
        "maasserver_interface",
        "interface_pod_notify",
        "INSERT OR UPDATE OR DELETE",
    )

    # DNSData table
    register_procedure(
        DNSDATA_DOMAIN_NOTIFY.format(
            function_name="dnsdata_domain_insert_notify",
            match_expr="NEW.dnsresource_id",
        )
    )
    register_procedure(
        DNSDATA_DOMAIN_NOTIFY.format(
            function_name="dnsdata_domain_update_notify",
            match_expr="OLD.dnsresource_id OR dnsresource.id = NEW.dnsresource_id",
        )
    )
    register_procedure(
        DNSDATA_DOMAIN_NOTIFY.format(
            function_name="dnsdata_domain_delete_notify",
            match_expr="OLD.dnsresource_id",
        )
    )
    register_triggers(
        "maasserver_dnsdata", "dnsdata_domain", events=EVENTS_IUD
    )

    # DNSResource table
    register_procedure(
        DNSRESOURCE_DOMAIN_NOTIFY.format(
            function_name="dnsresource_domain_insert_notify", entry="NEW"
        )
    )
    register_procedure(DNSRESOURCE_DOMAIN_UPDATE_NOTIFY)
    register_procedure(
        DNSRESOURCE_DOMAIN_NOTIFY.format(
            function_name="dnsresource_domain_delete_notify", entry="OLD"
        )
    )
    register_triggers(
        "maasserver_dnsresource", "dnsresource_domain", events=EVENTS_IUD
    )

    # Domain table
    register_procedure(
        DOMAIN_NODE_NOTIFY.format(
            function_name="domain_node_update_notify",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_procedure(
        render_notification_procedure(
            "domain_create_notify", "domain_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "domain_update_notify", "domain_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "domain_delete_notify", "domain_delete", "OLD.id"
        )
    )
    register_trigger(
        "maasserver_domain", "domain_node_update_notify", "update"
    )
    register_triggers("maasserver_domain", "domain")

    # MAC static ip address table, update to linked domain via dnsresource
    register_procedure(
        DNSRESOURCE_IP_ADDRESS_DOMAIN_NOTIFY.format(
            function_name="rrset_sipaddress_link_notify", entry="NEW"
        )
    )
    register_procedure(
        DNSRESOURCE_IP_ADDRESS_DOMAIN_NOTIFY.format(
            function_name="rrset_sipaddress_unlink_notify", entry="OLD"
        )
    )
    register_trigger(
        "maasserver_dnsresource_ip_addresses",
        "rrset_sipaddress_link_notify",
        "insert",
    )
    register_trigger(
        "maasserver_dnsresource_ip_addresses",
        "rrset_sipaddress_unlink_notify",
        "delete",
    )

    # Zone table
    register_procedure(
        render_notification_procedure(
            "zone_create_notify", "zone_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "zone_update_notify", "zone_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "zone_delete_notify", "zone_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_zone", "zone")

    # ResourcePool table
    register_procedure(
        render_notification_procedure(
            "resourcepool_create_notify", "resourcepool_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "resourcepool_update_notify", "resourcepool_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "resourcepool_delete_notify", "resourcepool_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_resourcepool", "resourcepool")

    # Service table
    register_procedure(
        render_notification_procedure(
            "service_create_notify", "service_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "service_update_notify", "service_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "service_delete_notify", "service_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_service", "service")

    # Tag table
    register_procedure(
        render_notification_procedure(
            "tag_create_notify", "tag_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "tag_update_notify", "tag_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "tag_delete_notify", "tag_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_tag", "tag")

    # Node tag link table
    register_procedure(
        NODE_TAG_NOTIFY.format(
            function_name="machine_device_tag_link_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_procedure(
        NODE_TAG_NOTIFY.format(
            function_name="machine_device_tag_unlink_notify",
            entry="OLD",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_node_tags", "machine_device_tag_link_notify", "insert"
    )
    register_trigger(
        "maasserver_node_tags", "machine_device_tag_unlink_notify", "delete"
    )

    # Tag table, update to linked nodes.
    register_procedure(
        TAG_NODES_NOTIFY.format(
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_tag", "tag_update_machine_device_notify", "update"
    )

    # User table
    register_procedure(
        render_notification_procedure(
            "user_create_notify", "user_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "user_update_notify", "user_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "user_delete_notify", "user_delete", "OLD.id"
        )
    )
    register_triggers("auth_user", "user")

    # Events table
    register_procedure(
        render_notification_procedure(
            "event_create_notify", "event_create", "NEW.id"
        )
    )
    register_trigger("maasserver_event", "event_create_notify", "insert")

    # MAC static ip address table, update to linked node.
    register_procedure(
        INTERFACE_IP_ADDRESS_NODE_NOTIFY.format(
            function_name="nd_sipaddress_link_notify",
            entry="NEW",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_procedure(
        INTERFACE_IP_ADDRESS_NODE_NOTIFY.format(
            function_name="nd_sipaddress_unlink_notify",
            entry="OLD",
            type_machine=NODE_TYPE.MACHINE,
            type_controllers=TYPE_CONTROLLERS,
        )
    )
    register_trigger(
        "maasserver_interface_ip_addresses",
        "nd_sipaddress_link_notify",
        "insert",
    )
    register_trigger(
        "maasserver_interface_ip_addresses",
        "nd_sipaddress_unlink_notify",
        "delete",
    )

    # MAC static ip address table, update to linked domain via node.
    register_procedure(
        INTERFACE_IP_ADDRESS_DOMAIN_NOTIFY.format(
            function_name="nd_sipaddress_dns_link_notify",
            entry="NEW",
        )
    )
    register_procedure(
        INTERFACE_IP_ADDRESS_DOMAIN_NOTIFY.format(
            function_name="nd_sipaddress_dns_unlink_notify",
            entry="OLD",
        )
    )
    register_trigger(
        "maasserver_interface_ip_addresses",
        "nd_sipaddress_dns_link_notify",
        "insert",
    )
    register_trigger(
        "maasserver_interface_ip_addresses",
        "nd_sipaddress_dns_unlink_notify",
        "delete",
    )

    # Node result table, update to linked node.
    register_procedure(
        render_node_related_notification_procedure(
            "nd_scriptset_link_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure(
            "nd_scriptset_unlink_notify", "OLD"
        )
    )
    register_trigger(
        "maasserver_scriptset", "nd_scriptset_link_notify", "insert"
    )
    register_trigger(
        "maasserver_scriptset", "nd_scriptset_unlink_notify", "delete"
    )

    # ScriptResult triggers to the node for the nodes-listing page.
    register_procedure(
        render_script_result_notify(
            "nd_scriptresult_link_notify", "NEW.script_set_id"
        )
    )
    register_procedure(
        render_script_result_notify(
            "nd_scriptresult_update_notify", "NEW.script_set_id"
        )
    )
    register_procedure(
        render_script_result_notify(
            "nd_scriptresult_unlink_notify", "OLD.script_set_id"
        )
    )
    register_trigger(
        "maasserver_scriptresult", "nd_scriptresult_link_notify", "insert"
    )
    register_trigger(
        "maasserver_scriptresult",
        "nd_scriptresult_update_notify",
        "update",
    )
    register_trigger(
        "maasserver_scriptresult",
        "nd_scriptresult_unlink_notify",
        "delete",
    )

    # ScriptResult triggers for the details page.
    register_procedure(
        render_notification_procedure(
            "scriptresult_create_notify", "scriptresult_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "scriptresult_update_notify", "scriptresult_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "scriptresult_delete_notify", "scriptresult_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_scriptresult", "scriptresult")

    # Interface address table, update to linked node.
    register_procedure(
        render_node_related_notification_procedure_via_config(
            "nd_interface_link_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure_via_config(
            "nd_interface_unlink_notify", "OLD"
        )
    )
    register_procedure(INTERFACE_UPDATE_NODE_NOTIFY)
    register_trigger(
        "maasserver_interface", "nd_interface_link_notify", "insert"
    )
    register_trigger(
        "maasserver_interface", "nd_interface_unlink_notify", "delete"
    )
    register_trigger(
        "maasserver_interface", "nd_interface_update_notify", "update"
    )

    # Block device table, update to linked node.
    register_procedure(
        render_node_related_notification_procedure_via_config(
            "nd_blockdevice_link_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure_via_config(
            "nd_blockdevice_update_notify", "NEW"
        )
    )
    register_procedure(
        render_node_related_notification_procedure_via_config(
            "nd_blockdevice_unlink_notify", "OLD"
        )
    )
    register_procedure(
        PHYSICAL_OR_VIRTUAL_BLOCK_DEVICE_NODE_NOTIFY.format(
            func_name="nd_physblockdevice_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        PHYSICAL_OR_VIRTUAL_BLOCK_DEVICE_NODE_NOTIFY.format(
            func_name="nd_virtblockdevice_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_trigger(
        "maasserver_blockdevice", "nd_blockdevice_link_notify", "insert"
    )
    register_trigger(
        "maasserver_blockdevice", "nd_blockdevice_update_notify", "update"
    )
    register_trigger(
        "maasserver_blockdevice", "nd_blockdevice_unlink_notify", "delete"
    )
    register_trigger(
        "maasserver_physicalblockdevice",
        "nd_physblockdevice_update_notify",
        "update",
    )
    register_trigger(
        "maasserver_virtualblockdevice",
        "nd_virtblockdevice_update_notify",
        "update",
    )

    # Partition table, update to linked user.
    register_procedure(
        PARTITIONTABLE_NODE_NOTIFY.format(
            func_name="nd_partitiontable_link_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        PARTITIONTABLE_NODE_NOTIFY.format(
            func_name="nd_partitiontable_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        PARTITIONTABLE_NODE_NOTIFY.format(
            func_name="nd_partitiontable_unlink_notify",
            entry="OLD",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_trigger(
        "maasserver_partitiontable", "nd_partitiontable_link_notify", "insert"
    )
    register_trigger(
        "maasserver_partitiontable",
        "nd_partitiontable_update_notify",
        "update",
    )
    register_trigger(
        "maasserver_partitiontable",
        "nd_partitiontable_unlink_notify",
        "delete",
    )

    # Partition, update to linked user.
    register_procedure(
        PARTITION_NODE_NOTIFY.format(
            func_name="nd_partition_link_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        PARTITION_NODE_NOTIFY.format(
            func_name="nd_partition_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        PARTITION_NODE_NOTIFY.format(
            func_name="nd_partition_unlink_notify",
            entry="OLD",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_trigger(
        "maasserver_partition", "nd_partition_link_notify", "insert"
    )
    register_trigger(
        "maasserver_partition", "nd_partition_update_notify", "update"
    )
    register_trigger(
        "maasserver_partition", "nd_partition_unlink_notify", "delete"
    )

    # Filesystem, update to linked user.
    register_procedure(
        FILESYSTEM_NODE_NOTIFY.format(
            func_name="nd_filesystem_link_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        FILESYSTEM_NODE_NOTIFY.format(
            func_name="nd_filesystem_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        FILESYSTEM_NODE_NOTIFY.format(
            func_name="nd_filesystem_unlink_notify",
            entry="OLD",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_trigger(
        "maasserver_filesystem", "nd_filesystem_link_notify", "insert"
    )
    register_trigger(
        "maasserver_filesystem", "nd_filesystem_update_notify", "update"
    )
    register_trigger(
        "maasserver_filesystem", "nd_filesystem_unlink_notify", "delete"
    )

    # Filesystemgroup, update to linked user.
    register_procedure(
        FILESYSTEMGROUP_NODE_NOTIFY.format(
            func_name="nd_filesystemgroup_link_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        FILESYSTEMGROUP_NODE_NOTIFY.format(
            func_name="nd_filesystemgroup_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        FILESYSTEMGROUP_NODE_NOTIFY.format(
            func_name="nd_filesystemgroup_unlink_notify",
            entry="OLD",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_trigger(
        "maasserver_filesystemgroup",
        "nd_filesystemgroup_link_notify",
        "insert",
    )
    register_trigger(
        "maasserver_filesystemgroup",
        "nd_filesystemgroup_update_notify",
        "update",
    )
    register_trigger(
        "maasserver_filesystemgroup",
        "nd_filesystemgroup_unlink_notify",
        "delete",
    )

    # Cacheset, update to linked user.
    register_procedure(
        CACHESET_NODE_NOTIFY.format(
            func_name="nd_cacheset_link_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        CACHESET_NODE_NOTIFY.format(
            func_name="nd_cacheset_update_notify",
            entry="NEW",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_procedure(
        CACHESET_NODE_NOTIFY.format(
            func_name="nd_cacheset_unlink_notify",
            entry="OLD",
            machine_type=NODE_TYPE.MACHINE,
        )
    )
    register_trigger(
        "maasserver_cacheset", "nd_cacheset_link_notify", "insert"
    )
    register_trigger(
        "maasserver_cacheset", "nd_cacheset_update_notify", "update"
    )
    register_trigger(
        "maasserver_cacheset", "nd_cacheset_unlink_notify", "delete"
    )

    # Token table, update to linked user.
    register_procedure(
        render_notification_procedure(
            "user_token_link_notify", "user_update", "NEW.user_id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "user_token_unlink_notify", "user_update", "OLD.user_id"
        )
    )
    register_trigger("piston3_token", "user_token_link_notify", "insert")
    register_trigger("piston3_token", "user_token_unlink_notify", "delete")

    # Token/Consumer table.
    register_procedure(
        render_notification_procedure(
            "token_create_notify", "token_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "token_delete_notify", "token_delete", "OLD.id"
        )
    )
    register_procedure(
        CONSUMER_TOKEN_NOTIFY.format("consumer_token_update_notify")
    )
    register_triggers(
        "piston3_token",
        "token",
        events=[("insert", "create", "NEW"), ("delete", "delete", "OLD")],
    )
    register_trigger(
        "piston3_consumer",
        "consumer_token_update_notify",
        event="update",
        fields=["name"],
    )

    # SSH key table, update to linked user.
    register_procedure(
        render_notification_procedure(
            "user_sshkey_link_notify", "user_update", "NEW.user_id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "user_sshkey_unlink_notify", "user_update", "OLD.user_id"
        )
    )
    register_trigger("maasserver_sshkey", "user_sshkey_link_notify", "insert")
    register_trigger(
        "maasserver_sshkey", "user_sshkey_unlink_notify", "delete"
    )

    # SSH key table.
    register_procedure(
        render_notification_procedure(
            "sshkey_create_notify", "sshkey_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "sshkey_update_notify", "sshkey_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "sshkey_delete_notify", "sshkey_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_sshkey", "sshkey")

    # SSL key table, update to linked user.
    register_procedure(
        render_notification_procedure(
            "user_sslkey_link_notify", "user_update", "NEW.user_id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "user_sslkey_unlink_notify", "user_update", "OLD.user_id"
        )
    )
    register_trigger("maasserver_sslkey", "user_sslkey_link_notify", "insert")
    register_trigger(
        "maasserver_sslkey", "user_sslkey_unlink_notify", "delete"
    )

    # SSL key table.
    register_procedure(
        render_notification_procedure(
            "sslkey_create_notify", "sslkey_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "sslkey_update_notify", "sslkey_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "sslkey_delete_notify", "sslkey_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_sslkey", "sslkey")

    # DHCPSnippet table
    register_procedure(
        render_notification_procedure(
            "dhcpsnippet_create_notify", "dhcpsnippet_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "dhcpsnippet_update_notify", "dhcpsnippet_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "dhcpsnippet_delete_notify", "dhcpsnippet_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_dhcpsnippet", "dhcpsnippet")

    # PackageRepository table
    register_procedure(
        render_notification_procedure(
            "packagerepository_create_notify",
            "packagerepository_create",
            "NEW.id",
        )
    )
    register_procedure(
        render_notification_procedure(
            "packagerepository_update_notify",
            "packagerepository_update",
            "NEW.id",
        )
    )
    register_procedure(
        render_notification_procedure(
            "packagerepository_delete_notify",
            "packagerepository_delete",
            "OLD.id",
        )
    )
    register_triggers("maasserver_packagerepository", "packagerepository")

    # Node type change.
    register_procedure(NODE_TYPE_CHANGE)
    register_trigger(
        "maasserver_node",
        "node_type_change_notify",
        "update",
        fields=("node_type",),
    )

    # Notification table.
    register_procedure(
        render_notification_procedure(
            "notification_create_notify", "notification_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "notification_update_notify", "notification_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "notification_delete_notify", "notification_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_notification", "notification")

    # NotificationDismissal table.
    register_procedure(
        render_notification_dismissal_notification_procedure(
            "notificationdismissal_create_notify",
            "notificationdismissal_create",
        )
    )
    register_trigger(
        "maasserver_notificationdismissal",
        "notificationdismissal_create_notify",
        "insert",
    )

    # Script table
    register_procedure(
        render_notification_procedure(
            "script_create_notify", "script_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "script_update_notify", "script_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "script_delete_notify", "script_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_script", "script")

    # NodeDevice table
    register_procedure(
        render_notification_procedure(
            "nodedevice_create_notify", "nodedevice_create", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "nodedevice_update_notify", "nodedevice_update", "NEW.id"
        )
    )
    register_procedure(
        render_notification_procedure(
            "nodedevice_delete_notify", "nodedevice_delete", "OLD.id"
        )
    )
    register_triggers("maasserver_nodedevice", "nodedevice")
