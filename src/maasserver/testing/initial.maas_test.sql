--
-- PostgreSQL database dump
--

-- Dumped from database version 14.11 (Ubuntu 14.11-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.11 (Ubuntu 14.11-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: temporal; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA temporal;


--
-- Name: temporal_visibility; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA temporal_visibility;


--
-- Name: btree_gin; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS btree_gin WITH SCHEMA temporal_visibility;


--
-- Name: EXTENSION btree_gin; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION btree_gin IS 'support for indexing common datatypes in GIN';


--
-- Name: bmc_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.bmc_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  FOR node IN (
    SELECT system_id, node_type
    FROM maasserver_node
    WHERE bmc_id = NEW.id)
  LOOP
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
      PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
    END IF;
  END LOOP;
  RETURN NEW;
END;
$$;


--
-- Name: config_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.config_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('config_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: config_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.config_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('config_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: config_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.config_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('config_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: consumer_token_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.consumer_token_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: controllerinfo_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.controllerinfo_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: controllerinfo_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.controllerinfo_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: controllerinfo_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.controllerinfo_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: device_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.device_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  pnode RECORD;
BEGIN
  IF NEW.parent_id IS NOT NULL THEN
    SELECT system_id INTO pnode
    FROM maasserver_node
    WHERE id = NEW.parent_id;
    PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
  ELSE
    PERFORM pg_notify('device_create',CAST(NEW.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: device_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.device_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  pnode RECORD;
BEGIN
  IF OLD.parent_id IS NOT NULL THEN
    SELECT system_id INTO pnode
    FROM maasserver_node
    WHERE id = OLD.parent_id;
    PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
  ELSE
    PERFORM pg_notify('device_delete',CAST(OLD.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: device_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.device_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  pnode RECORD;
BEGIN
  IF NEW.parent_id IS NOT NULL THEN
    SELECT system_id INTO pnode
    FROM maasserver_node
    WHERE id = NEW.parent_id;
    PERFORM pg_notify('machine_update',CAST(pnode.system_id AS text));
  ELSE
    PERFORM pg_notify('device_update',CAST(NEW.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: dhcpsnippet_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dhcpsnippet_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('dhcpsnippet_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dhcpsnippet_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dhcpsnippet_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('dhcpsnippet_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dhcpsnippet_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dhcpsnippet_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('dhcpsnippet_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dnsdata_domain_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dnsdata_domain_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    dom RECORD;
BEGIN
  SELECT DISTINCT ON (domain_id) domain_id INTO dom
  FROM maasserver_dnsresource AS dnsresource
  WHERE dnsresource.id = OLD.dnsresource_id;
  PERFORM pg_notify('domain_update',CAST(dom.domain_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dnsdata_domain_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dnsdata_domain_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    dom RECORD;
BEGIN
  SELECT DISTINCT ON (domain_id) domain_id INTO dom
  FROM maasserver_dnsresource AS dnsresource
  WHERE dnsresource.id = NEW.dnsresource_id;
  PERFORM pg_notify('domain_update',CAST(dom.domain_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dnsdata_domain_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dnsdata_domain_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    dom RECORD;
BEGIN
  SELECT DISTINCT ON (domain_id) domain_id INTO dom
  FROM maasserver_dnsresource AS dnsresource
  WHERE dnsresource.id = OLD.dnsresource_id OR dnsresource.id = NEW.dnsresource_id;
  PERFORM pg_notify('domain_update',CAST(dom.domain_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dnsresource_domain_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dnsresource_domain_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    domain RECORD;
BEGIN
  PERFORM pg_notify('domain_update',CAST(OLD.domain_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dnsresource_domain_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dnsresource_domain_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    domain RECORD;
BEGIN
  PERFORM pg_notify('domain_update',CAST(NEW.domain_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: dnsresource_domain_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.dnsresource_domain_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    domain RECORD;
BEGIN
  PERFORM pg_notify('domain_update',CAST(OLD.domain_id AS text));
  IF OLD.domain_id != NEW.domain_id THEN
    PERFORM pg_notify('domain_update',CAST(NEW.domain_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: domain_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.domain_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('domain_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: domain_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.domain_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('domain_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: domain_node_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.domain_node_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
        IF node.node_type = 0 THEN
          PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
        ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: domain_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.domain_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('domain_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: event_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.event_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('event_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: event_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.event_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  type RECORD;
  node RECORD;
BEGIN
  SELECT level INTO type
  FROM maasserver_eventtype
  WHERE maasserver_eventtype.id = NEW.type_id;
  IF type.level >= 20 THEN
    SELECT system_id, node_type INTO node
    FROM maasserver_node
    WHERE maasserver_node.id = NEW.node_id;

    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
      PERFORM pg_notify('controller_update',CAST(node.system_id AS text));
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: fabric_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fabric_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('fabric_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: fabric_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fabric_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('fabric_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: fabric_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fabric_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    node RECORD;
    pnode RECORD;
BEGIN
  FOR node IN (
    SELECT DISTINCT ON (maasserver_node.id)
      system_id, node_type, parent_id
    FROM
      maasserver_node,
      maasserver_fabric,
      maasserver_interface,
      maasserver_vlan
    WHERE maasserver_fabric.id = NEW.id
    AND maasserver_vlan.fabric_id = maasserver_fabric.id
    AND maasserver_node.id = maasserver_interface.node_id
    AND maasserver_vlan.id = maasserver_interface.vlan_id)
  LOOP
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: fabric_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.fabric_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('fabric_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: interface_pod_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.interface_pod_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    _pod_id integer;
BEGIN
    IF TG_OP = 'INSERT' then
        SELECT INTO _pod_id pod_id FROM maasserver_podhost
            WHERE NEW.node_id = node_id;
        IF _pod_id IS NOT NULL then
            PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
         END IF;
    ELSIF TG_OP = 'UPDATE' then
        IF OLD.vlan_id IS NOT DISTINCT FROM NEW.vlan_id
            AND OLD.node_id IS NOT DISTINCT FROM NEW.node_id then
            -- Nothing relevant changed during interface update.
            RETURN NULL;
        END IF;
        SELECT INTO _pod_id pod_id FROM maasserver_podhost
            WHERE NEW.node_id = node_id;
        IF _pod_id IS NOT NULL then
            PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
         END IF;
        IF OLD.node_id != NEW.node_id then
            SELECT INTO _pod_id pod_id FROM maasserver_podhost
                WHERE OLD.node_id = node_id;
            IF _pod_id IS NOT NULL then
                PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
            END IF;
        END IF;
    ELSE
        SELECT INTO _pod_id pod_id FROM maasserver_podhost
            WHERE OLD.node_id = node_id;
        IF _pod_id IS NOT NULL then
            PERFORM pg_notify('pod_update',CAST(_pod_id AS text));
         END IF;
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: ipaddress_domain_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_domain_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  dom RECORD;
BEGIN
  FOR dom IN (
    SELECT DISTINCT ON (domain.id)
      domain.id
    FROM maasserver_staticipaddress AS staticipaddress
    LEFT JOIN (
      maasserver_interface_ip_addresses AS iia
      JOIN maasserver_interface AS interface ON
        iia.interface_id = interface.id
      JOIN maasserver_node AS node ON
        node.id = interface.node_id) ON
      iia.staticipaddress_id = staticipaddress.id
    LEFT JOIN (
      maasserver_dnsresource_ip_addresses AS dia
      JOIN maasserver_dnsresource AS dnsresource ON
        dia.dnsresource_id = dnsresource.id) ON
      dia.staticipaddress_id = staticipaddress.id
    JOIN maasserver_domain AS domain ON
      domain.id = node.domain_id OR domain.id = dnsresource.domain_id
    WHERE staticipaddress.id = OLD.id)
  LOOP
    PERFORM pg_notify('domain_update',CAST(dom.id AS text));
  END LOOP;
  RETURN NEW;
END;
$$;


--
-- Name: ipaddress_domain_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_domain_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  dom RECORD;
BEGIN
  FOR dom IN (
    SELECT DISTINCT ON (domain.id)
      domain.id
    FROM maasserver_staticipaddress AS staticipaddress
    LEFT JOIN (
      maasserver_interface_ip_addresses AS iia
      JOIN maasserver_interface AS interface ON
        iia.interface_id = interface.id
      JOIN maasserver_node AS node ON
        node.id = interface.node_id) ON
      iia.staticipaddress_id = staticipaddress.id
    LEFT JOIN (
      maasserver_dnsresource_ip_addresses AS dia
      JOIN maasserver_dnsresource AS dnsresource ON
        dia.dnsresource_id = dnsresource.id) ON
      dia.staticipaddress_id = staticipaddress.id
    JOIN maasserver_domain AS domain ON
      domain.id = node.domain_id OR domain.id = dnsresource.domain_id
    WHERE staticipaddress.id = NEW.id)
  LOOP
    PERFORM pg_notify('domain_update',CAST(dom.id AS text));
  END LOOP;
  RETURN NEW;
END;
$$;


--
-- Name: ipaddress_domain_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_domain_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
        JOIN maasserver_interface AS interface ON
          iia.interface_id = interface.id
        JOIN maasserver_node AS node ON
          node.id = interface.node_id) ON
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
$$;


--
-- Name: ipaddress_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    node RECORD;
    pnode RECORD;
BEGIN
  FOR node IN (
    SELECT DISTINCT ON (maasserver_node.id)
      system_id, node_type, parent_id
    FROM
      maasserver_node,
      maasserver_interface,
      maasserver_interface_ip_addresses AS ip_link
    WHERE ip_link.staticipaddress_id = NEW.id
    AND ip_link.interface_id = maasserver_interface.id
    AND maasserver_node.id = maasserver_interface.node_id)
  LOOP
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: ipaddress_subnet_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_subnet_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: ipaddress_subnet_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_subnet_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: ipaddress_subnet_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ipaddress_subnet_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: iprange_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.iprange_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('iprange_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: iprange_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.iprange_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('iprange_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: iprange_subnet_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.iprange_subnet_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.subnet_id IS NOT NULL THEN
    PERFORM pg_notify('subnet_update',CAST(OLD.subnet_id AS text));
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: iprange_subnet_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.iprange_subnet_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.subnet_id IS NOT NULL THEN
    PERFORM pg_notify('subnet_update',CAST(NEW.subnet_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: iprange_subnet_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.iprange_subnet_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: iprange_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.iprange_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('iprange_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: machine_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.machine_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('machine_create',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: machine_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.machine_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('machine_delete',CAST(OLD.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: machine_device_tag_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.machine_device_tag_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: machine_device_tag_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.machine_device_tag_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('machine_update',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: nd_blockdevice_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_blockdevice_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_blockdevice_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_blockdevice_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_blockdevice_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_blockdevice_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_cacheset_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_cacheset_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
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
  AND maasserver_filesystem.cache_set_id = NEW.id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_cacheset_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_cacheset_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
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
  AND maasserver_filesystem.cache_set_id = OLD.id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_cacheset_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_cacheset_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
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
  AND maasserver_filesystem.cache_set_id = NEW.id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_filesystem_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_filesystem_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  IF NEW.block_device_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node,
           maasserver_blockdevice
     WHERE maasserver_node.id = maasserver_blockdevice.node_id
       AND maasserver_blockdevice.id = NEW.block_device_id;
  ELSIF NEW.partition_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partition,
           maasserver_partitiontable
     WHERE maasserver_node.id = maasserver_blockdevice.node_id
       AND maasserver_blockdevice.id =
           maasserver_partitiontable.block_device_id
       AND maasserver_partitiontable.id =
           maasserver_partition.partition_table_id
       AND maasserver_partition.id = NEW.partition_id;
  ELSIF NEW.node_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node
     WHERE maasserver_node.id = NEW.node_id;
  END IF;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
  END IF;

  RETURN NEW;
END;
$$;


--
-- Name: nd_filesystem_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_filesystem_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  IF OLD.block_device_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node,
           maasserver_blockdevice
     WHERE maasserver_node.id = maasserver_blockdevice.node_id
       AND maasserver_blockdevice.id = OLD.block_device_id;
  ELSIF OLD.partition_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partition,
           maasserver_partitiontable
     WHERE maasserver_node.id = maasserver_blockdevice.node_id
       AND maasserver_blockdevice.id =
           maasserver_partitiontable.block_device_id
       AND maasserver_partitiontable.id =
           maasserver_partition.partition_table_id
       AND maasserver_partition.id = OLD.partition_id;
  ELSIF OLD.node_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node
     WHERE maasserver_node.id = OLD.node_id;
  END IF;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
  END IF;

  RETURN NEW;
END;
$$;


--
-- Name: nd_filesystem_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_filesystem_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  IF NEW.block_device_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node,
           maasserver_blockdevice
     WHERE maasserver_node.id = maasserver_blockdevice.node_id
       AND maasserver_blockdevice.id = NEW.block_device_id;
  ELSIF NEW.partition_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node,
           maasserver_blockdevice,
           maasserver_partition,
           maasserver_partitiontable
     WHERE maasserver_node.id = maasserver_blockdevice.node_id
       AND maasserver_blockdevice.id =
           maasserver_partitiontable.block_device_id
       AND maasserver_partitiontable.id =
           maasserver_partition.partition_table_id
       AND maasserver_partition.id = NEW.partition_id;
  ELSIF NEW.node_id IS NOT NULL
  THEN
    SELECT system_id, node_type INTO node
      FROM maasserver_node
     WHERE maasserver_node.id = NEW.node_id;
  END IF;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
  END IF;

  RETURN NEW;
END;
$$;


--
-- Name: nd_filesystemgroup_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_filesystemgroup_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
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
  AND (maasserver_filesystem.filesystem_group_id = NEW.id
      OR maasserver_filesystem.cache_set_id = NEW.cache_set_id);

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_filesystemgroup_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_filesystemgroup_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
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
  AND (maasserver_filesystem.filesystem_group_id = OLD.id
      OR maasserver_filesystem.cache_set_id = OLD.cache_set_id);

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_filesystemgroup_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_filesystemgroup_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
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
  AND (maasserver_filesystem.filesystem_group_id = NEW.id
      OR maasserver_filesystem.cache_set_id = NEW.cache_set_id);

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_interface_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_interface_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_interface_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_interface_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_interface_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_interface_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  IF OLD.node_id != NEW.node_id THEN
    SELECT system_id, node_type, parent_id INTO node
    FROM maasserver_node
    WHERE id = OLD.node_id;

    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_partition_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_partition_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node,
       maasserver_blockdevice,
       maasserver_partitiontable
  WHERE maasserver_node.id = maasserver_blockdevice.node_id
  AND maasserver_blockdevice.id = maasserver_partitiontable.block_device_id
  AND maasserver_partitiontable.id = NEW.partition_table_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_partition_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_partition_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node,
       maasserver_blockdevice,
       maasserver_partitiontable
  WHERE maasserver_node.id = maasserver_blockdevice.node_id
  AND maasserver_blockdevice.id = maasserver_partitiontable.block_device_id
  AND maasserver_partitiontable.id = OLD.partition_table_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_partition_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_partition_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node,
       maasserver_blockdevice,
       maasserver_partitiontable
  WHERE maasserver_node.id = maasserver_blockdevice.node_id
  AND maasserver_blockdevice.id = maasserver_partitiontable.block_device_id
  AND maasserver_partitiontable.id = NEW.partition_table_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_partitiontable_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_partitiontable_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node, maasserver_blockdevice
    WHERE maasserver_node.id = maasserver_blockdevice.node_id
    AND maasserver_blockdevice.id = NEW.block_device_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_partitiontable_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_partitiontable_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node, maasserver_blockdevice
    WHERE maasserver_node.id = maasserver_blockdevice.node_id
    AND maasserver_blockdevice.id = OLD.block_device_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_partitiontable_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_partitiontable_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node, maasserver_blockdevice
    WHERE maasserver_node.id = maasserver_blockdevice.node_id
    AND maasserver_blockdevice.id = NEW.block_device_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_physblockdevice_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_physblockdevice_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node, maasserver_blockdevice
  WHERE maasserver_node.id = maasserver_blockdevice.node_id
  AND maasserver_blockdevice.id = NEW.blockdevice_ptr_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_scriptresult_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_scriptresult_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT
    system_id, node_type INTO node
  FROM
    maasserver_node AS nodet,
    metadataserver_scriptset AS scriptset
  WHERE
    scriptset.id = NEW.script_set_id AND
    scriptset.node_id = nodet.id;
  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
    PERFORM pg_notify(
      'controller_update',CAST(node.system_id AS text));
  ELSIF node.node_type = 1 THEN
    PERFORM pg_notify('device_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_scriptresult_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_scriptresult_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT
    system_id, node_type INTO node
  FROM
    maasserver_node AS nodet,
    metadataserver_scriptset AS scriptset
  WHERE
    scriptset.id = OLD.script_set_id AND
    scriptset.node_id = nodet.id;
  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
    PERFORM pg_notify(
      'controller_update',CAST(node.system_id AS text));
  ELSIF node.node_type = 1 THEN
    PERFORM pg_notify('device_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_scriptresult_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_scriptresult_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT
    system_id, node_type INTO node
  FROM
    maasserver_node AS nodet,
    metadataserver_scriptset AS scriptset
  WHERE
    scriptset.id = NEW.script_set_id AND
    scriptset.node_id = nodet.id;
  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
    PERFORM pg_notify(
      'controller_update',CAST(node.system_id AS text));
  ELSIF node.node_type = 1 THEN
    PERFORM pg_notify('device_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_scriptset_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_scriptset_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_scriptset_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_scriptset_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_sipaddress_dns_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_sipaddress_dns_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain RECORD;
BEGIN
  SELECT maasserver_domain.id INTO domain
  FROM maasserver_node, maasserver_interface, maasserver_domain
  WHERE maasserver_node.id = maasserver_interface.node_id
  AND maasserver_domain.id = maasserver_node.domain_id
  AND maasserver_interface.id = NEW.interface_id;

  IF domain.id IS NOT NULL THEN
    PERFORM pg_notify('domain_update',CAST(domain.id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_sipaddress_dns_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_sipaddress_dns_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain RECORD;
BEGIN
  SELECT maasserver_domain.id INTO domain
  FROM maasserver_node, maasserver_interface, maasserver_domain
  WHERE maasserver_node.id = maasserver_interface.node_id
  AND maasserver_domain.id = maasserver_node.domain_id
  AND maasserver_interface.id = OLD.interface_id;

  IF domain.id IS NOT NULL THEN
    PERFORM pg_notify('domain_update',CAST(domain.id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: nd_sipaddress_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_sipaddress_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node, maasserver_interface
  WHERE maasserver_node.id = maasserver_interface.node_id
  AND maasserver_interface.id = NEW.interface_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_sipaddress_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_sipaddress_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node, maasserver_interface
  WHERE maasserver_node.id = maasserver_interface.node_id
  AND maasserver_interface.id = OLD.interface_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nd_virtblockdevice_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nd_virtblockdevice_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
BEGIN
  SELECT system_id, node_type INTO node
  FROM maasserver_node, maasserver_blockdevice
  WHERE maasserver_node.id = maasserver_blockdevice.node_id
  AND maasserver_blockdevice.id = NEW.blockdevice_ptr_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: neighbour_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.neighbour_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('neighbour_create',CAST(NEW.ip AS text));
  RETURN NEW;
END;
$$;


--
-- Name: neighbour_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.neighbour_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('neighbour_delete',CAST(OLD.ip AS text));
  RETURN NEW;
END;
$$;


--
-- Name: neighbour_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.neighbour_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('neighbour_update',CAST(NEW.ip AS text));
  RETURN NEW;
END;
$$;


--
-- Name: node_pod_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_pod_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  bmc RECORD;
BEGIN
  IF OLD.bmc_id IS NOT NULL THEN
    SELECT * INTO bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
    IF bmc.bmc_type = 1 THEN
      PERFORM pg_notify('pod_update',CAST(OLD.bmc_id AS text));
    END IF;
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: node_pod_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_pod_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  bmc RECORD;
BEGIN
  IF NEW.bmc_id IS NOT NULL THEN
    SELECT * INTO bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
    IF bmc.bmc_type = 1 THEN
      PERFORM pg_notify('pod_update',CAST(NEW.bmc_id AS text));
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: node_pod_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_pod_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  bmc RECORD;
BEGIN
  IF ((OLD.bmc_id IS NULL and NEW.bmc_id IS NOT NULL) OR
      (OLD.bmc_id IS NOT NULL and NEW.bmc_id IS NULL) OR
      OLD.bmc_id != NEW.bmc_id) THEN
    IF OLD.bmc_id IS NOT NULL THEN
      SELECT * INTO bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
      IF bmc.bmc_type = 1 THEN
        PERFORM pg_notify('pod_update',CAST(OLD.bmc_id AS text));
      END IF;
    END IF;
  END IF;
  IF NEW.bmc_id IS NOT NULL THEN
    SELECT * INTO bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
    IF bmc.bmc_type = 1 THEN
      PERFORM pg_notify('pod_update',CAST(NEW.bmc_id AS text));
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: node_resourcepool_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_resourcepool_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: node_type_change_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_type_change_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF (OLD.node_type != NEW.node_type AND NOT (
      (
        OLD.node_type IN (2, 3, 4)
      ) AND (
        NEW.node_type IN (2, 3, 4)
      ))) THEN
    CASE OLD.node_type
      WHEN 0 THEN
        PERFORM pg_notify('machine_delete',CAST(
          OLD.system_id AS TEXT));
      WHEN 1 THEN
        PERFORM pg_notify('device_delete',CAST(
          OLD.system_id AS TEXT));
      WHEN 2 THEN
        PERFORM pg_notify('controller_delete',CAST(
          OLD.system_id AS TEXT));
      WHEN 3 THEN
        PERFORM pg_notify('controller_delete',CAST(
          OLD.system_id AS TEXT));
      WHEN 4 THEN
        PERFORM pg_notify('controller_delete',CAST(
          OLD.system_id AS TEXT));
    END CASE;
    CASE NEW.node_type
      WHEN 0 THEN
        PERFORM pg_notify('machine_create',CAST(
          NEW.system_id AS TEXT));
      WHEN 1 THEN
        PERFORM pg_notify('device_create',CAST(
          NEW.system_id AS TEXT));
      WHEN 2 THEN
        PERFORM pg_notify('controller_create',CAST(
          NEW.system_id AS TEXT));
      WHEN 3 THEN
        PERFORM pg_notify('controller_create',CAST(
          NEW.system_id AS TEXT));
      WHEN 4 THEN
        PERFORM pg_notify('controller_create',CAST(
          NEW.system_id AS TEXT));
    END CASE;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: node_vmcluster_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_vmcluster_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  bmc RECORD;
  hints RECORD;
BEGIN
  IF OLD.bmc_id IS NOT NULL THEN
    SELECT * INTO bmc FROM maasserver_bmc WHERE id = OLD.bmc_id;
    IF bmc.bmc_type = 1 THEN
      SELECT * INTO hints FROM maasserver_podhints WHERE pod_id = bmc.id;
      IF hints.cluster_id IS NOT NULL THEN
        PERFORM pg_notify('vmcluster_update',CAST(hints.cluster_id AS text));
      END IF;
    END IF;
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: node_vmcluster_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_vmcluster_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  bmc RECORD;
  hints RECORD;
BEGIN
  IF NEW.bmc_id IS NOT NULL THEN
    SELECT * INTO bmc FROM maasserver_bmc WHERE id = NEW.bmc_id;
    IF bmc.bmc_type = 1 THEN
      SELECT * INTO hints FROM maasserver_podhints WHERE pod_id = bmc.id;
      IF hints IS NOT NULL AND hints.cluster_id IS NOT NULL THEN
        PERFORM pg_notify('vmcluster_update',CAST(hints.cluster_id AS text));
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: node_vmcluster_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_vmcluster_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  bmc_type INT;
  new_bmc RECORD;
  old_bmc RECORD;
  old_hints RECORD;
  new_hints RECORD;
BEGIN
  bmc_type = 1;
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
      ELSE
        new_hints = NULL;
      END IF;
      IF old_bmc.bmc_type = bmc_type THEN
        SELECT * INTO old_hints FROM maasserver_podhints WHERE pod_id = old_bmc.id;
      ELSE
        old_hints = NULL;
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
$$;


--
-- Name: nodedevice_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nodedevice_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('nodedevice_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: nodedevice_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nodedevice_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('nodedevice_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: nodedevice_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nodedevice_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('nodedevice_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: nodemetadata_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nodemetadata_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nodemetadata_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nodemetadata_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: nodemetadata_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.nodemetadata_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: notification_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notification_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('notification_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: notification_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notification_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('notification_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: notification_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notification_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('notification_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: notificationdismissal_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.notificationdismissal_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify(
      'notificationdismissal_create', CAST(NEW.notification_id AS text) || ':' ||
      CAST(NEW.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: ownerdata_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ownerdata_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: ownerdata_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ownerdata_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = OLD.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: ownerdata_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.ownerdata_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node RECORD;
  pnode RECORD;
BEGIN
  SELECT system_id, node_type, parent_id INTO node
  FROM maasserver_node
  WHERE id = NEW.node_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: packagerepository_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.packagerepository_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('packagerepository_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: packagerepository_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.packagerepository_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('packagerepository_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: packagerepository_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.packagerepository_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('packagerepository_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: pod_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pod_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.bmc_type = 1 THEN
      PERFORM pg_notify('pod_delete',CAST(OLD.id AS text));
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: pod_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pod_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.bmc_type = 1 THEN
    PERFORM pg_notify('pod_create',CAST(NEW.id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: pod_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pod_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.bmc_type = NEW.bmc_type THEN
    IF OLD.bmc_type = 1 THEN
      PERFORM pg_notify('pod_update',CAST(OLD.id AS text));
    END IF;
  ELSIF OLD.bmc_type = 0 AND NEW.bmc_type = 1 THEN
      PERFORM pg_notify('pod_create',CAST(NEW.id AS text));
  ELSIF OLD.bmc_type = 1 AND NEW.bmc_type = 0 THEN
      PERFORM pg_notify('pod_delete',CAST(OLD.id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: rack_controller_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rack_controller_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_create',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: rack_controller_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rack_controller_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_delete',CAST(OLD.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: rack_controller_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rack_controller_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_update',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: region_and_rack_controller_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.region_and_rack_controller_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_create',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: region_and_rack_controller_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.region_and_rack_controller_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_delete',CAST(OLD.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: region_and_rack_controller_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.region_and_rack_controller_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_update',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: region_controller_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.region_controller_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_create',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: region_controller_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.region_controller_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_delete',CAST(OLD.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: region_controller_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.region_controller_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('controller_update',CAST(NEW.system_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: resourcepool_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resourcepool_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('resourcepool_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: resourcepool_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resourcepool_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('resourcepool_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: resourcepool_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resourcepool_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.pool_id IS NOT NULL THEN
    PERFORM pg_notify('resourcepool_update',CAST(NEW.pool_id AS TEXT));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: resourcepool_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resourcepool_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.pool_id IS NOT NULL THEN
    PERFORM pg_notify('resourcepool_update',CAST(OLD.pool_id AS TEXT));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: resourcepool_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.resourcepool_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('resourcepool_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: rrset_sipaddress_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rrset_sipaddress_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain RECORD;
BEGIN
  SELECT maasserver_domain.id INTO domain
  FROM maasserver_dnsresource, maasserver_domain
  WHERE maasserver_domain.id = maasserver_dnsresource.domain_id
  AND maasserver_dnsresource.id = NEW.dnsresource_id;

  IF domain.id IS NOT NULL THEN
    PERFORM pg_notify('domain_update',CAST(domain.id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: rrset_sipaddress_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.rrset_sipaddress_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain RECORD;
BEGIN
  SELECT maasserver_domain.id INTO domain
  FROM maasserver_dnsresource, maasserver_domain
  WHERE maasserver_domain.id = maasserver_dnsresource.domain_id
  AND maasserver_dnsresource.id = OLD.dnsresource_id;

  IF domain.id IS NOT NULL THEN
    PERFORM pg_notify('domain_update',CAST(domain.id AS text));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: script_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.script_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('script_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: script_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.script_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('script_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: script_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.script_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('script_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: scriptresult_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.scriptresult_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('scriptresult_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: scriptresult_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.scriptresult_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('scriptresult_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: scriptresult_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.scriptresult_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('scriptresult_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: service_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.service_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('service_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: service_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.service_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('service_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: service_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.service_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('service_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: space_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.space_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('space_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: space_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.space_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('space_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: space_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.space_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    node RECORD;
    pnode RECORD;
BEGIN
  FOR node IN (
    SELECT DISTINCT ON (maasserver_node.id)
      system_id, node_type, parent_id
    FROM
      maasserver_node,
      maasserver_space,
      maasserver_subnet,
      maasserver_vlan,
      maasserver_interface,
      maasserver_interface_ip_addresses AS ip_link,
      maasserver_staticipaddress
    WHERE maasserver_space.id = NEW.id
    AND maasserver_subnet.vlan_id = maasserver_vlan.id
    AND maasserver_vlan.space_id IS NOT DISTINCT FROM maasserver_space.id
    AND maasserver_staticipaddress.subnet_id = maasserver_subnet.id
    AND ip_link.staticipaddress_id = maasserver_staticipaddress.id
    AND ip_link.interface_id = maasserver_interface.id
    AND maasserver_node.id = maasserver_interface.node_id)
  LOOP
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: space_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.space_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('space_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: sshkey_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sshkey_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('sshkey_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: sshkey_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sshkey_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('sshkey_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: sshkey_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sshkey_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('sshkey_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: sslkey_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sslkey_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('sslkey_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: sslkey_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sslkey_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('sslkey_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: sslkey_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sslkey_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('sslkey_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: staticroute_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.staticroute_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('staticroute_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: staticroute_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.staticroute_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('staticroute_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: staticroute_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.staticroute_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('staticroute_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: subnet_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.subnet_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('subnet_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: subnet_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.subnet_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('subnet_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: subnet_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.subnet_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    node RECORD;
    pnode RECORD;
BEGIN
  FOR node IN (
    SELECT DISTINCT ON (maasserver_node.id)
      system_id, node_type, parent_id
    FROM
      maasserver_node,
      maasserver_subnet,
      maasserver_interface,
      maasserver_interface_ip_addresses AS ip_link,
      maasserver_staticipaddress
    WHERE maasserver_subnet.id = NEW.id
    AND maasserver_staticipaddress.subnet_id = maasserver_subnet.id
    AND ip_link.staticipaddress_id = maasserver_staticipaddress.id
    AND ip_link.interface_id = maasserver_interface.id
    AND maasserver_node.id = maasserver_interface.node_id)
  LOOP
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: subnet_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.subnet_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('subnet_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: maasserver_regioncontrollerprocess; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_regioncontrollerprocess (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    pid integer NOT NULL,
    region_id bigint NOT NULL
);


--
-- Name: sys_core_get_managing_count(public.maasserver_regioncontrollerprocess); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_get_managing_count(process public.maasserver_regioncontrollerprocess) RETURNS integer
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN (SELECT count(*)
    FROM maasserver_node
    WHERE maasserver_node.managing_process_id = process.id);
END;
$$;


--
-- Name: maasserver_node; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_node (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    system_id character varying(41) NOT NULL,
    hostname character varying(255) NOT NULL,
    status integer NOT NULL,
    bios_boot_method character varying(31),
    osystem character varying(255) NOT NULL,
    distro_series character varying(255) NOT NULL,
    architecture character varying(31),
    min_hwe_kernel character varying(31),
    hwe_kernel character varying(31),
    agent_name character varying(255),
    error_description text NOT NULL,
    cpu_count integer NOT NULL,
    memory integer NOT NULL,
    swap_size bigint,
    power_state character varying(10) NOT NULL,
    power_state_updated timestamp with time zone,
    error character varying(255) NOT NULL,
    netboot boolean NOT NULL,
    license_key character varying(30),
    boot_cluster_ip inet,
    enable_ssh boolean NOT NULL,
    skip_networking boolean NOT NULL,
    skip_storage boolean NOT NULL,
    boot_interface_id bigint,
    gateway_link_ipv4_id bigint,
    gateway_link_ipv6_id bigint,
    owner_id integer,
    parent_id bigint,
    zone_id bigint NOT NULL,
    boot_disk_id integer,
    node_type integer NOT NULL,
    domain_id integer,
    dns_process_id bigint,
    bmc_id bigint,
    address_ttl integer,
    status_expires timestamp with time zone,
    power_state_queried timestamp with time zone,
    url character varying(255) NOT NULL,
    managing_process_id bigint,
    last_image_sync timestamp with time zone,
    previous_status integer NOT NULL,
    default_user character varying(32) NOT NULL,
    cpu_speed integer NOT NULL,
    current_commissioning_script_set_id bigint,
    current_installation_script_set_id bigint,
    current_testing_script_set_id bigint,
    install_rackd boolean NOT NULL,
    locked boolean NOT NULL,
    pool_id integer,
    instance_power_parameters jsonb NOT NULL,
    install_kvm boolean NOT NULL,
    hardware_uuid character varying(36),
    ephemeral_deploy boolean NOT NULL,
    description text NOT NULL,
    dynamic boolean NOT NULL,
    register_vmhost boolean NOT NULL,
    last_applied_storage_layout character varying(50) NOT NULL,
    current_config_id bigint,
    enable_hw_sync boolean NOT NULL,
    last_sync timestamp with time zone,
    sync_interval integer,
    current_release_script_set_id bigint,
    CONSTRAINT maasserver_node_address_ttl_check CHECK ((address_ttl >= 0))
);


--
-- Name: sys_core_get_num_conn(public.maasserver_node); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_get_num_conn(rack public.maasserver_node) RETURNS integer
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN (
    SELECT count(*)
    FROM
      maasserver_regionrackrpcconnection AS connection
    WHERE connection.rack_controller_id = rack.id);
END;
$$;


--
-- Name: sys_core_get_num_processes(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_get_num_processes() RETURNS integer
    LANGUAGE plpgsql
    AS $$
BEGIN
  RETURN (
    SELECT count(*) FROM maasserver_regioncontrollerprocess);
END;
$$;


--
-- Name: sys_core_pick_new_region(public.maasserver_node); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_pick_new_region(rack public.maasserver_node) RETURNS public.maasserver_regioncontrollerprocess
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: sys_core_rpc_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_rpc_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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

  -- No connections of the rack controller requires the DNS to be
  -- reloaded for the internal MAAS domain.
  IF sys_core_get_num_conn(rack_controller) = 0 THEN
    PERFORM sys_dns_publish_update(
      'rack controller ' || rack_controller.hostname || ' disconnected');
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_core_rpc_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_rpc_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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

  -- First connection of the rack controller requires the DNS to be
  -- reloaded for the internal MAAS domain.
  IF sys_core_get_num_conn(rack_controller) = 1 THEN
    PERFORM sys_dns_publish_update(
      'rack controller ' || rack_controller.hostname || ' connected');
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_core_set_new_region(public.maasserver_node); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_core_set_new_region(rack public.maasserver_node) RETURNS void
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: maasserver_vlan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_vlan (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256),
    vid integer NOT NULL,
    mtu integer NOT NULL,
    fabric_id bigint NOT NULL,
    dhcp_on boolean NOT NULL,
    primary_rack_id bigint,
    secondary_rack_id bigint,
    external_dhcp inet,
    description text NOT NULL,
    relay_vlan_id bigint,
    space_id bigint
);


--
-- Name: sys_dhcp_alert(public.maasserver_vlan); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_alert(vlan public.maasserver_vlan) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  relay_vlan maasserver_vlan;
BEGIN
  IF vlan.dhcp_on THEN
    PERFORM pg_notify(CONCAT('sys_dhcp_', vlan.primary_rack_id), '');
    IF vlan.secondary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(CONCAT('sys_dhcp_', vlan.secondary_rack_id), '');
    END IF;
  END IF;
  IF vlan.relay_vlan_id IS NOT NULL THEN
    SELECT maasserver_vlan.* INTO relay_vlan
    FROM maasserver_vlan
    WHERE maasserver_vlan.id = vlan.relay_vlan_id;
    IF relay_vlan.dhcp_on THEN
      PERFORM pg_notify(CONCAT(
        'sys_dhcp_', relay_vlan.primary_rack_id), '');
      IF relay_vlan.secondary_rack_id IS NOT NULL THEN
        PERFORM pg_notify(CONCAT(
          'sys_dhcp_', relay_vlan.secondary_rack_id), '');
      END IF;
    END IF;
  END IF;
  RETURN;
END;
$$;


--
-- Name: sys_dhcp_config_ntp_servers_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_config_ntp_servers_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.name IN ('ntp_servers', 'ntp_external_only') THEN
    PERFORM sys_dhcp_update_all_vlans();
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_config_ntp_servers_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_config_ntp_servers_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.name = 'ntp_servers' THEN
    PERFORM sys_dhcp_update_all_vlans();
  ELSIF NEW.name = 'ntp_external_only' THEN
    PERFORM sys_dhcp_update_all_vlans();
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_config_ntp_servers_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_config_ntp_servers_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.name IN ('ntp_servers', 'ntp_external_only')
  OR NEW.name IN ('ntp_servers', 'ntp_external_only') THEN
    IF OLD.value != NEW.value THEN
      PERFORM sys_dhcp_update_all_vlans();
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_interface_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_interface_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
      AND maasserver_staticipaddress.temp_expires_on IS NULL
      AND host(maasserver_staticipaddress.ip) != ''
      AND maasserver_vlan.id = maasserver_subnet.vlan_id)
    LOOP
      PERFORM sys_dhcp_alert(vlan);
    END LOOP;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_iprange_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_iprange_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Update VLAN if DHCP is enabled and was dynamic range.
  IF OLD.type = 'dynamic' THEN
    SELECT maasserver_vlan.* INTO vlan
    FROM maasserver_vlan, maasserver_subnet
    WHERE maasserver_subnet.id = OLD.subnet_id AND
      maasserver_subnet.vlan_id = maasserver_vlan.id;
    PERFORM sys_dhcp_alert(vlan);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_iprange_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_iprange_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Update VLAN if DHCP is enabled and a dynamic range.
  IF NEW.type = 'dynamic' THEN
    SELECT maasserver_vlan.* INTO vlan
    FROM maasserver_vlan, maasserver_subnet
    WHERE maasserver_subnet.id = NEW.subnet_id AND
      maasserver_subnet.vlan_id = maasserver_vlan.id;
    PERFORM sys_dhcp_alert(vlan);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_iprange_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_iprange_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Update VLAN if DHCP is enabled and was or is now a dynamic range.
  IF OLD.type = 'dynamic' OR NEW.type = 'dynamic' THEN
    SELECT maasserver_vlan.* INTO vlan
    FROM maasserver_vlan, maasserver_subnet
    WHERE maasserver_subnet.id = NEW.subnet_id AND
      maasserver_subnet.vlan_id = maasserver_vlan.id;
    PERFORM sys_dhcp_alert(vlan);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_node_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_node_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
      AND maasserver_staticipaddress.temp_expires_on IS NULL
      AND host(maasserver_staticipaddress.ip) != ''
      AND maasserver_vlan.id = maasserver_subnet.vlan_id)
    LOOP
      PERFORM sys_dhcp_alert(vlan);
    END LOOP;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_snippet_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_snippet_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.enabled THEN
    PERFORM sys_dhcp_snippet_update_value(OLD);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_snippet_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_snippet_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.enabled THEN
    PERFORM sys_dhcp_snippet_update_value(NEW);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_snippet_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_snippet_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.enabled = NEW.enabled AND NEW.enabled IS FALSE THEN
    -- If the DHCP snippet is disabled don't fire any alerts
    RETURN NEW;
  ELSIF ((OLD.value_id != NEW.value_id) OR
      (OLD.enabled != NEW.enabled) OR
      (OLD.description != NEW.description)) THEN
    PERFORM sys_dhcp_snippet_update_value(NEW);
  ELSIF ((OLD.subnet_id IS NULL AND NEW.subnet_id IS NOT NULL) OR
      (OLD.subnet_id IS NOT NULL AND NEW.subnet_id IS NULL) OR
      (OLD.subnet_id != NEW.subnet_id)) THEN
    IF NEW.subnet_id IS NOT NULL THEN
      PERFORM sys_dhcp_snippet_update_subnet(NEW.subnet_id);
    END IF;
    IF OLD.subnet_id IS NOT NULL THEN
      PERFORM sys_dhcp_snippet_update_subnet(OLD.subnet_id);
    END IF;
  ELSIF ((OLD.node_id IS NULL AND NEW.node_id IS NOT NULL) OR
      (OLD.node_id IS NOT NULL AND NEW.node_id IS NULL) OR
      (OLD.node_id != NEW.node_id)) THEN
    IF NEW.node_id IS NOT NULL THEN
      PERFORM sys_dhcp_snippet_update_node(NEW.node_id);
    END IF;
    IF OLD.node_id IS NOT NULL THEN
      PERFORM sys_dhcp_snippet_update_node(OLD.node_id);
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_snippet_update_node(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_snippet_update_node(_node_id integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  rack INTEGER;
BEGIN
  FOR rack IN (
    WITH racks AS (
      SELECT primary_rack_id, secondary_rack_id
      FROM maasserver_vlan, maasserver_interface
      WHERE maasserver_interface.node_id = _node_id
        AND maasserver_interface.vlan_id = maasserver_vlan.id
      AND (maasserver_vlan.dhcp_on = true
        OR maasserver_vlan.relay_vlan_id IS NOT NULL))
    SELECT primary_rack_id FROM racks
    WHERE primary_rack_id IS NOT NULL
    UNION
    SELECT secondary_rack_id FROM racks
    WHERE secondary_rack_id IS NOT NULL)
  LOOP
    PERFORM pg_notify(CONCAT('sys_dhcp_', rack), '');
  END LOOP;
  RETURN;
END;
$$;


--
-- Name: sys_dhcp_snippet_update_subnet(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_snippet_update_subnet(_subnet_id integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  FOR vlan IN (
    SELECT
      maasserver_vlan.*
    FROM
      maasserver_vlan,
      maasserver_subnet
    WHERE maasserver_subnet.id = _subnet_id
      AND maasserver_vlan.id = maasserver_subnet.vlan_id
      AND (maasserver_vlan.dhcp_on = true
        OR maasserver_vlan.relay_vlan_id IS NOT NULL))
    LOOP
      PERFORM sys_dhcp_alert(vlan);
    END LOOP;
  RETURN;
END;
$$;


--
-- Name: maasserver_dhcpsnippet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dhcpsnippet (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    enabled boolean NOT NULL,
    node_id bigint,
    subnet_id bigint,
    value_id bigint NOT NULL,
    iprange_id bigint
);


--
-- Name: sys_dhcp_snippet_update_value(public.maasserver_dhcpsnippet); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_snippet_update_value(_dhcp_snippet public.maasserver_dhcpsnippet) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF _dhcp_snippet.subnet_id IS NOT NULL THEN
    PERFORM sys_dhcp_snippet_update_subnet(_dhcp_snippet.subnet_id);
  ELSIF _dhcp_snippet.node_id is NOT NULL THEN
    PERFORM sys_dhcp_snippet_update_node(_dhcp_snippet.node_id);
  ELSE
    -- This is a global snippet, everyone has to update. This should only
    -- be triggered when neither subnet_id or node_id are set. We verify
    -- that only subnet_id xor node_id are set in DHCPSnippet.clean()
    PERFORM sys_dhcp_update_all_vlans();
  END IF;
  RETURN;
END;
$$;


--
-- Name: sys_dhcp_staticipaddress_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_staticipaddress_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Update VLAN if DHCP is enabled and has an IP address.
  IF host(OLD.ip) != '' AND OLD.temp_expires_on IS NULL THEN
    SELECT maasserver_vlan.* INTO vlan
    FROM maasserver_vlan, maasserver_subnet
    WHERE maasserver_subnet.id = OLD.subnet_id AND
      maasserver_subnet.vlan_id = maasserver_vlan.id;
    PERFORM sys_dhcp_alert(vlan);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_staticipaddress_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_staticipaddress_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Update VLAN if DHCP is enabled, IP is set and not DISCOVERED.
  IF NEW.alloc_type != 6 AND NEW.ip IS NOT NULL AND host(NEW.ip) != '' AND
    NEW.temp_expires_on IS NULL THEN
    SELECT maasserver_vlan.* INTO vlan
    FROM maasserver_vlan, maasserver_subnet
    WHERE maasserver_subnet.id = NEW.subnet_id AND
      maasserver_subnet.vlan_id = maasserver_vlan.id;
    PERFORM sys_dhcp_alert(vlan);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_staticipaddress_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_staticipaddress_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
        PERFORM sys_dhcp_alert(old_vlan);
        PERFORM sys_dhcp_alert(new_vlan);
      ELSE
        -- Same VLAN so only need to update once.
        PERFORM sys_dhcp_alert(new_vlan);
      END IF;
    ELSIF (OLD.ip IS NULL AND NEW.ip IS NOT NULL) OR
      (OLD.ip IS NOT NULL and NEW.ip IS NULL) OR
      (OLD.temp_expires_on IS NULL AND NEW.temp_expires_on IS NOT NULL) OR
      (OLD.temp_expires_on IS NOT NULL AND NEW.temp_expires_on IS NULL) OR
      (host(OLD.ip) != host(NEW.ip)) THEN
      -- Assigned IP address has changed.
      SELECT maasserver_vlan.* INTO new_vlan
      FROM maasserver_vlan, maasserver_subnet
      WHERE maasserver_subnet.id = NEW.subnet_id AND
        maasserver_subnet.vlan_id = maasserver_vlan.id;
      PERFORM sys_dhcp_alert(new_vlan);
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_subnet_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_subnet_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Update VLAN if DHCP is enabled.
  SELECT * INTO vlan
  FROM maasserver_vlan WHERE id = OLD.vlan_id;
  PERFORM sys_dhcp_alert(vlan);
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_subnet_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_subnet_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  vlan maasserver_vlan;
BEGIN
  -- Subnet was moved to a new VLAN.
  IF OLD.vlan_id != NEW.vlan_id THEN
    -- Update old VLAN if DHCP is enabled.
    SELECT * INTO vlan
    FROM maasserver_vlan WHERE id = OLD.vlan_id;
    PERFORM sys_dhcp_alert(vlan);
    -- Update the new VLAN if DHCP is enabled.
    SELECT * INTO vlan
    FROM maasserver_vlan WHERE id = NEW.vlan_id;
    PERFORM sys_dhcp_alert(vlan);
  -- Related fields of subnet where changed.
  ELSIF OLD.cidr != NEW.cidr OR
    (OLD.gateway_ip IS NULL AND NEW.gateway_ip IS NOT NULL) OR
    (OLD.gateway_ip IS NOT NULL AND NEW.gateway_ip IS NULL) OR
    host(OLD.gateway_ip) != host(NEW.gateway_ip) OR
    OLD.dns_servers != NEW.dns_servers OR
    OLD.allow_dns != NEW.allow_dns OR
    OLD.disabled_boot_architectures != NEW.disabled_boot_architectures THEN
    -- Network has changed update alert DHCP if enabled.
    SELECT * INTO vlan
    FROM maasserver_vlan WHERE id = NEW.vlan_id;
    PERFORM sys_dhcp_alert(vlan);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dhcp_update_all_vlans(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_update_all_vlans() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
  rack INTEGER;
BEGIN
  FOR rack IN (
    WITH racks AS (
      SELECT primary_rack_id, secondary_rack_id FROM maasserver_vlan
      WHERE maasserver_vlan.dhcp_on = true
    )
    SELECT primary_rack_id FROM racks
    WHERE primary_rack_id IS NOT NULL
    UNION
    SELECT secondary_rack_id FROM racks
    WHERE secondary_rack_id IS NOT NULL)
  LOOP
    PERFORM pg_notify(CONCAT('sys_dhcp_', rack), '');
  END LOOP;
  RETURN;
END;
$$;


--
-- Name: sys_dhcp_vlan_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dhcp_vlan_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  relay_vlan maasserver_vlan;
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
  -- MTU was changed.
  ELSIF OLD.mtu != NEW.mtu THEN
    PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.primary_rack_id), '');
    IF OLD.secondary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.secondary_rack_id), '');
    END IF;
  -- DHCP state was not changed but the rack controllers might have been.
  ELSIF NEW.dhcp_on AND (
     OLD.primary_rack_id != NEW.primary_rack_id OR (
       OLD.secondary_rack_id IS NULL AND
       NEW.secondary_rack_id IS NOT NULL) OR (
       OLD.secondary_rack_id IS NOT NULL AND
       NEW.secondary_rack_id IS NULL) OR
     OLD.secondary_rack_id != NEW.secondary_rack_id) THEN
    -- Send the message to the old primary if no longer the primary.
    IF OLD.primary_rack_id != NEW.primary_rack_id THEN
      PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.primary_rack_id), '');
    END IF;
    -- Always send the message to the primary as it has to be set.
    PERFORM pg_notify(CONCAT('sys_dhcp_', NEW.primary_rack_id), '');
    -- Send message to both old and new secondary rack controller if set.
    IF OLD.secondary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(CONCAT('sys_dhcp_', OLD.secondary_rack_id), '');
    END IF;
    IF NEW.secondary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(CONCAT('sys_dhcp_', NEW.secondary_rack_id), '');
    END IF;
  END IF;

  -- Relay VLAN was set when it was previously unset, or
  -- the MTU has changed for a VLAN with DHCP relay enabled.
  IF (OLD.relay_vlan_id IS NULL AND NEW.relay_vlan_id IS NOT NULL)
     OR (OLD.mtu != NEW.mtu AND NEW.relay_vlan_id IS NOT NULL) THEN
    SELECT maasserver_vlan.* INTO relay_vlan
    FROM maasserver_vlan
    WHERE maasserver_vlan.id = NEW.relay_vlan_id;
    IF relay_vlan.primary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(
        CONCAT('sys_dhcp_', relay_vlan.primary_rack_id), '');
      IF relay_vlan.secondary_rack_id IS NOT NULL THEN
        PERFORM pg_notify(
          CONCAT('sys_dhcp_', relay_vlan.secondary_rack_id), '');
      END IF;
    END IF;
  -- Relay VLAN was unset when it was previously set.
  ELSIF OLD.relay_vlan_id IS NOT NULL AND NEW.relay_vlan_id IS NULL THEN
    SELECT maasserver_vlan.* INTO relay_vlan
    FROM maasserver_vlan
    WHERE maasserver_vlan.id = OLD.relay_vlan_id;
    IF relay_vlan.primary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(
        CONCAT('sys_dhcp_', relay_vlan.primary_rack_id), '');
      IF relay_vlan.secondary_rack_id IS NOT NULL THEN
        PERFORM pg_notify(
          CONCAT('sys_dhcp_', relay_vlan.secondary_rack_id), '');
      END IF;
    END IF;
  -- Relay VLAN has changed on the VLAN.
  ELSIF OLD.relay_vlan_id != NEW.relay_vlan_id THEN
    -- Alert old VLAN if required.
    SELECT maasserver_vlan.* INTO relay_vlan
    FROM maasserver_vlan
    WHERE maasserver_vlan.id = OLD.relay_vlan_id;
    IF relay_vlan.primary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(
        CONCAT('sys_dhcp_', relay_vlan.primary_rack_id), '');
      IF relay_vlan.secondary_rack_id IS NOT NULL THEN
        PERFORM pg_notify(
          CONCAT('sys_dhcp_', relay_vlan.secondary_rack_id), '');
      END IF;
    END IF;
    -- Alert new VLAN if required.
    SELECT maasserver_vlan.* INTO relay_vlan
    FROM maasserver_vlan
    WHERE maasserver_vlan.id = NEW.relay_vlan_id;
    IF relay_vlan.primary_rack_id IS NOT NULL THEN
      PERFORM pg_notify(
        CONCAT('sys_dhcp_', relay_vlan.primary_rack_id), '');
      IF relay_vlan.secondary_rack_id IS NOT NULL THEN
        PERFORM pg_notify(
          CONCAT('sys_dhcp_', relay_vlan.secondary_rack_id), '');
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_config_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_config_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Only care about the
  IF (NEW.name = 'upstream_dns' OR
      NEW.name = 'dnssec_validation' OR
      NEW.name = 'dns_trusted_acl' OR
      NEW.name = 'default_dns_ttl' OR
      NEW.name = 'windows_kms_host' OR
      NEW.name = 'maas_internal_domain')
  THEN
    PERFORM sys_dns_publish_update(
      'configuration ' || NEW.name || ' set to ' ||
      COALESCE(NEW.value, 'NULL'));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_config_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_config_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  -- Only care about the upstream_dns, default_dns_ttl,
  -- dns_trusted_acl and windows_kms_host.
  IF (OLD.value != NEW.value AND (
      NEW.name = 'upstream_dns' OR
      NEW.name = 'dnssec_validation' OR
      NEW.name = 'dns_trusted_acl' OR
      NEW.name = 'default_dns_ttl' OR
      NEW.name = 'windows_kms_host' OR
      NEW.name = 'maas_internal_domain'))
  THEN
    PERFORM sys_dns_publish_update(
      'configuration ' || NEW.name || ' changed to ' || NEW.value);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_dnsdata_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsdata_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  resource maasserver_dnsresource;
  domain maasserver_domain;
BEGIN
  SELECT maasserver_dnsresource.* INTO resource
  FROM maasserver_dnsresource
  WHERE maasserver_dnsresource.id = OLD.dnsresource_id;
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = resource.domain_id;
  PERFORM sys_dns_publish_update(
    'removed ' || OLD.rrtype || ' from resource ' || resource.name ||
    ' on zone ' || domain.name);
  RETURN OLD;
END;
$$;


--
-- Name: sys_dns_dnsdata_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsdata_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  resource maasserver_dnsresource;
  domain maasserver_domain;
BEGIN
  SELECT maasserver_dnsresource.* INTO resource
  FROM maasserver_dnsresource
  WHERE maasserver_dnsresource.id = NEW.dnsresource_id;
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = resource.domain_id;
  PERFORM sys_dns_publish_update(
    'added ' || NEW.rrtype || ' to resource ' || resource.name ||
    ' on zone ' || domain.name);
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_dnsdata_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsdata_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  resource maasserver_dnsresource;
  domain maasserver_domain;
BEGIN
  SELECT maasserver_dnsresource.* INTO resource
  FROM maasserver_dnsresource
  WHERE maasserver_dnsresource.id = NEW.dnsresource_id;
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = resource.domain_id;
  PERFORM sys_dns_publish_update(
    'updated ' || NEW.rrtype || ' in resource ' || resource.name ||
    ' on zone ' || domain.name);
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_dnsresource_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsresource_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain maasserver_domain;
BEGIN
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = OLD.domain_id;
  PERFORM sys_dns_publish_update(
    'zone ' || domain.name || ' removed resource ' ||
    COALESCE(OLD.name, 'NULL'));
  RETURN OLD;
END;
$$;


--
-- Name: sys_dns_dnsresource_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsresource_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain maasserver_domain;
BEGIN
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = NEW.domain_id;
  PERFORM sys_dns_publish_update(
    'zone ' || domain.name || ' added resource ' ||
    COALESCE(NEW.name, 'NULL'));
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_dnsresource_ip_link(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsresource_ip_link() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  sip maasserver_staticipaddress;
  resource maasserver_dnsresource;
  domain maasserver_domain;
BEGIN
  SELECT maasserver_staticipaddress.* INTO sip
  FROM maasserver_staticipaddress
  WHERE maasserver_staticipaddress.id = NEW.staticipaddress_id;
  SELECT maasserver_dnsresource.* INTO resource
  FROM maasserver_dnsresource
  WHERE maasserver_dnsresource.id = NEW.dnsresource_id;
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = resource.domain_id;
  IF sip.ip IS NOT NULL THEN
      PERFORM sys_dns_publish_update(
        'ip ' || host(sip.ip) || ' linked to resource ' ||
        COALESCE(resource.name, 'NULL') || ' on zone ' || domain.name);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_dnsresource_ip_unlink(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsresource_ip_unlink() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  sip maasserver_staticipaddress;
  resource maasserver_dnsresource;
  domain maasserver_domain;
BEGIN
  SELECT maasserver_staticipaddress.* INTO sip
  FROM maasserver_staticipaddress
  WHERE maasserver_staticipaddress.id = OLD.staticipaddress_id;
  SELECT maasserver_dnsresource.* INTO resource
  FROM maasserver_dnsresource
  WHERE maasserver_dnsresource.id = OLD.dnsresource_id;
  SELECT maasserver_domain.* INTO domain
  FROM maasserver_domain
  WHERE maasserver_domain.id = resource.domain_id;
  IF sip.ip IS NOT NULL THEN
      PERFORM sys_dns_publish_update(
        'ip ' || host(sip.ip) || ' unlinked from resource ' ||
        COALESCE(resource.name, 'NULL') || ' on zone ' || domain.name);
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: sys_dns_dnsresource_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_dnsresource_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain maasserver_domain;
BEGIN
  IF OLD.domain_id != NEW.domain_id THEN
    SELECT maasserver_domain.* INTO domain
    FROM maasserver_domain
    WHERE maasserver_domain.id = OLD.domain_id;
    PERFORM sys_dns_publish_update(
      'zone ' || domain.name || ' removed resource ' ||
      COALESCE(NEW.name, 'NULL'));
    SELECT maasserver_domain.* INTO domain
    FROM maasserver_domain
    WHERE maasserver_domain.id = NEW.domain_id;
    PERFORM sys_dns_publish_update(
      'zone ' || domain.name || ' added resource ' ||
      COALESCE(NEW.name, 'NULL'));
  ELSIF ((OLD.name IS NULL AND NEW.name IS NOT NULL) OR
      (OLD.name IS NOT NULL AND NEW.name IS NULL) OR
      (OLD.name != NEW.name) OR
      (OLD.address_ttl IS NULL AND NEW.address_ttl IS NOT NULL) OR
      (OLD.address_ttl IS NOT NULL AND NEW.address_ttl IS NULL) OR
      (OLD.address_ttl != NEW.address_ttl)) THEN
    SELECT maasserver_domain.* INTO domain
    FROM maasserver_domain
    WHERE maasserver_domain.id = NEW.domain_id;
    PERFORM sys_dns_publish_update(
      'zone ' || domain.name || ' updated resource ' ||
      COALESCE(NEW.name, 'NULL'));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_domain_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_domain_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.authoritative THEN
    PERFORM sys_dns_publish_update(
        'removed zone ' || OLD.name);
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: sys_dns_domain_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_domain_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.authoritative THEN
      PERFORM sys_dns_publish_update(
        'added zone ' || NEW.name);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_domain_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_domain_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  changes text[];
BEGIN
  IF OLD.authoritative AND NOT NEW.authoritative THEN
    PERFORM sys_dns_publish_update(
        'removed zone ' || NEW.name);
  ELSIF NOT OLD.authoritative AND NEW.authoritative THEN
    PERFORM sys_dns_publish_update(
        'added zone ' || NEW.name);
  ELSIF OLD.authoritative and NEW.authoritative THEN
    IF OLD.name != NEW.name THEN
        changes := changes || ('renamed to ' || NEW.name);
    END IF;
    IF ((OLD.ttl IS NULL AND NEW.ttl IS NOT NULL) OR
        (OLD.ttl IS NOT NULL and NEW.ttl IS NULL) OR
        (OLD.ttl != NEW.ttl)) THEN
        changes := changes || (
          'ttl changed to ' || COALESCE(text(NEW.ttl), 'default'));
    END IF;
    IF array_length(changes, 1) != 0 THEN
      PERFORM sys_dns_publish_update(
        'zone ' || OLD.name || ' ' || array_to_string(changes, ' and '));
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_interface_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_interface_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node maasserver_node;
  changes text[];
BEGIN
  IF OLD.name != NEW.name AND OLD.node_id = NEW.node_id THEN
    IF NEW.node_id IS NOT NULL THEN
        SELECT maasserver_node.* INTO node
        FROM maasserver_node
        WHERE maasserver_node.id = NEW.node_id;
        IF EXISTS(
            SELECT maasserver_domain.id
            FROM maasserver_domain
            WHERE
              maasserver_domain.authoritative = TRUE AND
              maasserver_domain.id = node.domain_id) THEN
          PERFORM sys_dns_publish_update(
            'node ' || node.hostname || ' renamed interface ' ||
            OLD.name || ' to ' || NEW.name);
        END IF;
    END IF;
  ELSIF OLD.node_id IS NULL and NEW.node_id IS NOT NULL THEN
    SELECT maasserver_node.* INTO node
    FROM maasserver_node
    WHERE maasserver_node.id = NEW.node_id;
    IF EXISTS(
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.authoritative = TRUE AND
          maasserver_domain.id = node.domain_id) THEN
      PERFORM sys_dns_publish_update(
        'node ' || node.hostname || ' added interface ' || NEW.name);
    END IF;
  ELSIF OLD.node_id IS NOT NULL and NEW.node_id IS NULL THEN
    SELECT maasserver_node.* INTO node
    FROM maasserver_node
    WHERE maasserver_node.id = OLD.node_id;
    IF EXISTS(
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.authoritative = TRUE AND
          maasserver_domain.id = node.domain_id) THEN
      PERFORM sys_dns_publish_update(
        'node ' || node.hostname || ' removed interface ' || NEW.name);
    END IF;
  ELSIF OLD.node_id != NEW.node_id THEN
    SELECT maasserver_node.* INTO node
    FROM maasserver_node
    WHERE maasserver_node.id = OLD.node_id;
    IF EXISTS(
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.authoritative = TRUE AND
          maasserver_domain.id = node.domain_id) THEN
      PERFORM sys_dns_publish_update(
        'node ' || node.hostname || ' removed interface ' || NEW.name);
    END IF;
    SELECT maasserver_node.* INTO node
    FROM maasserver_node
    WHERE maasserver_node.id = NEW.node_id;
    IF EXISTS(
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.authoritative = TRUE AND
          maasserver_domain.id = node.domain_id) THEN
      PERFORM sys_dns_publish_update(
        'node ' || node.hostname || ' added interface ' || NEW.name);
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_nic_ip_link(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_nic_ip_link() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node maasserver_node;
  nic maasserver_interface;
  ip maasserver_staticipaddress;
BEGIN
  SELECT maasserver_interface.* INTO nic
  FROM maasserver_interface
  WHERE maasserver_interface.id = NEW.interface_id;
  SELECT maasserver_node.* INTO node
  FROM maasserver_node
  WHERE maasserver_node.id = nic.node_id;
  SELECT maasserver_staticipaddress.* INTO ip
  FROM maasserver_staticipaddress
  WHERE maasserver_staticipaddress.id = NEW.staticipaddress_id;
  IF (ip.ip IS NOT NULL AND ip.temp_expires_on IS NULL AND
      host(ip.ip) != '' AND EXISTS (
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.id = node.domain_id AND
          maasserver_domain.authoritative = TRUE))
  THEN
    PERFORM sys_dns_publish_update(
      'ip ' || host(ip.ip) || ' connected to ' || node.hostname ||
      ' on ' || nic.name);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_nic_ip_unlink(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_nic_ip_unlink() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  node maasserver_node;
  nic maasserver_interface;
  ip maasserver_staticipaddress;
  changes text[];
BEGIN
  SELECT maasserver_interface.* INTO nic
  FROM maasserver_interface
  WHERE maasserver_interface.id = OLD.interface_id;
  SELECT maasserver_node.* INTO node
  FROM maasserver_node
  WHERE maasserver_node.id = nic.node_id;
  SELECT maasserver_staticipaddress.* INTO ip
  FROM maasserver_staticipaddress
  WHERE maasserver_staticipaddress.id = OLD.staticipaddress_id;
  IF (ip.ip IS NOT NULL AND ip.temp_expires_on IS NULL AND EXISTS (
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.id = node.domain_id AND
          maasserver_domain.authoritative = TRUE))
  THEN
    PERFORM sys_dns_publish_update(
      'ip ' || host(ip.ip) || ' disconnected from ' || node.hostname ||
      ' on ' || nic.name);
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: sys_dns_node_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_node_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain maasserver_domain;
  new_domain maasserver_domain;
  changes text[];
BEGIN
  IF EXISTS(
      SELECT maasserver_domain.id
      FROM maasserver_domain
      WHERE
        maasserver_domain.authoritative = TRUE AND
        maasserver_domain.id = OLD.domain_id) THEN
    PERFORM sys_dns_publish_update(
      'removed node ' || OLD.hostname);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_node_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_node_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  domain maasserver_domain;
  new_domain maasserver_domain;
  changes text[];
BEGIN
  IF OLD.hostname != NEW.hostname AND OLD.domain_id = NEW.domain_id THEN
    IF EXISTS(
        SELECT maasserver_domain.id
        FROM maasserver_domain
        WHERE
          maasserver_domain.authoritative = TRUE AND
          maasserver_domain.id = NEW.domain_id) THEN
      PERFORM sys_dns_publish_update(
        'node ' || OLD.hostname || ' changed hostname to ' ||
        NEW.hostname);
    END IF;
  ELSIF OLD.domain_id != NEW.domain_id THEN
    -- Domains have changed. If either one is authoritative then DNS
    -- needs to be updated.
    SELECT maasserver_domain.* INTO domain
    FROM maasserver_domain
    WHERE maasserver_domain.id = OLD.domain_id;
    SELECT maasserver_domain.* INTO new_domain
    FROM maasserver_domain
    WHERE maasserver_domain.id = NEW.domain_id;
    IF domain.authoritative = TRUE OR new_domain.authoritative = TRUE THEN
        PERFORM sys_dns_publish_update(
          'node ' || NEW.hostname || ' changed zone to ' ||
          new_domain.name);
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_publish(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_publish() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM pg_notify('sys_dns', '');
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_publish_update(text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_publish_update(reason text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO maasserver_dnspublication
    (serial, created, source)
  VALUES
    (nextval('maasserver_zone_serial_seq'), now(),
     substring(reason FOR 255));
END;
$$;


--
-- Name: sys_dns_staticipaddress_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_staticipaddress_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF ((OLD.ip IS NULL and NEW.ip IS NOT NULL) OR
      (OLD.ip IS NOT NULL and NEW.ip IS NULL) OR
      (OLD.temp_expires_on IS NULL AND NEW.temp_expires_on IS NOT NULL) OR
      (OLD.temp_expires_on IS NOT NULL AND NEW.temp_expires_on IS NULL) OR
      (OLD.ip != NEW.ip)) OR
      (OLD.alloc_type != NEW.alloc_type) THEN
    IF EXISTS (
        SELECT
          domain.id
        FROM maasserver_staticipaddress AS staticipaddress
        LEFT JOIN (
          maasserver_interface_ip_addresses AS iia
          JOIN maasserver_interface AS interface ON
            iia.interface_id = interface.id
          JOIN maasserver_node AS node ON
            node.id = interface.node_id) ON
          iia.staticipaddress_id = staticipaddress.id
        LEFT JOIN (
          maasserver_dnsresource_ip_addresses AS dia
          JOIN maasserver_dnsresource AS dnsresource ON
            dia.dnsresource_id = dnsresource.id) ON
          dia.staticipaddress_id = staticipaddress.id
        JOIN maasserver_domain AS domain ON
          domain.id = node.domain_id OR domain.id = dnsresource.domain_id
        WHERE
          domain.authoritative = TRUE AND
          (staticipaddress.id = OLD.id OR
           staticipaddress.id = NEW.id))
    THEN
      IF OLD.ip IS NULL and NEW.ip IS NOT NULL and
        NEW.temp_expires_on IS NULL THEN
        PERFORM sys_dns_publish_update(
          'ip ' || host(NEW.ip) || ' allocated');
        RETURN NEW;
      ELSIF OLD.ip IS NOT NULL and NEW.ip IS NULL and
        NEW.temp_expires_on IS NULL THEN
        PERFORM sys_dns_publish_update(
          'ip ' || host(OLD.ip) || ' released');
        RETURN NEW;
      ELSIF OLD.ip != NEW.ip and NEW.temp_expires_on IS NULL THEN
        PERFORM sys_dns_publish_update(
          'ip ' || host(OLD.ip) || ' changed to ' || host(NEW.ip));
        RETURN NEW;
      ELSIF OLD.ip = NEW.ip and OLD.temp_expires_on IS NOT NULL and
        NEW.temp_expires_on IS NULL THEN
        PERFORM sys_dns_publish_update(
          'ip ' || host(NEW.ip) || ' allocated');
        RETURN NEW;
      ELSIF OLD.ip = NEW.ip and OLD.temp_expires_on IS NULL and
        NEW.temp_expires_on IS NOT NULL THEN
        PERFORM sys_dns_publish_update(
          'ip ' || host(NEW.ip) || ' released');
        RETURN NEW;
      END IF;

      -- Made it this far then only alloc_type has changed. Only send
      -- a notification is the IP address is assigned.
      IF NEW.ip IS NOT NULL and NEW.temp_expires_on IS NULL THEN
        PERFORM sys_dns_publish_update(
          'ip ' || host(OLD.ip) || ' alloc_type changed to ' ||
          NEW.alloc_type);
      END IF;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_subnet_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_subnet_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  changes text[];
BEGIN
  IF OLD.rdns_mode != 0 THEN
    PERFORM sys_dns_publish_update('removed subnet ' || text(OLD.cidr));
  END IF;
  RETURN OLD;
END;
$$;


--
-- Name: sys_dns_subnet_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_subnet_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  changes text[];
BEGIN
  IF NEW.rdns_mode != 0 THEN
    PERFORM sys_dns_publish_update('added subnet ' || text(NEW.cidr));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_dns_subnet_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_dns_subnet_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.cidr != NEW.cidr THEN
    PERFORM sys_dns_publish_update(
        'subnet ' || text(OLD.cidr) || ' changed to ' || text(NEW.CIDR));
    RETURN NEW;
  END IF;
  IF OLD.rdns_mode != NEW.rdns_mode THEN
    PERFORM sys_dns_publish_update(
        'subnet ' || text(NEW.cidr) || ' rdns changed to ' ||
        NEW.rdns_mode);
  END IF;
  IF OLD.allow_dns != NEW.allow_dns THEN
    PERFORM sys_dns_publish_update(
        'subnet ' || text(NEW.cidr) || ' allow_dns changed to ' ||
        NEW.allow_dns);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_proxy_config_use_peer_proxy_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_proxy_config_use_peer_proxy_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: sys_proxy_config_use_peer_proxy_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_proxy_config_use_peer_proxy_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: sys_proxy_subnet_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_proxy_subnet_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM pg_notify('sys_proxy', '');
  RETURN OLD;
END;
$$;


--
-- Name: sys_proxy_subnet_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_proxy_subnet_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM pg_notify('sys_proxy', '');
  RETURN NEW;
END;
$$;


--
-- Name: sys_proxy_subnet_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_proxy_subnet_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF OLD.cidr != NEW.cidr OR OLD.allow_proxy != NEW.allow_proxy THEN
    PERFORM pg_notify('sys_proxy', '');
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_rbac_config_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_config_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF (NEW.name = 'external_auth_url' OR
      NEW.name = 'external_auth_user' OR
      NEW.name = 'external_auth_key' OR
      NEW.name = 'rbac_url') THEN
    PERFORM sys_rbac_sync_update(
      'configuration ' || NEW.name || ' set to ' ||
      COALESCE(NEW.value, 'NULL'));
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_rbac_config_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_config_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF (OLD.value != NEW.value AND (
      NEW.name = 'external_auth_url' OR
      NEW.name = 'external_auth_user' OR
      NEW.name = 'external_auth_key' OR
      NEW.name = 'rbac_url')) THEN
    PERFORM sys_rbac_sync_update(
      'configuration ' || NEW.name || ' changed to ' || NEW.value);
  END IF;
  RETURN NEW;
END;
$$;


--
-- Name: sys_rbac_rpool_delete(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_rpool_delete() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM sys_rbac_sync_update(
    'removed resource pool ' || OLD.name,
    'remove', 'resource-pool', OLD.id, OLD.name);
  RETURN OLD;
END;
$$;


--
-- Name: sys_rbac_rpool_insert(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_rpool_insert() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM sys_rbac_sync_update(
    'added resource pool ' || NEW.name,
    'add', 'resource-pool', NEW.id, NEW.name);
  RETURN NEW;
END;
$$;


--
-- Name: sys_rbac_rpool_update(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_rpool_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


--
-- Name: sys_rbac_sync(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_sync() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  PERFORM pg_notify('sys_rbac', '');
  RETURN NEW;
END;
$$;


--
-- Name: sys_rbac_sync_update(text, text, text, integer, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.sys_rbac_sync_update(reason text, action text DEFAULT 'full'::text, resource_type text DEFAULT ''::text, resource_id integer DEFAULT NULL::integer, resource_name text DEFAULT ''::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO maasserver_rbacsync
    (created, source, action, resource_type, resource_id, resource_name)
  VALUES (
    now(), substring(reason FOR 255),
    action, resource_type, resource_id, resource_name);
END;
$$;


--
-- Name: tag_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tag_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('tag_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: tag_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tag_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('tag_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: tag_update_machine_device_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tag_update_machine_device_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: tag_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.tag_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('tag_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: token_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.token_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('token_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: token_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.token_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('token_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_sshkey_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_sshkey_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(NEW.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_sshkey_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_sshkey_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(OLD.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_sslkey_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_sslkey_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(NEW.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_sslkey_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_sslkey_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(OLD.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_token_link_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_token_link_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(NEW.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_token_unlink_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_token_unlink_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(OLD.user_id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: user_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.user_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('user_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: vlan_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vlan_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('vlan_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: vlan_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vlan_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('vlan_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: vlan_machine_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vlan_machine_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    node RECORD;
    pnode RECORD;
BEGIN
  FOR node IN (
    SELECT DISTINCT ON (maasserver_node.id)
      system_id, node_type, parent_id
    FROM maasserver_node, maasserver_interface, maasserver_vlan
    WHERE maasserver_vlan.id = NEW.id
    AND maasserver_node.id = maasserver_interface.node_id
    AND maasserver_vlan.id = maasserver_interface.vlan_id)
  LOOP
    IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update',CAST(node.system_id AS text));
    ELSIF node.node_type IN (2, 3, 4) THEN
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
$$;


--
-- Name: vlan_subnet_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vlan_subnet_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    subnet RECORD;
BEGIN
  FOR subnet IN (
    SELECT DISTINCT maasserver_subnet.id AS id
    FROM maasserver_subnet, maasserver_vlan
    WHERE maasserver_vlan.id = NEW.id)
  LOOP
    PERFORM pg_notify('subnet_update',CAST(subnet.id AS text));
  END LOOP;
  RETURN NEW;
END;
$$;


--
-- Name: vlan_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vlan_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('vlan_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: vmcluster_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vmcluster_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM pg_notify('vmcluster_delete',CAST(OLD.id as text));
    RETURN OLD;
END;
$$;


--
-- Name: vmcluster_insert_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vmcluster_insert_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM pg_notify('vmcluster_create',CAST(NEW.id AS text));
    RETURN NEW;
END;
$$;


--
-- Name: vmcluster_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.vmcluster_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    PERFORM pg_notify('vmcluster_update',CAST(NEW.id AS text));
    RETURN NEW;
END;
$$;


--
-- Name: zone_create_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.zone_create_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('zone_create',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: zone_delete_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.zone_delete_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('zone_delete',CAST(OLD.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: zone_update_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.zone_update_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
BEGIN
  PERFORM pg_notify('zone_update',CAST(NEW.id AS text));
  RETURN NEW;
END;
$$;


--
-- Name: convert_ts(character varying); Type: FUNCTION; Schema: temporal_visibility; Owner: -
--

CREATE FUNCTION temporal_visibility.convert_ts(s character varying) RETURNS timestamp without time zone
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
BEGIN
  RETURN s::timestamptz at time zone 'UTC';
END
$$;


--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_group_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_group_id_seq OWNED BY public.auth_group.id;


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id integer NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_group_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_group_permissions_id_seq OWNED BY public.auth_group_permissions.id;


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_permission_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_permission_id_seq OWNED BY public.auth_permission.id;


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user (
    id integer NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    email character varying(254),
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL
);


--
-- Name: auth_user_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_groups (
    id integer NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_groups_id_seq OWNED BY public.auth_user_groups.id;


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_id_seq OWNED BY public.auth_user.id;


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_user_permissions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auth_user_user_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auth_user_user_permissions_id_seq OWNED BY public.auth_user_user_permissions.id;


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.django_content_type_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_content_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.django_content_type_id_seq OWNED BY public.django_content_type.id;


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id integer NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.django_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.django_migrations_id_seq OWNED BY public.django_migrations.id;


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


--
-- Name: django_site; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_site (
    id integer NOT NULL,
    domain character varying(100) NOT NULL,
    name character varying(50) NOT NULL
);


--
-- Name: django_site_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.django_site_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_site_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.django_site_id_seq OWNED BY public.django_site.id;


--
-- Name: maasserver_sshkey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_sshkey (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key text NOT NULL,
    user_id integer NOT NULL,
    keysource_id bigint
);


--
-- Name: maas_support__ssh_keys__by_user; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__ssh_keys__by_user AS
 SELECT u.username,
    sshkey.key
   FROM (public.auth_user u
     LEFT JOIN public.maasserver_sshkey sshkey ON ((u.id = sshkey.user_id)))
  ORDER BY u.username, sshkey.key;


--
-- Name: maasserver_blockdevice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_blockdevice (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    id_path character varying(4096),
    size bigint NOT NULL,
    block_size integer NOT NULL,
    tags text[],
    node_config_id bigint NOT NULL
);


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_blockdevice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_blockdevice_id_seq OWNED BY public.maasserver_blockdevice.id;


--
-- Name: maasserver_bmc; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bmc (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    power_type character varying(10) NOT NULL,
    ip_address_id bigint,
    architectures text[],
    bmc_type integer NOT NULL,
    capabilities text[],
    cores integer NOT NULL,
    cpu_speed integer NOT NULL,
    local_storage bigint NOT NULL,
    memory integer NOT NULL,
    name character varying(255) NOT NULL,
    pool_id integer,
    zone_id bigint NOT NULL,
    tags text[],
    cpu_over_commit_ratio double precision NOT NULL,
    memory_over_commit_ratio double precision NOT NULL,
    default_storage_pool_id bigint,
    power_parameters jsonb NOT NULL,
    default_macvlan_mode character varying(32),
    version text NOT NULL,
    created_with_cert_expiration_days integer,
    created_with_maas_generated_cert boolean,
    created_with_trust_password boolean,
    created_by_commissioning boolean
);


--
-- Name: maasserver_bmc_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bmc_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bmc_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bmc_id_seq OWNED BY public.maasserver_bmc.id;


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bmcroutablerackcontrollerrelationship (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    routable boolean NOT NULL,
    bmc_id bigint NOT NULL,
    rack_controller_id bigint NOT NULL
);


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bmcroutablerackcontrollerrelationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bmcroutablerackcontrollerrelationship_id_seq OWNED BY public.maasserver_bmcroutablerackcontrollerrelationship.id;


--
-- Name: maasserver_bootresource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootresource (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    rtype integer NOT NULL,
    name character varying(255) NOT NULL,
    architecture character varying(255) NOT NULL,
    extra jsonb NOT NULL,
    kflavor character varying(32),
    bootloader_type character varying(32),
    rolling boolean NOT NULL,
    base_image character varying(255) NOT NULL,
    alias character varying(255)
);


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootresource_id_seq OWNED BY public.maasserver_bootresource.id;


--
-- Name: maasserver_bootresourcefile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootresourcefile (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    filename character varying(255) NOT NULL,
    filetype character varying(20) NOT NULL,
    extra jsonb NOT NULL,
    largefile_id bigint,
    resource_set_id bigint NOT NULL,
    sha256 character varying(64) NOT NULL,
    size bigint NOT NULL
);


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresourcefile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootresourcefile_id_seq OWNED BY public.maasserver_bootresourcefile.id;


--
-- Name: maasserver_bootresourcefilesync; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootresourcefilesync (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    size bigint NOT NULL,
    file_id bigint NOT NULL,
    region_id bigint NOT NULL
);


--
-- Name: maasserver_bootresourcefilesync_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresourcefilesync_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresourcefilesync_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootresourcefilesync_id_seq OWNED BY public.maasserver_bootresourcefilesync.id;


--
-- Name: maasserver_bootresourceset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootresourceset (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    version character varying(255) NOT NULL,
    label character varying(255) NOT NULL,
    resource_id bigint NOT NULL
);


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresourceset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootresourceset_id_seq OWNED BY public.maasserver_bootresourceset.id;


--
-- Name: maasserver_bootsource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsource (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    url character varying(200) NOT NULL,
    keyring_filename character varying(4096) NOT NULL,
    keyring_data bytea NOT NULL
);


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootsource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootsource_id_seq OWNED BY public.maasserver_bootsource.id;


--
-- Name: maasserver_bootsourcecache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsourcecache (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    os character varying(32) NOT NULL,
    arch character varying(32) NOT NULL,
    subarch character varying(32) NOT NULL,
    release character varying(32) NOT NULL,
    label character varying(32) NOT NULL,
    boot_source_id bigint NOT NULL,
    release_codename character varying(255),
    release_title character varying(255),
    support_eol date,
    kflavor character varying(32),
    bootloader_type character varying(32),
    extra jsonb NOT NULL
);


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootsourcecache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootsourcecache_id_seq OWNED BY public.maasserver_bootsourcecache.id;


--
-- Name: maasserver_bootsourceselection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsourceselection (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    os character varying(20) NOT NULL,
    release character varying(20) NOT NULL,
    arches text[],
    subarches text[],
    labels text[],
    boot_source_id bigint NOT NULL
);


--
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootsourceselection_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_bootsourceselection_id_seq OWNED BY public.maasserver_bootsourceselection.id;


--
-- Name: maasserver_cacheset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_cacheset (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL
);


--
-- Name: maasserver_cacheset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_cacheset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_cacheset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_cacheset_id_seq OWNED BY public.maasserver_cacheset.id;


--
-- Name: maasserver_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_config (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    value jsonb
);


--
-- Name: maasserver_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_config_id_seq OWNED BY public.maasserver_config.id;


--
-- Name: maasserver_controllerinfo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_controllerinfo (
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    node_id bigint NOT NULL,
    version character varying(255) NOT NULL,
    install_type character varying(255) NOT NULL,
    snap_cohort character varying(255) NOT NULL,
    snap_revision character varying(255) NOT NULL,
    snap_update_revision character varying(255) NOT NULL,
    update_origin character varying(255) NOT NULL,
    update_version character varying(255) NOT NULL,
    update_first_reported timestamp with time zone,
    vault_configured boolean NOT NULL
);


--
-- Name: maasserver_defaultresource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_defaultresource (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    zone_id bigint NOT NULL
);


--
-- Name: maasserver_defaultresource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_defaultresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_defaultresource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_defaultresource_id_seq OWNED BY public.maasserver_defaultresource.id;


--
-- Name: maasserver_dhcpsnippet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dhcpsnippet_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_dhcpsnippet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_dhcpsnippet_id_seq OWNED BY public.maasserver_dhcpsnippet.id;


--
-- Name: maasserver_fabric; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_fabric (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256),
    class_type character varying(256),
    description text NOT NULL
);


--
-- Name: maasserver_interface; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_interface (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(20) NOT NULL,
    mac_address text,
    params jsonb NOT NULL,
    tags text[],
    enabled boolean NOT NULL,
    vlan_id bigint,
    acquired boolean NOT NULL,
    mdns_discovery_state boolean NOT NULL,
    neighbour_discovery_state boolean NOT NULL,
    firmware_version character varying(255),
    product character varying(255),
    vendor character varying(255),
    interface_speed integer NOT NULL,
    link_connected boolean NOT NULL,
    link_speed integer NOT NULL,
    numa_node_id bigint,
    sriov_max_vf integer NOT NULL,
    node_config_id bigint,
    CONSTRAINT maasserver_interface_interface_speed_check CHECK ((interface_speed >= 0)),
    CONSTRAINT maasserver_interface_link_speed_check CHECK ((link_speed >= 0)),
    CONSTRAINT maasserver_interface_sriov_max_vf_check CHECK ((sriov_max_vf >= 0))
);


--
-- Name: maasserver_mdns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_mdns (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet,
    hostname character varying(256),
    count integer NOT NULL,
    interface_id bigint NOT NULL
);


--
-- Name: maasserver_neighbour; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_neighbour (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet,
    "time" integer NOT NULL,
    vid integer,
    count integer NOT NULL,
    mac_address text,
    interface_id bigint NOT NULL
);


--
-- Name: maasserver_rdns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_rdns (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet NOT NULL,
    hostname character varying(256),
    hostnames text[] NOT NULL,
    observer_id bigint NOT NULL
);


--
-- Name: maasserver_subnet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_subnet (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    cidr cidr NOT NULL,
    gateway_ip inet,
    dns_servers text[],
    vlan_id bigint NOT NULL,
    rdns_mode integer NOT NULL,
    allow_proxy boolean NOT NULL,
    description text NOT NULL,
    active_discovery boolean NOT NULL,
    managed boolean NOT NULL,
    allow_dns boolean NOT NULL,
    disabled_boot_architectures character varying(64)[] NOT NULL
);


--
-- Name: maasserver_discovery; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_discovery AS
 SELECT DISTINCT ON (neigh.mac_address, neigh.ip) neigh.id,
    replace(encode((((TRIM(TRAILING '/32'::text FROM (neigh.ip)::text) || ','::text) || neigh.mac_address))::bytea, 'base64'::text), chr(10), ''::text) AS discovery_id,
    neigh.id AS neighbour_id,
    neigh.ip,
    neigh.mac_address,
    neigh.vid,
    neigh.created AS first_seen,
    GREATEST(neigh.updated, mdns.updated) AS last_seen,
    mdns.id AS mdns_id,
    COALESCE(rdns.hostname, mdns.hostname) AS hostname,
    node.id AS observer_id,
    node.system_id AS observer_system_id,
    node.hostname AS observer_hostname,
    iface.id AS observer_interface_id,
    iface.name AS observer_interface_name,
    fabric.id AS fabric_id,
    fabric.name AS fabric_name,
    vlan.id AS vlan_id,
        CASE
            WHEN (neigh.ip = vlan.external_dhcp) THEN true
            ELSE false
        END AS is_external_dhcp,
    subnet.id AS subnet_id,
    subnet.cidr AS subnet_cidr,
    masklen((subnet.cidr)::inet) AS subnet_prefixlen
   FROM (((((((public.maasserver_neighbour neigh
     JOIN public.maasserver_interface iface ON ((neigh.interface_id = iface.id)))
     JOIN public.maasserver_node node ON ((node.current_config_id = iface.node_config_id)))
     JOIN public.maasserver_vlan vlan ON ((iface.vlan_id = vlan.id)))
     JOIN public.maasserver_fabric fabric ON ((vlan.fabric_id = fabric.id)))
     LEFT JOIN public.maasserver_mdns mdns ON ((mdns.ip = neigh.ip)))
     LEFT JOIN public.maasserver_rdns rdns ON ((rdns.ip = neigh.ip)))
     LEFT JOIN public.maasserver_subnet subnet ON (((vlan.id = subnet.vlan_id) AND (neigh.ip << (subnet.cidr)::inet))))
  ORDER BY neigh.mac_address, neigh.ip, neigh.updated DESC, rdns.updated DESC, mdns.updated DESC, (masklen((subnet.cidr)::inet)) DESC;


--
-- Name: maasserver_dnsdata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dnsdata (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    rrtype character varying(8) NOT NULL,
    rrdata text NOT NULL,
    dnsresource_id bigint NOT NULL,
    ttl integer,
    CONSTRAINT maasserver_dnsdata_ttl_check CHECK ((ttl >= 0))
);


--
-- Name: maasserver_dnsdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dnsdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_dnsdata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_dnsdata_id_seq OWNED BY public.maasserver_dnsdata.id;


--
-- Name: maasserver_dnspublication; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dnspublication (
    id bigint NOT NULL,
    serial bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    source character varying(255) NOT NULL
);


--
-- Name: maasserver_dnspublication_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dnspublication_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_dnspublication_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_dnspublication_id_seq OWNED BY public.maasserver_dnspublication.id;


--
-- Name: maasserver_dnsresource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dnsresource (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(191),
    domain_id integer NOT NULL,
    address_ttl integer,
    CONSTRAINT maasserver_dnsresource_address_ttl_check CHECK ((address_ttl >= 0))
);


--
-- Name: maasserver_dnsresource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dnsresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_dnsresource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_dnsresource_id_seq OWNED BY public.maasserver_dnsresource.id;


--
-- Name: maasserver_dnsresource_ip_addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dnsresource_ip_addresses (
    id integer NOT NULL,
    dnsresource_id bigint NOT NULL,
    staticipaddress_id bigint NOT NULL
);


--
-- Name: maasserver_dnsresource_ip_addresses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dnsresource_ip_addresses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_dnsresource_ip_addresses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_dnsresource_ip_addresses_id_seq OWNED BY public.maasserver_dnsresource_ip_addresses.id;


--
-- Name: maasserver_domain; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_domain (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    authoritative boolean,
    ttl integer,
    CONSTRAINT maasserver_domain_ttl_check CHECK ((ttl >= 0))
);


--
-- Name: maasserver_domain_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_domain_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_domain_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_domain_id_seq OWNED BY public.maasserver_domain.id;


--
-- Name: maasserver_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_event (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    action text NOT NULL,
    description text NOT NULL,
    node_id bigint,
    type_id bigint NOT NULL,
    node_hostname character varying(255) NOT NULL,
    username character varying(150) NOT NULL,
    ip_address inet,
    user_agent text NOT NULL,
    endpoint integer NOT NULL,
    node_system_id character varying(41),
    user_id integer
);


--
-- Name: maasserver_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_event_id_seq OWNED BY public.maasserver_event.id;


--
-- Name: maasserver_eventtype; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_eventtype (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    description character varying(255) NOT NULL,
    level integer NOT NULL
);


--
-- Name: maasserver_eventtype_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_eventtype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_eventtype_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_eventtype_id_seq OWNED BY public.maasserver_eventtype.id;


--
-- Name: maasserver_fabric_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_fabric_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_fabric_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_fabric_id_seq OWNED BY public.maasserver_fabric.id;


--
-- Name: maasserver_filestorage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_filestorage (
    id bigint NOT NULL,
    filename character varying(255) NOT NULL,
    content text NOT NULL,
    key character varying(36) NOT NULL,
    owner_id integer
);


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_filestorage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_filestorage_id_seq OWNED BY public.maasserver_filestorage.id;


--
-- Name: maasserver_filesystem; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_filesystem (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid text NOT NULL,
    fstype character varying(20) NOT NULL,
    label character varying(255),
    create_params character varying(255),
    mount_point character varying(255),
    mount_options character varying(255),
    acquired boolean NOT NULL,
    block_device_id bigint,
    cache_set_id bigint,
    filesystem_group_id bigint,
    partition_id bigint,
    node_config_id bigint NOT NULL
);


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_filesystem_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_filesystem_id_seq OWNED BY public.maasserver_filesystem.id;


--
-- Name: maasserver_filesystemgroup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_filesystemgroup (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid text NOT NULL,
    group_type character varying(20) NOT NULL,
    name character varying(255) NOT NULL,
    create_params character varying(255),
    cache_mode character varying(20),
    cache_set_id bigint
);


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_filesystemgroup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_filesystemgroup_id_seq OWNED BY public.maasserver_filesystemgroup.id;


--
-- Name: maasserver_forwarddnsserver; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_forwarddnsserver (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip_address inet NOT NULL,
    port integer NOT NULL
);


--
-- Name: maasserver_forwarddnsserver_domains; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_forwarddnsserver_domains (
    id integer NOT NULL,
    forwarddnsserver_id bigint NOT NULL,
    domain_id integer NOT NULL
);


--
-- Name: maasserver_forwarddnsserver_domains_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_forwarddnsserver_domains_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_forwarddnsserver_domains_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_forwarddnsserver_domains_id_seq OWNED BY public.maasserver_forwarddnsserver_domains.id;


--
-- Name: maasserver_forwarddnsserver_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_forwarddnsserver_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_forwarddnsserver_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_forwarddnsserver_id_seq OWNED BY public.maasserver_forwarddnsserver.id;


--
-- Name: maasserver_globaldefault; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_globaldefault (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    domain_id integer NOT NULL
);


--
-- Name: maasserver_globaldefault_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_globaldefault_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_globaldefault_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_globaldefault_id_seq OWNED BY public.maasserver_globaldefault.id;


--
-- Name: maasserver_interface_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_interface_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_interface_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_interface_id_seq OWNED BY public.maasserver_interface.id;


--
-- Name: maasserver_interface_ip_addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_interface_ip_addresses (
    id integer NOT NULL,
    interface_id bigint NOT NULL,
    staticipaddress_id bigint NOT NULL
);


--
-- Name: maasserver_interface_ip_addresses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_interface_ip_addresses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_interface_ip_addresses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_interface_ip_addresses_id_seq OWNED BY public.maasserver_interface_ip_addresses.id;


--
-- Name: maasserver_interfacerelationship; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_interfacerelationship (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    child_id bigint NOT NULL,
    parent_id bigint NOT NULL
);


--
-- Name: maasserver_interfacerelationship_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_interfacerelationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_interfacerelationship_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_interfacerelationship_id_seq OWNED BY public.maasserver_interfacerelationship.id;


--
-- Name: maasserver_iprange; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_iprange (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    type character varying(20) NOT NULL,
    start_ip inet NOT NULL,
    end_ip inet NOT NULL,
    comment character varying(255),
    subnet_id bigint NOT NULL,
    user_id integer
);


--
-- Name: maasserver_iprange_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_iprange_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_iprange_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_iprange_id_seq OWNED BY public.maasserver_iprange.id;


--
-- Name: maasserver_keysource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_keysource (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    protocol character varying(64) NOT NULL,
    auth_id character varying(255) NOT NULL,
    auto_update boolean NOT NULL
);


--
-- Name: maasserver_keysource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_keysource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_keysource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_keysource_id_seq OWNED BY public.maasserver_keysource.id;


--
-- Name: maasserver_largefile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_largefile (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    sha256 character varying(64) NOT NULL,
    total_size bigint NOT NULL,
    content oid NOT NULL,
    size bigint NOT NULL
);


--
-- Name: maasserver_largefile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_largefile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_largefile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_largefile_id_seq OWNED BY public.maasserver_largefile.id;


--
-- Name: maasserver_licensekey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_licensekey (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    osystem character varying(255) NOT NULL,
    distro_series character varying(255) NOT NULL,
    license_key character varying(255) NOT NULL
);


--
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_licensekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_licensekey_id_seq OWNED BY public.maasserver_licensekey.id;


--
-- Name: maasserver_mdns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_mdns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_mdns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_mdns_id_seq OWNED BY public.maasserver_mdns.id;


--
-- Name: maasserver_neighbour_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_neighbour_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_neighbour_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_neighbour_id_seq OWNED BY public.maasserver_neighbour.id;


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_node_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_node_id_seq OWNED BY public.maasserver_node.id;


--
-- Name: maasserver_node_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_node_tags (
    id integer NOT NULL,
    node_id bigint NOT NULL,
    tag_id bigint NOT NULL
);


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_node_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_node_tags_id_seq OWNED BY public.maasserver_node_tags.id;


--
-- Name: maasserver_nodeconfig; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodeconfig (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name text NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_nodeconfig_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodeconfig_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodeconfig_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodeconfig_id_seq OWNED BY public.maasserver_nodeconfig.id;


--
-- Name: maasserver_nodedevice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodedevice (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    bus integer NOT NULL,
    hardware_type integer NOT NULL,
    vendor_id character varying(4) NOT NULL,
    product_id character varying(4) NOT NULL,
    vendor_name character varying(256) NOT NULL,
    product_name character varying(256) NOT NULL,
    commissioning_driver character varying(256) NOT NULL,
    bus_number integer NOT NULL,
    device_number integer NOT NULL,
    pci_address character varying(64),
    numa_node_id bigint NOT NULL,
    physical_blockdevice_id integer,
    physical_interface_id bigint,
    node_config_id bigint NOT NULL,
    CONSTRAINT maasserver_nodedevice_bus_number_check CHECK ((bus_number >= 0)),
    CONSTRAINT maasserver_nodedevice_device_number_check CHECK ((device_number >= 0))
);


--
-- Name: maasserver_nodedevice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodedevice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodedevice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodedevice_id_seq OWNED BY public.maasserver_nodedevice.id;


--
-- Name: maasserver_nodedevicevpd; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodedevicevpd (
    id bigint NOT NULL,
    key text NOT NULL,
    value text NOT NULL,
    node_device_id bigint NOT NULL
);


--
-- Name: maasserver_nodedevicevpd_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodedevicevpd_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodedevicevpd_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodedevicevpd_id_seq OWNED BY public.maasserver_nodedevicevpd.id;


--
-- Name: maasserver_nodegrouptorackcontroller; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodegrouptorackcontroller (
    id bigint NOT NULL,
    uuid character varying(36) NOT NULL,
    subnet_id bigint NOT NULL
);


--
-- Name: maasserver_nodegrouptorackcontroller_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodegrouptorackcontroller_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodegrouptorackcontroller_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodegrouptorackcontroller_id_seq OWNED BY public.maasserver_nodegrouptorackcontroller.id;


--
-- Name: maasserver_nodekey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodekey (
    id bigint NOT NULL,
    node_id bigint NOT NULL,
    token_id bigint NOT NULL
);


--
-- Name: maasserver_nodekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodekey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodekey_id_seq OWNED BY public.maasserver_nodekey.id;


--
-- Name: maasserver_nodemetadata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodemetadata (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key character varying(64) NOT NULL,
    value text NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_nodemetadata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodemetadata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodemetadata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodemetadata_id_seq OWNED BY public.maasserver_nodemetadata.id;


--
-- Name: maasserver_nodeuserdata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodeuserdata (
    id bigint NOT NULL,
    data text NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_nodeuserdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodeuserdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodeuserdata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_nodeuserdata_id_seq OWNED BY public.maasserver_nodeuserdata.id;


--
-- Name: maasserver_notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_notification (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ident character varying(40),
    users boolean NOT NULL,
    admins boolean NOT NULL,
    message text NOT NULL,
    context jsonb NOT NULL,
    user_id integer,
    category character varying(10) NOT NULL,
    dismissable boolean NOT NULL
);


--
-- Name: maasserver_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_notification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_notification_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_notification_id_seq OWNED BY public.maasserver_notification.id;


--
-- Name: maasserver_notificationdismissal; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_notificationdismissal (
    id bigint NOT NULL,
    notification_id bigint NOT NULL,
    user_id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL
);


--
-- Name: maasserver_notificationdismissal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_notificationdismissal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_notificationdismissal_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_notificationdismissal_id_seq OWNED BY public.maasserver_notificationdismissal.id;


--
-- Name: maasserver_numanode; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_numanode (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    index integer NOT NULL,
    memory integer NOT NULL,
    cores integer[] NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_numanode_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_numanode_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_numanode_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_numanode_id_seq OWNED BY public.maasserver_numanode.id;


--
-- Name: maasserver_numanodehugepages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_numanodehugepages (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    page_size bigint NOT NULL,
    total bigint NOT NULL,
    numanode_id bigint NOT NULL
);


--
-- Name: maasserver_numanodehugepages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_numanodehugepages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_numanodehugepages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_numanodehugepages_id_seq OWNED BY public.maasserver_numanodehugepages.id;


--
-- Name: maasserver_ownerdata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_ownerdata (
    id bigint NOT NULL,
    key character varying(255) NOT NULL,
    value text NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_ownerdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_ownerdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_ownerdata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_ownerdata_id_seq OWNED BY public.maasserver_ownerdata.id;


--
-- Name: maasserver_packagerepository; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_packagerepository (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(41) NOT NULL,
    url character varying(200) NOT NULL,
    components text[],
    arches text[],
    key text NOT NULL,
    "default" boolean NOT NULL,
    enabled boolean NOT NULL,
    disabled_pockets text[],
    distributions text[],
    disabled_components text[],
    disable_sources boolean NOT NULL
);


--
-- Name: maasserver_packagerepository_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_packagerepository_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_packagerepository_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_packagerepository_id_seq OWNED BY public.maasserver_packagerepository.id;


--
-- Name: maasserver_partition; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_partition (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid text,
    size bigint NOT NULL,
    bootable boolean NOT NULL,
    partition_table_id bigint NOT NULL,
    tags text[],
    index integer NOT NULL
);


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_partition_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_partition_id_seq OWNED BY public.maasserver_partition.id;


--
-- Name: maasserver_partitiontable; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_partitiontable (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    table_type character varying(20) NOT NULL,
    block_device_id bigint NOT NULL
);


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_partitiontable_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_partitiontable_id_seq OWNED BY public.maasserver_partitiontable.id;


--
-- Name: maasserver_physicalblockdevice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_physicalblockdevice (
    blockdevice_ptr_id bigint NOT NULL,
    model character varying(255) NOT NULL,
    serial character varying(255) NOT NULL,
    firmware_version character varying(255),
    numa_node_id bigint NOT NULL
);


--
-- Name: maasserver_podhints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_podhints (
    id bigint NOT NULL,
    cores integer NOT NULL,
    memory integer NOT NULL,
    local_storage bigint NOT NULL,
    pod_id bigint NOT NULL,
    cpu_speed integer NOT NULL,
    cluster_id bigint
);


--
-- Name: maasserver_podhints_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_podhints_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_podhints_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_podhints_id_seq OWNED BY public.maasserver_podhints.id;


--
-- Name: maasserver_podhints_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_podhints_nodes (
    id integer NOT NULL,
    podhints_id bigint NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_podhints_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_podhints_nodes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_podhints_nodes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_podhints_nodes_id_seq OWNED BY public.maasserver_podhints_nodes.id;


--
-- Name: maasserver_staticipaddress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_staticipaddress (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet,
    alloc_type integer NOT NULL,
    subnet_id bigint,
    user_id integer,
    lease_time integer NOT NULL,
    temp_expires_on timestamp with time zone
);


--
-- Name: maasserver_podhost; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_podhost AS
 SELECT ((pod.id << 32) | node.id) AS id,
    node.id AS node_id,
    node.system_id,
    node.hostname,
    pod.id AS pod_id,
    pod.name AS pod_name,
    pod.power_type,
    if.id AS interface_id,
    if.name AS interface_name,
    ip.id AS staticipaddress_id,
    ip.ip
   FROM ((((public.maasserver_bmc pod
     LEFT JOIN public.maasserver_staticipaddress ip ON (((pod.ip_address_id = ip.id) AND (pod.bmc_type = 1))))
     LEFT JOIN public.maasserver_interface_ip_addresses ifip ON ((ifip.staticipaddress_id = ip.id)))
     LEFT JOIN public.maasserver_interface if ON ((if.id = ifip.interface_id)))
     LEFT JOIN public.maasserver_node node ON ((node.current_config_id = if.node_config_id)));


--
-- Name: maasserver_podstoragepool; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_podstoragepool (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    pool_id character varying(255) NOT NULL,
    pool_type character varying(255) NOT NULL,
    path character varying(4095) NOT NULL,
    storage bigint NOT NULL,
    pod_id bigint NOT NULL
);


--
-- Name: maasserver_podstoragepool_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_podstoragepool_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_podstoragepool_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_podstoragepool_id_seq OWNED BY public.maasserver_podstoragepool.id;


--
-- Name: maasserver_rbaclastsync; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_rbaclastsync (
    id bigint NOT NULL,
    resource_type character varying(255) NOT NULL,
    sync_id character varying(255) NOT NULL
);


--
-- Name: maasserver_rbaclastsync_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_rbaclastsync_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_rbaclastsync_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_rbaclastsync_id_seq OWNED BY public.maasserver_rbaclastsync.id;


--
-- Name: maasserver_rbacsync; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_rbacsync (
    id bigint NOT NULL,
    action character varying(6) NOT NULL,
    resource_type character varying(255) NOT NULL,
    resource_id integer,
    resource_name character varying(255) NOT NULL,
    created timestamp with time zone NOT NULL,
    source character varying(255) NOT NULL
);


--
-- Name: maasserver_rbacsync_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_rbacsync_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_rbacsync_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_rbacsync_id_seq OWNED BY public.maasserver_rbacsync.id;


--
-- Name: maasserver_rdns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_rdns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_rdns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_rdns_id_seq OWNED BY public.maasserver_rdns.id;


--
-- Name: maasserver_regioncontrollerprocess_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_regioncontrollerprocess_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_regioncontrollerprocess_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_regioncontrollerprocess_id_seq OWNED BY public.maasserver_regioncontrollerprocess.id;


--
-- Name: maasserver_regioncontrollerprocessendpoint; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_regioncontrollerprocessendpoint (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    address inet NOT NULL,
    port integer NOT NULL,
    process_id bigint NOT NULL
);


--
-- Name: maasserver_regioncontrollerprocessendpoint_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_regioncontrollerprocessendpoint_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_regioncontrollerprocessendpoint_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_regioncontrollerprocessendpoint_id_seq OWNED BY public.maasserver_regioncontrollerprocessendpoint.id;


--
-- Name: maasserver_regionrackrpcconnection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_regionrackrpcconnection (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    endpoint_id bigint NOT NULL,
    rack_controller_id bigint NOT NULL
);


--
-- Name: maasserver_regionrackrpcconnection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_regionrackrpcconnection_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_regionrackrpcconnection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_regionrackrpcconnection_id_seq OWNED BY public.maasserver_regionrackrpcconnection.id;


--
-- Name: maasserver_resourcepool; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_resourcepool (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    description text NOT NULL
);


--
-- Name: maasserver_resourcepool_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_resourcepool_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_resourcepool_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_resourcepool_id_seq OWNED BY public.maasserver_resourcepool.id;


--
-- Name: maasserver_rootkey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_rootkey (
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    id bigint NOT NULL,
    expiration timestamp with time zone NOT NULL
);


--
-- Name: maasserver_rootkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_rootkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_rootkey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_rootkey_id_seq OWNED BY public.maasserver_rootkey.id;


--
-- Name: maasserver_routable_pairs; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_routable_pairs AS
 SELECT n_left.id AS left_node_id,
    if_left.id AS left_interface_id,
    subnet_left.id AS left_subnet_id,
    vlan_left.id AS left_vlan_id,
    sip_left.ip AS left_ip,
    n_right.id AS right_node_id,
    if_right.id AS right_interface_id,
    subnet_right.id AS right_subnet_id,
    vlan_right.id AS right_vlan_id,
    sip_right.ip AS right_ip,
    vlan_left.space_id,
        CASE
            WHEN (if_left.node_config_id = if_right.node_config_id) THEN 0
            WHEN (subnet_left.id = subnet_right.id) THEN 1
            WHEN (vlan_left.id = vlan_right.id) THEN 2
            WHEN (vlan_left.space_id IS NOT NULL) THEN 3
            ELSE 4
        END AS metric
   FROM (((((((((((public.maasserver_interface if_left
     JOIN public.maasserver_node n_left ON ((n_left.current_config_id = if_left.node_config_id)))
     JOIN public.maasserver_interface_ip_addresses ifia_left ON ((if_left.id = ifia_left.interface_id)))
     JOIN public.maasserver_staticipaddress sip_left ON ((ifia_left.staticipaddress_id = sip_left.id)))
     JOIN public.maasserver_subnet subnet_left ON ((sip_left.subnet_id = subnet_left.id)))
     JOIN public.maasserver_vlan vlan_left ON ((subnet_left.vlan_id = vlan_left.id)))
     JOIN public.maasserver_vlan vlan_right ON ((NOT (vlan_left.space_id IS DISTINCT FROM vlan_right.space_id))))
     JOIN public.maasserver_subnet subnet_right ON ((vlan_right.id = subnet_right.vlan_id)))
     JOIN public.maasserver_staticipaddress sip_right ON ((subnet_right.id = sip_right.subnet_id)))
     JOIN public.maasserver_interface_ip_addresses ifia_right ON ((sip_right.id = ifia_right.staticipaddress_id)))
     JOIN public.maasserver_interface if_right ON ((ifia_right.interface_id = if_right.id)))
     JOIN public.maasserver_node n_right ON ((if_right.node_config_id = n_right.current_config_id)))
  WHERE (if_left.enabled AND (sip_left.ip IS NOT NULL) AND if_right.enabled AND (sip_right.ip IS NOT NULL) AND (family(sip_left.ip) = family(sip_right.ip)));


--
-- Name: maasserver_script; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_script (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    tags text[],
    script_type integer NOT NULL,
    timeout interval NOT NULL,
    destructive boolean NOT NULL,
    "default" boolean NOT NULL,
    script_id bigint NOT NULL,
    title character varying(255) NOT NULL,
    hardware_type integer NOT NULL,
    packages jsonb NOT NULL,
    parallel integer NOT NULL,
    parameters jsonb NOT NULL,
    results jsonb NOT NULL,
    for_hardware character varying(255)[] NOT NULL,
    may_reboot boolean NOT NULL,
    recommission boolean NOT NULL,
    apply_configured_networking boolean NOT NULL
);


--
-- Name: maasserver_script_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_script_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_script_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_script_id_seq OWNED BY public.maasserver_script.id;


--
-- Name: maasserver_scriptresult; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_scriptresult (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    status integer NOT NULL,
    exit_status integer,
    script_name character varying(255),
    stdout text NOT NULL,
    stderr text NOT NULL,
    result text NOT NULL,
    script_id bigint,
    script_set_id bigint NOT NULL,
    script_version_id bigint,
    output text NOT NULL,
    ended timestamp with time zone,
    started timestamp with time zone,
    parameters jsonb NOT NULL,
    physical_blockdevice_id integer,
    suppressed boolean NOT NULL,
    interface_id bigint
);


--
-- Name: maasserver_scriptresult_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_scriptresult_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_scriptresult_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_scriptresult_id_seq OWNED BY public.maasserver_scriptresult.id;


--
-- Name: maasserver_scriptset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_scriptset (
    id bigint NOT NULL,
    last_ping timestamp with time zone,
    result_type integer NOT NULL,
    node_id bigint NOT NULL,
    power_state_before_transition character varying(10) NOT NULL,
    tags text[]
);


--
-- Name: maasserver_scriptset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_scriptset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_scriptset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_scriptset_id_seq OWNED BY public.maasserver_scriptset.id;


--
-- Name: maasserver_secret; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_secret (
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    path text NOT NULL,
    value jsonb NOT NULL
);


--
-- Name: maasserver_service; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_service (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    status character varying(10) NOT NULL,
    status_info character varying(255) NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_service_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_service_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_service_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_service_id_seq OWNED BY public.maasserver_service.id;


--
-- Name: maasserver_space; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_space (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256),
    description text NOT NULL
);


--
-- Name: maasserver_space_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_space_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_space_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_space_id_seq OWNED BY public.maasserver_space.id;


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_sshkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_sshkey_id_seq OWNED BY public.maasserver_sshkey.id;


--
-- Name: maasserver_sslkey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_sslkey (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key text NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_sslkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_sslkey_id_seq OWNED BY public.maasserver_sslkey.id;


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_staticipaddress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_staticipaddress_id_seq OWNED BY public.maasserver_staticipaddress.id;


--
-- Name: maasserver_staticroute; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_staticroute (
    id bigint NOT NULL,
    gateway_ip inet NOT NULL,
    metric integer NOT NULL,
    destination_id bigint NOT NULL,
    source_id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    CONSTRAINT maasserver_staticroute_metric_check CHECK ((metric >= 0))
);


--
-- Name: maasserver_staticroute_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_staticroute_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_staticroute_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_staticroute_id_seq OWNED BY public.maasserver_staticroute.id;


--
-- Name: maasserver_subnet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_subnet_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_subnet_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_subnet_id_seq OWNED BY public.maasserver_subnet.id;


--
-- Name: maasserver_tag; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_tag (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    definition text NOT NULL,
    comment text NOT NULL,
    kernel_opts text NOT NULL
);


--
-- Name: maasserver_tag_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_tag_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_tag_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_tag_id_seq OWNED BY public.maasserver_tag.id;


--
-- Name: maasserver_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_template (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    filename character varying(64) NOT NULL,
    default_version_id bigint NOT NULL,
    version_id bigint
);


--
-- Name: maasserver_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_template_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_template_id_seq OWNED BY public.maasserver_template.id;


--
-- Name: maasserver_userprofile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_userprofile (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    completed_intro boolean NOT NULL,
    auth_last_check timestamp with time zone,
    is_local boolean NOT NULL
);


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_userprofile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_userprofile_id_seq OWNED BY public.maasserver_userprofile.id;


--
-- Name: maasserver_vaultsecret; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_vaultsecret (
    path text NOT NULL,
    deleted boolean NOT NULL
);


--
-- Name: maasserver_versionedtextfile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_versionedtextfile (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    data text,
    comment character varying(255),
    previous_version_id bigint
);


--
-- Name: maasserver_versionedtextfile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_versionedtextfile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_versionedtextfile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_versionedtextfile_id_seq OWNED BY public.maasserver_versionedtextfile.id;


--
-- Name: maasserver_virtualblockdevice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_virtualblockdevice (
    blockdevice_ptr_id bigint NOT NULL,
    uuid text NOT NULL,
    filesystem_group_id bigint NOT NULL
);


--
-- Name: maasserver_virtualmachine; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_virtualmachine (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    identifier text NOT NULL,
    pinned_cores integer[] NOT NULL,
    unpinned_cores integer NOT NULL,
    memory integer NOT NULL,
    hugepages_backed boolean NOT NULL,
    bmc_id bigint NOT NULL,
    machine_id bigint,
    project text NOT NULL
);


--
-- Name: maasserver_virtualmachine_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_virtualmachine_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_virtualmachine_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_virtualmachine_id_seq OWNED BY public.maasserver_virtualmachine.id;


--
-- Name: maasserver_virtualmachinedisk; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_virtualmachinedisk (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    size bigint NOT NULL,
    backing_pool_id bigint,
    block_device_id bigint,
    vm_id bigint NOT NULL
);


--
-- Name: maasserver_virtualmachinedisk_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_virtualmachinedisk_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_virtualmachinedisk_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_virtualmachinedisk_id_seq OWNED BY public.maasserver_virtualmachinedisk.id;


--
-- Name: maasserver_virtualmachineinterface; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_virtualmachineinterface (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    mac_address text,
    attachment_type character varying(10) NOT NULL,
    host_interface_id bigint,
    vm_id bigint NOT NULL
);


--
-- Name: maasserver_virtualmachineinterface_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_virtualmachineinterface_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_virtualmachineinterface_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_virtualmachineinterface_id_seq OWNED BY public.maasserver_virtualmachineinterface.id;


--
-- Name: maasserver_vlan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_vlan_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_vlan_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_vlan_id_seq OWNED BY public.maasserver_vlan.id;


--
-- Name: maasserver_vmcluster; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_vmcluster (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name text NOT NULL,
    project text NOT NULL,
    pool_id integer,
    zone_id bigint NOT NULL
);


--
-- Name: maasserver_vmcluster_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_vmcluster_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_vmcluster_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_vmcluster_id_seq OWNED BY public.maasserver_vmcluster.id;


--
-- Name: maasserver_zone; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_zone (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    description text NOT NULL
);


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_zone_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_zone_id_seq OWNED BY public.maasserver_zone.id;


--
-- Name: maasserver_zone_serial_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_zone_serial_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 4294967295
    CACHE 1
    CYCLE;


--
-- Name: maasserver_zone_serial_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_zone_serial_seq OWNED BY public.maasserver_dnspublication.serial;


--
-- Name: maastesting_perftestbuild; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maastesting_perftestbuild (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    start_ts timestamp with time zone NOT NULL,
    end_ts timestamp with time zone,
    git_branch text NOT NULL,
    git_hash text NOT NULL,
    release text
);


--
-- Name: maastesting_perftestbuild_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maastesting_perftestbuild_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maastesting_perftestbuild_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maastesting_perftestbuild_id_seq OWNED BY public.maastesting_perftestbuild.id;


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_nodekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_nodekey_id_seq OWNED BY public.maasserver_nodekey.id;


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_nodeuserdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_nodeuserdata_id_seq OWNED BY public.maasserver_nodeuserdata.id;


--
-- Name: metadataserver_script_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_script_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_script_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_script_id_seq OWNED BY public.maasserver_script.id;


--
-- Name: metadataserver_scriptresult_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_scriptresult_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_scriptresult_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_scriptresult_id_seq OWNED BY public.maasserver_scriptresult.id;


--
-- Name: metadataserver_scriptset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_scriptset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_scriptset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_scriptset_id_seq OWNED BY public.maasserver_scriptset.id;


--
-- Name: piston3_consumer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.piston3_consumer (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    key character varying(18) NOT NULL,
    secret character varying(32) NOT NULL,
    status character varying(16) NOT NULL,
    user_id integer
);


--
-- Name: piston3_consumer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.piston3_consumer_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piston3_consumer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.piston3_consumer_id_seq OWNED BY public.piston3_consumer.id;


--
-- Name: piston3_nonce; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.piston3_nonce (
    id bigint NOT NULL,
    token_key character varying(18) NOT NULL,
    consumer_key character varying(18) NOT NULL,
    key character varying(255) NOT NULL
);


--
-- Name: piston3_nonce_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.piston3_nonce_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piston3_nonce_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.piston3_nonce_id_seq OWNED BY public.piston3_nonce.id;


--
-- Name: piston3_token; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.piston3_token (
    id bigint NOT NULL,
    key character varying(18) NOT NULL,
    secret character varying(32) NOT NULL,
    verifier character varying(10) NOT NULL,
    token_type integer NOT NULL,
    "timestamp" integer NOT NULL,
    is_approved boolean NOT NULL,
    callback character varying(255),
    callback_confirmed boolean NOT NULL,
    consumer_id bigint NOT NULL,
    user_id integer
);


--
-- Name: piston3_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.piston3_token_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piston3_token_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.piston3_token_id_seq OWNED BY public.piston3_token.id;


--
-- Name: activity_info_maps; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.activity_info_maps (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    schedule_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16)
);


--
-- Name: buffered_events; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.buffered_events (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: buffered_events_id_seq; Type: SEQUENCE; Schema: temporal; Owner: -
--

CREATE SEQUENCE temporal.buffered_events_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: buffered_events_id_seq; Type: SEQUENCE OWNED BY; Schema: temporal; Owner: -
--

ALTER SEQUENCE temporal.buffered_events_id_seq OWNED BY temporal.buffered_events.id;


--
-- Name: build_id_to_task_queue; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.build_id_to_task_queue (
    namespace_id bytea NOT NULL,
    build_id character varying(255) NOT NULL,
    task_queue_name character varying(255) NOT NULL
);


--
-- Name: child_execution_info_maps; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.child_execution_info_maps (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    initiated_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16)
);


--
-- Name: cluster_membership; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.cluster_membership (
    membership_partition integer NOT NULL,
    host_id bytea NOT NULL,
    rpc_address character varying(128) NOT NULL,
    rpc_port smallint NOT NULL,
    role smallint NOT NULL,
    session_start timestamp without time zone DEFAULT '1970-01-01 00:00:01'::timestamp without time zone,
    last_heartbeat timestamp without time zone DEFAULT '1970-01-01 00:00:01'::timestamp without time zone,
    record_expiry timestamp without time zone DEFAULT '1970-01-01 00:00:01'::timestamp without time zone
);


--
-- Name: cluster_metadata; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.cluster_metadata (
    metadata_partition integer NOT NULL,
    data bytea DEFAULT '\x'::bytea NOT NULL,
    data_encoding character varying(16) DEFAULT 'Proto3'::character varying NOT NULL,
    version bigint DEFAULT 1 NOT NULL
);


--
-- Name: cluster_metadata_info; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.cluster_metadata_info (
    metadata_partition integer NOT NULL,
    cluster_name character varying(255) NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL,
    version bigint NOT NULL
);


--
-- Name: current_executions; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.current_executions (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    create_request_id character varying(255) NOT NULL,
    state integer NOT NULL,
    status integer NOT NULL,
    start_version bigint DEFAULT 0 NOT NULL,
    last_write_version bigint NOT NULL
);


--
-- Name: executions; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.executions (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    next_event_id bigint NOT NULL,
    last_write_version bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL,
    state bytea NOT NULL,
    state_encoding character varying(16) NOT NULL,
    db_record_version bigint DEFAULT 0 NOT NULL
);


--
-- Name: history_immediate_tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.history_immediate_tasks (
    shard_id integer NOT NULL,
    category_id integer NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: history_node; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.history_node (
    shard_id integer NOT NULL,
    tree_id bytea NOT NULL,
    branch_id bytea NOT NULL,
    node_id bigint NOT NULL,
    txn_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL,
    prev_txn_id bigint DEFAULT 0 NOT NULL
);


--
-- Name: history_scheduled_tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.history_scheduled_tasks (
    shard_id integer NOT NULL,
    category_id integer NOT NULL,
    visibility_timestamp timestamp without time zone NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: history_tree; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.history_tree (
    shard_id integer NOT NULL,
    tree_id bytea NOT NULL,
    branch_id bytea NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: namespace_metadata; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.namespace_metadata (
    partition_id integer NOT NULL,
    notification_version bigint NOT NULL
);


--
-- Name: namespaces; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.namespaces (
    partition_id integer NOT NULL,
    id bytea NOT NULL,
    name character varying(255) NOT NULL,
    notification_version bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL,
    is_global boolean NOT NULL
);


--
-- Name: queue; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.queue (
    queue_type integer NOT NULL,
    message_id bigint NOT NULL,
    message_payload bytea NOT NULL,
    message_encoding character varying(16) DEFAULT 'Json'::character varying NOT NULL
);


--
-- Name: queue_metadata; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.queue_metadata (
    queue_type integer NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) DEFAULT 'Json'::character varying NOT NULL,
    version bigint DEFAULT 0 NOT NULL
);


--
-- Name: replication_tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.replication_tasks (
    shard_id integer NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: replication_tasks_dlq; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.replication_tasks_dlq (
    source_cluster_name character varying(255) NOT NULL,
    shard_id integer NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: request_cancel_info_maps; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.request_cancel_info_maps (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    initiated_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16)
);


--
-- Name: schema_update_history; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.schema_update_history (
    version_partition integer NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL,
    update_time timestamp without time zone NOT NULL,
    description character varying(255),
    manifest_md5 character varying(64),
    new_version character varying(64),
    old_version character varying(64)
);


--
-- Name: schema_version; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.schema_version (
    version_partition integer NOT NULL,
    db_name character varying(255) NOT NULL,
    creation_time timestamp without time zone,
    curr_version character varying(64),
    min_compatible_version character varying(64)
);


--
-- Name: shards; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.shards (
    shard_id integer NOT NULL,
    range_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: signal_info_maps; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.signal_info_maps (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    initiated_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16)
);


--
-- Name: signals_requested_sets; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.signals_requested_sets (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    signal_id character varying(255) NOT NULL
);


--
-- Name: task_queue_user_data; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.task_queue_user_data (
    namespace_id bytea NOT NULL,
    task_queue_name character varying(255) NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL,
    version bigint NOT NULL
);


--
-- Name: task_queues; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.task_queues (
    range_hash bigint NOT NULL,
    task_queue_id bytea NOT NULL,
    range_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.tasks (
    range_hash bigint NOT NULL,
    task_queue_id bytea NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: timer_info_maps; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.timer_info_maps (
    shard_id integer NOT NULL,
    namespace_id bytea NOT NULL,
    workflow_id character varying(255) NOT NULL,
    run_id bytea NOT NULL,
    timer_id character varying(255) NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16)
);


--
-- Name: timer_tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.timer_tasks (
    shard_id integer NOT NULL,
    visibility_timestamp timestamp without time zone NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: transfer_tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.transfer_tasks (
    shard_id integer NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: visibility_tasks; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.visibility_tasks (
    shard_id integer NOT NULL,
    task_id bigint NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL
);


--
-- Name: executions_visibility; Type: TABLE; Schema: temporal_visibility; Owner: -
--

CREATE TABLE temporal_visibility.executions_visibility (
    namespace_id character(64) NOT NULL,
    run_id character(64) NOT NULL,
    start_time timestamp without time zone NOT NULL,
    execution_time timestamp without time zone NOT NULL,
    workflow_id character varying(255) NOT NULL,
    workflow_type_name character varying(255) NOT NULL,
    status integer NOT NULL,
    close_time timestamp without time zone,
    history_length bigint,
    memo bytea,
    encoding character varying(64) NOT NULL,
    task_queue character varying(255) DEFAULT ''::character varying NOT NULL,
    search_attributes jsonb,
    temporalchangeversion jsonb GENERATED ALWAYS AS ((search_attributes -> 'TemporalChangeVersion'::text)) STORED,
    binarychecksums jsonb GENERATED ALWAYS AS ((search_attributes -> 'BinaryChecksums'::text)) STORED,
    batcheruser character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'BatcherUser'::text)) STORED,
    temporalscheduledstarttime timestamp without time zone GENERATED ALWAYS AS (temporal_visibility.convert_ts(((search_attributes ->> 'TemporalScheduledStartTime'::text))::character varying)) STORED,
    temporalscheduledbyid character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'TemporalScheduledById'::text)) STORED,
    temporalschedulepaused boolean GENERATED ALWAYS AS (((search_attributes -> 'TemporalSchedulePaused'::text))::boolean) STORED,
    temporalnamespacedivision character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'TemporalNamespaceDivision'::text)) STORED,
    bool01 boolean GENERATED ALWAYS AS (((search_attributes -> 'Bool01'::text))::boolean) STORED,
    bool02 boolean GENERATED ALWAYS AS (((search_attributes -> 'Bool02'::text))::boolean) STORED,
    bool03 boolean GENERATED ALWAYS AS (((search_attributes -> 'Bool03'::text))::boolean) STORED,
    datetime01 timestamp without time zone GENERATED ALWAYS AS (temporal_visibility.convert_ts(((search_attributes ->> 'Datetime01'::text))::character varying)) STORED,
    datetime02 timestamp without time zone GENERATED ALWAYS AS (temporal_visibility.convert_ts(((search_attributes ->> 'Datetime02'::text))::character varying)) STORED,
    datetime03 timestamp without time zone GENERATED ALWAYS AS (temporal_visibility.convert_ts(((search_attributes ->> 'Datetime03'::text))::character varying)) STORED,
    double01 numeric(20,5) GENERATED ALWAYS AS (((search_attributes -> 'Double01'::text))::numeric) STORED,
    double02 numeric(20,5) GENERATED ALWAYS AS (((search_attributes -> 'Double02'::text))::numeric) STORED,
    double03 numeric(20,5) GENERATED ALWAYS AS (((search_attributes -> 'Double03'::text))::numeric) STORED,
    int01 bigint GENERATED ALWAYS AS (((search_attributes -> 'Int01'::text))::bigint) STORED,
    int02 bigint GENERATED ALWAYS AS (((search_attributes -> 'Int02'::text))::bigint) STORED,
    int03 bigint GENERATED ALWAYS AS (((search_attributes -> 'Int03'::text))::bigint) STORED,
    keyword01 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword01'::text)) STORED,
    keyword02 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword02'::text)) STORED,
    keyword03 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword03'::text)) STORED,
    keyword04 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword04'::text)) STORED,
    keyword05 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword05'::text)) STORED,
    keyword06 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword06'::text)) STORED,
    keyword07 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword07'::text)) STORED,
    keyword08 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword08'::text)) STORED,
    keyword09 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword09'::text)) STORED,
    keyword10 character varying(255) GENERATED ALWAYS AS ((search_attributes ->> 'Keyword10'::text)) STORED,
    text01 tsvector GENERATED ALWAYS AS (((search_attributes ->> 'Text01'::text))::tsvector) STORED,
    text02 tsvector GENERATED ALWAYS AS (((search_attributes ->> 'Text02'::text))::tsvector) STORED,
    text03 tsvector GENERATED ALWAYS AS (((search_attributes ->> 'Text03'::text))::tsvector) STORED,
    keywordlist01 jsonb GENERATED ALWAYS AS ((search_attributes -> 'KeywordList01'::text)) STORED,
    keywordlist02 jsonb GENERATED ALWAYS AS ((search_attributes -> 'KeywordList02'::text)) STORED,
    keywordlist03 jsonb GENERATED ALWAYS AS ((search_attributes -> 'KeywordList03'::text)) STORED,
    history_size_bytes bigint,
    buildids jsonb GENERATED ALWAYS AS ((search_attributes -> 'BuildIds'::text)) STORED
);


--
-- Name: schema_update_history; Type: TABLE; Schema: temporal_visibility; Owner: -
--

CREATE TABLE temporal_visibility.schema_update_history (
    version_partition integer NOT NULL,
    year integer NOT NULL,
    month integer NOT NULL,
    update_time timestamp without time zone NOT NULL,
    description character varying(255),
    manifest_md5 character varying(64),
    new_version character varying(64),
    old_version character varying(64)
);


--
-- Name: schema_version; Type: TABLE; Schema: temporal_visibility; Owner: -
--

CREATE TABLE temporal_visibility.schema_version (
    version_partition integer NOT NULL,
    db_name character varying(255) NOT NULL,
    creation_time timestamp without time zone,
    curr_version character varying(64),
    min_compatible_version character varying(64)
);


--
-- Name: auth_group id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group ALTER COLUMN id SET DEFAULT nextval('public.auth_group_id_seq'::regclass);


--
-- Name: auth_group_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_group_permissions_id_seq'::regclass);


--
-- Name: auth_permission id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission ALTER COLUMN id SET DEFAULT nextval('public.auth_permission_id_seq'::regclass);


--
-- Name: auth_user id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user ALTER COLUMN id SET DEFAULT nextval('public.auth_user_id_seq'::regclass);


--
-- Name: auth_user_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups ALTER COLUMN id SET DEFAULT nextval('public.auth_user_groups_id_seq'::regclass);


--
-- Name: auth_user_user_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions ALTER COLUMN id SET DEFAULT nextval('public.auth_user_user_permissions_id_seq'::regclass);


--
-- Name: django_content_type id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type ALTER COLUMN id SET DEFAULT nextval('public.django_content_type_id_seq'::regclass);


--
-- Name: django_migrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations ALTER COLUMN id SET DEFAULT nextval('public.django_migrations_id_seq'::regclass);


--
-- Name: django_site id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_site ALTER COLUMN id SET DEFAULT nextval('public.django_site_id_seq'::regclass);


--
-- Name: maasserver_blockdevice id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice ALTER COLUMN id SET DEFAULT nextval('public.maasserver_blockdevice_id_seq'::regclass);


--
-- Name: maasserver_bmc id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bmc_id_seq'::regclass);


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmcroutablerackcontrollerrelationship ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bmcroutablerackcontrollerrelationship_id_seq'::regclass);


--
-- Name: maasserver_bootresource id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresource ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootresource_id_seq'::regclass);


--
-- Name: maasserver_bootresourcefile id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootresourcefile_id_seq'::regclass);


--
-- Name: maasserver_bootresourcefilesync id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefilesync ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootresourcefilesync_id_seq'::regclass);


--
-- Name: maasserver_bootresourceset id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourceset ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootresourceset_id_seq'::regclass);


--
-- Name: maasserver_bootsource id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsource ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootsource_id_seq'::regclass);


--
-- Name: maasserver_bootsourcecache id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourcecache ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootsourcecache_id_seq'::regclass);


--
-- Name: maasserver_bootsourceselection id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection ALTER COLUMN id SET DEFAULT nextval('public.maasserver_bootsourceselection_id_seq'::regclass);


--
-- Name: maasserver_cacheset id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_cacheset ALTER COLUMN id SET DEFAULT nextval('public.maasserver_cacheset_id_seq'::regclass);


--
-- Name: maasserver_config id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_config ALTER COLUMN id SET DEFAULT nextval('public.maasserver_config_id_seq'::regclass);


--
-- Name: maasserver_defaultresource id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_defaultresource ALTER COLUMN id SET DEFAULT nextval('public.maasserver_defaultresource_id_seq'::regclass);


--
-- Name: maasserver_dhcpsnippet id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet ALTER COLUMN id SET DEFAULT nextval('public.maasserver_dhcpsnippet_id_seq'::regclass);


--
-- Name: maasserver_dnsdata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsdata ALTER COLUMN id SET DEFAULT nextval('public.maasserver_dnsdata_id_seq'::regclass);


--
-- Name: maasserver_dnspublication id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnspublication ALTER COLUMN id SET DEFAULT nextval('public.maasserver_dnspublication_id_seq'::regclass);


--
-- Name: maasserver_dnsresource id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource ALTER COLUMN id SET DEFAULT nextval('public.maasserver_dnsresource_id_seq'::regclass);


--
-- Name: maasserver_dnsresource_ip_addresses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses ALTER COLUMN id SET DEFAULT nextval('public.maasserver_dnsresource_ip_addresses_id_seq'::regclass);


--
-- Name: maasserver_domain id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_domain ALTER COLUMN id SET DEFAULT nextval('public.maasserver_domain_id_seq'::regclass);


--
-- Name: maasserver_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_event ALTER COLUMN id SET DEFAULT nextval('public.maasserver_event_id_seq'::regclass);


--
-- Name: maasserver_eventtype id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_eventtype ALTER COLUMN id SET DEFAULT nextval('public.maasserver_eventtype_id_seq'::regclass);


--
-- Name: maasserver_fabric id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fabric ALTER COLUMN id SET DEFAULT nextval('public.maasserver_fabric_id_seq'::regclass);


--
-- Name: maasserver_filestorage id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filestorage ALTER COLUMN id SET DEFAULT nextval('public.maasserver_filestorage_id_seq'::regclass);


--
-- Name: maasserver_filesystem id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem ALTER COLUMN id SET DEFAULT nextval('public.maasserver_filesystem_id_seq'::regclass);


--
-- Name: maasserver_filesystemgroup id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystemgroup ALTER COLUMN id SET DEFAULT nextval('public.maasserver_filesystemgroup_id_seq'::regclass);


--
-- Name: maasserver_forwarddnsserver id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver ALTER COLUMN id SET DEFAULT nextval('public.maasserver_forwarddnsserver_id_seq'::regclass);


--
-- Name: maasserver_forwarddnsserver_domains id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver_domains ALTER COLUMN id SET DEFAULT nextval('public.maasserver_forwarddnsserver_domains_id_seq'::regclass);


--
-- Name: maasserver_globaldefault id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_globaldefault ALTER COLUMN id SET DEFAULT nextval('public.maasserver_globaldefault_id_seq'::regclass);


--
-- Name: maasserver_interface id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface ALTER COLUMN id SET DEFAULT nextval('public.maasserver_interface_id_seq'::regclass);


--
-- Name: maasserver_interface_ip_addresses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses ALTER COLUMN id SET DEFAULT nextval('public.maasserver_interface_ip_addresses_id_seq'::regclass);


--
-- Name: maasserver_interfacerelationship id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interfacerelationship ALTER COLUMN id SET DEFAULT nextval('public.maasserver_interfacerelationship_id_seq'::regclass);


--
-- Name: maasserver_iprange id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iprange ALTER COLUMN id SET DEFAULT nextval('public.maasserver_iprange_id_seq'::regclass);


--
-- Name: maasserver_keysource id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_keysource ALTER COLUMN id SET DEFAULT nextval('public.maasserver_keysource_id_seq'::regclass);


--
-- Name: maasserver_largefile id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_largefile ALTER COLUMN id SET DEFAULT nextval('public.maasserver_largefile_id_seq'::regclass);


--
-- Name: maasserver_licensekey id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_licensekey ALTER COLUMN id SET DEFAULT nextval('public.maasserver_licensekey_id_seq'::regclass);


--
-- Name: maasserver_mdns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_mdns ALTER COLUMN id SET DEFAULT nextval('public.maasserver_mdns_id_seq'::regclass);


--
-- Name: maasserver_neighbour id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_neighbour ALTER COLUMN id SET DEFAULT nextval('public.maasserver_neighbour_id_seq'::regclass);


--
-- Name: maasserver_node id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node ALTER COLUMN id SET DEFAULT nextval('public.maasserver_node_id_seq'::regclass);


--
-- Name: maasserver_node_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags ALTER COLUMN id SET DEFAULT nextval('public.maasserver_node_tags_id_seq'::regclass);


--
-- Name: maasserver_nodeconfig id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeconfig ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodeconfig_id_seq'::regclass);


--
-- Name: maasserver_nodedevice id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodedevice_id_seq'::regclass);


--
-- Name: maasserver_nodedevicevpd id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevicevpd ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodedevicevpd_id_seq'::regclass);


--
-- Name: maasserver_nodegrouptorackcontroller id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodegrouptorackcontroller ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodegrouptorackcontroller_id_seq'::regclass);


--
-- Name: maasserver_nodekey id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodekey ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodekey_id_seq'::regclass);


--
-- Name: maasserver_nodemetadata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodemetadata ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodemetadata_id_seq'::regclass);


--
-- Name: maasserver_nodeuserdata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeuserdata ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodeuserdata_id_seq'::regclass);


--
-- Name: maasserver_notification id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notification ALTER COLUMN id SET DEFAULT nextval('public.maasserver_notification_id_seq'::regclass);


--
-- Name: maasserver_notificationdismissal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal ALTER COLUMN id SET DEFAULT nextval('public.maasserver_notificationdismissal_id_seq'::regclass);


--
-- Name: maasserver_numanode id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanode ALTER COLUMN id SET DEFAULT nextval('public.maasserver_numanode_id_seq'::regclass);


--
-- Name: maasserver_numanodehugepages id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanodehugepages ALTER COLUMN id SET DEFAULT nextval('public.maasserver_numanodehugepages_id_seq'::regclass);


--
-- Name: maasserver_ownerdata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_ownerdata ALTER COLUMN id SET DEFAULT nextval('public.maasserver_ownerdata_id_seq'::regclass);


--
-- Name: maasserver_packagerepository id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_packagerepository ALTER COLUMN id SET DEFAULT nextval('public.maasserver_packagerepository_id_seq'::regclass);


--
-- Name: maasserver_partition id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition ALTER COLUMN id SET DEFAULT nextval('public.maasserver_partition_id_seq'::regclass);


--
-- Name: maasserver_partitiontable id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partitiontable ALTER COLUMN id SET DEFAULT nextval('public.maasserver_partitiontable_id_seq'::regclass);


--
-- Name: maasserver_podhints id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints ALTER COLUMN id SET DEFAULT nextval('public.maasserver_podhints_id_seq'::regclass);


--
-- Name: maasserver_podhints_nodes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes ALTER COLUMN id SET DEFAULT nextval('public.maasserver_podhints_nodes_id_seq'::regclass);


--
-- Name: maasserver_podstoragepool id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podstoragepool ALTER COLUMN id SET DEFAULT nextval('public.maasserver_podstoragepool_id_seq'::regclass);


--
-- Name: maasserver_rbaclastsync id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rbaclastsync ALTER COLUMN id SET DEFAULT nextval('public.maasserver_rbaclastsync_id_seq'::regclass);


--
-- Name: maasserver_rbacsync id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rbacsync ALTER COLUMN id SET DEFAULT nextval('public.maasserver_rbacsync_id_seq'::regclass);


--
-- Name: maasserver_rdns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rdns ALTER COLUMN id SET DEFAULT nextval('public.maasserver_rdns_id_seq'::regclass);


--
-- Name: maasserver_regioncontrollerprocess id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocess ALTER COLUMN id SET DEFAULT nextval('public.maasserver_regioncontrollerprocess_id_seq'::regclass);


--
-- Name: maasserver_regioncontrollerprocessendpoint id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocessendpoint ALTER COLUMN id SET DEFAULT nextval('public.maasserver_regioncontrollerprocessendpoint_id_seq'::regclass);


--
-- Name: maasserver_regionrackrpcconnection id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection ALTER COLUMN id SET DEFAULT nextval('public.maasserver_regionrackrpcconnection_id_seq'::regclass);


--
-- Name: maasserver_resourcepool id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_resourcepool ALTER COLUMN id SET DEFAULT nextval('public.maasserver_resourcepool_id_seq'::regclass);


--
-- Name: maasserver_rootkey id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rootkey ALTER COLUMN id SET DEFAULT nextval('public.maasserver_rootkey_id_seq'::regclass);


--
-- Name: maasserver_script id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_script ALTER COLUMN id SET DEFAULT nextval('public.maasserver_script_id_seq'::regclass);


--
-- Name: maasserver_scriptresult id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult ALTER COLUMN id SET DEFAULT nextval('public.maasserver_scriptresult_id_seq'::regclass);


--
-- Name: maasserver_scriptset id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptset ALTER COLUMN id SET DEFAULT nextval('public.maasserver_scriptset_id_seq'::regclass);


--
-- Name: maasserver_service id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_service ALTER COLUMN id SET DEFAULT nextval('public.maasserver_service_id_seq'::regclass);


--
-- Name: maasserver_space id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_space ALTER COLUMN id SET DEFAULT nextval('public.maasserver_space_id_seq'::regclass);


--
-- Name: maasserver_sshkey id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sshkey ALTER COLUMN id SET DEFAULT nextval('public.maasserver_sshkey_id_seq'::regclass);


--
-- Name: maasserver_sslkey id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sslkey ALTER COLUMN id SET DEFAULT nextval('public.maasserver_sslkey_id_seq'::regclass);


--
-- Name: maasserver_staticipaddress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticipaddress ALTER COLUMN id SET DEFAULT nextval('public.maasserver_staticipaddress_id_seq'::regclass);


--
-- Name: maasserver_staticroute id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticroute ALTER COLUMN id SET DEFAULT nextval('public.maasserver_staticroute_id_seq'::regclass);


--
-- Name: maasserver_subnet id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_subnet ALTER COLUMN id SET DEFAULT nextval('public.maasserver_subnet_id_seq'::regclass);


--
-- Name: maasserver_tag id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_tag ALTER COLUMN id SET DEFAULT nextval('public.maasserver_tag_id_seq'::regclass);


--
-- Name: maasserver_template id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template ALTER COLUMN id SET DEFAULT nextval('public.maasserver_template_id_seq'::regclass);


--
-- Name: maasserver_userprofile id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_userprofile ALTER COLUMN id SET DEFAULT nextval('public.maasserver_userprofile_id_seq'::regclass);


--
-- Name: maasserver_versionedtextfile id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_versionedtextfile ALTER COLUMN id SET DEFAULT nextval('public.maasserver_versionedtextfile_id_seq'::regclass);


--
-- Name: maasserver_virtualmachine id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachine ALTER COLUMN id SET DEFAULT nextval('public.maasserver_virtualmachine_id_seq'::regclass);


--
-- Name: maasserver_virtualmachinedisk id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachinedisk ALTER COLUMN id SET DEFAULT nextval('public.maasserver_virtualmachinedisk_id_seq'::regclass);


--
-- Name: maasserver_virtualmachineinterface id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachineinterface ALTER COLUMN id SET DEFAULT nextval('public.maasserver_virtualmachineinterface_id_seq'::regclass);


--
-- Name: maasserver_vlan id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan ALTER COLUMN id SET DEFAULT nextval('public.maasserver_vlan_id_seq'::regclass);


--
-- Name: maasserver_vmcluster id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vmcluster ALTER COLUMN id SET DEFAULT nextval('public.maasserver_vmcluster_id_seq'::regclass);


--
-- Name: maasserver_zone id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_zone ALTER COLUMN id SET DEFAULT nextval('public.maasserver_zone_id_seq'::regclass);


--
-- Name: maastesting_perftestbuild id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maastesting_perftestbuild ALTER COLUMN id SET DEFAULT nextval('public.maastesting_perftestbuild_id_seq'::regclass);


--
-- Name: piston3_consumer id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_consumer ALTER COLUMN id SET DEFAULT nextval('public.piston3_consumer_id_seq'::regclass);


--
-- Name: piston3_nonce id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_nonce ALTER COLUMN id SET DEFAULT nextval('public.piston3_nonce_id_seq'::regclass);


--
-- Name: piston3_token id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token ALTER COLUMN id SET DEFAULT nextval('public.piston3_token_id_seq'::regclass);


--
-- Name: buffered_events id; Type: DEFAULT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.buffered_events ALTER COLUMN id SET DEFAULT nextval('temporal.buffered_events_id_seq'::regclass);


--
-- Data for Name: auth_group; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_group (id, name) FROM stdin;
\.


--
-- Data for Name: auth_group_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_group_permissions (id, group_id, permission_id) FROM stdin;
\.


--
-- Data for Name: auth_permission; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_permission (id, name, content_type_id, codename) FROM stdin;
1	Can add permission	1	add_permission
2	Can change permission	1	change_permission
3	Can delete permission	1	delete_permission
4	Can view permission	1	view_permission
5	Can add group	2	add_group
6	Can change group	2	change_group
7	Can delete group	2	delete_group
8	Can view group	2	view_group
9	Can add user	3	add_user
10	Can change user	3	change_user
11	Can delete user	3	delete_user
12	Can view user	3	view_user
13	Can add content type	4	add_contenttype
14	Can change content type	4	change_contenttype
15	Can delete content type	4	delete_contenttype
16	Can view content type	4	view_contenttype
17	Can add session	5	add_session
18	Can change session	5	change_session
19	Can delete session	5	delete_session
20	Can view session	5	view_session
21	Can add site	6	add_site
22	Can change site	6	change_site
23	Can delete site	6	delete_site
24	Can view site	6	view_site
25	Can add block device	7	add_blockdevice
26	Can change block device	7	change_blockdevice
27	Can delete block device	7	delete_blockdevice
28	Can view block device	7	view_blockdevice
29	Can add boot resource	8	add_bootresource
30	Can change boot resource	8	change_bootresource
31	Can delete boot resource	8	delete_bootresource
32	Can view boot resource	8	view_bootresource
33	Can add boot resource file	9	add_bootresourcefile
34	Can change boot resource file	9	change_bootresourcefile
35	Can delete boot resource file	9	delete_bootresourcefile
36	Can view boot resource file	9	view_bootresourcefile
37	Can add boot resource set	10	add_bootresourceset
38	Can change boot resource set	10	change_bootresourceset
39	Can delete boot resource set	10	delete_bootresourceset
40	Can view boot resource set	10	view_bootresourceset
41	Can add boot source	11	add_bootsource
42	Can change boot source	11	change_bootsource
43	Can delete boot source	11	delete_bootsource
44	Can view boot source	11	view_bootsource
45	Can add boot source cache	12	add_bootsourcecache
46	Can change boot source cache	12	change_bootsourcecache
47	Can delete boot source cache	12	delete_bootsourcecache
48	Can view boot source cache	12	view_bootsourcecache
49	Can add boot source selection	13	add_bootsourceselection
50	Can change boot source selection	13	change_bootsourceselection
51	Can delete boot source selection	13	delete_bootsourceselection
52	Can view boot source selection	13	view_bootsourceselection
53	Can add cache set	14	add_cacheset
54	Can change cache set	14	change_cacheset
55	Can delete cache set	14	delete_cacheset
56	Can view cache set	14	view_cacheset
57	Can add config	15	add_config
58	Can change config	15	change_config
59	Can delete config	15	delete_config
60	Can view config	15	view_config
61	Can add Event record	16	add_event
62	Can change Event record	16	change_event
63	Can delete Event record	16	delete_event
64	Can view Event record	16	view_event
65	Can add Event type	17	add_eventtype
66	Can change Event type	17	change_eventtype
67	Can delete Event type	17	delete_eventtype
68	Can view Event type	17	view_eventtype
69	Can add Fabric	18	add_fabric
70	Can change Fabric	18	change_fabric
71	Can delete Fabric	18	delete_fabric
72	Can view Fabric	18	view_fabric
73	Can add Fan Network	19	add_fannetwork
74	Can change Fan Network	19	change_fannetwork
75	Can delete Fan Network	19	delete_fannetwork
76	Can view Fan Network	19	view_fannetwork
77	Can add file storage	20	add_filestorage
78	Can change file storage	20	change_filestorage
79	Can delete file storage	20	delete_filestorage
80	Can view file storage	20	view_filestorage
81	Can add filesystem	21	add_filesystem
82	Can change filesystem	21	change_filesystem
83	Can delete filesystem	21	delete_filesystem
84	Can view filesystem	21	view_filesystem
85	Can add filesystem group	22	add_filesystemgroup
86	Can change filesystem group	22	change_filesystemgroup
87	Can delete filesystem group	22	delete_filesystemgroup
88	Can view filesystem group	22	view_filesystemgroup
89	Can add Interface	23	add_interface
90	Can change Interface	23	change_interface
91	Can delete Interface	23	delete_interface
92	Can view Interface	23	view_interface
93	Can add interface relationship	24	add_interfacerelationship
94	Can change interface relationship	24	change_interfacerelationship
95	Can delete interface relationship	24	delete_interfacerelationship
96	Can view interface relationship	24	view_interfacerelationship
97	Can add large file	25	add_largefile
98	Can change large file	25	change_largefile
99	Can delete large file	25	delete_largefile
100	Can view large file	25	view_largefile
101	Can add license key	26	add_licensekey
102	Can change license key	26	change_licensekey
103	Can delete license key	26	delete_licensekey
104	Can view license key	26	view_licensekey
105	Can add node	27	add_node
106	Can change node	27	change_node
107	Can delete node	27	delete_node
108	Can view node	27	view_node
109	Can add partition	28	add_partition
110	Can change partition	28	change_partition
111	Can delete partition	28	delete_partition
112	Can view partition	28	view_partition
113	Can add partition table	29	add_partitiontable
114	Can change partition table	29	change_partitiontable
115	Can delete partition table	29	delete_partitiontable
116	Can view partition table	29	view_partitiontable
117	Can add Space	30	add_space
118	Can change Space	30	change_space
119	Can delete Space	30	delete_space
120	Can view Space	30	view_space
121	Can add SSH key	31	add_sshkey
122	Can change SSH key	31	change_sshkey
123	Can delete SSH key	31	delete_sshkey
124	Can view SSH key	31	view_sshkey
125	Can add SSL key	32	add_sslkey
126	Can change SSL key	32	change_sslkey
127	Can delete SSL key	32	delete_sslkey
128	Can view SSL key	32	view_sslkey
129	Can add Static IP Address	33	add_staticipaddress
130	Can change Static IP Address	33	change_staticipaddress
131	Can delete Static IP Address	33	delete_staticipaddress
132	Can view Static IP Address	33	view_staticipaddress
133	Can add subnet	34	add_subnet
134	Can change subnet	34	change_subnet
135	Can delete subnet	34	delete_subnet
136	Can view subnet	34	view_subnet
137	Can add tag	35	add_tag
138	Can change tag	35	change_tag
139	Can delete tag	35	delete_tag
140	Can view tag	35	view_tag
141	Can add user profile	36	add_userprofile
142	Can change user profile	36	change_userprofile
143	Can delete user profile	36	delete_userprofile
144	Can view user profile	36	view_userprofile
145	Can add VLAN	37	add_vlan
146	Can change VLAN	37	change_vlan
147	Can delete VLAN	37	delete_vlan
148	Can view VLAN	37	view_vlan
149	Can add Physical zone	38	add_zone
150	Can change Physical zone	38	change_zone
151	Can delete Physical zone	38	delete_zone
152	Can view Physical zone	38	view_zone
153	Can add physical block device	39	add_physicalblockdevice
154	Can change physical block device	39	change_physicalblockdevice
155	Can delete physical block device	39	delete_physicalblockdevice
156	Can view physical block device	39	view_physicalblockdevice
157	Can add virtual block device	40	add_virtualblockdevice
158	Can change virtual block device	40	change_virtualblockdevice
159	Can delete virtual block device	40	delete_virtualblockdevice
160	Can view virtual block device	40	view_virtualblockdevice
161	Can add bcache	41	add_bcache
162	Can change bcache	41	change_bcache
163	Can delete bcache	41	delete_bcache
164	Can view bcache	41	view_bcache
165	Can add Bond	42	add_bondinterface
166	Can change Bond	42	change_bondinterface
167	Can delete Bond	42	delete_bondinterface
168	Can view Bond	42	view_bondinterface
169	Can add device	43	add_device
170	Can change device	43	change_device
171	Can delete device	43	delete_device
172	Can view device	43	view_device
173	Can add Physical interface	44	add_physicalinterface
174	Can change Physical interface	44	change_physicalinterface
175	Can delete Physical interface	44	delete_physicalinterface
176	Can view Physical interface	44	view_physicalinterface
177	Can add raid	45	add_raid
178	Can change raid	45	change_raid
179	Can delete raid	45	delete_raid
180	Can view raid	45	view_raid
181	Can add Unknown interface	46	add_unknowninterface
182	Can change Unknown interface	46	change_unknowninterface
183	Can delete Unknown interface	46	delete_unknowninterface
184	Can view Unknown interface	46	view_unknowninterface
185	Can add VLAN interface	47	add_vlaninterface
186	Can change VLAN interface	47	change_vlaninterface
187	Can delete VLAN interface	47	delete_vlaninterface
188	Can view VLAN interface	47	view_vlaninterface
189	Can add volume group	48	add_volumegroup
190	Can change volume group	48	change_volumegroup
191	Can delete volume group	48	delete_volumegroup
192	Can view volume group	48	view_volumegroup
193	Can add machine	49	add_machine
194	Can change machine	49	change_machine
195	Can delete machine	49	delete_machine
196	Can view machine	49	view_machine
197	Can add rack controller	50	add_rackcontroller
198	Can change rack controller	50	change_rackcontroller
199	Can delete rack controller	50	delete_rackcontroller
200	Can view rack controller	50	view_rackcontroller
201	Can add DNSResource	51	add_dnsresource
202	Can change DNSResource	51	change_dnsresource
203	Can delete DNSResource	51	delete_dnsresource
204	Can view DNSResource	51	view_dnsresource
205	Can add Domain	52	add_domain
206	Can change Domain	52	change_domain
207	Can delete Domain	52	delete_domain
208	Can view Domain	52	view_domain
209	Can add region controller process	53	add_regioncontrollerprocess
210	Can change region controller process	53	change_regioncontrollerprocess
211	Can delete region controller process	53	delete_regioncontrollerprocess
212	Can view region controller process	53	view_regioncontrollerprocess
213	Can add region controller process endpoint	54	add_regioncontrollerprocessendpoint
214	Can change region controller process endpoint	54	change_regioncontrollerprocessendpoint
215	Can delete region controller process endpoint	54	delete_regioncontrollerprocessendpoint
216	Can view region controller process endpoint	54	view_regioncontrollerprocessendpoint
217	Can add region controller	55	add_regioncontroller
218	Can change region controller	55	change_regioncontroller
219	Can delete region controller	55	delete_regioncontroller
220	Can view region controller	55	view_regioncontroller
221	Can add bmc	56	add_bmc
222	Can change bmc	56	change_bmc
223	Can delete bmc	56	delete_bmc
224	Can view bmc	56	view_bmc
225	Can add DNSData	57	add_dnsdata
226	Can change DNSData	57	change_dnsdata
227	Can delete DNSData	57	delete_dnsdata
228	Can view DNSData	57	view_dnsdata
229	Can add ip range	58	add_iprange
230	Can change ip range	58	change_iprange
231	Can delete ip range	58	delete_iprange
232	Can view ip range	58	view_iprange
233	Can add node group to rack controller	59	add_nodegrouptorackcontroller
234	Can change node group to rack controller	59	change_nodegrouptorackcontroller
235	Can delete node group to rack controller	59	delete_nodegrouptorackcontroller
236	Can view node group to rack controller	59	view_nodegrouptorackcontroller
237	Can add region rack rpc connection	60	add_regionrackrpcconnection
238	Can change region rack rpc connection	60	change_regionrackrpcconnection
239	Can delete region rack rpc connection	60	delete_regionrackrpcconnection
240	Can view region rack rpc connection	60	view_regionrackrpcconnection
241	Can add service	61	add_service
242	Can change service	61	change_service
243	Can delete service	61	delete_service
244	Can view service	61	view_service
245	Can add Template	62	add_template
246	Can change Template	62	change_template
247	Can delete Template	62	delete_template
248	Can view Template	62	view_template
249	Can add VersionedTextFile	63	add_versionedtextfile
250	Can change VersionedTextFile	63	change_versionedtextfile
251	Can delete VersionedTextFile	63	delete_versionedtextfile
252	Can view VersionedTextFile	63	view_versionedtextfile
253	Can add bmc routable rack controller relationship	64	add_bmcroutablerackcontrollerrelationship
254	Can change bmc routable rack controller relationship	64	change_bmcroutablerackcontrollerrelationship
255	Can delete bmc routable rack controller relationship	64	delete_bmcroutablerackcontrollerrelationship
256	Can view bmc routable rack controller relationship	64	view_bmcroutablerackcontrollerrelationship
257	Can add dhcp snippet	65	add_dhcpsnippet
258	Can change dhcp snippet	65	change_dhcpsnippet
259	Can delete dhcp snippet	65	delete_dhcpsnippet
260	Can view dhcp snippet	65	view_dhcpsnippet
261	Can add child interface	66	add_childinterface
262	Can change child interface	66	change_childinterface
263	Can delete child interface	66	delete_childinterface
264	Can view child interface	66	view_childinterface
265	Can add Bridge	67	add_bridgeinterface
266	Can change Bridge	67	change_bridgeinterface
267	Can delete Bridge	67	delete_bridgeinterface
268	Can view Bridge	67	view_bridgeinterface
269	Can add owner data	68	add_ownerdata
270	Can change owner data	68	change_ownerdata
271	Can delete owner data	68	delete_ownerdata
272	Can view owner data	68	view_ownerdata
273	Can add controller	69	add_controller
274	Can change controller	69	change_controller
275	Can delete controller	69	delete_controller
276	Can view controller	69	view_controller
277	Can add dns publication	70	add_dnspublication
278	Can change dns publication	70	change_dnspublication
279	Can delete dns publication	70	delete_dnspublication
280	Can view dns publication	70	view_dnspublication
281	Can add package repository	71	add_packagerepository
282	Can change package repository	71	change_packagerepository
283	Can delete package repository	71	delete_packagerepository
284	Can view package repository	71	view_packagerepository
285	Can add mDNS binding	72	add_mdns
286	Can change mDNS binding	72	change_mdns
287	Can delete mDNS binding	72	delete_mdns
288	Can view mDNS binding	72	view_mdns
289	Can add Neighbour	73	add_neighbour
290	Can change Neighbour	73	change_neighbour
291	Can delete Neighbour	73	delete_neighbour
292	Can view Neighbour	73	view_neighbour
293	Can add static route	74	add_staticroute
294	Can change static route	74	change_staticroute
295	Can delete static route	74	delete_staticroute
296	Can view static route	74	view_staticroute
297	Can add Key Source	75	add_keysource
298	Can change Key Source	75	change_keysource
299	Can delete Key Source	75	delete_keysource
300	Can view Key Source	75	view_keysource
301	Can add Discovery	76	add_discovery
302	Can change Discovery	76	change_discovery
303	Can delete Discovery	76	delete_discovery
304	Can view Discovery	76	view_discovery
305	Can add Reverse-DNS entry	77	add_rdns
306	Can change Reverse-DNS entry	77	change_rdns
307	Can delete Reverse-DNS entry	77	delete_rdns
308	Can view Reverse-DNS entry	77	view_rdns
309	Can add notification	78	add_notification
310	Can change notification	78	change_notification
311	Can delete notification	78	delete_notification
312	Can view notification	78	view_notification
313	Can add notification dismissal	79	add_notificationdismissal
314	Can change notification dismissal	79	change_notificationdismissal
315	Can delete notification dismissal	79	delete_notificationdismissal
316	Can view notification dismissal	79	view_notificationdismissal
317	Can add pod hints	80	add_podhints
318	Can change pod hints	80	change_podhints
319	Can delete pod hints	80	delete_podhints
320	Can view pod hints	80	view_podhints
321	Can add pod	81	add_pod
322	Can change pod	81	change_pod
323	Can delete pod	81	delete_pod
324	Can view pod	81	view_pod
325	Can add ControllerInfo	82	add_controllerinfo
326	Can change ControllerInfo	82	change_controllerinfo
327	Can delete ControllerInfo	82	delete_controllerinfo
328	Can view ControllerInfo	82	view_controllerinfo
329	Can add NodeMetadata	83	add_nodemetadata
330	Can change NodeMetadata	83	change_nodemetadata
331	Can delete NodeMetadata	83	delete_nodemetadata
332	Can view NodeMetadata	83	view_nodemetadata
333	Can add resource pool	84	add_resourcepool
334	Can change resource pool	84	change_resourcepool
335	Can delete resource pool	84	delete_resourcepool
336	Can view resource pool	84	view_resourcepool
337	Can add root key	85	add_rootkey
338	Can change root key	85	change_rootkey
339	Can delete root key	85	delete_rootkey
340	Can view root key	85	view_rootkey
341	Can add global default	86	add_globaldefault
342	Can change global default	86	change_globaldefault
343	Can delete global default	86	delete_globaldefault
344	Can view global default	86	view_globaldefault
345	Can add pod storage pool	87	add_podstoragepool
346	Can change pod storage pool	87	change_podstoragepool
347	Can delete pod storage pool	87	delete_podstoragepool
348	Can view pod storage pool	87	view_podstoragepool
349	Can add rbac sync	88	add_rbacsync
350	Can change rbac sync	88	change_rbacsync
351	Can delete rbac sync	88	delete_rbacsync
352	Can view rbac sync	88	view_rbacsync
353	Can add rbac last sync	89	add_rbaclastsync
354	Can change rbac last sync	89	change_rbaclastsync
355	Can delete rbac last sync	89	delete_rbaclastsync
356	Can view rbac last sync	89	view_rbaclastsync
357	Can add vmfs	90	add_vmfs
358	Can change vmfs	90	change_vmfs
359	Can delete vmfs	90	delete_vmfs
360	Can view vmfs	90	view_vmfs
361	Can add numa node	91	add_numanode
362	Can change numa node	91	change_numanode
363	Can delete numa node	91	delete_numanode
364	Can view numa node	91	view_numanode
365	Can add virtual machine	92	add_virtualmachine
366	Can change virtual machine	92	change_virtualmachine
367	Can delete virtual machine	92	delete_virtualmachine
368	Can view virtual machine	92	view_virtualmachine
369	Can add numa node hugepages	93	add_numanodehugepages
370	Can change numa node hugepages	93	change_numanodehugepages
371	Can delete numa node hugepages	93	delete_numanodehugepages
372	Can view numa node hugepages	93	view_numanodehugepages
373	Can add virtual machine interface	94	add_virtualmachineinterface
374	Can change virtual machine interface	94	change_virtualmachineinterface
375	Can delete virtual machine interface	94	delete_virtualmachineinterface
376	Can view virtual machine interface	94	view_virtualmachineinterface
377	Can add node device	95	add_nodedevice
378	Can change node device	95	change_nodedevice
379	Can delete node device	95	delete_nodedevice
380	Can view node device	95	view_nodedevice
381	Can add virtual machine disk	96	add_virtualmachinedisk
382	Can change virtual machine disk	96	change_virtualmachinedisk
383	Can delete virtual machine disk	96	delete_virtualmachinedisk
384	Can view virtual machine disk	96	view_virtualmachinedisk
385	Can add forward dns server	97	add_forwarddnsserver
386	Can change forward dns server	97	change_forwarddnsserver
387	Can delete forward dns server	97	delete_forwarddnsserver
388	Can view forward dns server	97	view_forwarddnsserver
389	Can add vm cluster	98	add_vmcluster
390	Can change vm cluster	98	change_vmcluster
391	Can delete vm cluster	98	delete_vmcluster
392	Can view vm cluster	98	view_vmcluster
393	Can add node key	99	add_nodekey
394	Can change node key	99	change_nodekey
395	Can delete node key	99	delete_nodekey
396	Can view node key	99	view_nodekey
397	Can add node user data	100	add_nodeuserdata
398	Can change node user data	100	change_nodeuserdata
399	Can delete node user data	100	delete_nodeuserdata
400	Can view node user data	100	view_nodeuserdata
401	Can add script	101	add_script
402	Can change script	101	change_script
403	Can delete script	101	delete_script
404	Can view script	101	view_script
405	Can add script result	102	add_scriptresult
406	Can change script result	102	change_scriptresult
407	Can delete script result	102	delete_scriptresult
408	Can view script result	102	view_scriptresult
409	Can add script set	103	add_scriptset
410	Can change script set	103	change_scriptset
411	Can delete script set	103	delete_scriptset
412	Can view script set	103	view_scriptset
413	Can add consumer	104	add_consumer
414	Can change consumer	104	change_consumer
415	Can delete consumer	104	delete_consumer
416	Can view consumer	104	view_consumer
417	Can add nonce	105	add_nonce
418	Can change nonce	105	change_nonce
419	Can delete nonce	105	delete_nonce
420	Can view nonce	105	view_nonce
421	Can add token	106	add_token
422	Can change token	106	change_token
423	Can delete token	106	delete_token
424	Can view token	106	view_token
425	Can add node config	107	add_nodeconfig
426	Can change node config	107	change_nodeconfig
427	Can delete node config	107	delete_nodeconfig
428	Can view node config	107	view_nodeconfig
429	Can add perf test build	108	add_perftestbuild
430	Can change perf test build	108	change_perftestbuild
431	Can delete perf test build	108	delete_perftestbuild
432	Can view perf test build	108	view_perftestbuild
433	Can add NodeDeviceVPD	109	add_nodedevicevpd
434	Can change NodeDeviceVPD	109	change_nodedevicevpd
435	Can delete NodeDeviceVPD	109	delete_nodedevicevpd
436	Can view NodeDeviceVPD	109	view_nodedevicevpd
437	Can add secret	110	add_secret
438	Can change secret	110	change_secret
439	Can delete secret	110	delete_secret
440	Can view secret	110	view_secret
441	Can add vault secret	111	add_vaultsecret
442	Can change vault secret	111	change_vaultsecret
443	Can delete vault secret	111	delete_vaultsecret
444	Can view vault secret	111	view_vaultsecret
445	Can add node key	112	add_nodekey
446	Can change node key	112	change_nodekey
447	Can delete node key	112	delete_nodekey
448	Can view node key	112	view_nodekey
449	Can add node user data	113	add_nodeuserdata
450	Can change node user data	113	change_nodeuserdata
451	Can delete node user data	113	delete_nodeuserdata
452	Can view node user data	113	view_nodeuserdata
453	Can add script set	114	add_scriptset
454	Can change script set	114	change_scriptset
455	Can delete script set	114	delete_scriptset
456	Can view script set	114	view_scriptset
457	Can add script	115	add_script
458	Can change script	115	change_script
459	Can delete script	115	delete_script
460	Can view script	115	view_script
461	Can add script result	116	add_scriptresult
462	Can change script result	116	change_scriptresult
463	Can delete script result	116	delete_scriptresult
464	Can view script result	116	view_scriptresult
465	Can add boot resource file sync	117	add_bootresourcefilesync
466	Can change boot resource file sync	117	change_bootresourcefilesync
467	Can delete boot resource file sync	117	delete_bootresourcefilesync
468	Can view boot resource file sync	117	view_bootresourcefilesync
469	Can add default resource	118	add_defaultresource
470	Can change default resource	118	change_defaultresource
471	Can delete default resource	118	delete_defaultresource
472	Can view default resource	118	view_defaultresource
\.


--
-- Data for Name: auth_user; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) FROM stdin;
\.


--
-- Data for Name: auth_user_groups; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_user_groups (id, user_id, group_id) FROM stdin;
\.


--
-- Data for Name: auth_user_user_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.auth_user_user_permissions (id, user_id, permission_id) FROM stdin;
\.


--
-- Data for Name: django_content_type; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_content_type (id, app_label, model) FROM stdin;
1	auth	permission
2	auth	group
3	auth	user
4	contenttypes	contenttype
5	sessions	session
6	sites	site
7	maasserver	blockdevice
8	maasserver	bootresource
9	maasserver	bootresourcefile
10	maasserver	bootresourceset
11	maasserver	bootsource
12	maasserver	bootsourcecache
13	maasserver	bootsourceselection
14	maasserver	cacheset
15	maasserver	config
16	maasserver	event
17	maasserver	eventtype
18	maasserver	fabric
19	maasserver	fannetwork
20	maasserver	filestorage
21	maasserver	filesystem
22	maasserver	filesystemgroup
23	maasserver	interface
24	maasserver	interfacerelationship
25	maasserver	largefile
26	maasserver	licensekey
27	maasserver	node
28	maasserver	partition
29	maasserver	partitiontable
30	maasserver	space
31	maasserver	sshkey
32	maasserver	sslkey
33	maasserver	staticipaddress
34	maasserver	subnet
35	maasserver	tag
36	maasserver	userprofile
37	maasserver	vlan
38	maasserver	zone
39	maasserver	physicalblockdevice
40	maasserver	virtualblockdevice
41	maasserver	bcache
42	maasserver	bondinterface
43	maasserver	device
44	maasserver	physicalinterface
45	maasserver	raid
46	maasserver	unknowninterface
47	maasserver	vlaninterface
48	maasserver	volumegroup
49	maasserver	machine
50	maasserver	rackcontroller
51	maasserver	dnsresource
52	maasserver	domain
53	maasserver	regioncontrollerprocess
54	maasserver	regioncontrollerprocessendpoint
55	maasserver	regioncontroller
56	maasserver	bmc
57	maasserver	dnsdata
58	maasserver	iprange
59	maasserver	nodegrouptorackcontroller
60	maasserver	regionrackrpcconnection
61	maasserver	service
62	maasserver	template
63	maasserver	versionedtextfile
64	maasserver	bmcroutablerackcontrollerrelationship
65	maasserver	dhcpsnippet
66	maasserver	childinterface
67	maasserver	bridgeinterface
68	maasserver	ownerdata
69	maasserver	controller
70	maasserver	dnspublication
71	maasserver	packagerepository
72	maasserver	mdns
73	maasserver	neighbour
74	maasserver	staticroute
75	maasserver	keysource
76	maasserver	discovery
77	maasserver	rdns
78	maasserver	notification
79	maasserver	notificationdismissal
80	maasserver	podhints
81	maasserver	pod
82	maasserver	controllerinfo
83	maasserver	nodemetadata
84	maasserver	resourcepool
85	maasserver	rootkey
86	maasserver	globaldefault
87	maasserver	podstoragepool
88	maasserver	rbacsync
89	maasserver	rbaclastsync
90	maasserver	vmfs
91	maasserver	numanode
92	maasserver	virtualmachine
93	maasserver	numanodehugepages
94	maasserver	virtualmachineinterface
95	maasserver	nodedevice
96	maasserver	virtualmachinedisk
97	maasserver	forwarddnsserver
98	maasserver	vmcluster
99	metadataserver	nodekey
100	metadataserver	nodeuserdata
101	metadataserver	script
102	metadataserver	scriptresult
103	metadataserver	scriptset
104	piston3	consumer
105	piston3	nonce
106	piston3	token
107	maasserver	nodeconfig
108	maastesting	perftestbuild
109	maasserver	nodedevicevpd
110	maasserver	secret
111	maasserver	vaultsecret
112	maasserver	nodekey
113	maasserver	nodeuserdata
114	maasserver	scriptset
115	maasserver	script
116	maasserver	scriptresult
117	maasserver	bootresourcefilesync
118	maasserver	defaultresource
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
1	contenttypes	0001_initial	2021-11-19 12:40:42.824414+00
2	auth	0001_initial	2021-11-19 12:40:42.858779+00
3	auth	0002_auto_20151119_1629	2021-11-19 12:40:42.961604+00
4	auth	0003_django_1_11_update	2021-11-19 12:40:42.982989+00
5	auth	0004_user_email_allow_null	2021-11-19 12:40:42.99213+00
6	auth	0005_auto_20200626_1049	2021-11-19 12:40:43.011789+00
7	contenttypes	0002_remove_content_type_name	2021-11-19 12:40:43.030316+00
8	piston3	0001_initial	2021-11-19 12:40:43.062801+00
9	maasserver	0001_initial	2021-11-19 12:40:44.340749+00
10	metadataserver	0001_initial	2021-11-19 12:40:44.570766+00
11	maasserver	0002_remove_candidate_name_model	2021-11-19 12:40:44.582572+00
12	maasserver	0003_add_node_type_to_node	2021-11-19 12:40:44.617527+00
13	maasserver	0004_migrate_installable_to_node_type	2021-11-19 12:40:44.678379+00
14	maasserver	0005_delete_installable_from_node	2021-11-19 12:40:44.706324+00
15	maasserver	0006_add_lease_time_to_staticipaddress	2021-11-19 12:40:44.734773+00
16	maasserver	0007_create_node_proxy_models	2021-11-19 12:40:44.745761+00
17	maasserver	0008_use_new_arrayfield	2021-11-19 12:40:44.879861+00
18	maasserver	0009_remove_routers_field_from_node	2021-11-19 12:40:44.910292+00
19	maasserver	0010_add_dns_models	2021-11-19 12:40:45.10435+00
20	maasserver	0011_domain_data	2021-11-19 12:40:45.23398+00
21	maasserver	0012_drop_dns_fields	2021-11-19 12:40:45.349177+00
22	maasserver	0013_remove_boot_type_from_node	2021-11-19 12:40:45.384578+00
23	maasserver	0014_add_region_models	2021-11-19 12:40:45.594747+00
24	maasserver	0015_add_bmc_model	2021-11-19 12:40:45.735538+00
25	maasserver	0016_migrate_power_data_node_to_bmc	2021-11-19 12:40:45.917089+00
26	maasserver	0017_remove_node_power_type	2021-11-19 12:40:45.951225+00
27	maasserver	0018_add_dnsdata	2021-11-19 12:40:46.03917+00
28	maasserver	0019_add_iprange	2021-11-19 12:40:46.085306+00
29	maasserver	0020_nodegroup_to_rackcontroller	2021-11-19 12:40:46.203411+00
30	maasserver	0021_nodegroupinterface_to_iprange	2021-11-19 12:40:46.280663+00
31	maasserver	0022_extract_ip_for_bmcs	2021-11-19 12:40:46.355619+00
32	maasserver	0023_add_ttl_field	2021-11-19 12:40:46.52367+00
33	maasserver	0024_remove_nodegroupinterface	2021-11-19 12:40:47.168394+00
34	maasserver	0025_create_node_system_id_sequence	2021-11-19 12:40:47.188836+00
35	maasserver	0026_create_zone_serial_sequence	2021-11-19 12:40:47.194285+00
36	maasserver	0027_replace_static_range_with_admin_reserved_ranges	2021-11-19 12:40:47.266471+00
37	maasserver	0028_update_default_vlan_on_interface_and_subnet	2021-11-19 12:40:47.364843+00
38	maasserver	0029_add_rdns_mode	2021-11-19 12:40:47.384279+00
39	maasserver	0030_drop_all_old_funcs	2021-11-19 12:40:47.455476+00
40	maasserver	0031_add_region_rack_rpc_conn_model	2021-11-19 12:40:47.690756+00
41	maasserver	0032_loosen_vlan	2021-11-19 12:40:47.77097+00
42	maasserver	0033_iprange_minor_changes	2021-11-19 12:40:47.865484+00
43	maasserver	0034_rename_mount_params_as_mount_options	2021-11-19 12:40:47.916277+00
44	maasserver	0035_convert_ether_wake_to_manual_power_type	2021-11-19 12:40:47.981797+00
45	maasserver	0036_add_service_model	2021-11-19 12:40:48.064125+00
46	maasserver	0037_node_last_image_sync	2021-11-19 12:40:48.104895+00
47	maasserver	0038_filesystem_ramfs_tmpfs_support	2021-11-19 12:40:48.191633+00
48	maasserver	0039_create_template_and_versionedtextfile_models	2021-11-19 12:40:48.218415+00
49	maasserver	0040_fix_id_seq	2021-11-19 12:40:48.238787+00
50	maasserver	0041_change_bmc_on_delete_to_set_null	2021-11-19 12:40:48.293066+00
51	maasserver	0042_add_routable_rack_controllers_to_bmc	2021-11-19 12:40:48.485532+00
52	maasserver	0043_dhcpsnippet	2021-11-19 12:40:48.545241+00
53	maasserver	0044_remove_di_bootresourcefiles	2021-11-19 12:40:48.634506+00
54	maasserver	0045_add_node_to_filesystem	2021-11-19 12:40:48.685887+00
55	maasserver	0046_add_bridge_interface_type	2021-11-19 12:40:48.731426+00
56	maasserver	0047_fix_spelling_of_degraded	2021-11-19 12:40:48.830138+00
57	maasserver	0048_add_subnet_allow_proxy	2021-11-19 12:40:48.845873+00
58	maasserver	0049_add_external_dhcp_present_to_vlan	2021-11-19 12:40:48.970804+00
59	maasserver	0050_modify_external_dhcp_on_vlan	2021-11-19 12:40:49.134295+00
60	maasserver	0051_space_fabric_unique	2021-11-19 12:40:49.397372+00
61	maasserver	0052_add_codename_title_eol_to_bootresourcecache	2021-11-19 12:40:49.424495+00
62	maasserver	0053_add_ownerdata_model	2021-11-19 12:40:49.516296+00
63	maasserver	0054_controller	2021-11-19 12:40:49.524257+00
64	maasserver	0055_dns_publications	2021-11-19 12:40:49.531248+00
65	maasserver	0056_zone_serial_ownership	2021-11-19 12:40:49.538801+00
66	maasserver	0057_initial_dns_publication	2021-11-19 12:40:49.60903+00
67	maasserver	0058_bigger_integer_for_dns_publication_serial	2021-11-19 12:40:49.618122+00
68	maasserver	0056_add_description_to_fabric_and_space	2021-11-19 12:40:49.77264+00
69	maasserver	0057_merge	2021-11-19 12:40:49.775133+00
70	maasserver	0059_merge	2021-11-19 12:40:49.77711+00
71	maasserver	0060_amt_remove_mac_address	2021-11-19 12:40:49.851165+00
72	maasserver	0061_maas_nodegroup_worker_to_maas	2021-11-19 12:40:49.925509+00
73	maasserver	0062_fix_bootsource_daily_label	2021-11-19 12:40:50.006741+00
74	maasserver	0063_remove_orphaned_bmcs_and_ips	2021-11-19 12:40:50.202739+00
75	maasserver	0064_remove_unneeded_event_triggers	2021-11-19 12:40:50.270623+00
76	maasserver	0065_larger_osystem_and_distro_series	2021-11-19 12:40:50.349286+00
77	maasserver	0066_allow_squashfs	2021-11-19 12:40:50.359214+00
78	maasserver	0067_add_size_to_largefile	2021-11-19 12:40:50.438721+00
79	maasserver	0068_drop_node_system_id_sequence	2021-11-19 12:40:50.443859+00
80	maasserver	0069_add_previous_node_status_to_node	2021-11-19 12:40:50.489576+00
81	maasserver	0070_allow_null_vlan_on_interface	2021-11-19 12:40:50.551797+00
82	maasserver	0071_ntp_server_to_ntp_servers	2021-11-19 12:40:50.556645+00
83	maasserver	0072_packagerepository	2021-11-19 12:40:50.565478+00
84	maasserver	0073_migrate_package_repositories	2021-11-19 12:40:50.707607+00
85	maasserver	0072_update_status_and_previous_status	2021-11-19 12:40:50.78421+00
86	maasserver	0074_merge	2021-11-19 12:40:50.786449+00
87	maasserver	0075_modify_packagerepository	2021-11-19 12:40:50.816827+00
88	maasserver	0076_interface_discovery_rescue_mode	2021-11-19 12:40:51.29596+00
89	maasserver	0077_static_routes	2021-11-19 12:40:51.369006+00
90	maasserver	0078_remove_packagerepository_description	2021-11-19 12:40:51.381147+00
91	maasserver	0079_add_keysource_model	2021-11-19 12:40:51.476509+00
92	maasserver	0080_change_packagerepository_url_type	2021-11-19 12:40:51.489155+00
93	maasserver	0081_allow_larger_bootsourcecache_fields	2021-11-19 12:40:51.542287+00
94	maasserver	0082_add_kflavor	2021-11-19 12:40:51.710735+00
95	maasserver	0083_device_discovery	2021-11-19 12:40:51.781692+00
96	maasserver	0084_add_default_user_to_node_model	2021-11-19 12:40:51.832194+00
97	maasserver	0085_no_intro_on_upgrade	2021-11-19 12:40:51.910638+00
98	maasserver	0086_remove_powerpc_from_ports_arches	2021-11-19 12:40:51.990442+00
99	maasserver	0087_add_completed_intro_to_userprofile	2021-11-19 12:40:52.015202+00
100	maasserver	0088_remove_node_disable_ipv4	2021-11-19 12:40:52.063366+00
101	maasserver	0089_active_discovery	2021-11-19 12:40:52.291119+00
102	maasserver	0090_bootloaders	2021-11-19 12:40:52.330415+00
103	maasserver	0091_v2_to_v3	2021-11-19 12:40:52.415851+00
104	maasserver	0092_rolling	2021-11-19 12:40:52.426926+00
105	maasserver	0093_add_rdns_model	2021-11-19 12:40:52.507603+00
106	maasserver	0094_add_unmanaged_subnets	2021-11-19 12:40:52.527624+00
107	maasserver	0095_vlan_relay_vlan	2021-11-19 12:40:52.575416+00
108	maasserver	0096_set_default_vlan_field	2021-11-19 12:40:52.631384+00
109	maasserver	0097_node_chassis_storage_hints	2021-11-19 12:40:52.852524+00
110	maasserver	0098_add_space_to_vlan	2021-11-19 12:40:52.911629+00
111	maasserver	0099_set_default_vlan_field	2021-11-19 12:40:52.975955+00
112	maasserver	0100_migrate_spaces_from_subnet_to_vlan	2021-11-19 12:40:53.065011+00
113	maasserver	0101_filesystem_btrfs_support	2021-11-19 12:40:53.234079+00
114	maasserver	0102_remove_space_from_subnet	2021-11-19 12:40:53.304323+00
115	maasserver	0103_notifications	2021-11-19 12:40:53.356504+00
116	maasserver	0104_notifications_dismissals	2021-11-19 12:40:53.420674+00
117	metadataserver	0002_script_models	2021-11-19 12:40:53.730744+00
118	maasserver	0105_add_script_sets_to_node_model	2021-11-19 12:40:53.911179+00
119	maasserver	0106_testing_status	2021-11-19 12:40:54.13962+00
120	maasserver	0107_chassis_to_pods	2021-11-19 12:40:54.559838+00
121	maasserver	0108_generate_bmc_names	2021-11-19 12:40:54.64426+00
122	maasserver	0109_bmc_names_unique	2021-11-19 12:40:54.682417+00
123	maasserver	0110_notification_category	2021-11-19 12:40:54.705165+00
124	maasserver	0111_remove_component_error	2021-11-19 12:40:54.714145+00
125	maasserver	0112_update_notification	2021-11-19 12:40:54.853551+00
126	maasserver	0113_set_filepath_limit_to_linux_max	2021-11-19 12:40:54.904174+00
127	maasserver	0114_node_dynamic_to_creation_type	2021-11-19 12:40:55.13626+00
128	maasserver	0115_additional_boot_resource_filetypes	2021-11-19 12:40:55.153205+00
129	maasserver	0116_add_disabled_components_for_mirrors	2021-11-19 12:40:55.164284+00
130	maasserver	0117_add_iscsi_block_device	2021-11-19 12:40:55.230126+00
131	maasserver	0118_add_iscsi_storage_pod	2021-11-19 12:40:55.305038+00
132	maasserver	0119_set_default_vlan_field	2021-11-19 12:40:55.398439+00
133	maasserver	0120_bootsourcecache_extra	2021-11-19 12:40:55.40932+00
134	maasserver	0121_relax_staticipaddress_unique_constraint	2021-11-19 12:40:55.498095+00
135	maasserver	0122_make_virtualblockdevice_uuid_editable	2021-11-19 12:40:55.525899+00
136	maasserver	0123_make_iprange_comment_default_to_empty_string	2021-11-19 12:40:55.573294+00
137	maasserver	0124_staticipaddress_address_family_index	2021-11-19 12:40:55.583593+00
138	maasserver	0125_add_switch_model	2021-11-19 12:40:55.652599+00
139	maasserver	0126_add_controllerinfo_model	2021-11-19 12:40:55.804495+00
140	maasserver	0127_nodemetadata	2021-11-19 12:40:55.902125+00
141	maasserver	0128_events_created_index	2021-11-19 12:40:55.910201+00
142	maasserver	0129_add_install_rackd_flag	2021-11-19 12:40:55.958036+00
143	maasserver	0130_node_locked_flag	2021-11-19 12:40:56.012856+00
144	maasserver	0131_update_event_model_for_audit_logs	2021-11-19 12:40:56.575592+00
145	maasserver	0132_consistent_model_name_validation	2021-11-19 12:40:56.705325+00
146	maasserver	0133_add_resourcepool_model	2021-11-19 12:40:56.722044+00
147	maasserver	0134_create_default_resourcepool	2021-11-19 12:40:56.915219+00
148	maasserver	0135_add_pool_reference_to_node	2021-11-19 12:40:57.23517+00
149	maasserver	0136_add_user_role_models	2021-11-19 12:40:57.359211+00
150	maasserver	0137_create_default_roles	2021-11-19 12:40:57.494462+00
151	maasserver	0138_add_ip_and_user_agent_to_event_model	2021-11-19 12:40:57.598659+00
152	maasserver	0139_add_endpoint_and_increase_user_agent_length_for_event	2021-11-19 12:40:57.713103+00
153	maasserver	0140_add_usergroup_model	2021-11-19 12:40:57.924026+00
154	maasserver	0141_add_default_usergroup	2021-11-19 12:40:58.132156+00
155	maasserver	0142_pod_default_resource_pool	2021-11-19 12:40:58.708092+00
156	maasserver	0143_blockdevice_firmware	2021-11-19 12:40:58.738474+00
157	maasserver	0144_filesystem_zfsroot_support	2021-11-19 12:40:58.787936+00
158	maasserver	0145_interface_firmware	2021-11-19 12:40:58.942118+00
159	maasserver	0146_add_rootkey	2021-11-19 12:40:58.955765+00
160	maasserver	0147_pod_zones	2021-11-19 12:40:59.027306+00
161	maasserver	0148_add_tags_on_pods	2021-11-19 12:40:59.085931+00
162	maasserver	0149_userprofile_auth_last_check	2021-11-19 12:40:59.123072+00
163	maasserver	0150_add_pod_commit_ratios	2021-11-19 12:40:59.210989+00
164	maasserver	0151_userprofile_is_local	2021-11-19 12:40:59.237346+00
165	maasserver	0152_add_usergroup_local	2021-11-19 12:40:59.273197+00
166	maasserver	0153_add_skip_bmc_config	2021-11-19 12:40:59.34225+00
167	maasserver	0154_link_usergroup_role	2021-11-19 12:40:59.533655+00
168	maasserver	0155_add_globaldefaults_model	2021-11-19 12:40:59.964278+00
169	maasserver	0156_drop_ssh_unique_key_index	2021-11-19 12:41:00.004865+00
170	maasserver	0157_drop_usergroup_and_role	2021-11-19 12:41:00.438749+00
171	maasserver	0158_pod_default_pool_to_pod	2021-11-19 12:41:00.517242+00
172	maasserver	0159_userprofile_auth_last_check_no_now_default	2021-11-19 12:41:00.546172+00
173	maasserver	0160_pool_only_for_machines	2021-11-19 12:41:00.644982+00
174	maasserver	0161_pod_storage_pools	2021-11-19 12:41:01.024573+00
175	maasserver	0162_storage_pools_notification	2021-11-19 12:41:01.127099+00
176	maasserver	0163_create_new_power_parameters_with_jsonfield	2021-11-19 12:41:01.219672+00
177	maasserver	0164_copy_over_existing_power_parameters	2021-11-19 12:41:01.320742+00
178	maasserver	0165_remove_and_rename_power_parameters	2021-11-19 12:41:01.535613+00
179	maasserver	0166_auto_select_s390x_extra_arches	2021-11-19 12:41:01.634578+00
180	maasserver	0167_add_pod_host	2021-11-19 12:41:01.70175+00
181	maasserver	0168_add_pod_default_macvlan_mode	2021-11-19 12:41:01.750756+00
182	maasserver	0169_find_pod_host	2021-11-19 12:41:01.754893+00
183	maasserver	0170_add_subnet_allow_dns	2021-11-19 12:41:01.777208+00
184	maasserver	0171_remove_pod_host	2021-11-19 12:41:01.854558+00
185	maasserver	0172_partition_tags	2021-11-19 12:41:01.8685+00
186	maasserver	0173_add_node_install_kvm	2021-11-19 12:41:02.092937+00
187	maasserver	0174_add_user_id_and_node_system_id_for_events	2021-11-19 12:41:02.182792+00
188	maasserver	0175_copy_user_id_and_node_system_id_for_events	2021-11-19 12:41:02.278096+00
189	maasserver	0176_rename_user_id_migrate_to_user_id_for_events	2021-11-19 12:41:02.405644+00
190	maasserver	0177_remove_unique_together_on_bmc	2021-11-19 12:41:02.453066+00
191	maasserver	0178_break_apart_linked_bmcs	2021-11-19 12:41:02.554466+00
192	maasserver	0179_rbacsync	2021-11-19 12:41:02.563308+00
193	maasserver	0180_rbaclastsync	2021-11-19 12:41:02.572676+00
194	maasserver	0181_packagerepository_disable_sources	2021-11-19 12:41:02.584713+00
195	maasserver	0182_remove_duplicate_null_ips	2021-11-19 12:41:02.600768+00
196	maasserver	0183_node_uuid	2021-11-19 12:41:02.657634+00
197	maasserver	0184_add_ephemeral_deploy_setting_to_node	2021-11-19 12:41:02.717017+00
198	maasserver	0185_vmfs6	2021-11-19 12:41:02.782762+00
199	maasserver	0186_node_description	2021-11-19 12:41:02.835891+00
200	maasserver	0187_status_messages_change_event_logging_levels	2021-11-19 12:41:02.936874+00
201	maasserver	0192_event_node_no_set_null	2021-11-19 12:41:03.169205+00
202	maasserver	0194_machine_listing_event_index	2021-11-19 12:41:03.217197+00
203	maasserver	0188_network_testing	2021-11-19 12:41:03.353922+00
204	maasserver	0189_staticipaddress_temp_expires_on	2021-11-19 12:41:03.387202+00
205	maasserver	0190_bmc_clean_duplicates	2021-11-19 12:41:03.494379+00
206	maasserver	0191_bmc_unique_power_type_and_parameters	2021-11-19 12:41:03.500855+00
207	maasserver	0193_merge_maasserver_0191_1092	2021-11-19 12:41:03.503326+00
208	maasserver	0195_merge_20190902_1357	2021-11-19 12:41:03.505799+00
209	maasserver	0196_numa_model	2021-11-19 12:41:03.857158+00
210	maasserver	0197_remove_duplicate_physical_interfaces	2021-11-19 12:41:03.962039+00
211	maasserver	0198_interface_physical_unique_mac	2021-11-19 12:41:03.968275+00
212	maasserver	0199_bootresource_tbz_txz	2021-11-19 12:41:03.980856+00
213	maasserver	0200_interface_sriov_max_vf	2021-11-19 12:41:04.032233+00
214	maasserver	0195_event_username_max_length	2021-11-19 12:41:04.148037+00
215	maasserver	0201_merge_20191008_1426	2021-11-19 12:41:04.150753+00
216	maasserver	0202_event_node_on_delete	2021-11-19 12:41:04.415722+00
217	maasserver	0203_interface_node_name_duplicates_delete	2021-11-19 12:41:04.513428+00
218	maasserver	0204_interface_node_name_unique_together	2021-11-19 12:41:04.562861+00
219	maasserver	0205_pod_nodes	2021-11-19 12:41:04.640497+00
220	maasserver	0206_remove_node_token	2021-11-19 12:41:04.721787+00
221	maasserver	0207_notification_dismissable	2021-11-19 12:41:04.743513+00
222	maasserver	0208_no_power_query_events	2021-11-19 12:41:04.846899+00
223	maasserver	0209_default_partitiontable_gpt	2021-11-19 12:41:04.867675+00
224	maasserver	0210_filepathfield_to_charfield	2021-11-19 12:41:04.91246+00
225	maasserver	0211_jsonfield_default_callable	2021-11-19 12:41:05.008252+00
226	maasserver	0212_notifications_fields	2021-11-19 12:41:05.07502+00
227	maasserver	0213_virtual_machine	2021-11-19 12:41:05.247006+00
228	maasserver	0214_virtualmachine_one_to_one	2021-11-19 12:41:05.336279+00
229	maasserver	0215_numanode_hugepages	2021-11-19 12:41:05.590857+00
230	maasserver	0216_remove_skip_bmc_config_column	2021-11-19 12:41:05.661625+00
231	maasserver	0217_notification_dismissal_timestamp	2021-11-19 12:41:05.71417+00
232	maasserver	0218_images_maas_io_daily_to_stable	2021-11-19 12:41:05.8216+00
233	maasserver	0219_vm_nic_link	2021-11-19 12:41:05.907892+00
234	maasserver	0220_nodedevice	2021-11-19 12:41:06.004318+00
235	maasserver	0221_track_lxd_project	2021-11-19 12:41:06.219817+00
236	maasserver	0222_replace_node_creation_type	2021-11-19 12:41:06.43745+00
237	maasserver	0223_virtualmachine_blank_project	2021-11-19 12:41:06.847243+00
238	maasserver	0224_virtual_machine_disk	2021-11-19 12:41:07.032887+00
239	maasserver	0225_drop_rsd_pod	2021-11-19 12:41:07.148362+00
240	maasserver	0226_drop_iscsi_storage	2021-11-19 12:41:07.247321+00
241	maasserver	0227_drop_pod_local_storage	2021-11-19 12:41:07.343709+00
242	maasserver	0228_drop_iscsiblockdevice	2021-11-19 12:41:07.350424+00
243	maasserver	0229_drop_physicalblockdevice_storage_pool	2021-11-19 12:41:07.435156+00
244	maasserver	0230_tag_kernel_opts_blank_instead_of_null	2021-11-19 12:41:07.453178+00
245	maasserver	0231_bmc_version	2021-11-19 12:41:07.515054+00
246	maasserver	0232_drop_controllerinfo_interface_fields	2021-11-19 12:41:07.606905+00
247	maasserver	0233_drop_switch	2021-11-19 12:41:07.613541+00
248	maasserver	0234_node_register_vmhost	2021-11-19 12:41:07.675696+00
249	maasserver	0235_controllerinfo_versions_details	2021-11-19 12:41:08.164885+00
250	maasserver	0236_controllerinfo_update_first_reported	2021-11-19 12:41:08.237173+00
251	maasserver	0237_drop_controller_version_mismatch_notifications	2021-11-19 12:41:08.350623+00
252	maasserver	0238_disable_boot_architectures	2021-11-19 12:41:08.374021+00
253	maasserver	0239_add_iprange_specific_dhcp_snippets	2021-11-19 12:41:08.467242+00
254	maasserver	0240_ownerdata_key_fix	2021-11-19 12:41:08.576326+00
255	maasserver	0241_physical_interface_default_node_numanode	2021-11-19 12:41:08.806888+00
256	maasserver	0242_forwarddnsserver	2021-11-19 12:41:08.936299+00
257	maasserver	0243_node_dynamic_for_controller_and_vmhost	2021-11-19 12:41:09.0856+00
258	maasserver	0244_controller_nodes_deployed	2021-11-19 12:41:09.483833+00
259	maasserver	0245_bmc_power_parameters_index_hash	2021-11-19 12:41:09.635635+00
260	maasserver	0246_bootresource_custom_base_type	2021-11-19 12:41:09.651438+00
261	maasserver	0247_auto_20210915_1545	2021-11-19 12:41:09.769845+00
262	maasserver	0248_auto_20211006_1829	2021-11-19 12:41:10.011088+00
263	maasserver	0249_lxd_auth_metrics	2021-11-19 12:41:10.193577+00
264	maasserver	0250_node_last_applied_storage_layout	2021-11-19 12:41:10.257785+00
265	maasserver	0251_auto_20211027_2128	2021-11-19 12:41:10.383283+00
266	metadataserver	0003_remove_noderesult	2021-11-19 12:41:10.497317+00
267	metadataserver	0004_aborted_script_status	2021-11-19 12:41:10.519628+00
268	metadataserver	0005_store_powerstate_on_scriptset_creation	2021-11-19 12:41:10.555844+00
269	metadataserver	0006_scriptresult_combined_output	2021-11-19 12:41:10.582204+00
270	metadataserver	0007_migrate-commissioningscripts	2021-11-19 12:41:10.887103+00
271	metadataserver	0008_remove-commissioningscripts	2021-11-19 12:41:10.894502+00
272	metadataserver	0009_remove_noderesult_schema	2021-11-19 12:41:10.902347+00
273	metadataserver	0010_scriptresult_time_and_script_title	2021-11-19 12:41:10.957528+00
274	metadataserver	0011_script_metadata	2021-11-19 12:41:11.051289+00
275	metadataserver	0012_store_script_results	2021-11-19 12:41:11.091909+00
276	metadataserver	0013_scriptresult_physicalblockdevice	2021-11-19 12:41:11.26438+00
277	metadataserver	0014_rename_dhcp_unconfigured_ifaces	2021-11-19 12:41:11.379168+00
278	metadataserver	0015_migrate_storage_tests	2021-11-19 12:41:11.494202+00
279	metadataserver	0016_script_model_fw_update_and_hw_config	2021-11-19 12:41:11.542797+00
280	metadataserver	0017_store_requested_scripts	2021-11-19 12:41:11.607621+00
281	metadataserver	0018_script_result_skipped	2021-11-19 12:41:11.635989+00
282	metadataserver	0019_add_script_result_suppressed	2021-11-19 12:41:11.674488+00
283	metadataserver	0020_network_testing	2021-11-19 12:41:11.795427+00
284	metadataserver	0021_scriptresult_applying_netconf	2021-11-19 12:41:11.839799+00
285	metadataserver	0022_internet-connectivity-network-validation	2021-11-19 12:41:11.848087+00
286	metadataserver	0023_reorder_network_scripts	2021-11-19 12:41:11.955536+00
287	metadataserver	0024_reorder_commissioning_scripts	2021-11-19 12:41:12.070671+00
288	metadataserver	0025_nodedevice	2021-11-19 12:41:12.085411+00
289	metadataserver	0026_drop_ipaddr_script	2021-11-19 12:41:12.40226+00
290	piston3	0002_auto_20151209_1652	2021-11-19 12:41:12.422797+00
291	piston3	0003_piston_nonce_index	2021-11-19 12:41:12.433498+00
292	sessions	0001_initial	2021-11-19 12:41:12.444821+00
293	sites	0001_initial	2021-11-19 12:41:12.455763+00
294	sites	0002_alter_domain_unique	2021-11-19 12:41:12.467536+00
295	maasserver	0252_drop_fannetwork	2021-11-26 17:02:43.267105+00
296	maasserver	0253_nodeconfig	2022-03-01 15:55:02.690198+00
297	maasserver	0254_default_nodeconfig_devices	2022-03-01 15:55:02.735735+00
298	maasserver	0255_node_current_config	2022-03-01 15:55:02.863062+00
299	maasserver	0256_blockdevice_nodeconfig_only	2022-03-01 15:55:02.882362+00
300	maasserver	0257_filesystem_populate_node_config_id	2022-03-01 15:55:02.892658+00
301	maasserver	0258_filesystem_nodeconfig_only	2022-03-01 15:55:03.355721+00
302	maasserver	0259_add_hardware_sync_flag	2022-03-01 15:55:03.478532+00
303	maasserver	0260_drop_maas_support_views	2022-03-01 15:55:03.536395+00
304	maasserver	0261_interface_nodeconfig_only	2022-03-01 15:55:03.547634+00
305	maasserver	0262_nodeconfig_link_replace_node	2022-03-01 15:55:04.117676+00
306	maasserver	0263_vlan_racks_on_delete	2022-03-01 15:55:04.573912+00
307	maasserver	0264_nodedevice_nodeconfig_link	2022-03-01 15:55:04.795457+00
308	maasserver	0265_nodedevice_nodeconfig_migrate	2022-03-01 15:55:04.81799+00
309	maasserver	0266_nodedevice_unlink_node	2022-03-01 15:55:05.13206+00
310	maastesting	0001_initial	2022-03-08 14:01:53.649122+00
311	maasserver	0267_add_machine_specific_sync_interval_fields	2022-06-13 14:48:40.504678+00
312	maasserver	0268_partition_index	2022-06-13 14:48:40.670232+00
313	maasserver	0269_interface_idx_include_nodeconfig	2022-06-13 14:48:40.68281+00
314	maasserver	0270_storage_uuid_drop_unique	2022-06-13 14:48:40.781473+00
315	maasserver	0271_interface_unique	2022-06-13 14:48:40.900017+00
316	maasserver	0272_virtualmachine_resources_unique	2022-06-13 14:48:41.864679+00
317	maasserver	0273_ipaddress_defaults	2022-06-13 14:48:41.907316+00
318	maasserver	0274_audit_log_add_endpoint_cli_type	2022-06-13 14:48:41.94551+00
319	maasserver	0275_interface_children	2022-06-13 14:48:42.048243+00
320	maasserver	0276_bmc_autodetect_metric	2022-06-13 14:48:42.290065+00
321	maasserver	0277_replace_nullbooleanfield	2022-06-13 14:48:42.308843+00
322	metadataserver	0027_reorder_machine_resources_script	2022-06-13 14:48:42.420499+00
323	metadataserver	0028_scriptset_requested_scripts_rename	2022-06-13 14:48:42.503381+00
324	metadataserver	0029_scriptset_tags_cleanup	2022-06-13 14:48:42.510804+00
325	metadataserver	0030_scriptresult_script_link	2022-06-13 14:48:42.738442+00
326	auth	0006_default_auto_field	2022-07-07 11:09:02.38743+00
327	maasserver	0278_generic_jsonfield	2022-07-07 11:09:02.563813+00
328	metadataserver	0031_id_field_bigint	2022-07-07 11:09:03.047446+00
329	metadataserver	0032_default_auto_field	2022-07-07 11:09:03.68517+00
330	maasserver	0279_store_vpd_metadata_for_nodedevice	2022-09-05 00:16:36.329151+00
331	maasserver	0280_set_parent_for_existing_vms	2022-09-15 11:24:45.945397+00
332	maasserver	0281_secret_model	2022-09-15 11:24:45.959926+00
333	maasserver	0282_rpc_shared_secret_to_secret	2022-10-03 12:52:26.794349+00
334	maasserver	0283_migrate_tls_secrets	2022-10-03 12:52:26.80416+00
335	maasserver	0284_migrate_more_global_secrets	2022-10-03 12:52:26.811989+00
336	maasserver	0285_migrate_external_auth_secrets	2022-10-06 11:12:27.640004+00
337	metadataserver	0033_remove_nodekey_key	2022-10-07 06:51:34.349659+00
338	maasserver	0286_node_deploy_metadata	2022-10-11 03:29:32.800937+00
339	maasserver	0287_add_controller_info_vault_flag	2022-10-15 03:29:44.399652+00
340	maasserver	0288_rootkey_material_secret	2022-10-21 03:29:26.788885+00
341	maasserver	0289_vault_secret	2022-10-28 03:29:40.716763+00
342	maasserver	0290_migrate_node_power_parameters	2022-11-19 03:29:31.92822+00
343	maasserver	0291_rdns_hostnames_as_array	2023-01-19 03:29:20.405694+00
344	maasserver	0292_use_builtin_json_field	2023-01-24 03:29:54.34659+00
345	metadataserver	0034_use_builtin_json_field	2023-01-24 03:29:54.467889+00
346	maasserver	0293_drop_verbose_regex_validator	2023-02-28 03:29:15.412014+00
347	maasserver	0294_keyring_data_binary_field	2023-03-01 03:29:34.859599+00
348	maasserver	0295_macaddress_text_field	2023-03-04 03:29:30.976082+00
349	metadataserver	0035_move_metadata_node_models	2023-04-27 03:30:37.453124+00
350	maasserver	0296_move_metadata_node_models	2023-04-27 03:30:37.656471+00
351	metadataserver	0036_move_metadata_script_models	2023-04-28 03:30:33.711429+00
352	maasserver	0297_move_metadata_script_models	2023-04-28 03:30:34.516888+00
353	maasserver	0298_current_script_set_foreign_keys_drop_indexes	2023-04-28 03:30:34.954887+00
354	maasserver	0299_current_script_set_foreign_keys_cleanup	2023-04-28 03:30:34.967579+00
355	maasserver	0300_current_script_set_foreign_keys_readd	2023-04-28 03:30:35.35594+00
356	maasserver	0301_discovery_ignore_fks	2023-05-03 03:30:38.164577+00
357	maasserver	0302_big_auto_field	2023-05-03 03:30:46.026112+00
358	piston3	0004_big_auto_field	2023-05-03 03:30:46.539848+00
359	maasserver	0303_interface_params_cleanups	2023-05-12 03:30:35.152079+00
360	maasserver	0304_interface_params_no_autoconf	2023-05-12 03:30:35.161528+00
361	maasserver	0305_add_temporal_schema	2023-08-25 09:27:56.827957+00
362	maasserver	0306_diskless_ephemeral_deploy	2023-09-01 03:30:49.394747+00
363	maasserver	0307_bootresource_type_drop_generated	2023-09-05 03:30:35.621467+00
364	maasserver	0308_remove_images_from_db	2023-09-05 03:30:35.88739+00
365	maasserver	0309_drop_bootloader_filetype	2023-09-06 03:30:38.148484+00
366	maasserver	0310_rootfs_image_extensions	2023-09-15 03:30:27.345312+00
367	maasserver	0311_image_sync_tracking	2023-09-28 03:30:52.503645+00
368	maasserver	0312_release_script_type	2023-10-24 03:52:07.798195+00
369	maasserver	0313_add_superuser_flag_to_existing_sysuser	2023-10-24 14:17:19.969776+00
370	maasserver	0314_bootresourcefile_sha256_index	2023-11-02 03:30:47.980664+00
371	maasserver	0315_add_current_release_script_set_to_node_model	2023-11-28 13:29:59.274246+00
372	maasserver	0316_add_defaultresource_table	2024-03-06 03:31:14.227521+00
373	maasserver	0317_migrate_defaultresource_zone	2024-03-06 03:31:14.238827+00
374	maasserver	0318_add_port_to_forward_dns_servers	2024-03-17 03:30:45.589405+00
375	maasserver	0319_merge_0304_and_0318	2024-03-20 10:17:51.582553+00
376	maasserver	0320_current_script_set_foreign_keys_drop_indexes	2024-03-20 10:17:51.918962+00
377	maasserver	0321_current_script_set_foreign_keys_cleanup	2024-03-20 10:17:51.927243+00
378	maasserver	0322_current_script_set_foreign_keys_readd	2024-03-20 10:17:52.193804+00
379	maasserver	0323_add_bootresource_alias_column	2024-05-22 03:30:53.729029+00
380	maasserver	0324_populate_distro_alias	2024-05-24 03:30:57.883427+00
381	maasserver	0325_foreign_key_drop	2024-05-28 12:00:15.12313+00
382	maasserver	0326_foreign_key_cleanup	2024-05-28 12:00:15.576421+00
383	maasserver	0327_foreign_key_readd	2024-05-28 12:00:16.543243+00
384	maasserver	0328_merge_0327_and_0324	2024-05-28 19:46:08.641012+00
\.


--
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_session (session_key, session_data, expire_date) FROM stdin;
\.


--
-- Data for Name: django_site; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_site (id, domain, name) FROM stdin;
1	example.com	example.com
\.


--
-- Data for Name: maasserver_blockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_blockdevice (id, created, updated, name, id_path, size, block_size, tags, node_config_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bmc; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bmc (id, created, updated, power_type, ip_address_id, architectures, bmc_type, capabilities, cores, cpu_speed, local_storage, memory, name, pool_id, zone_id, tags, cpu_over_commit_ratio, memory_over_commit_ratio, default_storage_pool_id, power_parameters, default_macvlan_mode, version, created_with_cert_expiration_days, created_with_maas_generated_cert, created_with_trust_password, created_by_commissioning) FROM stdin;
\.


--
-- Data for Name: maasserver_bmcroutablerackcontrollerrelationship; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bmcroutablerackcontrollerrelationship (id, created, updated, routable, bmc_id, rack_controller_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresource (id, created, updated, rtype, name, architecture, extra, kflavor, bootloader_type, rolling, base_image, alias) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresourcefile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresourcefile (id, created, updated, filename, filetype, extra, largefile_id, resource_set_id, sha256, size) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresourcefilesync; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresourcefilesync (id, created, updated, size, file_id, region_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresourceset; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresourceset (id, created, updated, version, label, resource_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootsource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootsource (id, created, updated, url, keyring_filename, keyring_data) FROM stdin;
\.


--
-- Data for Name: maasserver_bootsourcecache; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootsourcecache (id, created, updated, os, arch, subarch, release, label, boot_source_id, release_codename, release_title, support_eol, kflavor, bootloader_type, extra) FROM stdin;
\.


--
-- Data for Name: maasserver_bootsourceselection; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootsourceselection (id, created, updated, os, release, arches, subarches, labels, boot_source_id) FROM stdin;
\.


--
-- Data for Name: maasserver_cacheset; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_cacheset (id, created, updated) FROM stdin;
\.


--
-- Data for Name: maasserver_config; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_config (id, name, value) FROM stdin;
\.


--
-- Data for Name: maasserver_controllerinfo; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_controllerinfo (created, updated, node_id, version, install_type, snap_cohort, snap_revision, snap_update_revision, update_origin, update_version, update_first_reported, vault_configured) FROM stdin;
\.


--
-- Data for Name: maasserver_defaultresource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_defaultresource (id, created, updated, zone_id) FROM stdin;
1	2024-03-06 03:31:14.232149+00	2024-03-06 03:31:14.232149+00	1
\.


--
-- Data for Name: maasserver_dhcpsnippet; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_dhcpsnippet (id, created, updated, name, description, enabled, node_id, subnet_id, value_id, iprange_id) FROM stdin;
\.


--
-- Data for Name: maasserver_dnsdata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_dnsdata (id, created, updated, rrtype, rrdata, dnsresource_id, ttl) FROM stdin;
\.


--
-- Data for Name: maasserver_dnspublication; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_dnspublication (id, serial, created, source) FROM stdin;
1	1	2021-11-19 12:40:49.607453+00	Initial publication
\.


--
-- Data for Name: maasserver_dnsresource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_dnsresource (id, created, updated, name, domain_id, address_ttl) FROM stdin;
\.


--
-- Data for Name: maasserver_dnsresource_ip_addresses; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_dnsresource_ip_addresses (id, dnsresource_id, staticipaddress_id) FROM stdin;
\.


--
-- Data for Name: maasserver_domain; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_domain (id, created, updated, name, authoritative, ttl) FROM stdin;
0	2021-11-19 12:40:45.172211+00	2021-11-19 12:40:45.172211+00	maas	t	\N
\.


--
-- Data for Name: maasserver_event; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_event (id, created, updated, action, description, node_id, type_id, node_hostname, username, ip_address, user_agent, endpoint, node_system_id, user_id) FROM stdin;
\.


--
-- Data for Name: maasserver_eventtype; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_eventtype (id, created, updated, name, description, level) FROM stdin;
\.


--
-- Data for Name: maasserver_fabric; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_fabric (id, created, updated, name, class_type, description) FROM stdin;
\.


--
-- Data for Name: maasserver_filestorage; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_filestorage (id, filename, content, key, owner_id) FROM stdin;
\.


--
-- Data for Name: maasserver_filesystem; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_filesystem (id, created, updated, uuid, fstype, label, create_params, mount_point, mount_options, acquired, block_device_id, cache_set_id, filesystem_group_id, partition_id, node_config_id) FROM stdin;
\.


--
-- Data for Name: maasserver_filesystemgroup; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_filesystemgroup (id, created, updated, uuid, group_type, name, create_params, cache_mode, cache_set_id) FROM stdin;
\.


--
-- Data for Name: maasserver_forwarddnsserver; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_forwarddnsserver (id, created, updated, ip_address, port) FROM stdin;
\.


--
-- Data for Name: maasserver_forwarddnsserver_domains; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_forwarddnsserver_domains (id, forwarddnsserver_id, domain_id) FROM stdin;
\.


--
-- Data for Name: maasserver_globaldefault; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_globaldefault (id, created, updated, domain_id) FROM stdin;
0	2021-11-19 12:40:59.690026+00	2021-11-19 12:40:59.694316+00	0
\.


--
-- Data for Name: maasserver_interface; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_interface (id, created, updated, name, type, mac_address, params, tags, enabled, vlan_id, acquired, mdns_discovery_state, neighbour_discovery_state, firmware_version, product, vendor, interface_speed, link_connected, link_speed, numa_node_id, sriov_max_vf, node_config_id) FROM stdin;
\.


--
-- Data for Name: maasserver_interface_ip_addresses; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_interface_ip_addresses (id, interface_id, staticipaddress_id) FROM stdin;
\.


--
-- Data for Name: maasserver_interfacerelationship; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_interfacerelationship (id, created, updated, child_id, parent_id) FROM stdin;
\.


--
-- Data for Name: maasserver_iprange; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_iprange (id, created, updated, type, start_ip, end_ip, comment, subnet_id, user_id) FROM stdin;
\.


--
-- Data for Name: maasserver_keysource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_keysource (id, created, updated, protocol, auth_id, auto_update) FROM stdin;
\.


--
-- Data for Name: maasserver_largefile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_largefile (id, created, updated, sha256, total_size, content, size) FROM stdin;
\.


--
-- Data for Name: maasserver_licensekey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_licensekey (id, created, updated, osystem, distro_series, license_key) FROM stdin;
\.


--
-- Data for Name: maasserver_mdns; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_mdns (id, created, updated, ip, hostname, count, interface_id) FROM stdin;
\.


--
-- Data for Name: maasserver_neighbour; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_neighbour (id, created, updated, ip, "time", vid, count, mac_address, interface_id) FROM stdin;
\.


--
-- Data for Name: maasserver_node; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_node (id, created, updated, system_id, hostname, status, bios_boot_method, osystem, distro_series, architecture, min_hwe_kernel, hwe_kernel, agent_name, error_description, cpu_count, memory, swap_size, power_state, power_state_updated, error, netboot, license_key, boot_cluster_ip, enable_ssh, skip_networking, skip_storage, boot_interface_id, gateway_link_ipv4_id, gateway_link_ipv6_id, owner_id, parent_id, zone_id, boot_disk_id, node_type, domain_id, dns_process_id, bmc_id, address_ttl, status_expires, power_state_queried, url, managing_process_id, last_image_sync, previous_status, default_user, cpu_speed, current_commissioning_script_set_id, current_installation_script_set_id, current_testing_script_set_id, install_rackd, locked, pool_id, instance_power_parameters, install_kvm, hardware_uuid, ephemeral_deploy, description, dynamic, register_vmhost, last_applied_storage_layout, current_config_id, enable_hw_sync, last_sync, sync_interval, current_release_script_set_id) FROM stdin;
\.


--
-- Data for Name: maasserver_node_tags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_node_tags (id, node_id, tag_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodeconfig; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodeconfig (id, created, updated, name, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodedevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodedevice (id, created, updated, bus, hardware_type, vendor_id, product_id, vendor_name, product_name, commissioning_driver, bus_number, device_number, pci_address, numa_node_id, physical_blockdevice_id, physical_interface_id, node_config_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodedevicevpd; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodedevicevpd (id, key, value, node_device_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodegrouptorackcontroller; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodegrouptorackcontroller (id, uuid, subnet_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodekey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodekey (id, node_id, token_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodemetadata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodemetadata (id, created, updated, key, value, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodeuserdata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodeuserdata (id, data, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_notification; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_notification (id, created, updated, ident, users, admins, message, context, user_id, category, dismissable) FROM stdin;
\.


--
-- Data for Name: maasserver_notificationdismissal; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_notificationdismissal (id, notification_id, user_id, created, updated) FROM stdin;
\.


--
-- Data for Name: maasserver_numanode; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_numanode (id, created, updated, index, memory, cores, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_numanodehugepages; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_numanodehugepages (id, created, updated, page_size, total, numanode_id) FROM stdin;
\.


--
-- Data for Name: maasserver_ownerdata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_ownerdata (id, key, value, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_packagerepository; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_packagerepository (id, created, updated, name, url, components, arches, key, "default", enabled, disabled_pockets, distributions, disabled_components, disable_sources) FROM stdin;
1	2021-11-19 12:40:50.636477+00	2021-11-19 12:40:50.636477+00	main_archive	http://archive.ubuntu.com/ubuntu	{}	{amd64,i386}		t	t	{}	{}	{}	t
2	2021-11-19 12:40:50.636477+00	2021-11-19 12:40:50.636477+00	ports_archive	http://ports.ubuntu.com/ubuntu-ports	{}	{armhf,arm64,ppc64el,s390x}		t	t	{}	{}	{}	t
\.


--
-- Data for Name: maasserver_partition; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_partition (id, created, updated, uuid, size, bootable, partition_table_id, tags, index) FROM stdin;
\.


--
-- Data for Name: maasserver_partitiontable; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_partitiontable (id, created, updated, table_type, block_device_id) FROM stdin;
\.


--
-- Data for Name: maasserver_physicalblockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_physicalblockdevice (blockdevice_ptr_id, model, serial, firmware_version, numa_node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_podhints; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_podhints (id, cores, memory, local_storage, pod_id, cpu_speed, cluster_id) FROM stdin;
\.


--
-- Data for Name: maasserver_podhints_nodes; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_podhints_nodes (id, podhints_id, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_podstoragepool; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_podstoragepool (id, name, pool_id, pool_type, path, storage, pod_id) FROM stdin;
\.


--
-- Data for Name: maasserver_rbaclastsync; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_rbaclastsync (id, resource_type, sync_id) FROM stdin;
\.


--
-- Data for Name: maasserver_rbacsync; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_rbacsync (id, action, resource_type, resource_id, resource_name, created, source) FROM stdin;
\.


--
-- Data for Name: maasserver_rdns; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_rdns (id, created, updated, ip, hostname, hostnames, observer_id) FROM stdin;
\.


--
-- Data for Name: maasserver_regioncontrollerprocess; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_regioncontrollerprocess (id, created, updated, pid, region_id) FROM stdin;
\.


--
-- Data for Name: maasserver_regioncontrollerprocessendpoint; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_regioncontrollerprocessendpoint (id, created, updated, address, port, process_id) FROM stdin;
\.


--
-- Data for Name: maasserver_regionrackrpcconnection; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_regionrackrpcconnection (id, created, updated, endpoint_id, rack_controller_id) FROM stdin;
\.


--
-- Data for Name: maasserver_resourcepool; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_resourcepool (id, created, updated, name, description) FROM stdin;
0	2021-11-19 12:40:56.90477+00	2021-11-19 12:40:56.90477+00	default	Default pool
\.


--
-- Data for Name: maasserver_rootkey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_rootkey (created, updated, id, expiration) FROM stdin;
\.


--
-- Data for Name: maasserver_script; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_script (id, created, updated, name, description, tags, script_type, timeout, destructive, "default", script_id, title, hardware_type, packages, parallel, parameters, results, for_hardware, may_reboot, recommission, apply_configured_networking) FROM stdin;
\.


--
-- Data for Name: maasserver_scriptresult; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_scriptresult (id, created, updated, status, exit_status, script_name, stdout, stderr, result, script_id, script_set_id, script_version_id, output, ended, started, parameters, physical_blockdevice_id, suppressed, interface_id) FROM stdin;
\.


--
-- Data for Name: maasserver_scriptset; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_scriptset (id, last_ping, result_type, node_id, power_state_before_transition, tags) FROM stdin;
\.


--
-- Data for Name: maasserver_secret; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_secret (created, updated, path, value) FROM stdin;
\.


--
-- Data for Name: maasserver_service; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_service (id, created, updated, name, status, status_info, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_space; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_space (id, created, updated, name, description) FROM stdin;
\.


--
-- Data for Name: maasserver_sshkey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_sshkey (id, created, updated, key, user_id, keysource_id) FROM stdin;
\.


--
-- Data for Name: maasserver_sslkey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_sslkey (id, created, updated, key, user_id) FROM stdin;
\.


--
-- Data for Name: maasserver_staticipaddress; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_staticipaddress (id, created, updated, ip, alloc_type, subnet_id, user_id, lease_time, temp_expires_on) FROM stdin;
\.


--
-- Data for Name: maasserver_staticroute; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_staticroute (id, gateway_ip, metric, destination_id, source_id, created, updated) FROM stdin;
\.


--
-- Data for Name: maasserver_subnet; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_subnet (id, created, updated, name, cidr, gateway_ip, dns_servers, vlan_id, rdns_mode, allow_proxy, description, active_discovery, managed, allow_dns, disabled_boot_architectures) FROM stdin;
\.


--
-- Data for Name: maasserver_tag; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_tag (id, created, updated, name, definition, comment, kernel_opts) FROM stdin;
\.


--
-- Data for Name: maasserver_template; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_template (id, created, updated, filename, default_version_id, version_id) FROM stdin;
\.


--
-- Data for Name: maasserver_userprofile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_userprofile (id, user_id, completed_intro, auth_last_check, is_local) FROM stdin;
\.


--
-- Data for Name: maasserver_vaultsecret; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_vaultsecret (path, deleted) FROM stdin;
\.


--
-- Data for Name: maasserver_versionedtextfile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_versionedtextfile (id, created, updated, data, comment, previous_version_id) FROM stdin;
\.


--
-- Data for Name: maasserver_virtualblockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_virtualblockdevice (blockdevice_ptr_id, uuid, filesystem_group_id) FROM stdin;
\.


--
-- Data for Name: maasserver_virtualmachine; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_virtualmachine (id, created, updated, identifier, pinned_cores, unpinned_cores, memory, hugepages_backed, bmc_id, machine_id, project) FROM stdin;
\.


--
-- Data for Name: maasserver_virtualmachinedisk; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_virtualmachinedisk (id, created, updated, name, size, backing_pool_id, block_device_id, vm_id) FROM stdin;
\.


--
-- Data for Name: maasserver_virtualmachineinterface; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_virtualmachineinterface (id, created, updated, mac_address, attachment_type, host_interface_id, vm_id) FROM stdin;
\.


--
-- Data for Name: maasserver_vlan; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_vlan (id, created, updated, name, vid, mtu, fabric_id, dhcp_on, primary_rack_id, secondary_rack_id, external_dhcp, description, relay_vlan_id, space_id) FROM stdin;
\.


--
-- Data for Name: maasserver_vmcluster; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_vmcluster (id, created, updated, name, project, pool_id, zone_id) FROM stdin;
\.


--
-- Data for Name: maasserver_zone; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_zone (id, created, updated, name, description) FROM stdin;
1	2021-11-19 12:40:43.705399+00	2021-11-19 12:40:43.705399+00	default	
\.


--
-- Data for Name: maastesting_perftestbuild; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maastesting_perftestbuild (id, created, updated, start_ts, end_ts, git_branch, git_hash, release) FROM stdin;
\.


--
-- Data for Name: piston3_consumer; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.piston3_consumer (id, name, description, key, secret, status, user_id) FROM stdin;
\.


--
-- Data for Name: piston3_nonce; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.piston3_nonce (id, token_key, consumer_key, key) FROM stdin;
\.


--
-- Data for Name: piston3_token; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.piston3_token (id, key, secret, verifier, token_type, "timestamp", is_approved, callback, callback_confirmed, consumer_id, user_id) FROM stdin;
\.


--
-- Data for Name: activity_info_maps; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.activity_info_maps (shard_id, namespace_id, workflow_id, run_id, schedule_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: buffered_events; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.buffered_events (shard_id, namespace_id, workflow_id, run_id, id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: build_id_to_task_queue; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.build_id_to_task_queue (namespace_id, build_id, task_queue_name) FROM stdin;
\.


--
-- Data for Name: child_execution_info_maps; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.child_execution_info_maps (shard_id, namespace_id, workflow_id, run_id, initiated_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: cluster_membership; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.cluster_membership (membership_partition, host_id, rpc_address, rpc_port, role, session_start, last_heartbeat, record_expiry) FROM stdin;
\.


--
-- Data for Name: cluster_metadata; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.cluster_metadata (metadata_partition, data, data_encoding, version) FROM stdin;
\.


--
-- Data for Name: cluster_metadata_info; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.cluster_metadata_info (metadata_partition, cluster_name, data, data_encoding, version) FROM stdin;
\.


--
-- Data for Name: current_executions; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.current_executions (shard_id, namespace_id, workflow_id, run_id, create_request_id, state, status, start_version, last_write_version) FROM stdin;
\.


--
-- Data for Name: executions; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.executions (shard_id, namespace_id, workflow_id, run_id, next_event_id, last_write_version, data, data_encoding, state, state_encoding, db_record_version) FROM stdin;
\.


--
-- Data for Name: history_immediate_tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.history_immediate_tasks (shard_id, category_id, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: history_node; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.history_node (shard_id, tree_id, branch_id, node_id, txn_id, data, data_encoding, prev_txn_id) FROM stdin;
\.


--
-- Data for Name: history_scheduled_tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.history_scheduled_tasks (shard_id, category_id, visibility_timestamp, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: history_tree; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.history_tree (shard_id, tree_id, branch_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: namespace_metadata; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.namespace_metadata (partition_id, notification_version) FROM stdin;
54321	1
\.


--
-- Data for Name: namespaces; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.namespaces (partition_id, id, name, notification_version, data, data_encoding, is_global) FROM stdin;
\.


--
-- Data for Name: queue; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.queue (queue_type, message_id, message_payload, message_encoding) FROM stdin;
\.


--
-- Data for Name: queue_metadata; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.queue_metadata (queue_type, data, data_encoding, version) FROM stdin;
\.


--
-- Data for Name: replication_tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.replication_tasks (shard_id, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: replication_tasks_dlq; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.replication_tasks_dlq (source_cluster_name, shard_id, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: request_cancel_info_maps; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.request_cancel_info_maps (shard_id, namespace_id, workflow_id, run_id, initiated_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: schema_update_history; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.schema_update_history (version_partition, year, month, update_time, description, manifest_md5, new_version, old_version) FROM stdin;
0	2023	9	2023-09-01 03:30:50.320866	initial version		0.0	0
0	2023	9	2023-09-01 03:30:50.469309	base version of schema	55b84ca114ac34d84bdc5f52c198fa33	1.0	0.0
0	2023	9	2023-09-01 03:30:50.472776	schema update for cluster metadata	58f06841bbb187cb210db32a090c21ee	1.1	1.0
0	2023	9	2023-09-01 03:30:50.474978	schema update for RPC replication	c6bdeea21882e2625038927a84929b16	1.2	1.1
0	2023	9	2023-09-01 03:30:50.478556	schema update for kafka deprecation	3beee7d470421674194475f94b58d89b	1.3	1.2
0	2023	9	2023-09-01 03:30:50.480822	schema update for cluster metadata cleanup	c53e2e9cea5660c8a1f3b2ac73cdb138	1.4	1.3
0	2023	9	2023-09-01 03:30:50.484438	schema update for cluster_membership, executions and history_node tables	bfb307ba10ac0fdec83e0065dc5ffee4	1.5	1.4
0	2023	9	2023-09-01 03:30:50.486108	schema update for queue_metadata	978e1a6500d377ba91c6e37e5275a59b	1.6	1.5
0	2023	9	2023-09-01 03:30:50.491825	create cluster metadata info table to store cluster information and executions to store tiered storage queue	366b8b49d6701a6a09778e51ad1682ed	1.7	1.6
0	2023	9	2023-09-01 03:30:50.496234	drop unused tasks table; Expand VARCHAR columns governed by maxIDLength to VARCHAR(255)	229846b5beb0b96f49e7a3c5fde09fa7	1.8	1.7
0	2023	9	2023-09-01 03:30:50.502285	add history tasks table	b62e4e5826967e152e00b75da42d12ea	1.9	1.8
0	2023	10	2023-10-24 03:52:08.21352	add storage for update records and create task_queue_user_data table	2b0c361b0d4ab7cf09ead5566f0db520	1.10	1.9
\.


--
-- Data for Name: schema_version; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.schema_version (version_partition, db_name, creation_time, curr_version, min_compatible_version) FROM stdin;
0	maas	2023-10-24 03:52:08.21298	1.10	1.0
\.


--
-- Data for Name: shards; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.shards (shard_id, range_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: signal_info_maps; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.signal_info_maps (shard_id, namespace_id, workflow_id, run_id, initiated_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: signals_requested_sets; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.signals_requested_sets (shard_id, namespace_id, workflow_id, run_id, signal_id) FROM stdin;
\.


--
-- Data for Name: task_queue_user_data; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.task_queue_user_data (namespace_id, task_queue_name, data, data_encoding, version) FROM stdin;
\.


--
-- Data for Name: task_queues; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.task_queues (range_hash, task_queue_id, range_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.tasks (range_hash, task_queue_id, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: timer_info_maps; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.timer_info_maps (shard_id, namespace_id, workflow_id, run_id, timer_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: timer_tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.timer_tasks (shard_id, visibility_timestamp, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: transfer_tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.transfer_tasks (shard_id, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: visibility_tasks; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.visibility_tasks (shard_id, task_id, data, data_encoding) FROM stdin;
\.


--
-- Data for Name: executions_visibility; Type: TABLE DATA; Schema: temporal_visibility; Owner: -
--

COPY temporal_visibility.executions_visibility (namespace_id, run_id, start_time, execution_time, workflow_id, workflow_type_name, status, close_time, history_length, memo, encoding, task_queue, search_attributes, history_size_bytes) FROM stdin;
\.


--
-- Data for Name: schema_update_history; Type: TABLE DATA; Schema: temporal_visibility; Owner: -
--

COPY temporal_visibility.schema_update_history (version_partition, year, month, update_time, description, manifest_md5, new_version, old_version) FROM stdin;
0	2023	9	2023-09-01 03:30:50.537388	initial version		0.0	0
0	2023	9	2023-09-01 03:30:50.66697	base version of visibility schema	6a739dc4ceb78e29e490cd7cef662a80	1.0	0.0
0	2023	9	2023-09-01 03:30:50.668808	add close time & status index	3bc835a57de6e863cf545c25aa418aa3	1.1	1.0
0	2023	9	2023-09-01 03:30:50.821314	update schema to support advanced visibility	3943d27399fe3df0f1be869a4982c0bb	1.2	1.1
0	2023	10	2023-10-24 03:52:08.304127	add history size bytes and build IDs visibility columns and indices	62928bdd9093a8c18bb4a39bfe8e3a22	1.3	1.2
\.


--
-- Data for Name: schema_version; Type: TABLE DATA; Schema: temporal_visibility; Owner: -
--

COPY temporal_visibility.schema_version (version_partition, db_name, creation_time, curr_version, min_compatible_version) FROM stdin;
0	maas	2023-10-24 03:52:08.303597	1.3	0.1
\.


--
-- Name: auth_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_group_id_seq', 1, false);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_group_permissions_id_seq', 1, false);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_permission_id_seq', 472, true);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_user_groups_id_seq', 1, false);


--
-- Name: auth_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_user_id_seq', 1, false);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.auth_user_user_permissions_id_seq', 1, false);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_content_type_id_seq', 118, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 384, true);


--
-- Name: django_site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_site_id_seq', 1, true);


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_blockdevice_id_seq', 1, false);


--
-- Name: maasserver_bmc_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bmc_id_seq', 1, false);


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bmcroutablerackcontrollerrelationship_id_seq', 1, false);


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootresource_id_seq', 1, false);


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootresourcefile_id_seq', 1, false);


--
-- Name: maasserver_bootresourcefilesync_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootresourcefilesync_id_seq', 1, false);


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootresourceset_id_seq', 1, false);


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootsource_id_seq', 1, false);


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootsourcecache_id_seq', 1, false);


--
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootsourceselection_id_seq', 1, false);


--
-- Name: maasserver_cacheset_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_cacheset_id_seq', 1, false);


--
-- Name: maasserver_config_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_config_id_seq', 1, false);


--
-- Name: maasserver_defaultresource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_defaultresource_id_seq', 1, true);


--
-- Name: maasserver_dhcpsnippet_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_dhcpsnippet_id_seq', 1, false);


--
-- Name: maasserver_dnsdata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_dnsdata_id_seq', 1, false);


--
-- Name: maasserver_dnspublication_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_dnspublication_id_seq', 1, true);


--
-- Name: maasserver_dnsresource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_dnsresource_id_seq', 1, false);


--
-- Name: maasserver_dnsresource_ip_addresses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_dnsresource_ip_addresses_id_seq', 1, false);


--
-- Name: maasserver_domain_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_domain_id_seq', 1, false);


--
-- Name: maasserver_event_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_event_id_seq', 1, false);


--
-- Name: maasserver_eventtype_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_eventtype_id_seq', 1, false);


--
-- Name: maasserver_fabric_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_fabric_id_seq', 1, false);


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_filestorage_id_seq', 1, false);


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_filesystem_id_seq', 1, false);


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_filesystemgroup_id_seq', 1, false);


--
-- Name: maasserver_forwarddnsserver_domains_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_forwarddnsserver_domains_id_seq', 1, false);


--
-- Name: maasserver_forwarddnsserver_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_forwarddnsserver_id_seq', 1, false);


--
-- Name: maasserver_globaldefault_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_globaldefault_id_seq', 1, false);


--
-- Name: maasserver_interface_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_interface_id_seq', 1, false);


--
-- Name: maasserver_interface_ip_addresses_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_interface_ip_addresses_id_seq', 1, false);


--
-- Name: maasserver_interfacerelationship_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_interfacerelationship_id_seq', 1, false);


--
-- Name: maasserver_iprange_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_iprange_id_seq', 1, false);


--
-- Name: maasserver_keysource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_keysource_id_seq', 1, false);


--
-- Name: maasserver_largefile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_largefile_id_seq', 1, false);


--
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_licensekey_id_seq', 1, false);


--
-- Name: maasserver_mdns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_mdns_id_seq', 1, false);


--
-- Name: maasserver_neighbour_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_neighbour_id_seq', 1, false);


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_node_id_seq', 1, false);


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_node_tags_id_seq', 1, false);


--
-- Name: maasserver_nodeconfig_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodeconfig_id_seq', 1, false);


--
-- Name: maasserver_nodedevice_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodedevice_id_seq', 1, false);


--
-- Name: maasserver_nodedevicevpd_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodedevicevpd_id_seq', 1, false);


--
-- Name: maasserver_nodegrouptorackcontroller_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodegrouptorackcontroller_id_seq', 1, false);


--
-- Name: maasserver_nodekey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodekey_id_seq', 1, false);


--
-- Name: maasserver_nodemetadata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodemetadata_id_seq', 1, false);


--
-- Name: maasserver_nodeuserdata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodeuserdata_id_seq', 1, false);


--
-- Name: maasserver_notification_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_notification_id_seq', 1, false);


--
-- Name: maasserver_notificationdismissal_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_notificationdismissal_id_seq', 1, false);


--
-- Name: maasserver_numanode_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_numanode_id_seq', 1, false);


--
-- Name: maasserver_numanodehugepages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_numanodehugepages_id_seq', 1, false);


--
-- Name: maasserver_ownerdata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_ownerdata_id_seq', 1, false);


--
-- Name: maasserver_packagerepository_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_packagerepository_id_seq', 2, true);


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_partition_id_seq', 1, false);


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_partitiontable_id_seq', 1, false);


--
-- Name: maasserver_podhints_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_podhints_id_seq', 1, false);


--
-- Name: maasserver_podhints_nodes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_podhints_nodes_id_seq', 1, false);


--
-- Name: maasserver_podstoragepool_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_podstoragepool_id_seq', 1, false);


--
-- Name: maasserver_rbaclastsync_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_rbaclastsync_id_seq', 1, false);


--
-- Name: maasserver_rbacsync_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_rbacsync_id_seq', 1, false);


--
-- Name: maasserver_rdns_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_rdns_id_seq', 1, false);


--
-- Name: maasserver_regioncontrollerprocess_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_regioncontrollerprocess_id_seq', 1, false);


--
-- Name: maasserver_regioncontrollerprocessendpoint_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_regioncontrollerprocessendpoint_id_seq', 1, false);


--
-- Name: maasserver_regionrackrpcconnection_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_regionrackrpcconnection_id_seq', 1, false);


--
-- Name: maasserver_resourcepool_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_resourcepool_id_seq', 1, false);


--
-- Name: maasserver_rootkey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_rootkey_id_seq', 1, false);


--
-- Name: maasserver_script_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_script_id_seq', 1, false);


--
-- Name: maasserver_scriptresult_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_scriptresult_id_seq', 1, false);


--
-- Name: maasserver_scriptset_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_scriptset_id_seq', 1, false);


--
-- Name: maasserver_service_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_service_id_seq', 1, false);


--
-- Name: maasserver_space_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_space_id_seq', 1, false);


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_sshkey_id_seq', 1, false);


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_sslkey_id_seq', 1, false);


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_staticipaddress_id_seq', 1, false);


--
-- Name: maasserver_staticroute_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_staticroute_id_seq', 1, false);


--
-- Name: maasserver_subnet_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_subnet_id_seq', 1, false);


--
-- Name: maasserver_tag_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_tag_id_seq', 1, false);


--
-- Name: maasserver_template_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_template_id_seq', 1, false);


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_userprofile_id_seq', 1, false);


--
-- Name: maasserver_versionedtextfile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_versionedtextfile_id_seq', 1, false);


--
-- Name: maasserver_virtualmachine_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_virtualmachine_id_seq', 1, false);


--
-- Name: maasserver_virtualmachinedisk_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_virtualmachinedisk_id_seq', 1, false);


--
-- Name: maasserver_virtualmachineinterface_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_virtualmachineinterface_id_seq', 1, false);


--
-- Name: maasserver_vlan_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_vlan_id_seq', 1, false);


--
-- Name: maasserver_vmcluster_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_vmcluster_id_seq', 1, false);


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_zone_id_seq', 1, true);


--
-- Name: maasserver_zone_serial_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_zone_serial_seq', 3, true);


--
-- Name: maastesting_perftestbuild_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maastesting_perftestbuild_id_seq', 1, false);


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metadataserver_nodekey_id_seq', 1, false);


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metadataserver_nodeuserdata_id_seq', 1, false);


--
-- Name: metadataserver_script_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metadataserver_script_id_seq', 1, false);


--
-- Name: metadataserver_scriptresult_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metadataserver_scriptresult_id_seq', 1, false);


--
-- Name: metadataserver_scriptset_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.metadataserver_scriptset_id_seq', 1, false);


--
-- Name: piston3_consumer_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.piston3_consumer_id_seq', 1, false);


--
-- Name: piston3_nonce_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.piston3_nonce_id_seq', 1, false);


--
-- Name: piston3_token_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.piston3_token_id_seq', 1, false);


--
-- Name: buffered_events_id_seq; Type: SEQUENCE SET; Schema: temporal; Owner: -
--

SELECT pg_catalog.setval('temporal.buffered_events_id_seq', 1, false);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user auth_user_email_1c89df09_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_email_1c89df09_uniq UNIQUE (email);


--
-- Name: auth_user_groups auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_user_id_group_id_94350c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq UNIQUE (user_id, group_id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_permission_id_14a6b632_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq UNIQUE (user_id, permission_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: django_site django_site_domain_a2e37b91_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_site
    ADD CONSTRAINT django_site_domain_a2e37b91_uniq UNIQUE (domain);


--
-- Name: django_site django_site_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_site
    ADD CONSTRAINT django_site_pkey PRIMARY KEY (id);


--
-- Name: maasserver_blockdevice maasserver_blockdevice_node_config_id_name_9103d63b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_node_config_id_name_9103d63b_uniq UNIQUE (node_config_id, name);


--
-- Name: maasserver_blockdevice maasserver_blockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bmc maasserver_bmc_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship maasserver_bmcroutablerackcontrollerrelationship_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmcroutablerackcontrollerrelationship
    ADD CONSTRAINT maasserver_bmcroutablerackcontrollerrelationship_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresource maasserver_bootresource_name_architecture_alias_888a3de7_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresource
    ADD CONSTRAINT maasserver_bootresource_name_architecture_alias_888a3de7_uniq UNIQUE (name, architecture, alias);


--
-- Name: maasserver_bootresource maasserver_bootresource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresource
    ADD CONSTRAINT maasserver_bootresource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourcefile maasserver_bootresourcef_resource_set_id_filename_9238154e_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresourcef_resource_set_id_filename_9238154e_uniq UNIQUE (resource_set_id, filename);


--
-- Name: maasserver_bootresourcefile maasserver_bootresourcefile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresourcefile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourcefilesync maasserver_bootresourcefilesync_file_id_region_id_c44bfcb9_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefilesync
    ADD CONSTRAINT maasserver_bootresourcefilesync_file_id_region_id_c44bfcb9_uniq UNIQUE (file_id, region_id);


--
-- Name: maasserver_bootresourcefilesync maasserver_bootresourcefilesync_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefilesync
    ADD CONSTRAINT maasserver_bootresourcefilesync_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourceset maasserver_bootresourceset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourceset
    ADD CONSTRAINT maasserver_bootresourceset_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourceset maasserver_bootresourceset_resource_id_version_ec379b98_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourceset
    ADD CONSTRAINT maasserver_bootresourceset_resource_id_version_ec379b98_uniq UNIQUE (resource_id, version);


--
-- Name: maasserver_bootsource maasserver_bootsource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsource
    ADD CONSTRAINT maasserver_bootsource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootsource maasserver_bootsource_url_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsource
    ADD CONSTRAINT maasserver_bootsource_url_key UNIQUE (url);


--
-- Name: maasserver_bootsourcecache maasserver_bootsourcecache_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourcecache
    ADD CONSTRAINT maasserver_bootsourcecache_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootsourceselection maasserver_bootsourcesel_boot_source_id_os_releas_0b0d402c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourcesel_boot_source_id_os_releas_0b0d402c_uniq UNIQUE (boot_source_id, os, release);


--
-- Name: maasserver_bootsourceselection maasserver_bootsourceselection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_pkey PRIMARY KEY (id);


--
-- Name: maasserver_cacheset maasserver_cacheset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_cacheset
    ADD CONSTRAINT maasserver_cacheset_pkey PRIMARY KEY (id);


--
-- Name: maasserver_config maasserver_config_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_config
    ADD CONSTRAINT maasserver_config_name_key UNIQUE (name);


--
-- Name: maasserver_config maasserver_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_config
    ADD CONSTRAINT maasserver_config_pkey PRIMARY KEY (id);


--
-- Name: maasserver_controllerinfo maasserver_controllerinfo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_controllerinfo
    ADD CONSTRAINT maasserver_controllerinfo_pkey PRIMARY KEY (node_id);


--
-- Name: maasserver_defaultresource maasserver_defaultresource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_defaultresource
    ADD CONSTRAINT maasserver_defaultresource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnippet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnippet_pkey PRIMARY KEY (id);


--
-- Name: maasserver_dnsdata maasserver_dnsdata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsdata
    ADD CONSTRAINT maasserver_dnsdata_pkey PRIMARY KEY (id);


--
-- Name: maasserver_dnspublication maasserver_dnspublication_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnspublication
    ADD CONSTRAINT maasserver_dnspublication_pkey PRIMARY KEY (id);


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresource_i_dnsresource_id_staticipa_4ae7b01e_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresource_i_dnsresource_id_staticipa_4ae7b01e_uniq UNIQUE (dnsresource_id, staticipaddress_id);


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresource_ip_addresses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresource_ip_addresses_pkey PRIMARY KEY (id);


--
-- Name: maasserver_dnsresource maasserver_dnsresource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource
    ADD CONSTRAINT maasserver_dnsresource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_domain maasserver_domain_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_domain
    ADD CONSTRAINT maasserver_domain_name_key UNIQUE (name);


--
-- Name: maasserver_domain maasserver_domain_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_domain
    ADD CONSTRAINT maasserver_domain_pkey PRIMARY KEY (id);


--
-- Name: maasserver_event maasserver_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_event
    ADD CONSTRAINT maasserver_event_pkey PRIMARY KEY (id);


--
-- Name: maasserver_eventtype maasserver_eventtype_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_eventtype
    ADD CONSTRAINT maasserver_eventtype_name_key UNIQUE (name);


--
-- Name: maasserver_eventtype maasserver_eventtype_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_eventtype
    ADD CONSTRAINT maasserver_eventtype_pkey PRIMARY KEY (id);


--
-- Name: maasserver_fabric maasserver_fabric_name_3aaa3e4d_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fabric
    ADD CONSTRAINT maasserver_fabric_name_3aaa3e4d_uniq UNIQUE (name);


--
-- Name: maasserver_fabric maasserver_fabric_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fabric
    ADD CONSTRAINT maasserver_fabric_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filestorage maasserver_filestorage_filename_owner_id_2f223d72_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_filename_owner_id_2f223d72_uniq UNIQUE (filename, owner_id);


--
-- Name: maasserver_filestorage maasserver_filestorage_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_key_key UNIQUE (key);


--
-- Name: maasserver_filestorage maasserver_filestorage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filesystem maasserver_filesystem_block_device_id_acquired_3133e691_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_block_device_id_acquired_3133e691_uniq UNIQUE (block_device_id, acquired);


--
-- Name: maasserver_filesystem maasserver_filesystem_partition_id_acquired_5fe51ba7_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_partition_id_acquired_5fe51ba7_uniq UNIQUE (partition_id, acquired);


--
-- Name: maasserver_filesystem maasserver_filesystem_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filesystemgroup maasserver_filesystemgroup_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystemgroup
    ADD CONSTRAINT maasserver_filesystemgroup_pkey PRIMARY KEY (id);


--
-- Name: maasserver_forwarddnsserver_domains maasserver_forwarddnsser_forwarddnsserver_id_doma_1e95b8c5_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver_domains
    ADD CONSTRAINT maasserver_forwarddnsser_forwarddnsserver_id_doma_1e95b8c5_uniq UNIQUE (forwarddnsserver_id, domain_id);


--
-- Name: maasserver_forwarddnsserver_domains maasserver_forwarddnsserver_domains_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver_domains
    ADD CONSTRAINT maasserver_forwarddnsserver_domains_pkey PRIMARY KEY (id);


--
-- Name: maasserver_forwarddnsserver maasserver_forwarddnsserver_ip_address_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver
    ADD CONSTRAINT maasserver_forwarddnsserver_ip_address_key UNIQUE (ip_address);


--
-- Name: maasserver_forwarddnsserver maasserver_forwarddnsserver_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver
    ADD CONSTRAINT maasserver_forwarddnsserver_pkey PRIMARY KEY (id);


--
-- Name: maasserver_globaldefault maasserver_globaldefault_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_globaldefault
    ADD CONSTRAINT maasserver_globaldefault_pkey PRIMARY KEY (id);


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_ip__interface_id_staticipadd_dba63063_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_ip__interface_id_staticipadd_dba63063_uniq UNIQUE (interface_id, staticipaddress_id);


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_ip_addresses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_ip_addresses_pkey PRIMARY KEY (id);


--
-- Name: maasserver_interface maasserver_interface_node_config_id_name_348eea09_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_node_config_id_name_348eea09_uniq UNIQUE (node_config_id, name);


--
-- Name: maasserver_interface maasserver_interface_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_pkey PRIMARY KEY (id);


--
-- Name: maasserver_interfacerelationship maasserver_interfacerelationship_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interfacerelationship
    ADD CONSTRAINT maasserver_interfacerelationship_pkey PRIMARY KEY (id);


--
-- Name: maasserver_iprange maasserver_iprange_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iprange
    ADD CONSTRAINT maasserver_iprange_pkey PRIMARY KEY (id);


--
-- Name: maasserver_keysource maasserver_keysource_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_keysource
    ADD CONSTRAINT maasserver_keysource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_largefile maasserver_largefile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_largefile
    ADD CONSTRAINT maasserver_largefile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_largefile maasserver_largefile_sha256_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_largefile
    ADD CONSTRAINT maasserver_largefile_sha256_key UNIQUE (sha256);


--
-- Name: maasserver_licensekey maasserver_licensekey_osystem_distro_series_cb73fc24_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_licensekey
    ADD CONSTRAINT maasserver_licensekey_osystem_distro_series_cb73fc24_uniq UNIQUE (osystem, distro_series);


--
-- Name: maasserver_licensekey maasserver_licensekey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_licensekey
    ADD CONSTRAINT maasserver_licensekey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_mdns maasserver_mdns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_mdns
    ADD CONSTRAINT maasserver_mdns_pkey PRIMARY KEY (id);


--
-- Name: maasserver_neighbour maasserver_neighbour_interface_id_vid_mac_add_a35f7098_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_neighbour
    ADD CONSTRAINT maasserver_neighbour_interface_id_vid_mac_add_a35f7098_uniq UNIQUE (interface_id, vid, mac_address, ip);


--
-- Name: maasserver_neighbour maasserver_neighbour_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_neighbour
    ADD CONSTRAINT maasserver_neighbour_pkey PRIMARY KEY (id);


--
-- Name: maasserver_node maasserver_node_dns_process_id_22d3b862_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_dns_process_id_22d3b862_uniq UNIQUE (dns_process_id);


--
-- Name: maasserver_node maasserver_node_hardware_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_hardware_uuid_key UNIQUE (hardware_uuid);


--
-- Name: maasserver_node maasserver_node_hostname_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_hostname_key UNIQUE (hostname);


--
-- Name: maasserver_node maasserver_node_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_pkey PRIMARY KEY (id);


--
-- Name: maasserver_node maasserver_node_system_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_system_id_key UNIQUE (system_id);


--
-- Name: maasserver_node_tags maasserver_node_tags_node_id_tag_id_03035248_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_node_id_tag_id_03035248_uniq UNIQUE (node_id, tag_id);


--
-- Name: maasserver_node_tags maasserver_node_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodeconfig maasserver_nodeconfig_node_id_name_44bd083f_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeconfig
    ADD CONSTRAINT maasserver_nodeconfig_node_id_name_44bd083f_uniq UNIQUE (node_id, name);


--
-- Name: maasserver_nodeconfig maasserver_nodeconfig_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeconfig
    ADD CONSTRAINT maasserver_nodeconfig_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodedevice maasserver_nodedevice_node_config_id_bus_numbe_f4934ebf_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_node_config_id_bus_numbe_f4934ebf_uniq UNIQUE (node_config_id, bus_number, device_number, pci_address);


--
-- Name: maasserver_nodedevice maasserver_nodedevice_physical_blockdevice_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_physical_blockdevice_id_key UNIQUE (physical_blockdevice_id);


--
-- Name: maasserver_nodedevice maasserver_nodedevice_physical_interface_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_physical_interface_id_key UNIQUE (physical_interface_id);


--
-- Name: maasserver_nodedevice maasserver_nodedevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodedevicevpd maasserver_nodedevicevpd_node_device_id_key_beaa4c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevicevpd
    ADD CONSTRAINT maasserver_nodedevicevpd_node_device_id_key_beaa4c0c_uniq UNIQUE (node_device_id, key);


--
-- Name: maasserver_nodedevicevpd maasserver_nodedevicevpd_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevicevpd
    ADD CONSTRAINT maasserver_nodedevicevpd_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodegrouptorackcontroller maasserver_nodegrouptorackcontroller_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodegrouptorackcontroller
    ADD CONSTRAINT maasserver_nodegrouptorackcontroller_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodemetadata maasserver_nodemetadata_node_id_key_cbf30be7_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodemetadata
    ADD CONSTRAINT maasserver_nodemetadata_node_id_key_cbf30be7_uniq UNIQUE (node_id, key);


--
-- Name: maasserver_nodemetadata maasserver_nodemetadata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodemetadata
    ADD CONSTRAINT maasserver_nodemetadata_pkey PRIMARY KEY (id);


--
-- Name: maasserver_notification maasserver_notification_ident_d81e5931_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notification
    ADD CONSTRAINT maasserver_notification_ident_d81e5931_uniq UNIQUE (ident);


--
-- Name: maasserver_notification maasserver_notification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notification
    ADD CONSTRAINT maasserver_notification_pkey PRIMARY KEY (id);


--
-- Name: maasserver_notificationdismissal maasserver_notificationdismissal_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal
    ADD CONSTRAINT maasserver_notificationdismissal_pkey PRIMARY KEY (id);


--
-- Name: maasserver_numanode maasserver_numanode_node_id_index_dd400f07_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanode
    ADD CONSTRAINT maasserver_numanode_node_id_index_dd400f07_uniq UNIQUE (node_id, index);


--
-- Name: maasserver_numanode maasserver_numanode_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanode
    ADD CONSTRAINT maasserver_numanode_pkey PRIMARY KEY (id);


--
-- Name: maasserver_numanodehugepages maasserver_numanodehugep_numanode_id_page_size_e5f46837_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanodehugepages
    ADD CONSTRAINT maasserver_numanodehugep_numanode_id_page_size_e5f46837_uniq UNIQUE (numanode_id, page_size);


--
-- Name: maasserver_numanodehugepages maasserver_numanodehugepages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanodehugepages
    ADD CONSTRAINT maasserver_numanodehugepages_pkey PRIMARY KEY (id);


--
-- Name: maasserver_ownerdata maasserver_ownerdata_node_id_key_f0fbcda5_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_ownerdata
    ADD CONSTRAINT maasserver_ownerdata_node_id_key_f0fbcda5_uniq UNIQUE (node_id, key);


--
-- Name: maasserver_ownerdata maasserver_ownerdata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_ownerdata
    ADD CONSTRAINT maasserver_ownerdata_pkey PRIMARY KEY (id);


--
-- Name: maasserver_packagerepository maasserver_packagerepository_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_packagerepository
    ADD CONSTRAINT maasserver_packagerepository_name_key UNIQUE (name);


--
-- Name: maasserver_packagerepository maasserver_packagerepository_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_packagerepository
    ADD CONSTRAINT maasserver_packagerepository_pkey PRIMARY KEY (id);


--
-- Name: maasserver_partition maasserver_partition_partition_table_id_index_281198d5_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition
    ADD CONSTRAINT maasserver_partition_partition_table_id_index_281198d5_uniq UNIQUE (partition_table_id, index);


--
-- Name: maasserver_partition maasserver_partition_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition
    ADD CONSTRAINT maasserver_partition_pkey PRIMARY KEY (id);


--
-- Name: maasserver_partitiontable maasserver_partitiontable_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partitiontable
    ADD CONSTRAINT maasserver_partitiontable_pkey PRIMARY KEY (id);


--
-- Name: maasserver_physicalblockdevice maasserver_physicalblockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_physicalblockdevice
    ADD CONSTRAINT maasserver_physicalblockdevice_pkey PRIMARY KEY (blockdevice_ptr_id);


--
-- Name: maasserver_podhints_nodes maasserver_podhints_nodes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes
    ADD CONSTRAINT maasserver_podhints_nodes_pkey PRIMARY KEY (id);


--
-- Name: maasserver_podhints_nodes maasserver_podhints_nodes_podhints_id_node_id_785b70a7_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes
    ADD CONSTRAINT maasserver_podhints_nodes_podhints_id_node_id_785b70a7_uniq UNIQUE (podhints_id, node_id);


--
-- Name: maasserver_podhints maasserver_podhints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints
    ADD CONSTRAINT maasserver_podhints_pkey PRIMARY KEY (id);


--
-- Name: maasserver_podhints maasserver_podhints_pod_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints
    ADD CONSTRAINT maasserver_podhints_pod_id_key UNIQUE (pod_id);


--
-- Name: maasserver_podstoragepool maasserver_podstoragepool_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podstoragepool
    ADD CONSTRAINT maasserver_podstoragepool_pkey PRIMARY KEY (id);


--
-- Name: maasserver_rbaclastsync maasserver_rbaclastsync_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rbaclastsync
    ADD CONSTRAINT maasserver_rbaclastsync_pkey PRIMARY KEY (id);


--
-- Name: maasserver_rbaclastsync maasserver_rbaclastsync_resource_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rbaclastsync
    ADD CONSTRAINT maasserver_rbaclastsync_resource_type_key UNIQUE (resource_type);


--
-- Name: maasserver_rbacsync maasserver_rbacsync_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rbacsync
    ADD CONSTRAINT maasserver_rbacsync_pkey PRIMARY KEY (id);


--
-- Name: maasserver_rdns maasserver_rdns_ip_observer_id_3f997470_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rdns
    ADD CONSTRAINT maasserver_rdns_ip_observer_id_3f997470_uniq UNIQUE (ip, observer_id);


--
-- Name: maasserver_rdns maasserver_rdns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rdns
    ADD CONSTRAINT maasserver_rdns_pkey PRIMARY KEY (id);


--
-- Name: maasserver_regioncontrollerprocessendpoint maasserver_regioncontrol_process_id_address_port_0f92c07e_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocessendpoint
    ADD CONSTRAINT maasserver_regioncontrol_process_id_address_port_0f92c07e_uniq UNIQUE (process_id, address, port);


--
-- Name: maasserver_regioncontrollerprocess maasserver_regioncontrollerprocess_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocess
    ADD CONSTRAINT maasserver_regioncontrollerprocess_pkey PRIMARY KEY (id);


--
-- Name: maasserver_regioncontrollerprocess maasserver_regioncontrollerprocess_region_id_pid_2a2f2f26_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocess
    ADD CONSTRAINT maasserver_regioncontrollerprocess_region_id_pid_2a2f2f26_uniq UNIQUE (region_id, pid);


--
-- Name: maasserver_regioncontrollerprocessendpoint maasserver_regioncontrollerprocessendpoint_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocessendpoint
    ADD CONSTRAINT maasserver_regioncontrollerprocessendpoint_pkey PRIMARY KEY (id);


--
-- Name: maasserver_regionrackrpcconnection maasserver_regionrackrpc_endpoint_id_rack_control_c0439847_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection
    ADD CONSTRAINT maasserver_regionrackrpc_endpoint_id_rack_control_c0439847_uniq UNIQUE (endpoint_id, rack_controller_id);


--
-- Name: maasserver_regionrackrpcconnection maasserver_regionrackrpcconnection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection
    ADD CONSTRAINT maasserver_regionrackrpcconnection_pkey PRIMARY KEY (id);


--
-- Name: maasserver_resourcepool maasserver_resourcepool_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_resourcepool
    ADD CONSTRAINT maasserver_resourcepool_name_key UNIQUE (name);


--
-- Name: maasserver_resourcepool maasserver_resourcepool_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_resourcepool
    ADD CONSTRAINT maasserver_resourcepool_pkey PRIMARY KEY (id);


--
-- Name: maasserver_rootkey maasserver_rootkey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rootkey
    ADD CONSTRAINT maasserver_rootkey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_secret maasserver_secret_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_secret
    ADD CONSTRAINT maasserver_secret_pkey PRIMARY KEY (path);


--
-- Name: maasserver_service maasserver_service_node_id_name_f13bbbf4_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_service
    ADD CONSTRAINT maasserver_service_node_id_name_f13bbbf4_uniq UNIQUE (node_id, name);


--
-- Name: maasserver_service maasserver_service_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_service
    ADD CONSTRAINT maasserver_service_pkey PRIMARY KEY (id);


--
-- Name: maasserver_space maasserver_space_name_38f1b4f5_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_space
    ADD CONSTRAINT maasserver_space_name_38f1b4f5_uniq UNIQUE (name);


--
-- Name: maasserver_space maasserver_space_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_space
    ADD CONSTRAINT maasserver_space_pkey PRIMARY KEY (id);


--
-- Name: maasserver_sshkey maasserver_sshkey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sshkey
    ADD CONSTRAINT maasserver_sshkey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_sslkey maasserver_sslkey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sslkey
    ADD CONSTRAINT maasserver_sslkey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_sslkey maasserver_sslkey_user_id_key_d4c7960c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sslkey
    ADD CONSTRAINT maasserver_sslkey_user_id_key_d4c7960c_uniq UNIQUE (user_id, key);


--
-- Name: maasserver_staticipaddress maasserver_staticipaddress_alloc_type_ip_8274db4c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipaddress_alloc_type_ip_8274db4c_uniq UNIQUE (alloc_type, ip);


--
-- Name: maasserver_staticipaddress maasserver_staticipaddress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipaddress_pkey PRIMARY KEY (id);


--
-- Name: maasserver_staticroute maasserver_staticroute_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticroute
    ADD CONSTRAINT maasserver_staticroute_pkey PRIMARY KEY (id);


--
-- Name: maasserver_staticroute maasserver_staticroute_source_id_destination_id_e139c5b5_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticroute
    ADD CONSTRAINT maasserver_staticroute_source_id_destination_id_e139c5b5_uniq UNIQUE (source_id, destination_id, gateway_ip);


--
-- Name: maasserver_subnet maasserver_subnet_cidr_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_subnet
    ADD CONSTRAINT maasserver_subnet_cidr_key UNIQUE (cidr);


--
-- Name: maasserver_subnet maasserver_subnet_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_subnet
    ADD CONSTRAINT maasserver_subnet_pkey PRIMARY KEY (id);


--
-- Name: maasserver_tag maasserver_tag_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_tag
    ADD CONSTRAINT maasserver_tag_name_key UNIQUE (name);


--
-- Name: maasserver_tag maasserver_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_tag
    ADD CONSTRAINT maasserver_tag_pkey PRIMARY KEY (id);


--
-- Name: maasserver_template maasserver_template_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template
    ADD CONSTRAINT maasserver_template_filename_key UNIQUE (filename);


--
-- Name: maasserver_template maasserver_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template
    ADD CONSTRAINT maasserver_template_pkey PRIMARY KEY (id);


--
-- Name: maasserver_userprofile maasserver_userprofile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_userprofile maasserver_userprofile_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_user_id_key UNIQUE (user_id);


--
-- Name: maasserver_vaultsecret maasserver_vaultsecret_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vaultsecret
    ADD CONSTRAINT maasserver_vaultsecret_pkey PRIMARY KEY (path);


--
-- Name: maasserver_versionedtextfile maasserver_versionedtextfile_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_versionedtextfile
    ADD CONSTRAINT maasserver_versionedtextfile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_virtualblockdevice maasserver_virtualblockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualblockdevice_pkey PRIMARY KEY (blockdevice_ptr_id);


--
-- Name: maasserver_virtualmachine maasserver_virtualmachin_bmc_id_identifier_projec_29edbd12_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachine
    ADD CONSTRAINT maasserver_virtualmachin_bmc_id_identifier_projec_29edbd12_uniq UNIQUE (bmc_id, identifier, project);


--
-- Name: maasserver_virtualmachine maasserver_virtualmachine_machine_id_22da40a9_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachine
    ADD CONSTRAINT maasserver_virtualmachine_machine_id_22da40a9_uniq UNIQUE (machine_id);


--
-- Name: maasserver_virtualmachine maasserver_virtualmachine_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachine
    ADD CONSTRAINT maasserver_virtualmachine_pkey PRIMARY KEY (id);


--
-- Name: maasserver_virtualmachinedisk maasserver_virtualmachinedisk_block_device_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachinedisk
    ADD CONSTRAINT maasserver_virtualmachinedisk_block_device_id_key UNIQUE (block_device_id);


--
-- Name: maasserver_virtualmachinedisk maasserver_virtualmachinedisk_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachinedisk
    ADD CONSTRAINT maasserver_virtualmachinedisk_pkey PRIMARY KEY (id);


--
-- Name: maasserver_virtualmachineinterface maasserver_virtualmachineinterface_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachineinterface
    ADD CONSTRAINT maasserver_virtualmachineinterface_pkey PRIMARY KEY (id);


--
-- Name: maasserver_vlan maasserver_vlan_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_pkey PRIMARY KEY (id);


--
-- Name: maasserver_vlan maasserver_vlan_vid_fabric_id_881db3fa_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_vid_fabric_id_881db3fa_uniq UNIQUE (vid, fabric_id);


--
-- Name: maasserver_vmcluster maasserver_vmcluster_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vmcluster
    ADD CONSTRAINT maasserver_vmcluster_name_key UNIQUE (name);


--
-- Name: maasserver_vmcluster maasserver_vmcluster_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vmcluster
    ADD CONSTRAINT maasserver_vmcluster_pkey PRIMARY KEY (id);


--
-- Name: maasserver_zone maasserver_zone_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_zone
    ADD CONSTRAINT maasserver_zone_name_key UNIQUE (name);


--
-- Name: maasserver_zone maasserver_zone_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_zone
    ADD CONSTRAINT maasserver_zone_pkey PRIMARY KEY (id);


--
-- Name: maastesting_perftestbuild maastesting_perftestbuild_git_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maastesting_perftestbuild
    ADD CONSTRAINT maastesting_perftestbuild_git_hash_key UNIQUE (git_hash);


--
-- Name: maastesting_perftestbuild maastesting_perftestbuild_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maastesting_perftestbuild
    ADD CONSTRAINT maastesting_perftestbuild_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodekey metadataserver_nodekey_node_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_node_id_key UNIQUE (node_id);


--
-- Name: maasserver_nodekey metadataserver_nodekey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodekey metadataserver_nodekey_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_token_id_key UNIQUE (token_id);


--
-- Name: maasserver_nodeuserdata metadataserver_nodeuserdata_node_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_node_id_key UNIQUE (node_id);


--
-- Name: maasserver_nodeuserdata metadataserver_nodeuserdata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_pkey PRIMARY KEY (id);


--
-- Name: maasserver_script metadataserver_script_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_script
    ADD CONSTRAINT metadataserver_script_name_key UNIQUE (name);


--
-- Name: maasserver_script metadataserver_script_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_script
    ADD CONSTRAINT metadataserver_script_pkey PRIMARY KEY (id);


--
-- Name: maasserver_script metadataserver_script_script_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_script
    ADD CONSTRAINT metadataserver_script_script_id_key UNIQUE (script_id);


--
-- Name: maasserver_scriptresult metadataserver_scriptresult_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT metadataserver_scriptresult_pkey PRIMARY KEY (id);


--
-- Name: maasserver_scriptset metadataserver_scriptset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptset
    ADD CONSTRAINT metadataserver_scriptset_pkey PRIMARY KEY (id);


--
-- Name: piston3_consumer piston3_consumer_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_consumer
    ADD CONSTRAINT piston3_consumer_pkey PRIMARY KEY (id);


--
-- Name: piston3_nonce piston3_nonce_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_nonce
    ADD CONSTRAINT piston3_nonce_pkey PRIMARY KEY (id);


--
-- Name: piston3_nonce piston3_nonce_token_key_consumer_key_key_3f11425b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_nonce
    ADD CONSTRAINT piston3_nonce_token_key_consumer_key_key_3f11425b_uniq UNIQUE (token_key, consumer_key, key);


--
-- Name: piston3_token piston3_token_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token
    ADD CONSTRAINT piston3_token_pkey PRIMARY KEY (id);


--
-- Name: activity_info_maps activity_info_maps_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.activity_info_maps
    ADD CONSTRAINT activity_info_maps_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, schedule_id);


--
-- Name: buffered_events buffered_events_id_key; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.buffered_events
    ADD CONSTRAINT buffered_events_id_key UNIQUE (id);


--
-- Name: buffered_events buffered_events_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.buffered_events
    ADD CONSTRAINT buffered_events_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, id);


--
-- Name: build_id_to_task_queue build_id_to_task_queue_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.build_id_to_task_queue
    ADD CONSTRAINT build_id_to_task_queue_pkey PRIMARY KEY (namespace_id, build_id, task_queue_name);


--
-- Name: child_execution_info_maps child_execution_info_maps_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.child_execution_info_maps
    ADD CONSTRAINT child_execution_info_maps_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, initiated_id);


--
-- Name: cluster_membership cluster_membership_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.cluster_membership
    ADD CONSTRAINT cluster_membership_pkey PRIMARY KEY (membership_partition, host_id);


--
-- Name: cluster_metadata_info cluster_metadata_info_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.cluster_metadata_info
    ADD CONSTRAINT cluster_metadata_info_pkey PRIMARY KEY (metadata_partition, cluster_name);


--
-- Name: cluster_metadata cluster_metadata_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.cluster_metadata
    ADD CONSTRAINT cluster_metadata_pkey PRIMARY KEY (metadata_partition);


--
-- Name: current_executions current_executions_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.current_executions
    ADD CONSTRAINT current_executions_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id);


--
-- Name: executions executions_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.executions
    ADD CONSTRAINT executions_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id);


--
-- Name: history_immediate_tasks history_immediate_tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.history_immediate_tasks
    ADD CONSTRAINT history_immediate_tasks_pkey PRIMARY KEY (shard_id, category_id, task_id);


--
-- Name: history_node history_node_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.history_node
    ADD CONSTRAINT history_node_pkey PRIMARY KEY (shard_id, tree_id, branch_id, node_id, txn_id);


--
-- Name: history_scheduled_tasks history_scheduled_tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.history_scheduled_tasks
    ADD CONSTRAINT history_scheduled_tasks_pkey PRIMARY KEY (shard_id, category_id, visibility_timestamp, task_id);


--
-- Name: history_tree history_tree_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.history_tree
    ADD CONSTRAINT history_tree_pkey PRIMARY KEY (shard_id, tree_id, branch_id);


--
-- Name: namespace_metadata namespace_metadata_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.namespace_metadata
    ADD CONSTRAINT namespace_metadata_pkey PRIMARY KEY (partition_id);


--
-- Name: namespaces namespaces_name_key; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.namespaces
    ADD CONSTRAINT namespaces_name_key UNIQUE (name);


--
-- Name: namespaces namespaces_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.namespaces
    ADD CONSTRAINT namespaces_pkey PRIMARY KEY (partition_id, id);


--
-- Name: queue_metadata queue_metadata_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.queue_metadata
    ADD CONSTRAINT queue_metadata_pkey PRIMARY KEY (queue_type);


--
-- Name: queue queue_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.queue
    ADD CONSTRAINT queue_pkey PRIMARY KEY (queue_type, message_id);


--
-- Name: replication_tasks_dlq replication_tasks_dlq_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.replication_tasks_dlq
    ADD CONSTRAINT replication_tasks_dlq_pkey PRIMARY KEY (source_cluster_name, shard_id, task_id);


--
-- Name: replication_tasks replication_tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.replication_tasks
    ADD CONSTRAINT replication_tasks_pkey PRIMARY KEY (shard_id, task_id);


--
-- Name: request_cancel_info_maps request_cancel_info_maps_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.request_cancel_info_maps
    ADD CONSTRAINT request_cancel_info_maps_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, initiated_id);


--
-- Name: schema_update_history schema_update_history_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.schema_update_history
    ADD CONSTRAINT schema_update_history_pkey PRIMARY KEY (version_partition, year, month, update_time);


--
-- Name: schema_version schema_version_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.schema_version
    ADD CONSTRAINT schema_version_pkey PRIMARY KEY (version_partition, db_name);


--
-- Name: shards shards_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.shards
    ADD CONSTRAINT shards_pkey PRIMARY KEY (shard_id);


--
-- Name: signal_info_maps signal_info_maps_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.signal_info_maps
    ADD CONSTRAINT signal_info_maps_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, initiated_id);


--
-- Name: signals_requested_sets signals_requested_sets_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.signals_requested_sets
    ADD CONSTRAINT signals_requested_sets_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, signal_id);


--
-- Name: task_queue_user_data task_queue_user_data_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.task_queue_user_data
    ADD CONSTRAINT task_queue_user_data_pkey PRIMARY KEY (namespace_id, task_queue_name);


--
-- Name: task_queues task_queues_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.task_queues
    ADD CONSTRAINT task_queues_pkey PRIMARY KEY (range_hash, task_queue_id);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (range_hash, task_queue_id, task_id);


--
-- Name: timer_info_maps timer_info_maps_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.timer_info_maps
    ADD CONSTRAINT timer_info_maps_pkey PRIMARY KEY (shard_id, namespace_id, workflow_id, run_id, timer_id);


--
-- Name: timer_tasks timer_tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.timer_tasks
    ADD CONSTRAINT timer_tasks_pkey PRIMARY KEY (shard_id, visibility_timestamp, task_id);


--
-- Name: transfer_tasks transfer_tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.transfer_tasks
    ADD CONSTRAINT transfer_tasks_pkey PRIMARY KEY (shard_id, task_id);


--
-- Name: visibility_tasks visibility_tasks_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.visibility_tasks
    ADD CONSTRAINT visibility_tasks_pkey PRIMARY KEY (shard_id, task_id);


--
-- Name: executions_visibility executions_visibility_pkey; Type: CONSTRAINT; Schema: temporal_visibility; Owner: -
--

ALTER TABLE ONLY temporal_visibility.executions_visibility
    ADD CONSTRAINT executions_visibility_pkey PRIMARY KEY (namespace_id, run_id);


--
-- Name: schema_update_history schema_update_history_pkey; Type: CONSTRAINT; Schema: temporal_visibility; Owner: -
--

ALTER TABLE ONLY temporal_visibility.schema_update_history
    ADD CONSTRAINT schema_update_history_pkey PRIMARY KEY (version_partition, year, month, update_time);


--
-- Name: schema_version schema_version_pkey; Type: CONSTRAINT; Schema: temporal_visibility; Owner: -
--

ALTER TABLE ONLY temporal_visibility.schema_version
    ADD CONSTRAINT schema_version_pkey PRIMARY KEY (version_partition, db_name);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: auth_user_email_1c89df09_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_email_1c89df09_like ON public.auth_user USING btree (email varchar_pattern_ops);


--
-- Name: auth_user_groups_group_id_97559544; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_groups_group_id_97559544 ON public.auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id_6a12ed8b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_groups_user_id_6a12ed8b ON public.auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id_1fbb5f2c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_user_permissions_permission_id_1fbb5f2c ON public.auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id_a95ead1b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_user_permissions_user_id_a95ead1b ON public.auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_6821ab7c_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_user_username_6821ab7c_like ON public.auth_user USING btree (username varchar_pattern_ops);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: django_site_domain_a2e37b91_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX django_site_domain_a2e37b91_like ON public.django_site USING btree (domain varchar_pattern_ops);


--
-- Name: maasserver__key_ecce38_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver__key_ecce38_idx ON public.maasserver_nodedevicevpd USING btree (key, value);


--
-- Name: maasserver__node_id_e4a8dd_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver__node_id_e4a8dd_idx ON public.maasserver_event USING btree (node_id, created DESC, id DESC);


--
-- Name: maasserver__power_p_511df2_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver__power_p_511df2_hash ON public.maasserver_bmc USING hash (power_parameters);


--
-- Name: maasserver__sha256_f07a8e_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver__sha256_f07a8e_idx ON public.maasserver_bootresourcefile USING btree (sha256);


--
-- Name: maasserver_blockdevice_node_config_id_5b310b67; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_blockdevice_node_config_id_5b310b67 ON public.maasserver_blockdevice USING btree (node_config_id);


--
-- Name: maasserver_bmc_default_pool_id_848e4429; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_default_pool_id_848e4429 ON public.maasserver_bmc USING btree (pool_id);


--
-- Name: maasserver_bmc_default_storage_pool_id_5f48762b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_default_storage_pool_id_5f48762b ON public.maasserver_bmc USING btree (default_storage_pool_id);


--
-- Name: maasserver_bmc_ip_address_id_79362d14; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_ip_address_id_79362d14 ON public.maasserver_bmc USING btree (ip_address_id);


--
-- Name: maasserver_bmc_power_type_93755dda; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_power_type_93755dda ON public.maasserver_bmc USING btree (power_type);


--
-- Name: maasserver_bmc_power_type_93755dda_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_power_type_93755dda_like ON public.maasserver_bmc USING btree (power_type varchar_pattern_ops);


--
-- Name: maasserver_bmc_power_type_parameters_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_bmc_power_type_parameters_idx ON public.maasserver_bmc USING btree (power_type, md5((power_parameters)::text)) WHERE ((power_type)::text <> 'manual'::text);


--
-- Name: maasserver_bmc_zone_id_774ea0de; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_zone_id_774ea0de ON public.maasserver_bmc USING btree (zone_id);


--
-- Name: maasserver_bmcroutablerack_bmc_id_27dedd10; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmcroutablerack_bmc_id_27dedd10 ON public.maasserver_bmcroutablerackcontrollerrelationship USING btree (bmc_id);


--
-- Name: maasserver_bmcroutablerack_rack_controller_id_1a3ffa6e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmcroutablerack_rack_controller_id_1a3ffa6e ON public.maasserver_bmcroutablerackcontrollerrelationship USING btree (rack_controller_id);


--
-- Name: maasserver_bootresourcefile_largefile_id_cf035187; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootresourcefile_largefile_id_cf035187 ON public.maasserver_bootresourcefile USING btree (largefile_id);


--
-- Name: maasserver_bootresourcefile_resource_set_id_2fd093ab; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootresourcefile_resource_set_id_2fd093ab ON public.maasserver_bootresourcefile USING btree (resource_set_id);


--
-- Name: maasserver_bootresourcefilesync_file_id_22508d9b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootresourcefilesync_file_id_22508d9b ON public.maasserver_bootresourcefilesync USING btree (file_id);


--
-- Name: maasserver_bootresourcefilesync_region_id_b11e2230; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootresourcefilesync_region_id_b11e2230 ON public.maasserver_bootresourcefilesync USING btree (region_id);


--
-- Name: maasserver_bootresourceset_resource_id_c320a639; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootresourceset_resource_id_c320a639 ON public.maasserver_bootresourceset USING btree (resource_id);


--
-- Name: maasserver_bootsource_url_54c78ba3_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootsource_url_54c78ba3_like ON public.maasserver_bootsource USING btree (url varchar_pattern_ops);


--
-- Name: maasserver_bootsourcecache_boot_source_id_73abe4d2; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootsourcecache_boot_source_id_73abe4d2 ON public.maasserver_bootsourcecache USING btree (boot_source_id);


--
-- Name: maasserver_bootsourceselection_boot_source_id_b911aa0f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bootsourceselection_boot_source_id_b911aa0f ON public.maasserver_bootsourceselection USING btree (boot_source_id);


--
-- Name: maasserver_config_name_ad989064_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_config_name_ad989064_like ON public.maasserver_config USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_defaultresource_zone_id_29a5153a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_defaultresource_zone_id_29a5153a ON public.maasserver_defaultresource USING btree (zone_id);


--
-- Name: maasserver_dhcpsnippet_iprange_id_6a257e4d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dhcpsnippet_iprange_id_6a257e4d ON public.maasserver_dhcpsnippet USING btree (iprange_id);


--
-- Name: maasserver_dhcpsnippet_node_id_8f31c564; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dhcpsnippet_node_id_8f31c564 ON public.maasserver_dhcpsnippet USING btree (node_id);


--
-- Name: maasserver_dhcpsnippet_subnet_id_f626b848; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dhcpsnippet_subnet_id_f626b848 ON public.maasserver_dhcpsnippet USING btree (subnet_id);


--
-- Name: maasserver_dhcpsnippet_value_id_58a6a467; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dhcpsnippet_value_id_58a6a467 ON public.maasserver_dhcpsnippet USING btree (value_id);


--
-- Name: maasserver_dnsdata_dnsresource_id_9a9b5788; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dnsdata_dnsresource_id_9a9b5788 ON public.maasserver_dnsdata USING btree (dnsresource_id);


--
-- Name: maasserver_dnsresource_domain_id_c5abb245; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dnsresource_domain_id_c5abb245 ON public.maasserver_dnsresource USING btree (domain_id);


--
-- Name: maasserver_dnsresource_ip_addresses_dnsresource_id_49f1115e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dnsresource_ip_addresses_dnsresource_id_49f1115e ON public.maasserver_dnsresource_ip_addresses USING btree (dnsresource_id);


--
-- Name: maasserver_dnsresource_ip_addresses_staticipaddress_id_794f210e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_dnsresource_ip_addresses_staticipaddress_id_794f210e ON public.maasserver_dnsresource_ip_addresses USING btree (staticipaddress_id);


--
-- Name: maasserver_domain_authoritative_1d49b1f6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_domain_authoritative_1d49b1f6 ON public.maasserver_domain USING btree (authoritative);


--
-- Name: maasserver_domain_name_4267a38e_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_domain_name_4267a38e_like ON public.maasserver_domain USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_event__created; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_event__created ON public.maasserver_event USING btree (created);


--
-- Name: maasserver_event_node_id_dd4495a7; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_event_node_id_dd4495a7 ON public.maasserver_event USING btree (node_id);


--
-- Name: maasserver_event_node_id_id_a62e1358_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_event_node_id_id_a62e1358_idx ON public.maasserver_event USING btree (node_id, id);


--
-- Name: maasserver_event_type_id_702a532f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_event_type_id_702a532f ON public.maasserver_event USING btree (type_id);


--
-- Name: maasserver_eventtype_level_468acd98; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_eventtype_level_468acd98 ON public.maasserver_eventtype USING btree (level);


--
-- Name: maasserver_eventtype_name_49878f67_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_eventtype_name_49878f67_like ON public.maasserver_eventtype USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_fabric_name_3aaa3e4d_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_fabric_name_3aaa3e4d_like ON public.maasserver_fabric USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_filestorage_key_4458fcee_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filestorage_key_4458fcee_like ON public.maasserver_filestorage USING btree (key varchar_pattern_ops);


--
-- Name: maasserver_filestorage_owner_id_24d47e43; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filestorage_owner_id_24d47e43 ON public.maasserver_filestorage USING btree (owner_id);


--
-- Name: maasserver_filesystem_block_device_id_5d3ba742; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_block_device_id_5d3ba742 ON public.maasserver_filesystem USING btree (block_device_id);


--
-- Name: maasserver_filesystem_cache_set_id_f87650ce; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_cache_set_id_f87650ce ON public.maasserver_filesystem USING btree (cache_set_id);


--
-- Name: maasserver_filesystem_filesystem_group_id_9bc05fe7; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_filesystem_group_id_9bc05fe7 ON public.maasserver_filesystem USING btree (filesystem_group_id);


--
-- Name: maasserver_filesystem_node_config_id_741ff095; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_node_config_id_741ff095 ON public.maasserver_filesystem USING btree (node_config_id);


--
-- Name: maasserver_filesystem_partition_id_6174cd8b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_partition_id_6174cd8b ON public.maasserver_filesystem USING btree (partition_id);


--
-- Name: maasserver_filesystemgroup_cache_set_id_608e115e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystemgroup_cache_set_id_608e115e ON public.maasserver_filesystemgroup USING btree (cache_set_id);


--
-- Name: maasserver_forwarddnsserve_forwarddnsserver_id_c975e5df; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_forwarddnsserve_forwarddnsserver_id_c975e5df ON public.maasserver_forwarddnsserver_domains USING btree (forwarddnsserver_id);


--
-- Name: maasserver_forwarddnsserver_domains_domain_id_02e252ac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_forwarddnsserver_domains_domain_id_02e252ac ON public.maasserver_forwarddnsserver_domains USING btree (domain_id);


--
-- Name: maasserver_globaldefault_domain_id_11c3ee74; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_globaldefault_domain_id_11c3ee74 ON public.maasserver_globaldefault USING btree (domain_id);


--
-- Name: maasserver_interface_ip_addresses_interface_id_d3d873df; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interface_ip_addresses_interface_id_d3d873df ON public.maasserver_interface_ip_addresses USING btree (interface_id);


--
-- Name: maasserver_interface_ip_addresses_staticipaddress_id_5fa63951; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interface_ip_addresses_staticipaddress_id_5fa63951 ON public.maasserver_interface_ip_addresses USING btree (staticipaddress_id);


--
-- Name: maasserver_interface_node_config_id_a52b0f8a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interface_node_config_id_a52b0f8a ON public.maasserver_interface USING btree (node_config_id);


--
-- Name: maasserver_interface_node_config_mac_address_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_interface_node_config_mac_address_uniq ON public.maasserver_interface USING btree (node_config_id, mac_address) WHERE ((type)::text = 'physical'::text);


--
-- Name: maasserver_interface_numa_node_id_6e790407; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interface_numa_node_id_6e790407 ON public.maasserver_interface USING btree (numa_node_id);


--
-- Name: maasserver_interface_vlan_id_5f39995d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interface_vlan_id_5f39995d ON public.maasserver_interface USING btree (vlan_id);


--
-- Name: maasserver_interfacerelationship_child_id_7be5401e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interfacerelationship_child_id_7be5401e ON public.maasserver_interfacerelationship USING btree (child_id);


--
-- Name: maasserver_interfacerelationship_parent_id_d3c77c37; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interfacerelationship_parent_id_d3c77c37 ON public.maasserver_interfacerelationship USING btree (parent_id);


--
-- Name: maasserver_iprange_subnet_id_de83b8f1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_iprange_subnet_id_de83b8f1 ON public.maasserver_iprange USING btree (subnet_id);


--
-- Name: maasserver_iprange_user_id_5d0f7718; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_iprange_user_id_5d0f7718 ON public.maasserver_iprange USING btree (user_id);


--
-- Name: maasserver_largefile_sha256_40052db0_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_largefile_sha256_40052db0_like ON public.maasserver_largefile USING btree (sha256 varchar_pattern_ops);


--
-- Name: maasserver_mdns_interface_id_ef297041; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_mdns_interface_id_ef297041 ON public.maasserver_mdns USING btree (interface_id);


--
-- Name: maasserver_neighbour_interface_id_dd458d65; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_neighbour_interface_id_dd458d65 ON public.maasserver_neighbour USING btree (interface_id);


--
-- Name: maasserver_node_bmc_id_a2d33e12; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_bmc_id_a2d33e12 ON public.maasserver_node USING btree (bmc_id);


--
-- Name: maasserver_node_boot_disk_id_db8131e9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_boot_disk_id_db8131e9 ON public.maasserver_node USING btree (boot_disk_id);


--
-- Name: maasserver_node_boot_interface_id_fad48090; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_boot_interface_id_fad48090 ON public.maasserver_node USING btree (boot_interface_id);


--
-- Name: maasserver_node_current_commissioning_script_set_id_9ae2ec39; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_commissioning_script_set_id_9ae2ec39 ON public.maasserver_node USING btree (current_commissioning_script_set_id);


--
-- Name: maasserver_node_current_config_id_d9cbacad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_config_id_d9cbacad ON public.maasserver_node USING btree (current_config_id);


--
-- Name: maasserver_node_current_installation_script_set_id_a6e40738; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_installation_script_set_id_a6e40738 ON public.maasserver_node USING btree (current_installation_script_set_id);


--
-- Name: maasserver_node_current_release_script_set_id_1c3d13f5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_release_script_set_id_1c3d13f5 ON public.maasserver_node USING btree (current_release_script_set_id);


--
-- Name: maasserver_node_current_testing_script_set_id_4636f4f9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_testing_script_set_id_4636f4f9 ON public.maasserver_node USING btree (current_testing_script_set_id);


--
-- Name: maasserver_node_domain_id_7b592cbf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_domain_id_7b592cbf ON public.maasserver_node USING btree (domain_id);


--
-- Name: maasserver_node_gateway_link_ipv4_id_620a3c36; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_gateway_link_ipv4_id_620a3c36 ON public.maasserver_node USING btree (gateway_link_ipv4_id);


--
-- Name: maasserver_node_gateway_link_ipv6_id_b8542fea; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_gateway_link_ipv6_id_b8542fea ON public.maasserver_node USING btree (gateway_link_ipv6_id);


--
-- Name: maasserver_node_hardware_uuid_6b491c84_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_hardware_uuid_6b491c84_like ON public.maasserver_node USING btree (hardware_uuid varchar_pattern_ops);


--
-- Name: maasserver_node_hostname_23fbebec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_hostname_23fbebec_like ON public.maasserver_node USING btree (hostname varchar_pattern_ops);


--
-- Name: maasserver_node_managing_process_id_0f9f8640; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_managing_process_id_0f9f8640 ON public.maasserver_node USING btree (managing_process_id);


--
-- Name: maasserver_node_owner_id_455bec7f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_owner_id_455bec7f ON public.maasserver_node USING btree (owner_id);


--
-- Name: maasserver_node_parent_id_d0ac1fac; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_parent_id_d0ac1fac ON public.maasserver_node USING btree (parent_id);


--
-- Name: maasserver_node_pool_id_42cdfac9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_pool_id_42cdfac9 ON public.maasserver_node USING btree (pool_id);


--
-- Name: maasserver_node_system_id_b9f4e3e8_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_system_id_b9f4e3e8_like ON public.maasserver_node USING btree (system_id varchar_pattern_ops);


--
-- Name: maasserver_node_tags_node_id_a662a9f1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_tags_node_id_a662a9f1 ON public.maasserver_node_tags USING btree (node_id);


--
-- Name: maasserver_node_tags_tag_id_f4728372; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_tags_tag_id_f4728372 ON public.maasserver_node_tags USING btree (tag_id);


--
-- Name: maasserver_node_zone_id_97213f69; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_zone_id_97213f69 ON public.maasserver_node USING btree (zone_id);


--
-- Name: maasserver_nodeconfig_node_id_c9235109; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodeconfig_node_id_c9235109 ON public.maasserver_nodeconfig USING btree (node_id);


--
-- Name: maasserver_nodedevice_node_config_id_3f91f0a0; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodedevice_node_config_id_3f91f0a0 ON public.maasserver_nodedevice USING btree (node_config_id);


--
-- Name: maasserver_nodedevice_numa_node_id_fadf5b46; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodedevice_numa_node_id_fadf5b46 ON public.maasserver_nodedevice USING btree (numa_node_id);


--
-- Name: maasserver_nodedevicevpd_node_device_id_9c998e15; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodedevicevpd_node_device_id_9c998e15 ON public.maasserver_nodedevicevpd USING btree (node_device_id);


--
-- Name: maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b ON public.maasserver_nodegrouptorackcontroller USING btree (subnet_id);


--
-- Name: maasserver_nodemetadata_node_id_4350cc04; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodemetadata_node_id_4350cc04 ON public.maasserver_nodemetadata USING btree (node_id);


--
-- Name: maasserver_notification_ident_d81e5931_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_notification_ident_d81e5931_like ON public.maasserver_notification USING btree (ident varchar_pattern_ops);


--
-- Name: maasserver_notification_user_id_5a4d1d18; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_notification_user_id_5a4d1d18 ON public.maasserver_notification USING btree (user_id);


--
-- Name: maasserver_notificationdismissal_notification_id_fe4f68d4; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_notificationdismissal_notification_id_fe4f68d4 ON public.maasserver_notificationdismissal USING btree (notification_id);


--
-- Name: maasserver_notificationdismissal_user_id_87cc11da; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_notificationdismissal_user_id_87cc11da ON public.maasserver_notificationdismissal USING btree (user_id);


--
-- Name: maasserver_numanode_node_id_539a7e2f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_numanode_node_id_539a7e2f ON public.maasserver_numanode USING btree (node_id);


--
-- Name: maasserver_numanodehugepages_numanode_id_0f0542f0; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_numanodehugepages_numanode_id_0f0542f0 ON public.maasserver_numanodehugepages USING btree (numanode_id);


--
-- Name: maasserver_ownerdata_node_id_4ec53011; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_ownerdata_node_id_4ec53011 ON public.maasserver_ownerdata USING btree (node_id);


--
-- Name: maasserver_packagerepository_name_ae83c436_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_packagerepository_name_ae83c436_like ON public.maasserver_packagerepository USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_partition_partition_table_id_c94faed6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_partition_partition_table_id_c94faed6 ON public.maasserver_partition USING btree (partition_table_id);


--
-- Name: maasserver_partitiontable_block_device_id_ee132cc5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_partitiontable_block_device_id_ee132cc5 ON public.maasserver_partitiontable USING btree (block_device_id);


--
-- Name: maasserver_physicalblockdevice_numa_node_id_8bd61f48; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_physicalblockdevice_numa_node_id_8bd61f48 ON public.maasserver_physicalblockdevice USING btree (numa_node_id);


--
-- Name: maasserver_podhints_cluster_id_b526f79f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_podhints_cluster_id_b526f79f ON public.maasserver_podhints USING btree (cluster_id);


--
-- Name: maasserver_podhints_nodes_node_id_7e2e56a4; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_podhints_nodes_node_id_7e2e56a4 ON public.maasserver_podhints_nodes USING btree (node_id);


--
-- Name: maasserver_podhints_nodes_podhints_id_df1bafb3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_podhints_nodes_podhints_id_df1bafb3 ON public.maasserver_podhints_nodes USING btree (podhints_id);


--
-- Name: maasserver_podstoragepool_pod_id_11db94aa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_podstoragepool_pod_id_11db94aa ON public.maasserver_podstoragepool USING btree (pod_id);


--
-- Name: maasserver_rbaclastsync_resource_type_fb031e5a_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_rbaclastsync_resource_type_fb031e5a_like ON public.maasserver_rbaclastsync USING btree (resource_type varchar_pattern_ops);


--
-- Name: maasserver_rdns_observer_id_85a64c6b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_rdns_observer_id_85a64c6b ON public.maasserver_rdns USING btree (observer_id);


--
-- Name: maasserver_regioncontrollerprocess_region_id_ee210efa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_regioncontrollerprocess_region_id_ee210efa ON public.maasserver_regioncontrollerprocess USING btree (region_id);


--
-- Name: maasserver_regioncontrollerprocessendpoint_process_id_2bf84625; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_regioncontrollerprocessendpoint_process_id_2bf84625 ON public.maasserver_regioncontrollerprocessendpoint USING btree (process_id);


--
-- Name: maasserver_regionrackrpcconnection_endpoint_id_9e6814b4; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_regionrackrpcconnection_endpoint_id_9e6814b4 ON public.maasserver_regionrackrpcconnection USING btree (endpoint_id);


--
-- Name: maasserver_regionrackrpcconnection_rack_controller_id_7f5b60af; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_regionrackrpcconnection_rack_controller_id_7f5b60af ON public.maasserver_regionrackrpcconnection USING btree (rack_controller_id);


--
-- Name: maasserver_resourcepool_name_dc5d41eb_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_resourcepool_name_dc5d41eb_like ON public.maasserver_resourcepool USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_secret_path_1e974fd1_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_secret_path_1e974fd1_like ON public.maasserver_secret USING btree (path text_pattern_ops);


--
-- Name: maasserver_service_node_id_891637d4; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_service_node_id_891637d4 ON public.maasserver_service USING btree (node_id);


--
-- Name: maasserver_space_name_38f1b4f5_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_space_name_38f1b4f5_like ON public.maasserver_space USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_sshkey_keysource_id_701e0769; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_sshkey_keysource_id_701e0769 ON public.maasserver_sshkey USING btree (keysource_id);


--
-- Name: maasserver_sshkey_user_id_84b68559; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_sshkey_user_id_84b68559 ON public.maasserver_sshkey USING btree (user_id);


--
-- Name: maasserver_sslkey_user_id_d871db8c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_sslkey_user_id_d871db8c ON public.maasserver_sslkey USING btree (user_id);


--
-- Name: maasserver_staticipaddress__ip_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticipaddress__ip_family ON public.maasserver_staticipaddress USING btree (family(ip));


--
-- Name: maasserver_staticipaddress_discovered_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_staticipaddress_discovered_uniq ON public.maasserver_staticipaddress USING btree (ip) WHERE (NOT (alloc_type = 6));


--
-- Name: maasserver_staticipaddress_subnet_id_b30d84c3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticipaddress_subnet_id_b30d84c3 ON public.maasserver_staticipaddress USING btree (subnet_id);


--
-- Name: maasserver_staticipaddress_temp_expires_on_1cb8532a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticipaddress_temp_expires_on_1cb8532a ON public.maasserver_staticipaddress USING btree (temp_expires_on);


--
-- Name: maasserver_staticipaddress_user_id_a7e5e455; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticipaddress_user_id_a7e5e455 ON public.maasserver_staticipaddress USING btree (user_id);


--
-- Name: maasserver_staticroute_destination_id_4d1b294b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticroute_destination_id_4d1b294b ON public.maasserver_staticroute USING btree (destination_id);


--
-- Name: maasserver_staticroute_source_id_3321277a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticroute_source_id_3321277a ON public.maasserver_staticroute USING btree (source_id);


--
-- Name: maasserver_subnet_vlan_id_d4e96e9a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_subnet_vlan_id_d4e96e9a ON public.maasserver_subnet USING btree (vlan_id);


--
-- Name: maasserver_tag_name_7bda8c06_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_tag_name_7bda8c06_like ON public.maasserver_tag USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_template_default_version_id_10647fcf; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_template_default_version_id_10647fcf ON public.maasserver_template USING btree (default_version_id);


--
-- Name: maasserver_template_filename_aba74d61_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_template_filename_aba74d61_like ON public.maasserver_template USING btree (filename varchar_pattern_ops);


--
-- Name: maasserver_template_version_id_78c8754e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_template_version_id_78c8754e ON public.maasserver_template USING btree (version_id);


--
-- Name: maasserver_vaultsecret_path_4127e219_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vaultsecret_path_4127e219_like ON public.maasserver_vaultsecret USING btree (path text_pattern_ops);


--
-- Name: maasserver_versionedtextfile_previous_version_id_8c3734e6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_versionedtextfile_previous_version_id_8c3734e6 ON public.maasserver_versionedtextfile USING btree (previous_version_id);


--
-- Name: maasserver_virtualblockdevice_filesystem_group_id_405a7fc4; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualblockdevice_filesystem_group_id_405a7fc4 ON public.maasserver_virtualblockdevice USING btree (filesystem_group_id);


--
-- Name: maasserver_virtualmachine_bmc_id_e2b4f381; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualmachine_bmc_id_e2b4f381 ON public.maasserver_virtualmachine USING btree (bmc_id);


--
-- Name: maasserver_virtualmachinedisk_backing_pool_id_2fe2f82c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualmachinedisk_backing_pool_id_2fe2f82c ON public.maasserver_virtualmachinedisk USING btree (backing_pool_id);


--
-- Name: maasserver_virtualmachinedisk_bdev_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_virtualmachinedisk_bdev_uniq ON public.maasserver_virtualmachinedisk USING btree (vm_id, name, block_device_id) WHERE (block_device_id IS NOT NULL);


--
-- Name: maasserver_virtualmachinedisk_no_bdev_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_virtualmachinedisk_no_bdev_uniq ON public.maasserver_virtualmachinedisk USING btree (vm_id, name) WHERE (block_device_id IS NULL);


--
-- Name: maasserver_virtualmachinedisk_vm_id_a5308b7c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualmachinedisk_vm_id_a5308b7c ON public.maasserver_virtualmachinedisk USING btree (vm_id);


--
-- Name: maasserver_virtualmachineinterface_host_interface_id_9408be99; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualmachineinterface_host_interface_id_9408be99 ON public.maasserver_virtualmachineinterface USING btree (host_interface_id);


--
-- Name: maasserver_virtualmachineinterface_iface_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_virtualmachineinterface_iface_uniq ON public.maasserver_virtualmachineinterface USING btree (vm_id, mac_address, host_interface_id) WHERE (host_interface_id IS NOT NULL);


--
-- Name: maasserver_virtualmachineinterface_no_iface_uniq; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_virtualmachineinterface_no_iface_uniq ON public.maasserver_virtualmachineinterface USING btree (vm_id, mac_address) WHERE (host_interface_id IS NULL);


--
-- Name: maasserver_virtualmachineinterface_vm_id_a6acb3e9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualmachineinterface_vm_id_a6acb3e9 ON public.maasserver_virtualmachineinterface USING btree (vm_id);


--
-- Name: maasserver_vlan_fabric_id_af5275c8; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vlan_fabric_id_af5275c8 ON public.maasserver_vlan USING btree (fabric_id);


--
-- Name: maasserver_vlan_primary_rack_id_016c2af3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vlan_primary_rack_id_016c2af3 ON public.maasserver_vlan USING btree (primary_rack_id);


--
-- Name: maasserver_vlan_relay_vlan_id_c026b672; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vlan_relay_vlan_id_c026b672 ON public.maasserver_vlan USING btree (relay_vlan_id);


--
-- Name: maasserver_vlan_secondary_rack_id_3b97d19a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vlan_secondary_rack_id_3b97d19a ON public.maasserver_vlan USING btree (secondary_rack_id);


--
-- Name: maasserver_vlan_space_id_5e1dc51f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vlan_space_id_5e1dc51f ON public.maasserver_vlan USING btree (space_id);


--
-- Name: maasserver_vmcluster_name_dbc3c69c_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vmcluster_name_dbc3c69c_like ON public.maasserver_vmcluster USING btree (name text_pattern_ops);


--
-- Name: maasserver_vmcluster_pool_id_aad02386; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vmcluster_pool_id_aad02386 ON public.maasserver_vmcluster USING btree (pool_id);


--
-- Name: maasserver_vmcluster_zone_id_07623572; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_vmcluster_zone_id_07623572 ON public.maasserver_vmcluster USING btree (zone_id);


--
-- Name: maasserver_zone_name_a0aef207_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_zone_name_a0aef207_like ON public.maasserver_zone USING btree (name varchar_pattern_ops);


--
-- Name: maastesting_perftestbuild_git_hash_07335de3_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maastesting_perftestbuild_git_hash_07335de3_like ON public.maastesting_perftestbuild USING btree (git_hash text_pattern_ops);


--
-- Name: metadataserver_script_name_b2be1ba5_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_script_name_b2be1ba5_like ON public.maasserver_script USING btree (name varchar_pattern_ops);


--
-- Name: metadataserver_scriptresult_interface_id_a120e25e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_interface_id_a120e25e ON public.maasserver_scriptresult USING btree (interface_id);


--
-- Name: metadataserver_scriptresult_physical_blockdevice_id_c728b2ad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_physical_blockdevice_id_c728b2ad ON public.maasserver_scriptresult USING btree (physical_blockdevice_id);


--
-- Name: metadataserver_scriptresult_script_id_c5ff7318; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_script_id_c5ff7318 ON public.maasserver_scriptresult USING btree (script_id);


--
-- Name: metadataserver_scriptresult_script_set_id_625a037b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_script_set_id_625a037b ON public.maasserver_scriptresult USING btree (script_set_id);


--
-- Name: metadataserver_scriptresult_script_version_id_932ffdd1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_script_version_id_932ffdd1 ON public.maasserver_scriptresult USING btree (script_version_id);


--
-- Name: metadataserver_scriptset_node_id_72b6537b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptset_node_id_72b6537b ON public.maasserver_scriptset USING btree (node_id);


--
-- Name: name-unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX "name-unique" ON public.maasserver_bmc USING btree (name) WHERE ((power_parameters #> ARRAY['project'::text, 'exists'::text]) = 'false'::jsonb);


--
-- Name: piston3_consumer_user_id_ede69093; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX piston3_consumer_user_id_ede69093 ON public.piston3_consumer USING btree (user_id);


--
-- Name: piston3_token_consumer_id_b178993d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX piston3_token_consumer_id_b178993d ON public.piston3_token USING btree (consumer_id);


--
-- Name: piston3_token_user_id_e5cd818c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX piston3_token_user_id_e5cd818c ON public.piston3_token USING btree (user_id);


--
-- Name: cm_idx_lasthb; Type: INDEX; Schema: temporal; Owner: -
--

CREATE INDEX cm_idx_lasthb ON temporal.cluster_membership USING btree (last_heartbeat);


--
-- Name: cm_idx_recordexpiry; Type: INDEX; Schema: temporal; Owner: -
--

CREATE INDEX cm_idx_recordexpiry ON temporal.cluster_membership USING btree (record_expiry);


--
-- Name: cm_idx_rolehost; Type: INDEX; Schema: temporal; Owner: -
--

CREATE UNIQUE INDEX cm_idx_rolehost ON temporal.cluster_membership USING btree (role, host_id);


--
-- Name: cm_idx_rolelasthb; Type: INDEX; Schema: temporal; Owner: -
--

CREATE INDEX cm_idx_rolelasthb ON temporal.cluster_membership USING btree (role, last_heartbeat);


--
-- Name: cm_idx_rpchost; Type: INDEX; Schema: temporal; Owner: -
--

CREATE INDEX cm_idx_rpchost ON temporal.cluster_membership USING btree (rpc_address, role);


--
-- Name: by_batcher_user; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_batcher_user ON temporal_visibility.executions_visibility USING btree (namespace_id, batcheruser, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_binary_checksums; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_binary_checksums ON temporal_visibility.executions_visibility USING gin (namespace_id, binarychecksums jsonb_path_ops);


--
-- Name: by_bool_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_bool_01 ON temporal_visibility.executions_visibility USING btree (namespace_id, bool01, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_bool_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_bool_02 ON temporal_visibility.executions_visibility USING btree (namespace_id, bool02, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_bool_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_bool_03 ON temporal_visibility.executions_visibility USING btree (namespace_id, bool03, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_build_ids; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_build_ids ON temporal_visibility.executions_visibility USING gin (namespace_id, buildids jsonb_path_ops);


--
-- Name: by_datetime_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_datetime_01 ON temporal_visibility.executions_visibility USING btree (namespace_id, datetime01, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_datetime_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_datetime_02 ON temporal_visibility.executions_visibility USING btree (namespace_id, datetime02, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_datetime_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_datetime_03 ON temporal_visibility.executions_visibility USING btree (namespace_id, datetime03, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_double_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_double_01 ON temporal_visibility.executions_visibility USING btree (namespace_id, double01, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_double_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_double_02 ON temporal_visibility.executions_visibility USING btree (namespace_id, double02, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_double_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_double_03 ON temporal_visibility.executions_visibility USING btree (namespace_id, double03, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_execution_time; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_execution_time ON temporal_visibility.executions_visibility USING btree (namespace_id, execution_time, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_history_length; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_history_length ON temporal_visibility.executions_visibility USING btree (namespace_id, history_length, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_history_size_bytes; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_history_size_bytes ON temporal_visibility.executions_visibility USING btree (namespace_id, history_size_bytes, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_int_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_int_01 ON temporal_visibility.executions_visibility USING btree (namespace_id, int01, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_int_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_int_02 ON temporal_visibility.executions_visibility USING btree (namespace_id, int02, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_int_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_int_03 ON temporal_visibility.executions_visibility USING btree (namespace_id, int03, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_01 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword01, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_02 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword02, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_03 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword03, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_04; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_04 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword04, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_05; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_05 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword05, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_06; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_06 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword06, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_07; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_07 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword07, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_08; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_08 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword08, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_09; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_09 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword09, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_10; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_10 ON temporal_visibility.executions_visibility USING btree (namespace_id, keyword10, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_keyword_list_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_list_01 ON temporal_visibility.executions_visibility USING gin (namespace_id, keywordlist01 jsonb_path_ops);


--
-- Name: by_keyword_list_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_list_02 ON temporal_visibility.executions_visibility USING gin (namespace_id, keywordlist02 jsonb_path_ops);


--
-- Name: by_keyword_list_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_keyword_list_03 ON temporal_visibility.executions_visibility USING gin (namespace_id, keywordlist03 jsonb_path_ops);


--
-- Name: by_status; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_status ON temporal_visibility.executions_visibility USING btree (namespace_id, status, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_task_queue; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_task_queue ON temporal_visibility.executions_visibility USING btree (namespace_id, task_queue, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_temporal_change_version; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_temporal_change_version ON temporal_visibility.executions_visibility USING gin (namespace_id, temporalchangeversion jsonb_path_ops);


--
-- Name: by_temporal_namespace_division; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_temporal_namespace_division ON temporal_visibility.executions_visibility USING btree (namespace_id, temporalnamespacedivision, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_temporal_schedule_paused; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_temporal_schedule_paused ON temporal_visibility.executions_visibility USING btree (namespace_id, temporalschedulepaused, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_temporal_scheduled_by_id; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_temporal_scheduled_by_id ON temporal_visibility.executions_visibility USING btree (namespace_id, temporalscheduledbyid, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_temporal_scheduled_start_time; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_temporal_scheduled_start_time ON temporal_visibility.executions_visibility USING btree (namespace_id, temporalscheduledstarttime, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_text_01; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_text_01 ON temporal_visibility.executions_visibility USING gin (namespace_id, text01);


--
-- Name: by_text_02; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_text_02 ON temporal_visibility.executions_visibility USING gin (namespace_id, text02);


--
-- Name: by_text_03; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_text_03 ON temporal_visibility.executions_visibility USING gin (namespace_id, text03);


--
-- Name: by_workflow_id; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_workflow_id ON temporal_visibility.executions_visibility USING btree (namespace_id, workflow_id, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_workflow_type; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_workflow_type ON temporal_visibility.executions_visibility USING btree (namespace_id, workflow_type_name, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: default_idx; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX default_idx ON temporal_visibility.executions_visibility USING btree (namespace_id, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: piston3_consumer piston3_consumer_consumer_token_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER piston3_consumer_consumer_token_update_notify AFTER UPDATE ON public.piston3_consumer FOR EACH ROW WHEN (((new.name)::text IS DISTINCT FROM (old.name)::text)) EXECUTE FUNCTION public.consumer_token_update_notify();


--
-- Name: piston3_token piston3_token_token_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER piston3_token_token_create_notify AFTER INSERT ON public.piston3_token FOR EACH ROW EXECUTE FUNCTION public.token_create_notify();


--
-- Name: piston3_token piston3_token_token_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER piston3_token_token_delete_notify AFTER DELETE ON public.piston3_token FOR EACH ROW EXECUTE FUNCTION public.token_delete_notify();


--
-- Name: piston3_token piston3_token_user_token_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER piston3_token_user_token_link_notify AFTER INSERT ON public.piston3_token FOR EACH ROW EXECUTE FUNCTION public.user_token_link_notify();


--
-- Name: piston3_token piston3_token_user_token_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER piston3_token_user_token_unlink_notify AFTER DELETE ON public.piston3_token FOR EACH ROW EXECUTE FUNCTION public.user_token_unlink_notify();


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_group_id_97559544_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_97559544_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_user_id_6a12ed8b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_6a12ed8b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_blockdevice maasserver_blockdevice_node_config_id_5b310b67_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_node_config_id_5b310b67_fk FOREIGN KEY (node_config_id) REFERENCES public.maasserver_nodeconfig(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmc maasserver_bmc_default_storage_pool_5f48762b_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_default_storage_pool_5f48762b_fk_maasserve FOREIGN KEY (default_storage_pool_id) REFERENCES public.maasserver_podstoragepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmc maasserver_bmc_ip_address_id_79362d14_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_ip_address_id_79362d14_fk FOREIGN KEY (ip_address_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmc maasserver_bmc_pool_id_6c449d30_fk_maasserver_resourcepool_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_pool_id_6c449d30_fk_maasserver_resourcepool_id FOREIGN KEY (pool_id) REFERENCES public.maasserver_resourcepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmc maasserver_bmc_zone_id_774ea0de_fk_maasserver_zone_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_zone_id_774ea0de_fk_maasserver_zone_id FOREIGN KEY (zone_id) REFERENCES public.maasserver_zone(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship maasserver_bmcroutablerac_bmc_id_27dedd10_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmcroutablerackcontrollerrelationship
    ADD CONSTRAINT maasserver_bmcroutablerac_bmc_id_27dedd10_fk FOREIGN KEY (bmc_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship maasserver_bmcroutablerac_rack_controller_id_1a3ffa6e_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmcroutablerackcontrollerrelationship
    ADD CONSTRAINT maasserver_bmcroutablerac_rack_controller_id_1a3ffa6e_fk FOREIGN KEY (rack_controller_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourcefilesync maasserver_bootresou_file_id_22508d9b_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefilesync
    ADD CONSTRAINT maasserver_bootresou_file_id_22508d9b_fk_maasserve FOREIGN KEY (file_id) REFERENCES public.maasserver_bootresourcefile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourcefile maasserver_bootresou_largefile_id_cf035187_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresou_largefile_id_cf035187_fk_maasserve FOREIGN KEY (largefile_id) REFERENCES public.maasserver_largefile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourcefilesync maasserver_bootresou_region_id_b11e2230_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefilesync
    ADD CONSTRAINT maasserver_bootresou_region_id_b11e2230_fk_maasserve FOREIGN KEY (region_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourcefile maasserver_bootresourcefile_resource_set_id_2fd093ab_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresourcefile_resource_set_id_2fd093ab_fk FOREIGN KEY (resource_set_id) REFERENCES public.maasserver_bootresourceset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourceset maasserver_bootresourceset_resource_id_c320a639_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourceset
    ADD CONSTRAINT maasserver_bootresourceset_resource_id_c320a639_fk FOREIGN KEY (resource_id) REFERENCES public.maasserver_bootresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootsourcecache maasserver_bootsourcecache_boot_source_id_73abe4d2_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourcecache
    ADD CONSTRAINT maasserver_bootsourcecache_boot_source_id_73abe4d2_fk FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootsourceselection maasserver_bootsourceselection_boot_source_id_b911aa0f_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_boot_source_id_b911aa0f_fk FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_controllerinfo maasserver_controllerinfo_node_id_e38255a5_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_controllerinfo
    ADD CONSTRAINT maasserver_controllerinfo_node_id_e38255a5_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_defaultresource maasserver_defaultre_zone_id_29a5153a_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_defaultresource
    ADD CONSTRAINT maasserver_defaultre_zone_id_29a5153a_fk_maasserve FOREIGN KEY (zone_id) REFERENCES public.maasserver_zone(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnippet_iprange_id_6a257e4d_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnippet_iprange_id_6a257e4d_fk FOREIGN KEY (iprange_id) REFERENCES public.maasserver_iprange(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnippet_node_id_8f31c564_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnippet_node_id_8f31c564_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnippet_subnet_id_f626b848_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnippet_subnet_id_f626b848_fk FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnippet_value_id_58a6a467_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnippet_value_id_58a6a467_fk FOREIGN KEY (value_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsdata maasserver_dnsdata_dnsresource_id_9a9b5788_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsdata
    ADD CONSTRAINT maasserver_dnsdata_dnsresource_id_9a9b5788_fk FOREIGN KEY (dnsresource_id) REFERENCES public.maasserver_dnsresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresour_dnsresource_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresour_dnsresource_id_fk_maasserve FOREIGN KEY (dnsresource_id) REFERENCES public.maasserver_dnsresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource maasserver_dnsresour_domain_id_c5abb245_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource
    ADD CONSTRAINT maasserver_dnsresour_domain_id_c5abb245_fk_maasserve FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresour_staticipaddress_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresour_staticipaddress_id_fk_maasserve FOREIGN KEY (staticipaddress_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_event maasserver_event_node_id_dd4495a7_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_event
    ADD CONSTRAINT maasserver_event_node_id_dd4495a7_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_event maasserver_event_type_id_702a532f_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_event
    ADD CONSTRAINT maasserver_event_type_id_702a532f_fk FOREIGN KEY (type_id) REFERENCES public.maasserver_eventtype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filestorage maasserver_filestorage_owner_id_24d47e43_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_owner_id_24d47e43_fk_auth_user_id FOREIGN KEY (owner_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesystem_block_device_id_5d3ba742_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_block_device_id_5d3ba742_fk FOREIGN KEY (block_device_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesystem_cache_set_id_f87650ce_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_cache_set_id_f87650ce_fk FOREIGN KEY (cache_set_id) REFERENCES public.maasserver_cacheset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesystem_filesystem_group_id_9bc05fe7_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_filesystem_group_id_9bc05fe7_fk FOREIGN KEY (filesystem_group_id) REFERENCES public.maasserver_filesystemgroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesystem_node_config_id_741ff095_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_node_config_id_741ff095_fk FOREIGN KEY (node_config_id) REFERENCES public.maasserver_nodeconfig(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesystem_partition_id_6174cd8b_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_partition_id_6174cd8b_fk FOREIGN KEY (partition_id) REFERENCES public.maasserver_partition(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystemgroup maasserver_filesystemgroup_cache_set_id_608e115e_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystemgroup
    ADD CONSTRAINT maasserver_filesystemgroup_cache_set_id_608e115e_fk FOREIGN KEY (cache_set_id) REFERENCES public.maasserver_cacheset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_forwarddnsserver_domains maasserver_forwarddn_domain_id_02e252ac_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver_domains
    ADD CONSTRAINT maasserver_forwarddn_domain_id_02e252ac_fk_maasserve FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_forwarddnsserver_domains maasserver_forwarddn_forwarddnsserver_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver_domains
    ADD CONSTRAINT maasserver_forwarddn_forwarddnsserver_id_fk_maasserve FOREIGN KEY (forwarddnsserver_id) REFERENCES public.maasserver_forwarddnsserver(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_globaldefault maasserver_globaldef_domain_id_11c3ee74_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_globaldefault
    ADD CONSTRAINT maasserver_globaldef_domain_id_11c3ee74_fk_maasserve FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_interface_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_interface_id_fk_maasserve FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface maasserver_interface_node_config_id_a52b0f8a_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_node_config_id_a52b0f8a_fk FOREIGN KEY (node_config_id) REFERENCES public.maasserver_nodeconfig(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface maasserver_interface_numa_node_id_6e790407_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_numa_node_id_6e790407_fk FOREIGN KEY (numa_node_id) REFERENCES public.maasserver_numanode(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_staticipaddress_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_staticipaddress_id_fk_maasserve FOREIGN KEY (staticipaddress_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface maasserver_interface_vlan_id_5f39995d_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_vlan_id_5f39995d_fk FOREIGN KEY (vlan_id) REFERENCES public.maasserver_vlan(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interfacerelationship maasserver_interfacerelationship_child_id_7be5401e_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interfacerelationship
    ADD CONSTRAINT maasserver_interfacerelationship_child_id_7be5401e_fk FOREIGN KEY (child_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interfacerelationship maasserver_interfacerelationship_parent_id_d3c77c37_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interfacerelationship
    ADD CONSTRAINT maasserver_interfacerelationship_parent_id_d3c77c37_fk FOREIGN KEY (parent_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_iprange maasserver_iprange_subnet_id_de83b8f1_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iprange
    ADD CONSTRAINT maasserver_iprange_subnet_id_de83b8f1_fk FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_iprange maasserver_iprange_user_id_5d0f7718_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iprange
    ADD CONSTRAINT maasserver_iprange_user_id_5d0f7718_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_mdns maasserver_mdns_interface_id_ef297041_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_mdns
    ADD CONSTRAINT maasserver_mdns_interface_id_ef297041_fk FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_neighbour maasserver_neighbour_interface_id_dd458d65_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_neighbour
    ADD CONSTRAINT maasserver_neighbour_interface_id_dd458d65_fk FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_bmc_id_a2d33e12_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_bmc_id_a2d33e12_fk FOREIGN KEY (bmc_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_boot_disk_id_db8131e9_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_boot_disk_id_db8131e9_fk_maasserve FOREIGN KEY (boot_disk_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_boot_interface_id_fad48090_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_boot_interface_id_fad48090_fk_maasserve FOREIGN KEY (boot_interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_commissionin_9ae2ec39_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_commissionin_9ae2ec39_fk_maasserve FOREIGN KEY (current_commissioning_script_set_id) REFERENCES public.maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_config_id_d9cbacad_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_config_id_d9cbacad_fk_maasserve FOREIGN KEY (current_config_id) REFERENCES public.maasserver_nodeconfig(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_installation_a6e40738_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_installation_a6e40738_fk_maasserve FOREIGN KEY (current_installation_script_set_id) REFERENCES public.maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_release_scri_1c3d13f5_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_release_scri_1c3d13f5_fk_maasserve FOREIGN KEY (current_release_script_set_id) REFERENCES public.maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_testing_scri_4636f4f9_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_testing_scri_4636f4f9_fk_maasserve FOREIGN KEY (current_testing_script_set_id) REFERENCES public.maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_dns_process_id_22d3b862_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_dns_process_id_22d3b862_fk_maasserve FOREIGN KEY (dns_process_id) REFERENCES public.maasserver_regioncontrollerprocess(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_domain_id_7b592cbf_fk_maasserver_domain_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_domain_id_7b592cbf_fk_maasserver_domain_id FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_gateway_link_ipv4_id_620a3c36_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_gateway_link_ipv4_id_620a3c36_fk_maasserve FOREIGN KEY (gateway_link_ipv4_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_gateway_link_ipv6_id_b8542fea_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_gateway_link_ipv6_id_b8542fea_fk_maasserve FOREIGN KEY (gateway_link_ipv6_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_managing_process_id_0f9f8640_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_managing_process_id_0f9f8640_fk_maasserve FOREIGN KEY (managing_process_id) REFERENCES public.maasserver_regioncontrollerprocess(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_owner_id_455bec7f_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_owner_id_455bec7f_fk_auth_user_id FOREIGN KEY (owner_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_parent_id_d0ac1fac_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_parent_id_d0ac1fac_fk FOREIGN KEY (parent_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_pool_id_42cdfac9_fk_maasserver_resourcepool_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_pool_id_42cdfac9_fk_maasserver_resourcepool_id FOREIGN KEY (pool_id) REFERENCES public.maasserver_resourcepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node_tags maasserver_node_tags_node_id_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_node_id_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node_tags maasserver_node_tags_tag_id_fk_maasserver_tag_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_tag_id_fk_maasserver_tag_id FOREIGN KEY (tag_id) REFERENCES public.maasserver_tag(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_zone_id_97213f69_fk_maasserver_zone_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_zone_id_97213f69_fk_maasserver_zone_id FOREIGN KEY (zone_id) REFERENCES public.maasserver_zone(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodeconfig maasserver_nodeconfig_node_id_c9235109_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeconfig
    ADD CONSTRAINT maasserver_nodeconfig_node_id_c9235109_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodedevice maasserver_nodedevic_physical_blockdevice_7ce12336_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevic_physical_blockdevice_7ce12336_fk_maasserve FOREIGN KEY (physical_blockdevice_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodedevice maasserver_nodedevice_node_config_id_3f91f0a0_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_node_config_id_3f91f0a0_fk FOREIGN KEY (node_config_id) REFERENCES public.maasserver_nodeconfig(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodedevice maasserver_nodedevice_numa_node_id_fadf5b46_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_numa_node_id_fadf5b46_fk FOREIGN KEY (numa_node_id) REFERENCES public.maasserver_numanode(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodedevice maasserver_nodedevice_physical_interface_id_ee476ae3_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_physical_interface_id_ee476ae3_fk FOREIGN KEY (physical_interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodedevicevpd maasserver_nodedevicevpd_node_device_id_9c998e15_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevicevpd
    ADD CONSTRAINT maasserver_nodedevicevpd_node_device_id_9c998e15_fk FOREIGN KEY (node_device_id) REFERENCES public.maasserver_nodedevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodegrouptorackcontroller maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodegrouptorackcontroller
    ADD CONSTRAINT maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b_fk FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodekey maasserver_nodekey_node_id_f8ec864b_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodekey
    ADD CONSTRAINT maasserver_nodekey_node_id_f8ec864b_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodekey maasserver_nodekey_token_id_d07891b5_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodekey
    ADD CONSTRAINT maasserver_nodekey_token_id_d07891b5_fk FOREIGN KEY (token_id) REFERENCES public.piston3_token(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodemetadata maasserver_nodemetadata_node_id_4350cc04_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodemetadata
    ADD CONSTRAINT maasserver_nodemetadata_node_id_4350cc04_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodeuserdata maasserver_nodeuserdata_node_id_e535ab67_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeuserdata
    ADD CONSTRAINT maasserver_nodeuserdata_node_id_e535ab67_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_notificationdismissal maasserver_notificat_user_id_87cc11da_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal
    ADD CONSTRAINT maasserver_notificat_user_id_87cc11da_fk_auth_user FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_notification maasserver_notification_user_id_5a4d1d18_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notification
    ADD CONSTRAINT maasserver_notification_user_id_5a4d1d18_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_notificationdismissal maasserver_notificationdismissal_notification_id_fe4f68d4_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal
    ADD CONSTRAINT maasserver_notificationdismissal_notification_id_fe4f68d4_fk FOREIGN KEY (notification_id) REFERENCES public.maasserver_notification(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_numanode maasserver_numanode_node_id_539a7e2f_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanode
    ADD CONSTRAINT maasserver_numanode_node_id_539a7e2f_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_numanodehugepages maasserver_numanodehugepages_numanode_id_0f0542f0_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_numanodehugepages
    ADD CONSTRAINT maasserver_numanodehugepages_numanode_id_0f0542f0_fk FOREIGN KEY (numanode_id) REFERENCES public.maasserver_numanode(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_ownerdata maasserver_ownerdata_node_id_4ec53011_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_ownerdata
    ADD CONSTRAINT maasserver_ownerdata_node_id_4ec53011_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_partition maasserver_partition_partition_table_id_c94faed6_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition
    ADD CONSTRAINT maasserver_partition_partition_table_id_c94faed6_fk FOREIGN KEY (partition_table_id) REFERENCES public.maasserver_partitiontable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_partitiontable maasserver_partitiontable_block_device_id_ee132cc5_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partitiontable
    ADD CONSTRAINT maasserver_partitiontable_block_device_id_ee132cc5_fk FOREIGN KEY (block_device_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_physicalblockdevice maasserver_physicalblockdevice_blockdevice_ptr_id_6ca192fb_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_physicalblockdevice
    ADD CONSTRAINT maasserver_physicalblockdevice_blockdevice_ptr_id_6ca192fb_fk FOREIGN KEY (blockdevice_ptr_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_physicalblockdevice maasserver_physicalblockdevice_numa_node_id_8bd61f48_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_physicalblockdevice
    ADD CONSTRAINT maasserver_physicalblockdevice_numa_node_id_8bd61f48_fk FOREIGN KEY (numa_node_id) REFERENCES public.maasserver_numanode(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podhints_nodes maasserver_podhints__node_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes
    ADD CONSTRAINT maasserver_podhints__node_id_fk_maasserve FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podhints_nodes maasserver_podhints__podhints_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes
    ADD CONSTRAINT maasserver_podhints__podhints_id_fk_maasserve FOREIGN KEY (podhints_id) REFERENCES public.maasserver_podhints(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podhints maasserver_podhints_cluster_id_b526f79f_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints
    ADD CONSTRAINT maasserver_podhints_cluster_id_b526f79f_fk FOREIGN KEY (cluster_id) REFERENCES public.maasserver_vmcluster(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podhints maasserver_podhints_pod_id_42c87c40_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints
    ADD CONSTRAINT maasserver_podhints_pod_id_42c87c40_fk FOREIGN KEY (pod_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podstoragepool maasserver_podstoragepool_pod_id_11db94aa_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podstoragepool
    ADD CONSTRAINT maasserver_podstoragepool_pod_id_11db94aa_fk FOREIGN KEY (pod_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_rdns maasserver_rdns_observer_id_85a64c6b_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rdns
    ADD CONSTRAINT maasserver_rdns_observer_id_85a64c6b_fk FOREIGN KEY (observer_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regioncontrollerprocessendpoint maasserver_regioncontroll_process_id_2bf84625_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocessendpoint
    ADD CONSTRAINT maasserver_regioncontroll_process_id_2bf84625_fk FOREIGN KEY (process_id) REFERENCES public.maasserver_regioncontrollerprocess(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regioncontrollerprocess maasserver_regioncontrollerprocess_region_id_ee210efa_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocess
    ADD CONSTRAINT maasserver_regioncontrollerprocess_region_id_ee210efa_fk FOREIGN KEY (region_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regionrackrpcconnection maasserver_regionrackrpcc_rack_controller_id_7f5b60af_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection
    ADD CONSTRAINT maasserver_regionrackrpcc_rack_controller_id_7f5b60af_fk FOREIGN KEY (rack_controller_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regionrackrpcconnection maasserver_regionrackrpcconnection_endpoint_id_9e6814b4_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection
    ADD CONSTRAINT maasserver_regionrackrpcconnection_endpoint_id_9e6814b4_fk FOREIGN KEY (endpoint_id) REFERENCES public.maasserver_regioncontrollerprocessendpoint(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_script maasserver_script_script_id_c6846a97_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_script
    ADD CONSTRAINT maasserver_script_script_id_c6846a97_fk FOREIGN KEY (script_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_scriptresult maasserver_scriptresult_interface_id_9734c983_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT maasserver_scriptresult_interface_id_9734c983_fk FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_scriptresult maasserver_scriptresult_script_id_c9ca2567_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT maasserver_scriptresult_script_id_c9ca2567_fk FOREIGN KEY (script_id) REFERENCES public.maasserver_script(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_scriptresult maasserver_scriptresult_script_set_id_884f5902_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT maasserver_scriptresult_script_set_id_884f5902_fk FOREIGN KEY (script_set_id) REFERENCES public.maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_scriptresult maasserver_scriptresult_script_version_id_ea465429_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT maasserver_scriptresult_script_version_id_ea465429_fk FOREIGN KEY (script_version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_scriptset maasserver_scriptset_node_id_634a177c_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptset
    ADD CONSTRAINT maasserver_scriptset_node_id_634a177c_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_service maasserver_service_node_id_891637d4_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_service
    ADD CONSTRAINT maasserver_service_node_id_891637d4_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_sshkey maasserver_sshkey_keysource_id_701e0769_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sshkey
    ADD CONSTRAINT maasserver_sshkey_keysource_id_701e0769_fk FOREIGN KEY (keysource_id) REFERENCES public.maasserver_keysource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_sshkey maasserver_sshkey_user_id_84b68559_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sshkey
    ADD CONSTRAINT maasserver_sshkey_user_id_84b68559_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_sslkey maasserver_sslkey_user_id_d871db8c_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sslkey
    ADD CONSTRAINT maasserver_sslkey_user_id_d871db8c_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_staticipaddress maasserver_staticipaddress_subnet_id_b30d84c3_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipaddress_subnet_id_b30d84c3_fk FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_staticipaddress maasserver_staticipaddress_user_id_a7e5e455_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipaddress_user_id_a7e5e455_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_staticroute maasserver_staticrou_destination_id_4d1b294b_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticroute
    ADD CONSTRAINT maasserver_staticrou_destination_id_4d1b294b_fk_maasserve FOREIGN KEY (destination_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_staticroute maasserver_staticrou_source_id_3321277a_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticroute
    ADD CONSTRAINT maasserver_staticrou_source_id_3321277a_fk_maasserve FOREIGN KEY (source_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_subnet maasserver_subnet_vlan_id_d4e96e9a_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_subnet
    ADD CONSTRAINT maasserver_subnet_vlan_id_d4e96e9a_fk FOREIGN KEY (vlan_id) REFERENCES public.maasserver_vlan(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_template maasserver_template_default_version_id_10647fcf_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template
    ADD CONSTRAINT maasserver_template_default_version_id_10647fcf_fk FOREIGN KEY (default_version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_template maasserver_template_version_id_78c8754e_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template
    ADD CONSTRAINT maasserver_template_version_id_78c8754e_fk FOREIGN KEY (version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_userprofile maasserver_userprofile_user_id_dc73fcb9_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_user_id_dc73fcb9_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_versionedtextfile maasserver_versionedtextfile_previous_version_id_8c3734e6_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_versionedtextfile
    ADD CONSTRAINT maasserver_versionedtextfile_previous_version_id_8c3734e6_fk FOREIGN KEY (previous_version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualblockdevice maasserver_virtualblockdevice_blockdevice_ptr_id_a5827040_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualblockdevice_blockdevice_ptr_id_a5827040_fk FOREIGN KEY (blockdevice_ptr_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualblockdevice maasserver_virtualblockdevice_filesystem_group_id_405a7fc4_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualblockdevice_filesystem_group_id_405a7fc4_fk FOREIGN KEY (filesystem_group_id) REFERENCES public.maasserver_filesystemgroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachinedisk maasserver_virtualma_backing_pool_id_2fe2f82c_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachinedisk
    ADD CONSTRAINT maasserver_virtualma_backing_pool_id_2fe2f82c_fk_maasserve FOREIGN KEY (backing_pool_id) REFERENCES public.maasserver_podstoragepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachinedisk maasserver_virtualma_vm_id_a5308b7c_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachinedisk
    ADD CONSTRAINT maasserver_virtualma_vm_id_a5308b7c_fk_maasserve FOREIGN KEY (vm_id) REFERENCES public.maasserver_virtualmachine(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachineinterface maasserver_virtualma_vm_id_a6acb3e9_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachineinterface
    ADD CONSTRAINT maasserver_virtualma_vm_id_a6acb3e9_fk_maasserve FOREIGN KEY (vm_id) REFERENCES public.maasserver_virtualmachine(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachine maasserver_virtualmachine_bmc_id_e2b4f381_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachine
    ADD CONSTRAINT maasserver_virtualmachine_bmc_id_e2b4f381_fk FOREIGN KEY (bmc_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachineinterface maasserver_virtualmachine_host_interface_id_9408be99_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachineinterface
    ADD CONSTRAINT maasserver_virtualmachine_host_interface_id_9408be99_fk FOREIGN KEY (host_interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachine maasserver_virtualmachine_machine_id_22da40a9_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachine
    ADD CONSTRAINT maasserver_virtualmachine_machine_id_22da40a9_fk FOREIGN KEY (machine_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualmachinedisk maasserver_virtualmachinedisk_block_device_id_8b224e57_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualmachinedisk
    ADD CONSTRAINT maasserver_virtualmachinedisk_block_device_id_8b224e57_fk FOREIGN KEY (block_device_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_fabric_id_af5275c8_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_fabric_id_af5275c8_fk FOREIGN KEY (fabric_id) REFERENCES public.maasserver_fabric(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_primary_rack_id_016c2af3_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_primary_rack_id_016c2af3_fk_maasserver_node_id FOREIGN KEY (primary_rack_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_relay_vlan_id_c026b672_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_relay_vlan_id_c026b672_fk FOREIGN KEY (relay_vlan_id) REFERENCES public.maasserver_vlan(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_secondary_rack_id_3b97d19a_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_secondary_rack_id_3b97d19a_fk_maasserve FOREIGN KEY (secondary_rack_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_space_id_5e1dc51f_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_space_id_5e1dc51f_fk FOREIGN KEY (space_id) REFERENCES public.maasserver_space(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vmcluster maasserver_vmcluster_pool_id_aad02386_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vmcluster
    ADD CONSTRAINT maasserver_vmcluster_pool_id_aad02386_fk_maasserve FOREIGN KEY (pool_id) REFERENCES public.maasserver_resourcepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vmcluster maasserver_vmcluster_zone_id_07623572_fk_maasserver_zone_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vmcluster
    ADD CONSTRAINT maasserver_vmcluster_zone_id_07623572_fk_maasserver_zone_id FOREIGN KEY (zone_id) REFERENCES public.maasserver_zone(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_scriptresult metadataserver_scrip_physical_blockdevice_c728b2ad_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT metadataserver_scrip_physical_blockdevice_c728b2ad_fk_maasserve FOREIGN KEY (physical_blockdevice_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston3_consumer piston3_consumer_user_id_ede69093_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_consumer
    ADD CONSTRAINT piston3_consumer_user_id_ede69093_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston3_token piston3_token_consumer_id_b178993d_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token
    ADD CONSTRAINT piston3_token_consumer_id_b178993d_fk FOREIGN KEY (consumer_id) REFERENCES public.piston3_consumer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston3_token piston3_token_user_id_e5cd818c_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token
    ADD CONSTRAINT piston3_token_user_id_e5cd818c_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

