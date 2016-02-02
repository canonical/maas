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


@transactional
def register_system_triggers():
    """Register all system triggers into the database."""
    # DHCP triggers.
    register_procedure(DHCP_ALERT)
    register_procedure(DHCP_VLAN_UPDATE)
    register_trigger("maasserver_vlan", "sys_dhcp_vlan_update", "update")
    register_procedure(DHCP_SUBNET_UPDATE)
    register_trigger("maasserver_subnet", "sys_dhcp_subnet_update", "update")
    register_procedure(DHCP_SUBNET_DELETE)
    register_trigger("maasserver_subnet", "sys_dhcp_subnet_delete", "delete")
    register_procedure(DHCP_IPRANGE_INSERT)
    register_trigger("maasserver_iprange", "sys_dhcp_iprange_insert", "insert")
    register_procedure(DHCP_IPRANGE_UPDATE)
    register_trigger("maasserver_iprange", "sys_dhcp_iprange_update", "update")
    register_procedure(DHCP_IPRANGE_DELETE)
    register_trigger("maasserver_iprange", "sys_dhcp_iprange_delete", "delete")
