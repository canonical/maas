# Copyright 2016-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
System Triggers

Each trigger will call a procedure to send the notification. Each procedure
will raise a notify message in Postgres that a regiond process is listening
for.
"""

from textwrap import dedent

from maasserver.models.dnspublication import zone_serial
from maasserver.triggers import register_procedure, register_trigger
from maasserver.utils.orm import transactional

# Note that the corresponding test module (test_system) only tests that the
# triggers and procedures are registered.  The behavior of these procedures
# is tested (end-to-end testing) in test_system_listener.  We test it there
# because the asynchronous nature of the PG events makes it easier to seperate
# the tests.

# Helper that returns the number of rack controllers that region process is
# currently managing.
CORE_GET_MANAGING_COUNT = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_get_managing_count(
      process maasserver_regioncontrollerprocess)
    RETURNS integer as $$
    BEGIN
      RETURN (SELECT count(*)
        FROM maasserver_node
        WHERE maasserver_node.managing_process_id = process.id);
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Helper that returns the total number of RPC connections for the
# rack controller.
CORE_GET_NUMBER_OF_CONN = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_get_num_conn(rack maasserver_node)
    RETURNS integer as $$
    BEGIN
      RETURN (
        SELECT count(*)
        FROM
          maasserver_regionrackrpcconnection AS connection
        WHERE connection.rack_controller_id = rack.id);
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Helper that returns the total number of region processes.
CORE_GET_NUMBER_OF_PROCESSES = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_get_num_processes()
    RETURNS integer as $$
    BEGIN
      RETURN (
        SELECT count(*) FROM maasserver_regioncontrollerprocess);
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Helper that picks a new region process that can manage the given
# rack controller.
CORE_PICK_NEW_REGION = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_pick_new_region(rack maasserver_node)
    RETURNS maasserver_regioncontrollerprocess as $$
    DECLARE
      selected_managing integer;
      number_managing integer;
      selected_process maasserver_regioncontrollerprocess;
      process maasserver_regioncontrollerprocess;
    BEGIN
      -- Get best region controller that can manage this rack controller.
      -- This is identified by picking a region controller process that
      -- at least has a connection to the rack controller and managing the
      -- least number of rack controllers.
      FOR process IN (
        SELECT DISTINCT ON (maasserver_regioncontrollerprocess.id)
          maasserver_regioncontrollerprocess.*
        FROM
          maasserver_regioncontrollerprocess,
          maasserver_regioncontrollerprocessendpoint,
          maasserver_regionrackrpcconnection
        WHERE maasserver_regionrackrpcconnection.rack_controller_id = rack.id
          AND maasserver_regionrackrpcconnection.endpoint_id =
            maasserver_regioncontrollerprocessendpoint.id
          AND maasserver_regioncontrollerprocessendpoint.process_id =
            maasserver_regioncontrollerprocess.id)
      LOOP
        IF selected_process IS NULL THEN
          -- First time through the loop so set the default.
          selected_process = process;
          selected_managing = sys_core_get_managing_count(process);
        ELSE
          -- See if the current process is managing less then the currently
          -- selected process.
          number_managing = sys_core_get_managing_count(process);
          IF number_managing = 0 THEN
            -- This process is managing zero so its the best, so we exit the
            -- loop now to return the selected.
            selected_process = process;
            EXIT;
          ELSIF number_managing < selected_managing THEN
            -- Managing less than the currently selected; select this process
            -- instead.
            selected_process = process;
            selected_managing = number_managing;
          END IF;
        END IF;
      END LOOP;
      RETURN selected_process;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Helper that picks and sets a new region process to manage this rack
# controller.
CORE_SET_NEW_REGION = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_set_new_region(rack maasserver_node)
    RETURNS void as $$
    DECLARE
      region_process maasserver_regioncontrollerprocess;
    BEGIN
      -- Pick the new region process to manage this rack controller.
      region_process = sys_core_pick_new_region(rack);

      -- Update the rack controller and alert the region controller.
      UPDATE maasserver_node SET managing_process_id = region_process.id
      WHERE maasserver_node.id = rack.id;
      PERFORM pg_notify(
        CONCAT('sys_core_', region_process.id),
        CONCAT('watch_', CAST(rack.id AS text)));
      RETURN;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Triggered when a new region <-> rack RPC connection is made. This provides
# the logic to select the region controller that should manage this rack
# controller. Balancing of managed rack controllers is also done by this
# trigger.
CORE_REGIONRACKRPCONNECTION_INSERT = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_rpc_insert()
    RETURNS trigger as $$
    DECLARE
      rack_controller maasserver_node;
      region_process maasserver_regioncontrollerprocess;
    BEGIN
      -- New connection from region <-> rack, check that the rack controller
      -- has a managing region controller.
      SELECT maasserver_node.* INTO rack_controller
      FROM maasserver_node
      WHERE maasserver_node.id = NEW.rack_controller_id;

      IF rack_controller.managing_process_id IS NULL THEN
        -- No managing region process for this rack controller.
        PERFORM sys_core_set_new_region(rack_controller);
      ELSE
        -- Currently managed check that the managing process is not dead.
        SELECT maasserver_regioncontrollerprocess.* INTO region_process
        FROM maasserver_regioncontrollerprocess
        WHERE maasserver_regioncontrollerprocess.id =
          rack_controller.managing_process_id;
        IF EXTRACT(EPOCH FROM region_process.updated) -
          EXTRACT(EPOCH FROM now()) > 90 THEN
          -- Region controller process is dead. A new region process needs to
          -- be selected for this rack controller.
          UPDATE maasserver_node SET managing_process_id = NULL
          WHERE maasserver_node.id = NEW.rack_controller_id;
          NEW.rack_controller_id = NULL;
          PERFORM sys_core_set_new_region(rack_controller);
        ELSE
          -- Currently being managed but lets see if we can re-balance the
          -- managing processes better. We only do the re-balance once the
          -- rack controller is connected to more than half of the running
          -- processes.
          IF sys_core_get_num_conn(rack_controller) /
            sys_core_get_num_processes() > 0.5 THEN
            -- Pick a new region process for this rack controller. Only update
            -- and perform the notification if the selection is different.
            region_process = sys_core_pick_new_region(rack_controller);
            IF region_process.id != rack_controller.managing_process_id THEN
              -- Alter the old process that its no longer responsable for
              -- this rack controller.
              PERFORM pg_notify(
                CONCAT('sys_core_', rack_controller.managing_process_id),
                CONCAT('unwatch_', CAST(rack_controller.id AS text)));
              -- Update the rack controller and alert the region controller.
              UPDATE maasserver_node
              SET managing_process_id = region_process.id
              WHERE maasserver_node.id = rack_controller.id;
              PERFORM pg_notify(
                CONCAT('sys_core_', region_process.id),
                CONCAT('watch_', CAST(rack_controller.id AS text)));
            END IF;
          END IF;
        END IF;
      END IF;

      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

# Triggered when a region <-> rack connection is delete. When the managing
# region process is the one that loses its connection it will find a
# new region process to manage the rack controller.
CORE_REGIONRACKRPCONNECTION_DELETE = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_core_rpc_delete()
    RETURNS trigger as $$
    DECLARE
      rack_controller maasserver_node;
      region_process maasserver_regioncontrollerprocess;
    BEGIN
      -- Connection from region <-> rack, has been removed. If that region
      -- process was managing that rack controller then a new one needs to
      -- be selected.
      SELECT maasserver_node.* INTO rack_controller
      FROM maasserver_node
      WHERE maasserver_node.id = OLD.rack_controller_id;

      -- Get the region process from the endpoint.
      SELECT
        process.* INTO region_process
      FROM
        maasserver_regioncontrollerprocess AS process,
        maasserver_regioncontrollerprocessendpoint AS endpoint
      WHERE process.id = endpoint.process_id
        AND endpoint.id = OLD.endpoint_id;

      -- Only perform an action if processes equal.
      IF rack_controller.managing_process_id = region_process.id THEN
        -- Region process was managing this rack controller. Tell it to stop
        -- watching the rack controller.
        PERFORM pg_notify(
          CONCAT('sys_core_', region_process.id),
          CONCAT('unwatch_', CAST(rack_controller.id AS text)));

        -- Pick a new region process for this rack controller.
        region_process = sys_core_pick_new_region(rack_controller);

        -- Update the rack controller and inform the new process.
        UPDATE maasserver_node
        SET managing_process_id = region_process.id
        WHERE maasserver_node.id = rack_controller.id;
        IF region_process.id IS NOT NULL THEN
          PERFORM pg_notify(
            CONCAT('sys_core_', region_process.id),
            CONCAT('watch_', CAST(rack_controller.id AS text)));
        END IF;
      END IF;

      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)

CORE_GEN_RANDOM_PREFIX = dedent(
    """\
    CREATE OR REPLACE FUNCTION gen_random_prefix() RETURNS TEXT AS $$
    DECLARE
        result text;
    BEGIN
        result := md5(random()::text);
        RETURN result;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# be updated. Only watches changes on the cidr and allow_proxy.
PROXY_SUBNET_UPDATE = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_proxy_subnet_update()
    RETURNS trigger as $$
    BEGIN
      IF OLD.cidr != NEW.cidr OR OLD.allow_proxy != NEW.allow_proxy THEN
        PERFORM pg_notify('sys_proxy', '');
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Triggered when the proxy settings are updated.
PEER_PROXY_CONFIG_INSERT = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_proxy_config_use_peer_proxy_insert()
    RETURNS trigger as $$
    BEGIN
      IF (NEW.name = 'enable_proxy' OR
          NEW.name = 'maas_proxy_port' OR
          NEW.name = 'use_peer_proxy' OR
          NEW.name = 'http_proxy' OR
          NEW.name = 'prefer_v4_proxy') THEN
        PERFORM pg_notify('sys_proxy', '');
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Triggered when the proxy settings are updated.
PEER_PROXY_CONFIG_UPDATE = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_proxy_config_use_peer_proxy_update()
    RETURNS trigger as $$
    BEGIN
      IF (NEW.name = 'enable_proxy' OR
          NEW.name = 'maas_proxy_port' OR
          NEW.name = 'use_peer_proxy' OR
          NEW.name = 'http_proxy' OR
          NEW.name = 'prefer_v4_proxy') THEN
        PERFORM pg_notify('sys_proxy', '');
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Triggered when RBAC need to be synced. In essense this means on
# insert into maasserver_rbacsync.
RBAC_SYNC = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_rbac_sync()
    RETURNS trigger AS $$
    BEGIN
      PERFORM pg_notify('sys_rbac', '');
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Procedure to mark RBAC as needing a sync.
RBAC_SYNC_UPDATE = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_rbac_sync_update(
      reason text,
      action text DEFAULT 'full',
      resource_type text DEFAULT '',
      resource_id int DEFAULT NULL,
      resource_name text DEFAULT '')
    RETURNS void as $$
    BEGIN
      INSERT INTO maasserver_rbacsync
        (created, source, action, resource_type, resource_id, resource_name)
      VALUES (
        now(), substring(reason FOR 255),
        action, resource_type, resource_id, resource_name);
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Triggered when a new resource pool is added. Notifies that RBAC needs
# to be synced.
RBAC_RPOOL_INSERT = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_rbac_rpool_insert()
    RETURNS trigger as $$
    BEGIN
      PERFORM sys_rbac_sync_update(
        'added resource pool ' || NEW.name,
        'add', 'resource-pool', NEW.id, NEW.name);
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Triggered when a resource pool is updated. Notifies that RBAC needs
# to be synced. Only watches name.
RBAC_RPOOL_UPDATE = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_rbac_rpool_update()
    RETURNS trigger as $$
    DECLARE
      changes text[];
    BEGIN
      IF OLD.name != NEW.name THEN
        PERFORM sys_rbac_sync_update(
          'renamed resource pool ' || OLD.name || ' to ' || NEW.name,
          'update', 'resource-pool', OLD.id, NEW.name);
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
)


# Triggered when a resource pool is deleted. Notifies that RBAC needs
# to be synced.
RBAC_RPOOL_DELETE = dedent(
    """\
    CREATE OR REPLACE FUNCTION sys_rbac_rpool_delete()
    RETURNS trigger as $$
    BEGIN
      PERFORM sys_rbac_sync_update(
        'removed resource pool ' || OLD.name,
        'remove', 'resource-pool', OLD.id, OLD.name);
      RETURN OLD;
    END;
    $$ LANGUAGE plpgsql;
    """
)


def render_sys_proxy_procedure(proc_name, on_delete=False):
    """Render a database procedure with name `proc_name` that notifies that a
    proxy update is needed.

    :param proc_name: Name of the procedure.
    :param on_delete: True when procedure will be used as a delete trigger.
    """
    entry = "OLD" if on_delete else "NEW"
    return dedent(
        f"""\
        CREATE OR REPLACE FUNCTION {proc_name}() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_notify('sys_proxy', '');
          RETURN {entry};
        END;
        $$ LANGUAGE plpgsql;
        """
    )


@transactional
def register_system_triggers():
    """Register all system triggers into the database."""
    # Core
    register_procedure(CORE_GET_MANAGING_COUNT)
    register_procedure(CORE_GET_NUMBER_OF_CONN)
    register_procedure(CORE_GET_NUMBER_OF_PROCESSES)
    register_procedure(CORE_PICK_NEW_REGION)
    register_procedure(CORE_SET_NEW_REGION)
    register_procedure(CORE_GEN_RANDOM_PREFIX)

    # RegionRackRPCConnection
    register_procedure(CORE_REGIONRACKRPCONNECTION_INSERT)
    register_trigger(
        "maasserver_regionrackrpcconnection", "sys_core_rpc_insert", "insert"
    )
    register_procedure(CORE_REGIONRACKRPCONNECTION_DELETE)
    register_trigger(
        "maasserver_regionrackrpcconnection", "sys_core_rpc_delete", "delete"
    )

    # DNS
    # create zone serial sequence if not exist
    zone_serial.create_if_not_exists()

    # Proxy

    # - Subnet
    register_procedure(render_sys_proxy_procedure("sys_proxy_subnet_insert"))
    register_trigger("maasserver_subnet", "sys_proxy_subnet_insert", "insert")
    register_procedure(PROXY_SUBNET_UPDATE)
    register_trigger("maasserver_subnet", "sys_proxy_subnet_update", "update")
    register_procedure(
        render_sys_proxy_procedure("sys_proxy_subnet_delete", on_delete=True)
    )
    register_trigger("maasserver_subnet", "sys_proxy_subnet_delete", "delete")

    # - Config/http_proxy (when use_peer_proxy)
    register_procedure(PEER_PROXY_CONFIG_INSERT)
    register_trigger(
        "maasserver_config", "sys_proxy_config_use_peer_proxy_insert", "insert"
    )
    register_procedure(PEER_PROXY_CONFIG_UPDATE)
    register_trigger(
        "maasserver_config", "sys_proxy_config_use_peer_proxy_update", "update"
    )

    # - RBACSync
    register_procedure(RBAC_SYNC)
    register_trigger("maasserver_rbacsync", "sys_rbac_sync", "insert")
    register_procedure(RBAC_SYNC_UPDATE)

    # - ResourcePool
    register_procedure(RBAC_RPOOL_INSERT)
    register_trigger(
        "maasserver_resourcepool", "sys_rbac_rpool_insert", "insert"
    )
    register_procedure(RBAC_RPOOL_UPDATE)
    register_trigger(
        "maasserver_resourcepool", "sys_rbac_rpool_update", "update"
    )
    register_procedure(RBAC_RPOOL_DELETE)
    register_trigger(
        "maasserver_resourcepool", "sys_rbac_rpool_delete", "delete"
    )
