# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
System Triggers

Each trigger will call a procedure to send the notification. Each procedure
will raise a notify message in Postgres that a regiond process is listening
for.
"""

__all__ = [
    "register_system_triggers"
    ]

from textwrap import dedent

from maasserver.triggers import (
    register_procedure,
    register_trigger,
)
from maasserver.utils.orm import transactional

# Note that the corresponding test module (test_system) only tests that the
# triggers and procedures are registered.  The behavior of these procedures
# is tested (end-to-end testing) in test_system_listener.  We test it there
# because the asynchronous nature of the PG events makes it easier to seperate
# the tests.

# Triggered when the VLAN is modified. When DHCP is turned off/on it will alert
# the primary/secondary rack controller to update. If the primary rack or
# secondary rack is changed it will alert the previous and new rack controller.
DHCP_VLAN_UPDATE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_vlan_update()
    RETURNS trigger as $$
    BEGIN
      -- DHCP was turned off.
      IF OLD.dhcp_on AND NOT NEW.dhcp_on THEN
        PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.primary_rack_id), '');
        IF OLD.secondary_rack_id IS NOT NULL THEN
          PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.secondary_rack_id), '');
        END IF;
      -- DHCP was turned on.
      ELSIF NOT OLD.dhcp_on AND NEW.dhcp_on THEN
        PERFORM pg_notify(CONCAT('sys_dhcp_', NEW.primary_rack_id), '');
        IF NEW.secondary_rack_id IS NOT NULL THEN
          PERFORM pg_notify(CONCAT('sys_dhcp_', NEW.secondary_rack_id), '');
        END IF;
      -- DHCP state was not changed but the rack controllers might have been.
      ELSIF NEW.dhcp_on THEN
        -- Send message to both old and new primary rack controller.
        IF OLD.primary_rack_id != NEW.primary_rack_id THEN
          PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.primary_rack_id), '');
          PERFORM pg_notify(CONCAT('sys_dhcp_', NEW.primary_rack_id), '');
        END IF;
        -- Send message to both old and new secondary rack controller if set.
        IF OLD.secondary_rack_id != NEW.secondary_rack_id THEN
          IF OLD.secondary_rack_id IS NOT NULL THEN
            PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.secondary_rack_id), '');
          END IF;
          IF NEW.secondary_rack_id IS NOT NULL THEN
            PERFORM pg_notify(CONCAT('sys_dhcp_', NEW.secondary_rack_id), '');
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Helper that alerts the primary and secondary rack controller for a VLAN.
DHCP_ALERT = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_alert(vlan maasserver_vlan)
    RETURNS void AS $$
    BEGIN
      PERFORM pg_notify(CONCAT('sys_dhcp_', vlan.primary_rack_id), '');
      IF vlan.secondary_rack_id IS NOT NULL THEN
        PERFORM pg_notify(CONCAT('sys_dhcp_', vlan.secondary_rack_id), '');
      END IF;
      RETURN;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when a subnet's VLAN, CIDR, gateway IP, or DNS servers change.
# If the VLAN was changed it alerts both the rack controllers of the old VLAN
# and then the rack controllers of the new VLAN. Any other field that is
# updated just alerts the rack controllers of the current VLAN.
DHCP_SUBNET_UPDATE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_subnet_update()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Subnet was moved to a new VLAN.
      IF OLD.vlan_id != NEW.vlan_id THEN
        -- Update old VLAN if DHCP is enabled.
        SELECT * INTO vlan
        FROM maasserver_vlan WHERE id = OLD.vlan_id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
        -- Update the new VLAN if DHCP is enabled.
        SELECT * INTO vlan
        FROM maasserver_vlan WHERE id = NEW.vlan_id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      -- Related fields of subnet where changed.
      ELSIF OLD.cidr != NEW.cidr OR
        OLD.gateway_ip != NEW.gateway_ip OR
        OLD.dns_servers != NEW.dns_servers THEN
        -- Network has changed update alert DHCP if enabled.
        SELECT * INTO vlan
        FROM maasserver_vlan WHERE id = NEW.vlan_id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when the subnet is deleted. Alerts the rack controllers of the
# VLAN the subnet belonged to.
DHCP_SUBNET_DELETE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_subnet_delete()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled.
      SELECT * INTO vlan
      FROM maasserver_vlan WHERE id = OLD.vlan_id;
      IF vlan.dhcp_on THEN
        PERFORM sys_dhcp_alert(vlan);
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when a dynamic DHCP range is added to a subnet that is on a managed
# VLAN. Alerts the rack controllers for that VLAN.
DHCP_IPRANGE_INSERT = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_iprange_insert()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled and a dynamic range.
      IF NEW.type = 'managed_dhcp' THEN
        SELECT maasserver_vlan.* INTO vlan
        FROM maasserver_vlan, maasserver_subnet
        WHERE maasserver_subnet.id = NEW.subnet_id AND
          maasserver_subnet.vlan_id = maasserver_vlan.id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when a dynamic DHCP range is updated on a subnet that is on a
# managed VLAN. Alerts the rack controllers for that VLAN.
DHCP_IPRANGE_UPDATE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_iprange_update()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled and was or is now a dynamic range.
      IF OLD.type = 'managed_dhcp' OR NEW.type = 'managed_dhcp' THEN
        SELECT maasserver_vlan.* INTO vlan
        FROM maasserver_vlan, maasserver_subnet
        WHERE maasserver_subnet.id = NEW.subnet_id AND
          maasserver_subnet.vlan_id = maasserver_vlan.id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when a dynamic DHCP range is deleted from a subnet that is on a
# managed VLAN. Alerts the rack controllers for that VLAN.
DHCP_IPRANGE_DELETE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_iprange_delete()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled and was dynamic range.
      IF OLD.type = 'managed_dhcp' THEN
        SELECT maasserver_vlan.* INTO vlan
        FROM maasserver_vlan, maasserver_subnet
        WHERE maasserver_subnet.id = OLD.subnet_id AND
          maasserver_subnet.vlan_id = maasserver_vlan.id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when an IP address that has an IP set and is not DISCOVERED is
# inserted to a subnet on a managed VLAN. Alerts the rack controllers for that
# VLAN.
DHCP_STATICIPADDRESS_INSERT = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_staticipaddress_insert()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled, IP is set and not DISCOVERED.
      IF NEW.alloc_type != 6 AND NEW.ip IS NOT NULL AND host(NEW.ip) != '' THEN
        SELECT maasserver_vlan.* INTO vlan
        FROM maasserver_vlan, maasserver_subnet
        WHERE maasserver_subnet.id = NEW.subnet_id AND
          maasserver_subnet.vlan_id = maasserver_vlan.id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when an IP address that has an IP set and is not DISCOVERED is
# updated. If the subnet changes then it alerts the rack controllers of each
# VLAN if the VLAN differs from the previous VLAN.
DHCP_STATICIPADDRESS_UPDATE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_staticipaddress_update()
    RETURNS trigger as $$
    DECLARE
      old_vlan maasserver_vlan;
      new_vlan maasserver_vlan;
    BEGIN
      -- Ignore DISCOVERED IP addresses.
      IF NEW.alloc_type != 6 THEN
        IF OLD.subnet_id != NEW.subnet_id THEN
          -- Subnet has changed; update each VLAN if different.
          SELECT maasserver_vlan.* INTO old_vlan
          FROM maasserver_vlan, maasserver_subnet
          WHERE maasserver_subnet.id = OLD.subnet_id AND
            maasserver_subnet.vlan_id = maasserver_vlan.id;
          SELECT maasserver_vlan.* INTO new_vlan
          FROM maasserver_vlan, maasserver_subnet
          WHERE maasserver_subnet.id = NEW.subnet_id AND
            maasserver_subnet.vlan_id = maasserver_vlan.id;
          IF old_vlan.id != new_vlan.id THEN
            -- Different VLAN's; update each if DHCP enabled.
            IF old_vlan.dhcp_on THEN
              PERFORM sys_dhcp_alert(old_vlan);
            END IF;
            IF new_vlan.dhcp_on THEN
              PERFORM sys_dhcp_alert(new_vlan);
            END IF;
          ELSE
            -- Same VLAN so only need to update once.
            IF new_vlan.dhcp_on THEN
              PERFORM sys_dhcp_alert(new_vlan);
            END IF;
          END IF;
        ELSIF (OLD.ip IS NULL AND NEW.ip IS NOT NULL) OR
          (OLD.ip IS NOT NULL and NEW.ip IS NULL) OR
          (host(OLD.ip) != host(NEW.ip)) THEN
          -- Assigned IP address has changed.
          SELECT maasserver_vlan.* INTO new_vlan
          FROM maasserver_vlan, maasserver_subnet
          WHERE maasserver_subnet.id = NEW.subnet_id AND
            maasserver_subnet.vlan_id = maasserver_vlan.id;
          IF new_vlan.dhcp_on THEN
            PERFORM sys_dhcp_alert(new_vlan);
          END IF;
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when an IP address is removed from a subnet that is on a
# managed VLAN. Alerts the rack controllers of that VLAN.
DHCP_STATICIPADDRESS_DELETE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_staticipaddress_delete()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled and has an IP address.
      IF host(OLD.ip) != '' THEN
        SELECT maasserver_vlan.* INTO vlan
        FROM maasserver_vlan, maasserver_subnet
        WHERE maasserver_subnet.id = OLD.subnet_id AND
          maasserver_subnet.vlan_id = maasserver_vlan.id;
        IF vlan.dhcp_on THEN
          PERFORM sys_dhcp_alert(vlan);
        END IF;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when the interface name or MAC address is updated. Alerts
# rack controllers on all managed VLAN's that the interface has a non
# DISCOVERED IP address on.
DHCP_INTERFACE_UPDATE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_interface_update()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if DHCP is enabled and the interface name or MAC
      -- address has changed.
      IF OLD.name != NEW.name OR OLD.mac_address != NEW.mac_address THEN
        FOR vlan IN (
          SELECT DISTINCT ON (maasserver_vlan.id)
            maasserver_vlan.*
          FROM
            maasserver_vlan,
            maasserver_subnet,
            maasserver_staticipaddress,
            maasserver_interface_ip_addresses AS ip_link
          WHERE maasserver_staticipaddress.subnet_id = maasserver_subnet.id
          AND ip_link.staticipaddress_id = maasserver_staticipaddress.id
          AND ip_link.interface_id = NEW.id
          AND maasserver_staticipaddress.alloc_type != 6
          AND maasserver_staticipaddress.ip IS NOT NULL
          AND host(maasserver_staticipaddress.ip) != ''
          AND maasserver_vlan.id = maasserver_subnet.vlan_id
          AND maasserver_vlan.dhcp_on)
        LOOP
          PERFORM sys_dhcp_alert(vlan);
        END LOOP;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)

# Triggered when the hostname of the node is changed. Alerts rack controllers
# for all VLAN's that this interface has a non DISCOVERED IP address.
DHCP_NODE_UPDATE = dedent("""\
    CREATE OR REPLACE FUNCTION sys_dhcp_node_update()
    RETURNS trigger as $$
    DECLARE
      vlan maasserver_vlan;
    BEGIN
      -- Update VLAN if on every interface on the node that is managed when
      -- the node hostname is changed.
      IF OLD.hostname != NEW.hostname THEN
        FOR vlan IN (
          SELECT DISTINCT ON (maasserver_vlan.id)
            maasserver_vlan.*
          FROM
            maasserver_vlan,
            maasserver_staticipaddress,
            maasserver_subnet,
            maasserver_interface,
            maasserver_interface_ip_addresses AS ip_link
          WHERE maasserver_staticipaddress.subnet_id = maasserver_subnet.id
          AND ip_link.staticipaddress_id = maasserver_staticipaddress.id
          AND ip_link.interface_id = maasserver_interface.id
          AND maasserver_interface.node_id = NEW.id
          AND maasserver_staticipaddress.alloc_type != 6
          AND maasserver_staticipaddress.ip IS NOT NULL
          AND host(maasserver_staticipaddress.ip) != ''
          AND maasserver_vlan.id = maasserver_subnet.vlan_id
          AND maasserver_vlan.dhcp_on)
        LOOP
          PERFORM sys_dhcp_alert(vlan);
        END LOOP;
      END IF;
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)


@transactional
def register_system_triggers():
    """Register all system triggers into the database."""
    register_procedure(DHCP_ALERT)

    # VLAN
    register_procedure(DHCP_VLAN_UPDATE)
    register_trigger("maasserver_vlan", "sys_dhcp_vlan_update", "update")

    # Subnet
    register_procedure(DHCP_SUBNET_UPDATE)
    register_trigger("maasserver_subnet", "sys_dhcp_subnet_update", "update")
    register_procedure(DHCP_SUBNET_DELETE)
    register_trigger("maasserver_subnet", "sys_dhcp_subnet_delete", "delete")

    # IPRange
    register_procedure(DHCP_IPRANGE_INSERT)
    register_trigger("maasserver_iprange", "sys_dhcp_iprange_insert", "insert")
    register_procedure(DHCP_IPRANGE_UPDATE)
    register_trigger("maasserver_iprange", "sys_dhcp_iprange_update", "update")
    register_procedure(DHCP_IPRANGE_DELETE)
    register_trigger("maasserver_iprange", "sys_dhcp_iprange_delete", "delete")

    # StaticIPAddress
    register_procedure(DHCP_STATICIPADDRESS_INSERT)
    register_trigger(
        "maasserver_staticipaddress",
        "sys_dhcp_staticipaddress_insert",
        "insert")
    register_procedure(DHCP_STATICIPADDRESS_UPDATE)
    register_trigger(
        "maasserver_staticipaddress",
        "sys_dhcp_staticipaddress_update",
        "update")
    register_procedure(DHCP_STATICIPADDRESS_DELETE)
    register_trigger(
        "maasserver_staticipaddress",
        "sys_dhcp_staticipaddress_delete",
        "delete")

    # Interface
    register_procedure(DHCP_INTERFACE_UPDATE)
    register_trigger(
        "maasserver_interface",
        "sys_dhcp_interface_update",
        "update")

    # Node
    register_procedure(DHCP_NODE_UPDATE)
    register_trigger(
        "maasserver_node",
        "sys_dhcp_node_update",
        "update")
