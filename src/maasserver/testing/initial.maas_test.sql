--
-- PostgreSQL database dump
--

\restrict jDB4gdI1N8dbUCAC3vcdCvWs48TBU3tT39yhtb0ijqwqYnAc3QoCur8LfK1MnsD

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

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
-- Name: openfga; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA openfga;


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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_interface
      ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
    JOIN maasserver_vlan
      ON maasserver_vlan.id = maasserver_interface.vlan_id
    JOIN maasserver_fabric
      ON maasserver_vlan.fabric_id = maasserver_fabric.id
    WHERE maasserver_fabric.id = NEW.id
  )
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_interface
      ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
    JOIN maasserver_interface_ip_addresses
      ON maasserver_interface_ip_addresses.interface_id = maasserver_interface.id
    WHERE maasserver_interface_ip_addresses.staticipaddress_id = NEW.id
  )
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
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
    PERFORM pg_notify('controller_update', CAST(node.system_id AS text));
  ELSIF node.parent_id IS NOT NULL THEN
    SELECT system_id INTO pnode
    FROM maasserver_node
    WHERE id = node.parent_id;
    PERFORM pg_notify('machine_update', CAST(pnode.system_id AS text));
  ELSE
    PERFORM pg_notify('device_update', CAST(node.system_id AS text));
  END IF;
  PERFORM pg_notify('tag_update', CAST(NEW.tag_id AS text));
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
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
  ELSIF node.node_type IN (2, 3, 4) THEN
    PERFORM pg_notify('controller_update', CAST(node.system_id AS text));
  ELSIF node.parent_id IS NOT NULL THEN
    SELECT system_id INTO pnode
    FROM maasserver_node
    WHERE id = node.parent_id;
    PERFORM pg_notify('machine_update', CAST(pnode.system_id AS text));
  ELSE
    PERFORM pg_notify('device_update', CAST(node.system_id AS text));
  END IF;
  PERFORM pg_notify('tag_update', CAST(OLD.tag_id AS text));
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
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  WHERE maasserver_nodeconfig.id = NEW.node_config_id;

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
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  WHERE maasserver_nodeconfig.id = OLD.node_config_id;

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
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  WHERE maasserver_nodeconfig.id = NEW.node_config_id;

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
  WHERE maasserver_filesystem.cache_set_id = NEW.id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  WHERE maasserver_filesystem.cache_set_id = OLD.id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  WHERE maasserver_filesystem.cache_set_id = NEW.id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_blockdevice
      ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
    WHERE maasserver_blockdevice.id = NEW.block_device_id;
  ELSIF NEW.partition_id IS NOT NULL
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
    WHERE maasserver_partition.id = NEW.partition_id;
  ELSE
    SELECT system_id, node_type INTO node
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    WHERE NEW.node_config_id = maasserver_nodeconfig.id;
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_blockdevice
      ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
    WHERE maasserver_blockdevice.id = OLD.block_device_id;
  ELSIF OLD.partition_id IS NOT NULL
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
    WHERE maasserver_partition.id = OLD.partition_id;
  ELSE
    SELECT system_id, node_type INTO node
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    WHERE OLD.node_config_id = maasserver_nodeconfig.id;
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_blockdevice
      ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
    WHERE maasserver_blockdevice.id = NEW.block_device_id;
  ELSIF NEW.partition_id IS NOT NULL
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
    WHERE maasserver_partition.id = NEW.partition_id;
  ELSE
    SELECT system_id, node_type INTO node
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    WHERE NEW.node_config_id = maasserver_nodeconfig.id;
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
  WHERE maasserver_filesystem.filesystem_group_id = NEW.id
    OR maasserver_filesystem.cache_set_id = NEW.cache_set_id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  WHERE maasserver_filesystem.filesystem_group_id = OLD.id
    OR maasserver_filesystem.cache_set_id = OLD.cache_set_id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  WHERE maasserver_filesystem.filesystem_group_id = NEW.id
    OR maasserver_filesystem.cache_set_id = NEW.cache_set_id;

  IF node.node_type = 0 THEN
      PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  WHERE maasserver_nodeconfig.id = NEW.node_config_id;

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
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  WHERE maasserver_nodeconfig.id = OLD.node_config_id;

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
  IF OLD.node_config_id != NEW.node_config_id THEN
    SELECT system_id, node_type, parent_id INTO node
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    WHERE maasserver_nodeconfig.id = OLD.node_config_id;

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
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  WHERE maasserver_nodeconfig.id = NEW.node_config_id;

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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  JOIN maasserver_partitiontable
    ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
  WHERE maasserver_partitiontable.id = NEW.partition_table_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  JOIN maasserver_partitiontable
    ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
  WHERE maasserver_partitiontable.id = OLD.partition_table_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  JOIN maasserver_partitiontable
    ON maasserver_partitiontable.block_device_id = maasserver_blockdevice.id
  WHERE maasserver_partitiontable.id = NEW.partition_table_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_blockdevice.id = NEW.block_device_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_blockdevice.id = OLD.block_device_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_blockdevice.id = NEW.block_device_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_blockdevice.id = NEW.blockdevice_ptr_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
    maasserver_scriptset AS scriptset
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
    maasserver_scriptset AS scriptset
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
    maasserver_scriptset AS scriptset
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
  FROM maasserver_interface
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.id = maasserver_interface.node_config_id
  JOIN maasserver_node
    ON maasserver_node.id = maasserver_nodeconfig.node_id
  JOIN maasserver_domain
    ON maasserver_domain.id = maasserver_node.domain_id
  WHERE maasserver_interface.id = NEW.interface_id;

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
  FROM maasserver_interface
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.id = maasserver_interface.node_config_id
  JOIN maasserver_node
    ON maasserver_node.id = maasserver_nodeconfig.node_id
  JOIN maasserver_domain
    ON maasserver_domain.id = maasserver_node.domain_id
  WHERE maasserver_interface.id = OLD.interface_id;

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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_interface
    ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_interface.id = NEW.interface_id;

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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_interface
    ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_interface.id = OLD.interface_id;

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
  FROM maasserver_node
  JOIN maasserver_nodeconfig
    ON maasserver_nodeconfig.node_id = maasserver_node.id
  JOIN maasserver_blockdevice
    ON maasserver_blockdevice.node_config_id = maasserver_nodeconfig.id
  WHERE maasserver_blockdevice.id = NEW.blockdevice_ptr_id;

  IF node.node_type = 0 THEN
    PERFORM pg_notify('machine_update', CAST(node.system_id AS text));
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
-- Name: node_type_change_notify(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.node_type_change_notify() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF (OLD.node_type != NEW.node_type AND NOT (
      (OLD.node_type IN (2, 3, 4)) AND
      (NEW.node_type IN (2, 3, 4))
     )) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    PERFORM pg_notify(
      'machine_update', CAST(node.system_id AS text)
    );
  ELSIF node.node_type IN (2, 3, 4) THEN
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
    WHERE maasserver_space.id = NEW.id
  )
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_interface
      ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
    JOIN maasserver_interface_ip_addresses
      ON maasserver_interface_ip_addresses.interface_id = maasserver_interface.id
    JOIN maasserver_staticipaddress
      ON maasserver_staticipaddress.id = maasserver_interface_ip_addresses.staticipaddress_id
    WHERE maasserver_staticipaddress.subnet_id = NEW.id
  )
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
    boot_disk_id bigint,
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
    enable_kernel_crash_dump boolean NOT NULL,
    is_dpu boolean NOT NULL,
    current_deployment_script_set_id bigint,
    CONSTRAINT maasserver_node_address_ttl_check CHECK ((address_ttl >= 0)),
    CONSTRAINT maasserver_node_dpu_is_machine CHECK (((NOT is_dpu) OR (is_dpu AND (node_type = 0))))
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
    FROM maasserver_node
    JOIN maasserver_nodeconfig
      ON maasserver_nodeconfig.node_id = maasserver_node.id
    JOIN maasserver_interface
      ON maasserver_interface.node_config_id = maasserver_nodeconfig.id
    WHERE maasserver_interface.vlan_id = NEW.id
  )
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
-- Name: assertion; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.assertion (
    store text NOT NULL,
    authorization_model_id text NOT NULL,
    assertions bytea
);


--
-- Name: authorization_model; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.authorization_model (
    store text NOT NULL,
    authorization_model_id text NOT NULL,
    type text NOT NULL,
    type_definition bytea,
    schema_version text DEFAULT '1.0'::text NOT NULL,
    serialized_protobuf bytea
);


--
-- Name: changelog; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.changelog (
    store text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    relation text NOT NULL,
    _user text NOT NULL,
    operation integer NOT NULL,
    ulid text NOT NULL,
    inserted_at timestamp with time zone NOT NULL,
    condition_name text,
    condition_context bytea
);


--
-- Name: goose_app_db_version; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.goose_app_db_version (
    id integer NOT NULL,
    version_id bigint NOT NULL,
    is_applied boolean NOT NULL,
    tstamp timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: goose_app_db_version_id_seq; Type: SEQUENCE; Schema: openfga; Owner: -
--

ALTER TABLE openfga.goose_app_db_version ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME openfga.goose_app_db_version_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: goose_db_version; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.goose_db_version (
    id integer NOT NULL,
    version_id bigint NOT NULL,
    is_applied boolean NOT NULL,
    tstamp timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: goose_db_version_id_seq; Type: SEQUENCE; Schema: openfga; Owner: -
--

ALTER TABLE openfga.goose_db_version ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME openfga.goose_db_version_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: store; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.store (
    id text NOT NULL,
    name text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    updated_at timestamp with time zone,
    deleted_at timestamp with time zone
);


--
-- Name: tuple; Type: TABLE; Schema: openfga; Owner: -
--

CREATE TABLE openfga.tuple (
    store text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    relation text NOT NULL,
    _user text NOT NULL,
    user_type text NOT NULL,
    ulid text NOT NULL,
    inserted_at timestamp with time zone NOT NULL,
    condition_name text,
    condition_context bytea
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


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

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    id bigint NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_user_groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_user_user_permissions (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_user_user_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.django_site ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_site_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_agent; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_agent (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid character varying(36) NOT NULL,
    rack_id bigint NOT NULL,
    rackcontroller_id bigint
);


--
-- Name: maasserver_agent_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_agent ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_agent_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_blockdevice ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_blockdevice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_bmc ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bmc_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_bmcroutablerackcontrollerrelationship ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bmcroutablerackcontrollerrelationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    alias character varying(255),
    last_deployed timestamp without time zone,
    selection_id bigint
);


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_bootresource ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    size bigint NOT NULL,
    filename_on_disk character varying(64) NOT NULL
);


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_bootresourcefile ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootresourcefile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_bootresourcefilesync ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootresourcefilesync_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_bootresourceset ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootresourceset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_bootsource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsource (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    url character varying(200) NOT NULL,
    keyring_filename character varying(4096) NOT NULL,
    keyring_data bytea NOT NULL,
    priority integer NOT NULL,
    skip_keyring_verification boolean NOT NULL
);


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_bootsource ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootsource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    extra jsonb NOT NULL,
    latest_version character varying(32)
);


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_bootsourcecache ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootsourcecache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_bootsourceselection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsourceselection (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    os character varying(20) NOT NULL,
    release character varying(20) NOT NULL,
    arch text NOT NULL,
    boot_source_id bigint NOT NULL,
    legacyselection_id bigint NOT NULL
);


--
-- Name: maasserver_bootsourceselectionlegacy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsourceselectionlegacy (
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

ALTER TABLE public.maasserver_bootsourceselectionlegacy ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootsourceselection_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_bootsourceselection_id_seq1; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_bootsourceselection ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootsourceselection_id_seq1
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_bootsourceselectionstatus_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_bootsourceselectionstatus_view AS
 WITH sync_stats AS (
         SELECT rset.resource_id,
            rset.id AS set_id,
            rset.version,
            COALESCE((((sum(filesync.size) * (100)::numeric) / sum(file.size)) / (NULLIF(( SELECT count(*) AS count
                   FROM public.maasserver_node
                  WHERE (maasserver_node.node_type = ANY (ARRAY[3, 4]))), 0))::numeric), (0)::numeric) AS sync_percentage
           FROM ((public.maasserver_bootresourcefilesync filesync
             JOIN public.maasserver_bootresourcefile file ON ((file.id = filesync.file_id)))
             JOIN public.maasserver_bootresourceset rset ON ((rset.id = file.resource_set_id)))
          GROUP BY rset.resource_id, rset.id, rset.version
        ), latest_versions AS (
         SELECT res.id AS resource_id,
            cache.latest_version
           FROM (public.maasserver_bootsourcecache cache
             JOIN public.maasserver_bootresource res ON ((((res.name)::text = (((cache.os)::text || '/'::text) || (cache.release)::text)) AND ((res.kflavor)::text = (cache.kflavor)::text) AND (((res.architecture)::text = (((cache.arch)::text || '/'::text) || (cache.subarch)::text)) OR ((res.architecture)::text = (((((cache.arch)::text || '/'::text) || (cache.subarch)::text) || '-'::text) || (cache.kflavor)::text)) OR ((res.architecture)::text = ((((((cache.arch)::text || '/'::text) || (cache.subarch)::text) || '-'::text) || (cache.kflavor)::text) || '-edge'::text))))))
        ), resource_set_counts AS (
         SELECT sync_stats.resource_id,
            count(*) AS set_count
           FROM sync_stats
          GROUP BY sync_stats.resource_id
        ), resource_status AS (
         SELECT DISTINCT ON (ss.resource_id) ss.resource_id,
            ss.set_id,
            ss.version,
            lv.latest_version,
            ss.sync_percentage,
                CASE
                    WHEN ((rsc.set_count = 1) AND (ss.sync_percentage = (0)::numeric)) THEN 'Waiting for download'::text
                    WHEN ((rsc.set_count = 1) AND (ss.sync_percentage < (100)::numeric)) THEN 'Downloading'::text
                    WHEN ((rsc.set_count = 1) AND (ss.sync_percentage = (100)::numeric)) THEN 'Ready'::text
                    WHEN (rsc.set_count = 2) THEN 'Ready'::text
                    ELSE 'Waiting for download'::text
                END AS status,
                CASE
                    WHEN (rsc.set_count = 2) THEN 'Downloading'::text
                    WHEN (lv.latest_version IS NULL) THEN 'No updates available'::text
                    WHEN ((ss.version)::text >= (lv.latest_version)::text) THEN 'No updates available'::text
                    WHEN ((ss.version)::text < (lv.latest_version)::text) THEN 'Update available'::text
                    ELSE 'No updates available'::text
                END AS update_status
           FROM ((sync_stats ss
             JOIN latest_versions lv ON ((lv.resource_id = ss.resource_id)))
             JOIN resource_set_counts rsc ON ((rsc.resource_id = ss.resource_id)))
          ORDER BY ss.resource_id, ss.set_id DESC
        ), selection_resources AS (
         SELECT sel.id AS selection_id,
            res.id AS resource_id,
            rs.status,
            rs.update_status,
            rs.sync_percentage
           FROM ((public.maasserver_bootsourceselection sel
             LEFT JOIN public.maasserver_bootresource res ON ((res.selection_id = sel.id)))
             LEFT JOIN resource_status rs ON ((rs.resource_id = res.id)))
        ), selection_rank AS (
         SELECT sel.id AS selection_id,
            source.priority,
            row_number() OVER (PARTITION BY sel.os, sel.arch, sel.release ORDER BY source.priority DESC) AS rank
           FROM (public.maasserver_bootsourceselection sel
             JOIN public.maasserver_bootsource source ON ((source.id = sel.boot_source_id)))
        )
 SELECT selection_resources.selection_id AS id,
        CASE
            WHEN (count(selection_resources.resource_id) = 0) THEN 'Waiting for download'::text
            WHEN (count(*) FILTER (WHERE (selection_resources.status = 'Waiting for download'::text)) = count(*)) THEN 'Waiting for download'::text
            WHEN (count(*) FILTER (WHERE (selection_resources.status = 'Downloading'::text)) > 0) THEN 'Downloading'::text
            WHEN (count(*) FILTER (WHERE (selection_resources.status = 'Ready'::text)) = count(*)) THEN 'Ready'::text
            ELSE 'Waiting for download'::text
        END AS status,
        CASE
            WHEN (count(selection_resources.resource_id) = 0) THEN 'No updates available'::text
            WHEN (count(*) FILTER (WHERE (selection_resources.update_status = 'Downloading'::text)) > 0) THEN 'Downloading'::text
            WHEN (count(*) FILTER (WHERE (selection_resources.update_status = 'Update available'::text)) > 0) THEN 'Update available'::text
            WHEN (count(*) FILTER (WHERE (selection_resources.update_status = 'No updates available'::text)) = count(*)) THEN 'No updates available'::text
            ELSE 'No updates available'::text
        END AS update_status,
    COALESCE((avg(selection_resources.sync_percentage))::numeric(10,2), 0.00) AS sync_percentage,
        CASE
            WHEN (selection_rank.rank = 1) THEN true
            ELSE false
        END AS selected
   FROM (selection_resources
     JOIN selection_rank ON ((selection_rank.selection_id = selection_resources.selection_id)))
  GROUP BY selection_resources.selection_id, selection_rank.rank;


--
-- Name: maasserver_bootstraptoken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootstraptoken (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    secret character varying(64) NOT NULL,
    rack_id bigint NOT NULL
);


--
-- Name: maasserver_bootstraptoken_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_bootstraptoken ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_bootstraptoken_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_cacheset ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_cacheset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_config ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_defaultresource ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_defaultresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
-- Name: maasserver_dhcpsnippet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_dhcpsnippet ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_dhcpsnippet_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_fabric; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_fabric (
    id integer NOT NULL,
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
-- Name: maasserver_vlan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_vlan (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256),
    vid integer NOT NULL,
    mtu integer NOT NULL,
    fabric_id integer NOT NULL,
    dhcp_on boolean NOT NULL,
    primary_rack_id bigint,
    secondary_rack_id bigint,
    external_dhcp inet,
    description text NOT NULL,
    relay_vlan_id bigint,
    space_id bigint
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

ALTER TABLE public.maasserver_dnsdata ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_dnsdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_dnspublication; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dnspublication (
    id bigint NOT NULL,
    serial bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    source character varying(255) NOT NULL,
    update character varying(255) NOT NULL
);


--
-- Name: maasserver_dnspublication_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_dnspublication ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_dnspublication_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_dnsresource ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_dnsresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_dnsresource_ip_addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dnsresource_ip_addresses (
    id bigint NOT NULL,
    dnsresource_id bigint NOT NULL,
    staticipaddress_id bigint NOT NULL
);


--
-- Name: maasserver_dnsresource_ip_addresses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_dnsresource_ip_addresses ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_dnsresource_ip_addresses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_domain ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_domain_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_event ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_eventtype ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_eventtype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_fabric_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_fabric ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_fabric_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_filestorage ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_filestorage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_filesystem ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_filesystem_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_filesystemgroup ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_filesystemgroup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    id bigint NOT NULL,
    forwarddnsserver_id bigint NOT NULL,
    domain_id integer NOT NULL
);


--
-- Name: maasserver_forwarddnsserver_domains_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_forwarddnsserver_domains ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_forwarddnsserver_domains_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_forwarddnsserver_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_forwarddnsserver ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_forwarddnsserver_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_globaldefault ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_globaldefault_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_imagemanifest; Type: TABLE; Schema: public; Owner: -
--

CREATE UNLOGGED TABLE public.maasserver_imagemanifest (
    boot_source_id bigint NOT NULL,
    manifest jsonb NOT NULL,
    last_update timestamp with time zone NOT NULL
);


--
-- Name: maasserver_interface_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_interface ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_interface_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_interface_ip_addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_interface_ip_addresses (
    id bigint NOT NULL,
    interface_id bigint NOT NULL,
    staticipaddress_id bigint NOT NULL
);


--
-- Name: maasserver_interface_ip_addresses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_interface_ip_addresses ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_interface_ip_addresses_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_interfacerelationship ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_interfacerelationship_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_iprange ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_iprange_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_largefile ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_largefile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_licensekey ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_licensekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_mdns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_mdns ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_mdns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_neighbour_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_neighbour ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_neighbour_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_node ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_node_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_node_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_node_tags (
    id bigint NOT NULL,
    node_id bigint NOT NULL,
    tag_id bigint NOT NULL
);


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_node_tags ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_node_tags_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_nodeconfig ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_nodeconfig_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    physical_blockdevice_id bigint,
    physical_interface_id bigint,
    node_config_id bigint NOT NULL,
    CONSTRAINT maasserver_nodedevice_bus_number_check CHECK ((bus_number >= 0)),
    CONSTRAINT maasserver_nodedevice_device_number_check CHECK ((device_number >= 0))
);


--
-- Name: maasserver_nodedevice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_nodedevice ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_nodedevice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_nodedevicevpd ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_nodedevicevpd_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_nodegrouptorackcontroller ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_nodegrouptorackcontroller_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_nodekey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodekey (
    id bigint NOT NULL,
    node_id bigint NOT NULL,
    token_id bigint NOT NULL
);


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

ALTER TABLE public.maasserver_nodemetadata ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_nodemetadata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_nodeuserdata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodeuserdata (
    id bigint NOT NULL,
    data text NOT NULL,
    node_id bigint NOT NULL,
    for_ephemeral_environment boolean NOT NULL
);


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

ALTER TABLE public.maasserver_notification ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_notification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_notificationdismissal ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_notificationdismissal_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_numanode ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_numanode_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_numanodehugepages ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_numanodehugepages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_oidc_provider; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_oidc_provider (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    client_id character varying(255) NOT NULL,
    client_secret character varying(255) NOT NULL,
    issuer_url character varying(512) NOT NULL,
    redirect_uri text NOT NULL,
    scopes character varying(255) NOT NULL,
    enabled boolean NOT NULL,
    metadata jsonb NOT NULL,
    token_type integer NOT NULL
);


--
-- Name: maasserver_oidc_provider_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_oidc_provider ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_oidc_provider_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_oidcrevokedtoken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_oidcrevokedtoken (
    id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    revoked_at timestamp with time zone NOT NULL,
    user_email character varying(150) NOT NULL,
    provider_id bigint NOT NULL
);


--
-- Name: maasserver_oidcrevokedtoken_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_oidcrevokedtoken ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_oidcrevokedtoken_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_ownerdata ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_ownerdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_packagerepository ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_packagerepository_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_partition ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_partition_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_partitiontable ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_partitiontable_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_podhints ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_podhints_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_podhints_nodes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_podhints_nodes (
    id bigint NOT NULL,
    podhints_id bigint NOT NULL,
    node_id bigint NOT NULL
);


--
-- Name: maasserver_podhints_nodes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_podhints_nodes ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_podhints_nodes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_podstoragepool ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_podstoragepool_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_rack; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_rack (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL
);


--
-- Name: maasserver_rack_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_rack ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_rack_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_rbaclastsync ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_rbaclastsync_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_rbacsync ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_rbacsync_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_rdns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_rdns ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_rdns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_refreshtoken; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_refreshtoken (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    token character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: maasserver_refreshtoken_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_refreshtoken ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_refreshtoken_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_regioncontrollerprocess_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_regioncontrollerprocess ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_regioncontrollerprocess_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_regioncontrollerprocessendpoint ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_regioncontrollerprocessendpoint_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_regionrackrpcconnection ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_regionrackrpcconnection_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_reservedip; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_reservedip (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet NOT NULL,
    mac_address text NOT NULL,
    comment character varying(255),
    subnet_id bigint NOT NULL
);


--
-- Name: maasserver_reservedip_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_reservedip ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_reservedip_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_resourcepool ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_resourcepool_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_rootkey ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_rootkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
    physical_blockdevice_id bigint,
    suppressed boolean NOT NULL,
    interface_id bigint
);


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

ALTER TABLE public.maasserver_service ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_service_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_space ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_space_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_sshkey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_sshkey (
    id bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key text NOT NULL,
    user_id integer NOT NULL,
    auth_id character varying(255),
    protocol character varying(64)
);


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_sshkey ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_sshkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_sslkey ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_sslkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_staticipaddress ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_staticipaddress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_staticroute ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_staticroute_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_subnet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_subnet ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_subnet_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_tag ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_tag_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_template ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_ui_subnet_view; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_ui_subnet_view AS
 SELECT subnet.id,
    subnet.created,
    subnet.updated,
    subnet.name,
    subnet.cidr,
    subnet.gateway_ip,
    subnet.dns_servers,
    subnet.rdns_mode,
    subnet.allow_proxy,
    subnet.description,
    subnet.active_discovery,
    subnet.managed,
    subnet.allow_dns,
    subnet.disabled_boot_architectures,
    subnet.vlan_id,
    vlan.vid AS vlan_vid,
    vlan.name AS vlan_name,
    vlan.dhcp_on AS vlan_dhcp_on,
    vlan.external_dhcp AS vlan_external_dhcp,
    vlan.relay_vlan_id AS vlan_relay_vlan_id,
    space.id AS space_id,
    space.name AS space_name,
    fabric.id AS fabric_id,
    fabric.name AS fabric_name
   FROM (((public.maasserver_subnet subnet
     LEFT JOIN public.maasserver_vlan vlan ON ((subnet.vlan_id = vlan.id)))
     LEFT JOIN public.maasserver_fabric fabric ON ((vlan.fabric_id = fabric.id)))
     LEFT JOIN public.maasserver_space space ON ((vlan.space_id = space.id)));


--
-- Name: maasserver_userprofile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_userprofile (
    id bigint NOT NULL,
    user_id integer NOT NULL,
    completed_intro boolean NOT NULL,
    auth_last_check timestamp with time zone,
    is_local boolean NOT NULL,
    provider_id bigint
);


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_userprofile ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_userprofile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_versionedtextfile ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_versionedtextfile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_virtualmachine ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_virtualmachine_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_virtualmachinedisk ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_virtualmachinedisk_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_virtualmachineinterface ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_virtualmachineinterface_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: maasserver_vlan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_vlan ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_vlan_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_vmcluster ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_vmcluster_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.maasserver_zone ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.maasserver_zone_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_nodekey ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.metadataserver_nodekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_nodeuserdata ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.metadataserver_nodeuserdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: metadataserver_script_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_script ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.metadataserver_script_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: metadataserver_scriptresult_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_scriptresult ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.metadataserver_scriptresult_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: metadataserver_scriptset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.maasserver_scriptset ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.metadataserver_scriptset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.piston3_consumer ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.piston3_consumer_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.piston3_nonce ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.piston3_nonce_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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

ALTER TABLE public.piston3_token ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.piston3_token_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


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
-- Name: nexus_incoming_services; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.nexus_incoming_services (
    service_id bytea NOT NULL,
    data bytea NOT NULL,
    data_encoding character varying(16) NOT NULL,
    version bigint NOT NULL
);


--
-- Name: nexus_incoming_services_partition_status; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.nexus_incoming_services_partition_status (
    id integer DEFAULT 0 NOT NULL,
    version bigint NOT NULL,
    CONSTRAINT only_one_row CHECK ((id = 0))
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
-- Name: queue_messages; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.queue_messages (
    queue_type integer NOT NULL,
    queue_name character varying(255) NOT NULL,
    queue_partition bigint NOT NULL,
    message_id bigint NOT NULL,
    message_payload bytea NOT NULL,
    message_encoding character varying(16) NOT NULL
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
-- Name: queues; Type: TABLE; Schema: temporal; Owner: -
--

CREATE TABLE temporal.queues (
    queue_type integer NOT NULL,
    queue_name character varying(255) NOT NULL,
    metadata_payload bytea NOT NULL,
    metadata_encoding character varying(16) NOT NULL
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
    buildids jsonb GENERATED ALWAYS AS ((search_attributes -> 'BuildIds'::text)) STORED,
    execution_duration bigint,
    state_transition_count bigint,
    parent_workflow_id character varying(255),
    parent_run_id character varying(255),
    root_workflow_id character varying(255) DEFAULT ''::character varying NOT NULL,
    root_run_id character varying(255) DEFAULT ''::character varying NOT NULL
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
-- Name: buffered_events id; Type: DEFAULT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.buffered_events ALTER COLUMN id SET DEFAULT nextval('temporal.buffered_events_id_seq'::regclass);


--
-- Data for Name: assertion; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.assertion (store, authorization_model_id, assertions) FROM stdin;
\.


--
-- Data for Name: authorization_model; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.authorization_model (store, authorization_model_id, type, type_definition, schema_version, serialized_protobuf) FROM stdin;
00000000000000000000000000	00000000000000000000000000		\N	1.1	\\x0a1a30303030303030303030303030303030303030303030303030301203312e311a060a04757365721a2b0a0567726f7570120c0a066d656d62657212020a001a140a120a066d656d62657212080a060a04757365721afe0d0a046d61617312360a1363616e5f766965775f6964656e746974696573121f221d0a020a000a171215121363616e5f656469745f6964656e746974696573121c0a1663616e5f656469745f626f6f745f656e74697469657312020a00121b0a1563616e5f656469745f6c6963656e73655f6b65797312020a0012160a1063616e5f766965775f6465766963657312020a0012320a1163616e5f766965775f6d616368696e6573121d221b0a020a000a151213121163616e5f656469745f6d616368696e6573121e0a1863616e5f656469745f676c6f62616c5f656e74697469657312020a0012380a1463616e5f766965775f636f6e74726f6c6c6572731220221e0a020a000a181216121463616e5f656469745f636f6e74726f6c6c657273121c0a1663616e5f656469745f6e6f74696669636174696f6e7312020a0012170a1163616e5f656469745f6d616368696e657312020a0012340a1363616e5f6465706c6f795f6d616368696e6573121d221b0a020a000a151213121163616e5f656469745f6d616368696e657312400a1863616e5f766965775f676c6f62616c5f656e746974696573122422220a020a000a1c121a121863616e5f656469745f676c6f62616c5f656e74697469657312190a1363616e5f656469745f6964656e74697469657312020a00123c0a1663616e5f766965775f6e6f74696669636174696f6e73122222200a020a000a1a1218121663616e5f656469745f6e6f74696669636174696f6e73123c0a1663616e5f766965775f626f6f745f656e746974696573122222200a020a000a1a1218121663616e5f656469745f626f6f745f656e746974696573123a0a1563616e5f766965775f6c6963656e73655f6b6579731221221f0a020a000a191217121563616e5f656469745f6c6963656e73655f6b657973121a0a1463616e5f766965775f697061646472657373657312020a0012530a1b63616e5f766965775f617661696c61626c655f6d616368696e6573123422320a020a000a151213121163616e5f656469745f6d616368696e65730a151213121163616e5f766965775f6d616368696e6573121a0a1463616e5f656469745f636f6e74726f6c6c65727312020a00121d0a1763616e5f656469745f636f6e66696775726174696f6e7312020a00123e0a1763616e5f766965775f636f6e66696775726174696f6e73122322210a020a000a1b1219121763616e5f656469745f636f6e66696775726174696f6e731aee060a300a1b63616e5f766965775f617661696c61626c655f6d616368696e657312110a0f0a0567726f757012066d656d6265720a2d0a1863616e5f766965775f676c6f62616c5f656e74697469657312110a0f0a0567726f757012066d656d6265720a290a1463616e5f656469745f636f6e74726f6c6c65727312110a0f0a0567726f757012066d656d6265720a290a1463616e5f766965775f636f6e74726f6c6c65727312110a0f0a0567726f757012066d656d6265720a2b0a1663616e5f656469745f6e6f74696669636174696f6e7312110a0f0a0567726f757012066d656d6265720a2b0a1663616e5f656469745f626f6f745f656e74697469657312110a0f0a0567726f757012066d656d6265720a260a1163616e5f656469745f6d616368696e657312110a0f0a0567726f757012066d656d6265720a260a1163616e5f766965775f6d616368696e657312110a0f0a0567726f757012066d656d6265720a2d0a1863616e5f656469745f676c6f62616c5f656e74697469657312110a0f0a0567726f757012066d656d6265720a2c0a1763616e5f656469745f636f6e66696775726174696f6e7312110a0f0a0567726f757012066d656d6265720a2b0a1663616e5f766965775f626f6f745f656e74697469657312110a0f0a0567726f757012066d656d6265720a2a0a1563616e5f766965775f6c6963656e73655f6b65797312110a0f0a0567726f757012066d656d6265720a290a1463616e5f766965775f697061646472657373657312110a0f0a0567726f757012066d656d6265720a280a1363616e5f6465706c6f795f6d616368696e657312110a0f0a0567726f757012066d656d6265720a2c0a1763616e5f766965775f636f6e66696775726174696f6e7312110a0f0a0567726f757012066d656d6265720a2b0a1663616e5f766965775f6e6f74696669636174696f6e7312110a0f0a0567726f757012066d656d6265720a280a1363616e5f656469745f6964656e74697469657312110a0f0a0567726f757012066d656d6265720a280a1363616e5f766965775f6964656e74697469657312110a0f0a0567726f757012066d656d6265720a2a0a1563616e5f656469745f6c6963656e73655f6b65797312110a0f0a0567726f757012066d656d6265720a250a1063616e5f766965775f6465766963657312110a0f0a0567726f757012066d656d6265721acc040a04706f6f6c120c0a06706172656e7412020a00123e0a1163616e5f656469745f6d616368696e6573122922270a020a000a211a1f0a081206706172656e741213121163616e5f656469745f6d616368696e657312590a1363616e5f6465706c6f795f6d616368696e6573124222400a020a000a151213121163616e5f656469745f6d616368696e65730a231a210a081206706172656e741215121363616e5f6465706c6f795f6d616368696e657312550a1163616e5f766965775f6d616368696e65731240223e0a020a000a151213121163616e5f656469745f6d616368696e65730a211a1f0a081206706172656e741213121163616e5f766965775f6d616368696e65731280010a1b63616e5f766965775f617661696c61626c655f6d616368696e65731261225f0a020a000a151213121163616e5f656469745f6d616368696e65730a151213121163616e5f766965775f6d616368696e65730a2b1a290a081206706172656e74121d121b63616e5f766965775f617661696c61626c655f6d616368696e65731ac0010a120a06706172656e7412080a060a046d6161730a260a1163616e5f656469745f6d616368696e657312110a0f0a0567726f757012066d656d6265720a280a1363616e5f6465706c6f795f6d616368696e657312110a0f0a0567726f757012066d656d6265720a260a1163616e5f766965775f6d616368696e657312110a0f0a0567726f757012066d656d6265720a300a1b63616e5f766965775f617661696c61626c655f6d616368696e657312110a0f0a0567726f757012066d656d626572
\.


--
-- Data for Name: changelog; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.changelog (store, object_type, object_id, relation, _user, operation, ulid, inserted_at, condition_name, condition_context) FROM stdin;
\.


--
-- Data for Name: goose_app_db_version; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.goose_app_db_version (id, version_id, is_applied, tstamp) FROM stdin;
1	0	t	2026-02-25 12:51:32.115213
2	1	t	2026-02-25 12:51:32.117442
3	2	t	2026-02-25 12:51:32.120864
\.


--
-- Data for Name: goose_db_version; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.goose_db_version (id, version_id, is_applied, tstamp) FROM stdin;
1	0	t	2026-02-25 12:51:32.082624
2	1	t	2026-02-25 12:51:32.088433
3	2	t	2026-02-25 12:51:32.09556
4	3	t	2026-02-25 12:51:32.096702
5	4	t	2026-02-25 12:51:32.097391
6	5	t	2026-02-25 12:51:32.097902
7	6	t	2026-02-25 12:51:32.099461
\.


--
-- Data for Name: store; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.store (id, name, created_at, updated_at, deleted_at) FROM stdin;
00000000000000000000000000	MAAS	2026-02-25 12:51:32.117442+00	2026-02-25 12:51:32.117442+00	\N
\.


--
-- Data for Name: tuple; Type: TABLE DATA; Schema: openfga; Owner: -
--

COPY openfga.tuple (store, object_type, object_id, relation, _user, user_type, ulid, inserted_at, condition_name, condition_context) FROM stdin;
00000000000000000000000000	pool	0	parent	maas:0	user	01KJADNJ4SQYZSNWW30K6YGPZ1	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_machines	group:administrators#member	userset	01KJADNJ4SQYZSNWW30N6HNBM1	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_global_entities	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXJF7SNP6	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_controllers	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXKQZJNFV	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_identities	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXPGX4N7Z	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_configurations	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXR8T4GMZ	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_notifications	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXT1TCEC6	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_boot_entities	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXT3VP822	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_edit_license_keys	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXWR1MT1T	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_view_devices	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMXYF4WPB6	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_view_ipaddresses	group:administrators#member	userset	01KJADNJ4TZ5DWA3JMY0FDHD3V	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_deploy_machines	group:users#member	userset	01KJADNJ4TZ5DWA3JMY3C31QDA	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_view_deployable_machines	group:users#member	userset	01KJADNJ4V2G8EET0FFS0RKY3T	2026-02-25 12:51:32.120864+00	\N	\N
00000000000000000000000000	maas	0	can_view_global_entities	group:users#member	userset	01KJADNJ4V2G8EET0FFSY67QG0	2026-02-25 12:51:32.120864+00	\N	\N
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.alembic_version (version_num) FROM stdin;
0018
\.


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
73	Can add file storage	19	add_filestorage
74	Can change file storage	19	change_filestorage
75	Can delete file storage	19	delete_filestorage
76	Can view file storage	19	view_filestorage
77	Can add filesystem	20	add_filesystem
78	Can change filesystem	20	change_filesystem
79	Can delete filesystem	20	delete_filesystem
80	Can view filesystem	20	view_filesystem
81	Can add filesystem group	21	add_filesystemgroup
82	Can change filesystem group	21	change_filesystemgroup
83	Can delete filesystem group	21	delete_filesystemgroup
84	Can view filesystem group	21	view_filesystemgroup
85	Can add Interface	22	add_interface
86	Can change Interface	22	change_interface
87	Can delete Interface	22	delete_interface
88	Can view Interface	22	view_interface
89	Can add interface relationship	23	add_interfacerelationship
90	Can change interface relationship	23	change_interfacerelationship
91	Can delete interface relationship	23	delete_interfacerelationship
92	Can view interface relationship	23	view_interfacerelationship
93	Can add large file	24	add_largefile
94	Can change large file	24	change_largefile
95	Can delete large file	24	delete_largefile
96	Can view large file	24	view_largefile
97	Can add license key	25	add_licensekey
98	Can change license key	25	change_licensekey
99	Can delete license key	25	delete_licensekey
100	Can view license key	25	view_licensekey
101	Can add node	26	add_node
102	Can change node	26	change_node
103	Can delete node	26	delete_node
104	Can view node	26	view_node
105	Can add partition	27	add_partition
106	Can change partition	27	change_partition
107	Can delete partition	27	delete_partition
108	Can view partition	27	view_partition
109	Can add partition table	28	add_partitiontable
110	Can change partition table	28	change_partitiontable
111	Can delete partition table	28	delete_partitiontable
112	Can view partition table	28	view_partitiontable
113	Can add Space	29	add_space
114	Can change Space	29	change_space
115	Can delete Space	29	delete_space
116	Can view Space	29	view_space
117	Can add SSH key	30	add_sshkey
118	Can change SSH key	30	change_sshkey
119	Can delete SSH key	30	delete_sshkey
120	Can view SSH key	30	view_sshkey
121	Can add SSL key	31	add_sslkey
122	Can change SSL key	31	change_sslkey
123	Can delete SSL key	31	delete_sslkey
124	Can view SSL key	31	view_sslkey
125	Can add Static IP Address	32	add_staticipaddress
126	Can change Static IP Address	32	change_staticipaddress
127	Can delete Static IP Address	32	delete_staticipaddress
128	Can view Static IP Address	32	view_staticipaddress
129	Can add subnet	33	add_subnet
130	Can change subnet	33	change_subnet
131	Can delete subnet	33	delete_subnet
132	Can view subnet	33	view_subnet
133	Can add tag	34	add_tag
134	Can change tag	34	change_tag
135	Can delete tag	34	delete_tag
136	Can view tag	34	view_tag
137	Can add user profile	35	add_userprofile
138	Can change user profile	35	change_userprofile
139	Can delete user profile	35	delete_userprofile
140	Can view user profile	35	view_userprofile
141	Can add VLAN	36	add_vlan
142	Can change VLAN	36	change_vlan
143	Can delete VLAN	36	delete_vlan
144	Can view VLAN	36	view_vlan
145	Can add Physical zone	37	add_zone
146	Can change Physical zone	37	change_zone
147	Can delete Physical zone	37	delete_zone
148	Can view Physical zone	37	view_zone
149	Can add physical block device	38	add_physicalblockdevice
150	Can change physical block device	38	change_physicalblockdevice
151	Can delete physical block device	38	delete_physicalblockdevice
152	Can view physical block device	38	view_physicalblockdevice
153	Can add virtual block device	39	add_virtualblockdevice
154	Can change virtual block device	39	change_virtualblockdevice
155	Can delete virtual block device	39	delete_virtualblockdevice
156	Can view virtual block device	39	view_virtualblockdevice
157	Can add bcache	40	add_bcache
158	Can change bcache	40	change_bcache
159	Can delete bcache	40	delete_bcache
160	Can view bcache	40	view_bcache
161	Can add Bond	41	add_bondinterface
162	Can change Bond	41	change_bondinterface
163	Can delete Bond	41	delete_bondinterface
164	Can view Bond	41	view_bondinterface
165	Can add device	42	add_device
166	Can change device	42	change_device
167	Can delete device	42	delete_device
168	Can view device	42	view_device
169	Can add Physical interface	43	add_physicalinterface
170	Can change Physical interface	43	change_physicalinterface
171	Can delete Physical interface	43	delete_physicalinterface
172	Can view Physical interface	43	view_physicalinterface
173	Can add raid	44	add_raid
174	Can change raid	44	change_raid
175	Can delete raid	44	delete_raid
176	Can view raid	44	view_raid
177	Can add Unknown interface	45	add_unknowninterface
178	Can change Unknown interface	45	change_unknowninterface
179	Can delete Unknown interface	45	delete_unknowninterface
180	Can view Unknown interface	45	view_unknowninterface
181	Can add VLAN interface	46	add_vlaninterface
182	Can change VLAN interface	46	change_vlaninterface
183	Can delete VLAN interface	46	delete_vlaninterface
184	Can view VLAN interface	46	view_vlaninterface
185	Can add volume group	47	add_volumegroup
186	Can change volume group	47	change_volumegroup
187	Can delete volume group	47	delete_volumegroup
188	Can view volume group	47	view_volumegroup
189	Can add machine	48	add_machine
190	Can change machine	48	change_machine
191	Can delete machine	48	delete_machine
192	Can view machine	48	view_machine
193	Can add rack controller	49	add_rackcontroller
194	Can change rack controller	49	change_rackcontroller
195	Can delete rack controller	49	delete_rackcontroller
196	Can view rack controller	49	view_rackcontroller
197	Can add DNSResource	50	add_dnsresource
198	Can change DNSResource	50	change_dnsresource
199	Can delete DNSResource	50	delete_dnsresource
200	Can view DNSResource	50	view_dnsresource
201	Can add domain	51	add_domain
202	Can change domain	51	change_domain
203	Can delete domain	51	delete_domain
204	Can view domain	51	view_domain
205	Can add region controller process	52	add_regioncontrollerprocess
206	Can change region controller process	52	change_regioncontrollerprocess
207	Can delete region controller process	52	delete_regioncontrollerprocess
208	Can view region controller process	52	view_regioncontrollerprocess
209	Can add region controller process endpoint	53	add_regioncontrollerprocessendpoint
210	Can change region controller process endpoint	53	change_regioncontrollerprocessendpoint
211	Can delete region controller process endpoint	53	delete_regioncontrollerprocessendpoint
212	Can view region controller process endpoint	53	view_regioncontrollerprocessendpoint
213	Can add region controller	54	add_regioncontroller
214	Can change region controller	54	change_regioncontroller
215	Can delete region controller	54	delete_regioncontroller
216	Can view region controller	54	view_regioncontroller
217	Can add bmc	55	add_bmc
218	Can change bmc	55	change_bmc
219	Can delete bmc	55	delete_bmc
220	Can view bmc	55	view_bmc
221	Can add DNSData	56	add_dnsdata
222	Can change DNSData	56	change_dnsdata
223	Can delete DNSData	56	delete_dnsdata
224	Can view DNSData	56	view_dnsdata
225	Can add ip range	57	add_iprange
226	Can change ip range	57	change_iprange
227	Can delete ip range	57	delete_iprange
228	Can view ip range	57	view_iprange
229	Can add node group to rack controller	58	add_nodegrouptorackcontroller
230	Can change node group to rack controller	58	change_nodegrouptorackcontroller
231	Can delete node group to rack controller	58	delete_nodegrouptorackcontroller
232	Can view node group to rack controller	58	view_nodegrouptorackcontroller
233	Can add region rack rpc connection	59	add_regionrackrpcconnection
234	Can change region rack rpc connection	59	change_regionrackrpcconnection
235	Can delete region rack rpc connection	59	delete_regionrackrpcconnection
236	Can view region rack rpc connection	59	view_regionrackrpcconnection
237	Can add service	60	add_service
238	Can change service	60	change_service
239	Can delete service	60	delete_service
240	Can view service	60	view_service
241	Can add Template	61	add_template
242	Can change Template	61	change_template
243	Can delete Template	61	delete_template
244	Can view Template	61	view_template
245	Can add VersionedTextFile	62	add_versionedtextfile
246	Can change VersionedTextFile	62	change_versionedtextfile
247	Can delete VersionedTextFile	62	delete_versionedtextfile
248	Can view VersionedTextFile	62	view_versionedtextfile
249	Can add bmc routable rack controller relationship	63	add_bmcroutablerackcontrollerrelationship
250	Can change bmc routable rack controller relationship	63	change_bmcroutablerackcontrollerrelationship
251	Can delete bmc routable rack controller relationship	63	delete_bmcroutablerackcontrollerrelationship
252	Can view bmc routable rack controller relationship	63	view_bmcroutablerackcontrollerrelationship
253	Can add dhcp snippet	64	add_dhcpsnippet
254	Can change dhcp snippet	64	change_dhcpsnippet
255	Can delete dhcp snippet	64	delete_dhcpsnippet
256	Can view dhcp snippet	64	view_dhcpsnippet
257	Can add child interface	65	add_childinterface
258	Can change child interface	65	change_childinterface
259	Can delete child interface	65	delete_childinterface
260	Can view child interface	65	view_childinterface
261	Can add Bridge	66	add_bridgeinterface
262	Can change Bridge	66	change_bridgeinterface
263	Can delete Bridge	66	delete_bridgeinterface
264	Can view Bridge	66	view_bridgeinterface
265	Can add owner data	67	add_ownerdata
266	Can change owner data	67	change_ownerdata
267	Can delete owner data	67	delete_ownerdata
268	Can view owner data	67	view_ownerdata
269	Can add controller	68	add_controller
270	Can change controller	68	change_controller
271	Can delete controller	68	delete_controller
272	Can view controller	68	view_controller
273	Can add dns publication	69	add_dnspublication
274	Can change dns publication	69	change_dnspublication
275	Can delete dns publication	69	delete_dnspublication
276	Can view dns publication	69	view_dnspublication
277	Can add package repository	70	add_packagerepository
278	Can change package repository	70	change_packagerepository
279	Can delete package repository	70	delete_packagerepository
280	Can view package repository	70	view_packagerepository
281	Can add mDNS binding	71	add_mdns
282	Can change mDNS binding	71	change_mdns
283	Can delete mDNS binding	71	delete_mdns
284	Can view mDNS binding	71	view_mdns
285	Can add Neighbour	72	add_neighbour
286	Can change Neighbour	72	change_neighbour
287	Can delete Neighbour	72	delete_neighbour
288	Can view Neighbour	72	view_neighbour
289	Can add static route	73	add_staticroute
290	Can change static route	73	change_staticroute
291	Can delete static route	73	delete_staticroute
292	Can view static route	73	view_staticroute
293	Can add Discovery	74	add_discovery
294	Can change Discovery	74	change_discovery
295	Can delete Discovery	74	delete_discovery
296	Can view Discovery	74	view_discovery
297	Can add Reverse-DNS entry	75	add_rdns
298	Can change Reverse-DNS entry	75	change_rdns
299	Can delete Reverse-DNS entry	75	delete_rdns
300	Can view Reverse-DNS entry	75	view_rdns
301	Can add notification	76	add_notification
302	Can change notification	76	change_notification
303	Can delete notification	76	delete_notification
304	Can view notification	76	view_notification
305	Can add notification dismissal	77	add_notificationdismissal
306	Can change notification dismissal	77	change_notificationdismissal
307	Can delete notification dismissal	77	delete_notificationdismissal
308	Can view notification dismissal	77	view_notificationdismissal
309	Can add pod hints	78	add_podhints
310	Can change pod hints	78	change_podhints
311	Can delete pod hints	78	delete_podhints
312	Can view pod hints	78	view_podhints
313	Can add pod	79	add_pod
314	Can change pod	79	change_pod
315	Can delete pod	79	delete_pod
316	Can view pod	79	view_pod
317	Can add ControllerInfo	80	add_controllerinfo
318	Can change ControllerInfo	80	change_controllerinfo
319	Can delete ControllerInfo	80	delete_controllerinfo
320	Can view ControllerInfo	80	view_controllerinfo
321	Can add NodeMetadata	81	add_nodemetadata
322	Can change NodeMetadata	81	change_nodemetadata
323	Can delete NodeMetadata	81	delete_nodemetadata
324	Can view NodeMetadata	81	view_nodemetadata
325	Can add resource pool	82	add_resourcepool
326	Can change resource pool	82	change_resourcepool
327	Can delete resource pool	82	delete_resourcepool
328	Can view resource pool	82	view_resourcepool
329	Can add root key	83	add_rootkey
330	Can change root key	83	change_rootkey
331	Can delete root key	83	delete_rootkey
332	Can view root key	83	view_rootkey
333	Can add global default	84	add_globaldefault
334	Can change global default	84	change_globaldefault
335	Can delete global default	84	delete_globaldefault
336	Can view global default	84	view_globaldefault
337	Can add pod storage pool	85	add_podstoragepool
338	Can change pod storage pool	85	change_podstoragepool
339	Can delete pod storage pool	85	delete_podstoragepool
340	Can view pod storage pool	85	view_podstoragepool
341	Can add rbac sync	86	add_rbacsync
342	Can change rbac sync	86	change_rbacsync
343	Can delete rbac sync	86	delete_rbacsync
344	Can view rbac sync	86	view_rbacsync
345	Can add rbac last sync	87	add_rbaclastsync
346	Can change rbac last sync	87	change_rbaclastsync
347	Can delete rbac last sync	87	delete_rbaclastsync
348	Can view rbac last sync	87	view_rbaclastsync
349	Can add vmfs	88	add_vmfs
350	Can change vmfs	88	change_vmfs
351	Can delete vmfs	88	delete_vmfs
352	Can view vmfs	88	view_vmfs
353	Can add numa node	89	add_numanode
354	Can change numa node	89	change_numanode
355	Can delete numa node	89	delete_numanode
356	Can view numa node	89	view_numanode
357	Can add virtual machine	90	add_virtualmachine
358	Can change virtual machine	90	change_virtualmachine
359	Can delete virtual machine	90	delete_virtualmachine
360	Can view virtual machine	90	view_virtualmachine
361	Can add numa node hugepages	91	add_numanodehugepages
362	Can change numa node hugepages	91	change_numanodehugepages
363	Can delete numa node hugepages	91	delete_numanodehugepages
364	Can view numa node hugepages	91	view_numanodehugepages
365	Can add virtual machine interface	92	add_virtualmachineinterface
366	Can change virtual machine interface	92	change_virtualmachineinterface
367	Can delete virtual machine interface	92	delete_virtualmachineinterface
368	Can view virtual machine interface	92	view_virtualmachineinterface
369	Can add node device	93	add_nodedevice
370	Can change node device	93	change_nodedevice
371	Can delete node device	93	delete_nodedevice
372	Can view node device	93	view_nodedevice
373	Can add virtual machine disk	94	add_virtualmachinedisk
374	Can change virtual machine disk	94	change_virtualmachinedisk
375	Can delete virtual machine disk	94	delete_virtualmachinedisk
376	Can view virtual machine disk	94	view_virtualmachinedisk
377	Can add forward dns server	95	add_forwarddnsserver
378	Can change forward dns server	95	change_forwarddnsserver
379	Can delete forward dns server	95	delete_forwarddnsserver
380	Can view forward dns server	95	view_forwarddnsserver
381	Can add vm cluster	96	add_vmcluster
382	Can change vm cluster	96	change_vmcluster
383	Can delete vm cluster	96	delete_vmcluster
384	Can view vm cluster	96	view_vmcluster
385	Can add node config	97	add_nodeconfig
386	Can change node config	97	change_nodeconfig
387	Can delete node config	97	delete_nodeconfig
388	Can view node config	97	view_nodeconfig
389	Can add NodeDeviceVPD	98	add_nodedevicevpd
390	Can change NodeDeviceVPD	98	change_nodedevicevpd
391	Can delete NodeDeviceVPD	98	delete_nodedevicevpd
392	Can view NodeDeviceVPD	98	view_nodedevicevpd
393	Can add secret	99	add_secret
394	Can change secret	99	change_secret
395	Can delete secret	99	delete_secret
396	Can view secret	99	view_secret
397	Can add vault secret	100	add_vaultsecret
398	Can change vault secret	100	change_vaultsecret
399	Can delete vault secret	100	delete_vaultsecret
400	Can view vault secret	100	view_vaultsecret
401	Can add node key	101	add_nodekey
402	Can change node key	101	change_nodekey
403	Can delete node key	101	delete_nodekey
404	Can view node key	101	view_nodekey
405	Can add node user data	102	add_nodeuserdata
406	Can change node user data	102	change_nodeuserdata
407	Can delete node user data	102	delete_nodeuserdata
408	Can view node user data	102	view_nodeuserdata
409	Can add script	103	add_script
410	Can change script	103	change_script
411	Can delete script	103	delete_script
412	Can view script	103	view_script
413	Can add script set	104	add_scriptset
414	Can change script set	104	change_scriptset
415	Can delete script set	104	delete_scriptset
416	Can view script set	104	view_scriptset
417	Can add script result	105	add_scriptresult
418	Can change script result	105	change_scriptresult
419	Can delete script result	105	delete_scriptresult
420	Can view script result	105	view_scriptresult
421	Can add boot resource file sync	106	add_bootresourcefilesync
422	Can change boot resource file sync	106	change_bootresourcefilesync
423	Can delete boot resource file sync	106	delete_bootresourcefilesync
424	Can view boot resource file sync	106	view_bootresourcefilesync
425	Can add default resource	107	add_defaultresource
426	Can change default resource	107	change_defaultresource
427	Can delete default resource	107	delete_defaultresource
428	Can view default resource	107	view_defaultresource
429	Can add Reserved IP	108	add_reservedip
430	Can change Reserved IP	108	change_reservedip
431	Can delete Reserved IP	108	delete_reservedip
432	Can view Reserved IP	108	view_reservedip
433	Can add consumer	109	add_consumer
434	Can change consumer	109	change_consumer
435	Can delete consumer	109	delete_consumer
436	Can view consumer	109	view_consumer
437	Can add nonce	110	add_nonce
438	Can change nonce	110	change_nonce
439	Can delete nonce	110	delete_nonce
440	Can view nonce	110	view_nonce
441	Can add token	111	add_token
442	Can change token	111	change_token
443	Can delete token	111	delete_token
444	Can view token	111	view_token
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
19	maasserver	filestorage
20	maasserver	filesystem
21	maasserver	filesystemgroup
22	maasserver	interface
23	maasserver	interfacerelationship
24	maasserver	largefile
25	maasserver	licensekey
26	maasserver	node
27	maasserver	partition
28	maasserver	partitiontable
29	maasserver	space
30	maasserver	sshkey
31	maasserver	sslkey
32	maasserver	staticipaddress
33	maasserver	subnet
34	maasserver	tag
35	maasserver	userprofile
36	maasserver	vlan
37	maasserver	zone
38	maasserver	physicalblockdevice
39	maasserver	virtualblockdevice
40	maasserver	bcache
41	maasserver	bondinterface
42	maasserver	device
43	maasserver	physicalinterface
44	maasserver	raid
45	maasserver	unknowninterface
46	maasserver	vlaninterface
47	maasserver	volumegroup
48	maasserver	machine
49	maasserver	rackcontroller
50	maasserver	dnsresource
51	maasserver	domain
52	maasserver	regioncontrollerprocess
53	maasserver	regioncontrollerprocessendpoint
54	maasserver	regioncontroller
55	maasserver	bmc
56	maasserver	dnsdata
57	maasserver	iprange
58	maasserver	nodegrouptorackcontroller
59	maasserver	regionrackrpcconnection
60	maasserver	service
61	maasserver	template
62	maasserver	versionedtextfile
63	maasserver	bmcroutablerackcontrollerrelationship
64	maasserver	dhcpsnippet
65	maasserver	childinterface
66	maasserver	bridgeinterface
67	maasserver	ownerdata
68	maasserver	controller
69	maasserver	dnspublication
70	maasserver	packagerepository
71	maasserver	mdns
72	maasserver	neighbour
73	maasserver	staticroute
74	maasserver	discovery
75	maasserver	rdns
76	maasserver	notification
77	maasserver	notificationdismissal
78	maasserver	podhints
79	maasserver	pod
80	maasserver	controllerinfo
81	maasserver	nodemetadata
82	maasserver	resourcepool
83	maasserver	rootkey
84	maasserver	globaldefault
85	maasserver	podstoragepool
86	maasserver	rbacsync
87	maasserver	rbaclastsync
88	maasserver	vmfs
89	maasserver	numanode
90	maasserver	virtualmachine
91	maasserver	numanodehugepages
92	maasserver	virtualmachineinterface
93	maasserver	nodedevice
94	maasserver	virtualmachinedisk
95	maasserver	forwarddnsserver
96	maasserver	vmcluster
97	maasserver	nodeconfig
98	maasserver	nodedevicevpd
99	maasserver	secret
100	maasserver	vaultsecret
101	maasserver	nodekey
102	maasserver	nodeuserdata
104	maasserver	scriptset
103	maasserver	script
105	maasserver	scriptresult
106	maasserver	bootresourcefilesync
107	maasserver	defaultresource
108	maasserver	reservedip
109	piston3	consumer
110	piston3	nonce
111	piston3	token
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
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
\.


--
-- Data for Name: maasserver_agent; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_agent (id, created, updated, uuid, rack_id, rackcontroller_id) FROM stdin;
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

COPY public.maasserver_bootresource (id, created, updated, rtype, name, architecture, extra, kflavor, bootloader_type, rolling, base_image, alias, last_deployed, selection_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresourcefile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresourcefile (id, created, updated, filename, filetype, extra, largefile_id, resource_set_id, sha256, size, filename_on_disk) FROM stdin;
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

COPY public.maasserver_bootsource (id, created, updated, url, keyring_filename, keyring_data, priority, skip_keyring_verification) FROM stdin;
\.


--
-- Data for Name: maasserver_bootsourcecache; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootsourcecache (id, created, updated, os, arch, subarch, release, label, boot_source_id, release_codename, release_title, support_eol, kflavor, bootloader_type, extra, latest_version) FROM stdin;
\.


--
-- Data for Name: maasserver_bootsourceselection; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootsourceselection (id, created, updated, os, release, arch, boot_source_id, legacyselection_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootsourceselectionlegacy; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootsourceselectionlegacy (id, created, updated, os, release, arches, subarches, labels, boot_source_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootstraptoken; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootstraptoken (id, created, updated, expires_at, secret, rack_id) FROM stdin;
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
1	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	1
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

COPY public.maasserver_dnspublication (id, serial, created, source, update) FROM stdin;
1	1	2025-10-17 10:15:20.69894+00	Initial publication	
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
0	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	maas	t	\N
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
0	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	0
\.


--
-- Data for Name: maasserver_imagemanifest; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_imagemanifest (boot_source_id, manifest, last_update) FROM stdin;
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

COPY public.maasserver_node (id, created, updated, system_id, hostname, status, bios_boot_method, osystem, distro_series, architecture, min_hwe_kernel, hwe_kernel, agent_name, error_description, cpu_count, memory, swap_size, power_state, power_state_updated, error, netboot, license_key, boot_cluster_ip, enable_ssh, skip_networking, skip_storage, boot_interface_id, gateway_link_ipv4_id, gateway_link_ipv6_id, owner_id, parent_id, zone_id, boot_disk_id, node_type, domain_id, dns_process_id, bmc_id, address_ttl, status_expires, power_state_queried, url, managing_process_id, last_image_sync, previous_status, default_user, cpu_speed, current_commissioning_script_set_id, current_installation_script_set_id, current_testing_script_set_id, install_rackd, locked, pool_id, instance_power_parameters, install_kvm, hardware_uuid, ephemeral_deploy, description, dynamic, register_vmhost, last_applied_storage_layout, current_config_id, enable_hw_sync, last_sync, sync_interval, current_release_script_set_id, enable_kernel_crash_dump, is_dpu, current_deployment_script_set_id) FROM stdin;
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

COPY public.maasserver_nodeuserdata (id, data, node_id, for_ephemeral_environment) FROM stdin;
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
-- Data for Name: maasserver_oidc_provider; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_oidc_provider (id, created, updated, name, client_id, client_secret, issuer_url, redirect_uri, scopes, enabled, metadata, token_type) FROM stdin;
\.


--
-- Data for Name: maasserver_oidcrevokedtoken; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_oidcrevokedtoken (id, token_hash, revoked_at, user_email, provider_id) FROM stdin;
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
1	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	main_archive	http://archive.ubuntu.com/ubuntu	{}	{amd64,i386}		t	t	{}	{}	{}	t
2	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	ports_archive	http://ports.ubuntu.com/ubuntu-ports	{}	{armhf,arm64,ppc64el,s390x}		t	t	{}	{}	{}	t
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
-- Data for Name: maasserver_rack; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_rack (id, created, updated, name) FROM stdin;
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
-- Data for Name: maasserver_refreshtoken; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_refreshtoken (id, created, updated, token, expires_at, user_id) FROM stdin;
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
-- Data for Name: maasserver_reservedip; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_reservedip (id, created, updated, ip, mac_address, comment, subnet_id) FROM stdin;
\.


--
-- Data for Name: maasserver_resourcepool; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_resourcepool (id, created, updated, name, description) FROM stdin;
0	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	default	Default pool
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

COPY public.maasserver_sshkey (id, created, updated, key, user_id, auth_id, protocol) FROM stdin;
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

COPY public.maasserver_userprofile (id, user_id, completed_intro, auth_last_check, is_local, provider_id) FROM stdin;
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
1	2025-10-17 10:15:20.69894+00	2025-10-17 10:15:20.69894+00	default	
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
-- Data for Name: nexus_incoming_services; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.nexus_incoming_services (service_id, data, data_encoding, version) FROM stdin;
\.


--
-- Data for Name: nexus_incoming_services_partition_status; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.nexus_incoming_services_partition_status (id, version) FROM stdin;
\.


--
-- Data for Name: queue; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.queue (queue_type, message_id, message_payload, message_encoding) FROM stdin;
\.


--
-- Data for Name: queue_messages; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.queue_messages (queue_type, queue_name, queue_partition, message_id, message_payload, message_encoding) FROM stdin;
\.


--
-- Data for Name: queue_metadata; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.queue_metadata (queue_type, data, data_encoding, version) FROM stdin;
\.


--
-- Data for Name: queues; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.queues (queue_type, queue_name, metadata_payload, metadata_encoding) FROM stdin;
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
0	2025	10	2025-10-17 10:15:21.630672	initial version		0.0	0
0	2025	10	2025-10-17 10:15:21.71186	base version of schema	55b84ca114ac34d84bdc5f52c198fa33	1.0	0.0
0	2025	10	2025-10-17 10:15:21.712639	schema update for cluster metadata	58f06841bbb187cb210db32a090c21ee	1.1	1.0
0	2025	10	2025-10-17 10:15:21.713076	schema update for RPC replication	c6bdeea21882e2625038927a84929b16	1.2	1.1
0	2025	10	2025-10-17 10:15:21.714234	schema update for kafka deprecation	3beee7d470421674194475f94b58d89b	1.3	1.2
0	2025	10	2025-10-17 10:15:21.714835	schema update for cluster metadata cleanup	c53e2e9cea5660c8a1f3b2ac73cdb138	1.4	1.3
0	2025	10	2025-10-17 10:15:21.715872	schema update for cluster_membership, executions and history_node tables	bfb307ba10ac0fdec83e0065dc5ffee4	1.5	1.4
0	2025	10	2025-10-17 10:15:21.716261	schema update for queue_metadata	978e1a6500d377ba91c6e37e5275a59b	1.6	1.5
0	2025	10	2025-10-17 10:15:21.718475	create cluster metadata info table to store cluster information and executions to store tiered storage queue	366b8b49d6701a6a09778e51ad1682ed	1.7	1.6
0	2025	10	2025-10-17 10:15:21.720414	drop unused tasks table; Expand VARCHAR columns governed by maxIDLength to VARCHAR(255)	229846b5beb0b96f49e7a3c5fde09fa7	1.8	1.7
0	2025	10	2025-10-17 10:15:21.724153	add history tasks table	b62e4e5826967e152e00b75da42d12ea	1.9	1.8
0	2025	10	2025-10-17 10:15:21.728194	add storage for update records and create task_queue_user_data table	2b0c361b0d4ab7cf09ead5566f0db520	1.10	1.9
0	2025	10	2025-10-17 10:15:21.731854	add queues and queue_messages tables	790ad04897813446f2953f5bd174ad9e	1.11	1.10
0	2025	10	2025-10-17 10:15:21.734291	add storage for Nexus incoming service records and create nexus_incoming_services and nexus_incoming_services_partition_status tables	9a9c378fc124da5a172f8229872bd24c	1.12	1.11
\.


--
-- Data for Name: schema_version; Type: TABLE DATA; Schema: temporal; Owner: -
--

COPY temporal.schema_version (version_partition, db_name, creation_time, curr_version, min_compatible_version) FROM stdin;
0	maas	2025-10-17 10:15:21.734054	1.12	1.0
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

COPY temporal_visibility.executions_visibility (namespace_id, run_id, start_time, execution_time, workflow_id, workflow_type_name, status, close_time, history_length, memo, encoding, task_queue, search_attributes, history_size_bytes, execution_duration, state_transition_count, parent_workflow_id, parent_run_id, root_workflow_id, root_run_id) FROM stdin;
\.


--
-- Data for Name: schema_update_history; Type: TABLE DATA; Schema: temporal_visibility; Owner: -
--

COPY temporal_visibility.schema_update_history (version_partition, year, month, update_time, description, manifest_md5, new_version, old_version) FROM stdin;
0	2025	10	2025-10-17 10:15:21.661454	initial version		0.0	0
0	2025	10	2025-10-17 10:15:21.761802	base version of visibility schema	6a739dc4ceb78e29e490cd7cef662a80	1.0	0.0
0	2025	10	2025-10-17 10:15:21.762637	add close time & status index	3bc835a57de6e863cf545c25aa418aa3	1.1	1.0
0	2025	10	2025-10-17 10:15:21.81479	update schema to support advanced visibility	3943d27399fe3df0f1be869a4982c0bb	1.2	1.1
0	2025	10	2025-10-17 10:15:21.8283	add history size bytes and build IDs visibility columns and indices	62928bdd9093a8c18bb4a39bfe8e3a22	1.3	1.2
0	2025	10	2025-10-17 10:15:21.832585	add execution duration, state transition count and parent workflow info columns, and indices	c28266b8b78448f2fefb507a74c7dcdf	1.4	1.3
0	2025	10	2025-10-17 10:15:21.834606	add root workflow info columns and indices	f8da72ec53ef81b85988465e08b20319	1.5	1.4
0	2025	10	2025-10-17 10:15:21.837935	fix root workflow info columns	0cf22b219b64b4c76988c616e2c776de	1.6	1.5
\.


--
-- Data for Name: schema_version; Type: TABLE DATA; Schema: temporal_visibility; Owner: -
--

COPY temporal_visibility.schema_version (version_partition, db_name, creation_time, curr_version, min_compatible_version) FROM stdin;
0	maas	2025-10-17 10:15:21.837718	1.6	0.1
\.


--
-- Name: goose_app_db_version_id_seq; Type: SEQUENCE SET; Schema: openfga; Owner: -
--

SELECT pg_catalog.setval('openfga.goose_app_db_version_id_seq', 3, true);


--
-- Name: goose_db_version_id_seq; Type: SEQUENCE SET; Schema: openfga; Owner: -
--

SELECT pg_catalog.setval('openfga.goose_db_version_id_seq', 7, true);


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

SELECT pg_catalog.setval('public.auth_permission_id_seq', 444, true);


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

SELECT pg_catalog.setval('public.django_content_type_id_seq', 111, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 396, true);


--
-- Name: django_site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_site_id_seq', 1, true);


--
-- Name: maasserver_agent_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_agent_id_seq', 1, false);


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
-- Name: maasserver_bootsourceselection_id_seq1; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootsourceselection_id_seq1', 1, false);


--
-- Name: maasserver_bootstraptoken_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_bootstraptoken_id_seq', 1, false);


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
-- Name: maasserver_nodemetadata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_nodemetadata_id_seq', 1, false);


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
-- Name: maasserver_oidc_provider_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_oidc_provider_id_seq', 1, false);


--
-- Name: maasserver_oidcrevokedtoken_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_oidcrevokedtoken_id_seq', 1, false);


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
-- Name: maasserver_rack_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_rack_id_seq', 1, false);


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
-- Name: maasserver_refreshtoken_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_refreshtoken_id_seq', 1, false);


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
-- Name: maasserver_reservedip_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_reservedip_id_seq', 1, false);


--
-- Name: maasserver_resourcepool_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_resourcepool_id_seq', 1, false);


--
-- Name: maasserver_rootkey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_rootkey_id_seq', 1, false);


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

SELECT pg_catalog.setval('public.maasserver_vlan_id_seq', 5001, false);


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

SELECT pg_catalog.setval('public.maasserver_zone_serial_seq', 1, true);


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
-- Name: assertion assertion_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.assertion
    ADD CONSTRAINT assertion_pkey PRIMARY KEY (store, authorization_model_id);


--
-- Name: authorization_model authorization_model_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.authorization_model
    ADD CONSTRAINT authorization_model_pkey PRIMARY KEY (store, authorization_model_id, type);


--
-- Name: changelog changelog_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.changelog
    ADD CONSTRAINT changelog_pkey PRIMARY KEY (store, ulid, object_type);


--
-- Name: goose_app_db_version goose_app_db_version_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.goose_app_db_version
    ADD CONSTRAINT goose_app_db_version_pkey PRIMARY KEY (id);


--
-- Name: goose_db_version goose_db_version_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.goose_db_version
    ADD CONSTRAINT goose_db_version_pkey PRIMARY KEY (id);


--
-- Name: store store_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.store
    ADD CONSTRAINT store_pkey PRIMARY KEY (id);


--
-- Name: tuple tuple_pkey; Type: CONSTRAINT; Schema: openfga; Owner: -
--

ALTER TABLE ONLY openfga.tuple
    ADD CONSTRAINT tuple_pkey PRIMARY KEY (store, object_type, object_id, relation, _user);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


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
-- Name: maasserver_agent maasserver_agent_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_agent
    ADD CONSTRAINT maasserver_agent_pkey PRIMARY KEY (id);


--
-- Name: maasserver_agent maasserver_agent_rack_id_rackcontroller_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_agent
    ADD CONSTRAINT maasserver_agent_rack_id_rackcontroller_id_key UNIQUE (rack_id, rackcontroller_id);


--
-- Name: maasserver_agent maasserver_agent_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_agent
    ADD CONSTRAINT maasserver_agent_uuid_key UNIQUE (uuid);


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
-- Name: maasserver_bootsource maasserver_bootsource_priority_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsource
    ADD CONSTRAINT maasserver_bootsource_priority_key UNIQUE (priority);


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
-- Name: maasserver_bootsourceselectionlegacy maasserver_bootsourcesel_boot_source_id_os_releas_0b0d402c_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselectionlegacy
    ADD CONSTRAINT maasserver_bootsourcesel_boot_source_id_os_releas_0b0d402c_uniq UNIQUE (boot_source_id, os, release);


--
-- Name: maasserver_bootsourceselection maasserver_bootsourceselectio_os_release_arch_boot_source_i_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselectio_os_release_arch_boot_source_i_key UNIQUE (os, release, arch, boot_source_id);


--
-- Name: maasserver_bootsourceselectionlegacy maasserver_bootsourceselection_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselectionlegacy
    ADD CONSTRAINT maasserver_bootsourceselection_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootsourceselection maasserver_bootsourceselection_pkey1; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_pkey1 PRIMARY KEY (id);


--
-- Name: maasserver_bootstraptoken maasserver_bootstraptoken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootstraptoken
    ADD CONSTRAINT maasserver_bootstraptoken_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootstraptoken maasserver_bootstraptoken_secret_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootstraptoken
    ADD CONSTRAINT maasserver_bootstraptoken_secret_key UNIQUE (secret);


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
-- Name: maasserver_imagemanifest maasserver_imagemanifest_boot_source_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_imagemanifest
    ADD CONSTRAINT maasserver_imagemanifest_boot_source_id_key UNIQUE (boot_source_id);


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
-- Name: maasserver_oidc_provider maasserver_oidc_provider_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_oidc_provider
    ADD CONSTRAINT maasserver_oidc_provider_name_key UNIQUE (name);


--
-- Name: maasserver_oidc_provider maasserver_oidc_provider_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_oidc_provider
    ADD CONSTRAINT maasserver_oidc_provider_pkey PRIMARY KEY (id);


--
-- Name: maasserver_oidcrevokedtoken maasserver_oidcrevokedtoken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_oidcrevokedtoken
    ADD CONSTRAINT maasserver_oidcrevokedtoken_pkey PRIMARY KEY (id);


--
-- Name: maasserver_oidcrevokedtoken maasserver_oidcrevokedtoken_token_hash_provider_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_oidcrevokedtoken
    ADD CONSTRAINT maasserver_oidcrevokedtoken_token_hash_provider_id_key UNIQUE (token_hash, provider_id);


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
-- Name: maasserver_rack maasserver_rack_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rack
    ADD CONSTRAINT maasserver_rack_name_key UNIQUE (name);


--
-- Name: maasserver_rack maasserver_rack_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rack
    ADD CONSTRAINT maasserver_rack_pkey PRIMARY KEY (id);


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
-- Name: maasserver_refreshtoken maasserver_refreshtoken_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_refreshtoken
    ADD CONSTRAINT maasserver_refreshtoken_pkey PRIMARY KEY (id);


--
-- Name: maasserver_refreshtoken maasserver_refreshtoken_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_refreshtoken
    ADD CONSTRAINT maasserver_refreshtoken_token_key UNIQUE (token);


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
-- Name: maasserver_reservedip maasserver_reservedip_ip_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_reservedip
    ADD CONSTRAINT maasserver_reservedip_ip_key UNIQUE (ip);


--
-- Name: maasserver_reservedip maasserver_reservedip_mac_address_subnet_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_reservedip
    ADD CONSTRAINT maasserver_reservedip_mac_address_subnet_uniq UNIQUE (mac_address, subnet_id);


--
-- Name: maasserver_reservedip maasserver_reservedip_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_reservedip
    ADD CONSTRAINT maasserver_reservedip_pkey PRIMARY KEY (id);


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
-- Name: maasserver_nodeuserdata metadataserver_nodeuserdata_node_id_for_ephemeral_environment_k; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_node_id_for_ephemeral_environment_k UNIQUE (node_id, for_ephemeral_environment);


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
-- Name: nexus_incoming_services_partition_status nexus_incoming_services_partition_status_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.nexus_incoming_services_partition_status
    ADD CONSTRAINT nexus_incoming_services_partition_status_pkey PRIMARY KEY (id);


--
-- Name: nexus_incoming_services nexus_incoming_services_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.nexus_incoming_services
    ADD CONSTRAINT nexus_incoming_services_pkey PRIMARY KEY (service_id);


--
-- Name: queue_messages queue_messages_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.queue_messages
    ADD CONSTRAINT queue_messages_pkey PRIMARY KEY (queue_type, queue_name, queue_partition, message_id);


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
-- Name: queues queues_pkey; Type: CONSTRAINT; Schema: temporal; Owner: -
--

ALTER TABLE ONLY temporal.queues
    ADD CONSTRAINT queues_pkey PRIMARY KEY (queue_type, queue_name);


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
-- Name: idx_tuple_partial_user; Type: INDEX; Schema: openfga; Owner: -
--

CREATE INDEX idx_tuple_partial_user ON openfga.tuple USING btree (store, object_type, object_id, relation, _user) WHERE (user_type = 'user'::text);


--
-- Name: idx_tuple_partial_userset; Type: INDEX; Schema: openfga; Owner: -
--

CREATE INDEX idx_tuple_partial_userset ON openfga.tuple USING btree (store, object_type, object_id, relation, _user) WHERE (user_type = 'userset'::text);


--
-- Name: idx_tuple_ulid; Type: INDEX; Schema: openfga; Owner: -
--

CREATE UNIQUE INDEX idx_tuple_ulid ON openfga.tuple USING btree (ulid);


--
-- Name: idx_user_lookup; Type: INDEX; Schema: openfga; Owner: -
--

CREATE INDEX idx_user_lookup ON openfga.tuple USING btree (store, _user, relation, object_type, object_id COLLATE "C");


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

CREATE INDEX maasserver_bootsourceselection_boot_source_id_b911aa0f ON public.maasserver_bootsourceselectionlegacy USING btree (boot_source_id);


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
-- Name: maasserver_node_current_deployment_script_set_id_0013; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_deployment_script_set_id_0013 ON public.maasserver_node USING btree (current_deployment_script_set_id);


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
-- Name: maasserver_oidcrevokedtoken_provider_id_3d1f3f6b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_oidcrevokedtoken_provider_id_3d1f3f6b ON public.maasserver_oidcrevokedtoken USING btree (provider_id);


--
-- Name: maasserver_oidcrevokedtoken_user_email_5f4d1d18; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_oidcrevokedtoken_user_email_5f4d1d18 ON public.maasserver_oidcrevokedtoken USING btree (user_email);


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
-- Name: maasserver_refreshtoken_user_id_5f4d1d1a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_refreshtoken_user_id_5f4d1d1a ON public.maasserver_refreshtoken USING btree (user_id);


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
-- Name: maasserver_reservedip_subnet_id_548dd59f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_reservedip_subnet_id_548dd59f ON public.maasserver_reservedip USING btree (subnet_id);


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
-- Name: by_execution_duration; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_execution_duration ON temporal_visibility.executions_visibility USING btree (namespace_id, execution_duration, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


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
-- Name: by_parent_run_id; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_parent_run_id ON temporal_visibility.executions_visibility USING btree (namespace_id, parent_run_id, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_parent_workflow_id; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_parent_workflow_id ON temporal_visibility.executions_visibility USING btree (namespace_id, parent_workflow_id, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_root_run_id; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_root_run_id ON temporal_visibility.executions_visibility USING btree (namespace_id, root_run_id, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_root_workflow_id; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_root_workflow_id ON temporal_visibility.executions_visibility USING btree (namespace_id, root_workflow_id, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


--
-- Name: by_state_transition_count; Type: INDEX; Schema: temporal_visibility; Owner: -
--

CREATE INDEX by_state_transition_count ON temporal_visibility.executions_visibility USING btree (namespace_id, state_transition_count, COALESCE(close_time, '9999-12-31 23:59:59'::timestamp without time zone) DESC, start_time DESC, run_id);


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
-- Name: maasserver_blockdevice blockdevice_nd_blockdevice_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER blockdevice_nd_blockdevice_link_notify AFTER INSERT ON public.maasserver_blockdevice FOR EACH ROW EXECUTE FUNCTION public.nd_blockdevice_link_notify();


--
-- Name: maasserver_blockdevice blockdevice_nd_blockdevice_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER blockdevice_nd_blockdevice_unlink_notify AFTER DELETE ON public.maasserver_blockdevice FOR EACH ROW EXECUTE FUNCTION public.nd_blockdevice_unlink_notify();


--
-- Name: maasserver_blockdevice blockdevice_nd_blockdevice_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER blockdevice_nd_blockdevice_update_notify AFTER UPDATE ON public.maasserver_blockdevice FOR EACH ROW EXECUTE FUNCTION public.nd_blockdevice_update_notify();


--
-- Name: maasserver_bmc bmc_bmc_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bmc_bmc_machine_update_notify AFTER UPDATE ON public.maasserver_bmc FOR EACH ROW EXECUTE FUNCTION public.bmc_machine_update_notify();


--
-- Name: maasserver_bmc bmc_pod_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bmc_pod_delete_notify AFTER DELETE ON public.maasserver_bmc FOR EACH ROW EXECUTE FUNCTION public.pod_delete_notify();


--
-- Name: maasserver_bmc bmc_pod_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bmc_pod_insert_notify AFTER INSERT ON public.maasserver_bmc FOR EACH ROW EXECUTE FUNCTION public.pod_insert_notify();


--
-- Name: maasserver_bmc bmc_pod_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER bmc_pod_update_notify AFTER UPDATE ON public.maasserver_bmc FOR EACH ROW EXECUTE FUNCTION public.pod_update_notify();


--
-- Name: maasserver_cacheset cacheset_nd_cacheset_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER cacheset_nd_cacheset_link_notify AFTER INSERT ON public.maasserver_cacheset FOR EACH ROW EXECUTE FUNCTION public.nd_cacheset_link_notify();


--
-- Name: maasserver_cacheset cacheset_nd_cacheset_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER cacheset_nd_cacheset_unlink_notify AFTER DELETE ON public.maasserver_cacheset FOR EACH ROW EXECUTE FUNCTION public.nd_cacheset_unlink_notify();


--
-- Name: maasserver_cacheset cacheset_nd_cacheset_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER cacheset_nd_cacheset_update_notify AFTER UPDATE ON public.maasserver_cacheset FOR EACH ROW EXECUTE FUNCTION public.nd_cacheset_update_notify();


--
-- Name: maasserver_config config_sys_proxy_config_use_peer_proxy_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER config_sys_proxy_config_use_peer_proxy_insert AFTER INSERT ON public.maasserver_config FOR EACH ROW EXECUTE FUNCTION public.sys_proxy_config_use_peer_proxy_insert();


--
-- Name: maasserver_config config_sys_proxy_config_use_peer_proxy_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER config_sys_proxy_config_use_peer_proxy_update AFTER UPDATE ON public.maasserver_config FOR EACH ROW EXECUTE FUNCTION public.sys_proxy_config_use_peer_proxy_update();


--
-- Name: maasserver_controllerinfo controllerinfo_controllerinfo_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER controllerinfo_controllerinfo_link_notify AFTER INSERT ON public.maasserver_controllerinfo FOR EACH ROW EXECUTE FUNCTION public.controllerinfo_link_notify();


--
-- Name: maasserver_controllerinfo controllerinfo_controllerinfo_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER controllerinfo_controllerinfo_unlink_notify AFTER DELETE ON public.maasserver_controllerinfo FOR EACH ROW EXECUTE FUNCTION public.controllerinfo_unlink_notify();


--
-- Name: maasserver_controllerinfo controllerinfo_controllerinfo_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER controllerinfo_controllerinfo_update_notify AFTER UPDATE ON public.maasserver_controllerinfo FOR EACH ROW EXECUTE FUNCTION public.controllerinfo_update_notify();


--
-- Name: maasserver_dhcpsnippet dhcpsnippet_dhcpsnippet_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dhcpsnippet_dhcpsnippet_create_notify AFTER INSERT ON public.maasserver_dhcpsnippet FOR EACH ROW EXECUTE FUNCTION public.dhcpsnippet_create_notify();


--
-- Name: maasserver_dhcpsnippet dhcpsnippet_dhcpsnippet_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dhcpsnippet_dhcpsnippet_delete_notify AFTER DELETE ON public.maasserver_dhcpsnippet FOR EACH ROW EXECUTE FUNCTION public.dhcpsnippet_delete_notify();


--
-- Name: maasserver_dhcpsnippet dhcpsnippet_dhcpsnippet_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dhcpsnippet_dhcpsnippet_update_notify AFTER UPDATE ON public.maasserver_dhcpsnippet FOR EACH ROW EXECUTE FUNCTION public.dhcpsnippet_update_notify();


--
-- Name: maasserver_dnsdata dnsdata_dnsdata_domain_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsdata_dnsdata_domain_delete_notify AFTER DELETE ON public.maasserver_dnsdata FOR EACH ROW EXECUTE FUNCTION public.dnsdata_domain_delete_notify();


--
-- Name: maasserver_dnsdata dnsdata_dnsdata_domain_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsdata_dnsdata_domain_insert_notify AFTER INSERT ON public.maasserver_dnsdata FOR EACH ROW EXECUTE FUNCTION public.dnsdata_domain_insert_notify();


--
-- Name: maasserver_dnsdata dnsdata_dnsdata_domain_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsdata_dnsdata_domain_update_notify AFTER UPDATE ON public.maasserver_dnsdata FOR EACH ROW EXECUTE FUNCTION public.dnsdata_domain_update_notify();


--
-- Name: maasserver_dnsresource dnsresource_dnsresource_domain_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsresource_dnsresource_domain_delete_notify AFTER DELETE ON public.maasserver_dnsresource FOR EACH ROW EXECUTE FUNCTION public.dnsresource_domain_delete_notify();


--
-- Name: maasserver_dnsresource dnsresource_dnsresource_domain_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsresource_dnsresource_domain_insert_notify AFTER INSERT ON public.maasserver_dnsresource FOR EACH ROW EXECUTE FUNCTION public.dnsresource_domain_insert_notify();


--
-- Name: maasserver_dnsresource dnsresource_dnsresource_domain_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsresource_dnsresource_domain_update_notify AFTER UPDATE ON public.maasserver_dnsresource FOR EACH ROW EXECUTE FUNCTION public.dnsresource_domain_update_notify();


--
-- Name: maasserver_dnsresource_ip_addresses dnsresource_ip_addresses_rrset_sipaddress_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsresource_ip_addresses_rrset_sipaddress_link_notify AFTER INSERT ON public.maasserver_dnsresource_ip_addresses FOR EACH ROW EXECUTE FUNCTION public.rrset_sipaddress_link_notify();


--
-- Name: maasserver_dnsresource_ip_addresses dnsresource_ip_addresses_rrset_sipaddress_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER dnsresource_ip_addresses_rrset_sipaddress_unlink_notify AFTER DELETE ON public.maasserver_dnsresource_ip_addresses FOR EACH ROW EXECUTE FUNCTION public.rrset_sipaddress_unlink_notify();


--
-- Name: maasserver_domain domain_domain_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER domain_domain_create_notify AFTER INSERT ON public.maasserver_domain FOR EACH ROW EXECUTE FUNCTION public.domain_create_notify();


--
-- Name: maasserver_domain domain_domain_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER domain_domain_delete_notify AFTER DELETE ON public.maasserver_domain FOR EACH ROW EXECUTE FUNCTION public.domain_delete_notify();


--
-- Name: maasserver_domain domain_domain_node_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER domain_domain_node_update_notify AFTER UPDATE ON public.maasserver_domain FOR EACH ROW EXECUTE FUNCTION public.domain_node_update_notify();


--
-- Name: maasserver_domain domain_domain_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER domain_domain_update_notify AFTER UPDATE ON public.maasserver_domain FOR EACH ROW EXECUTE FUNCTION public.domain_update_notify();


--
-- Name: maasserver_event event_event_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER event_event_create_notify AFTER INSERT ON public.maasserver_event FOR EACH ROW EXECUTE FUNCTION public.event_create_notify();


--
-- Name: maasserver_event event_event_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER event_event_machine_update_notify AFTER INSERT ON public.maasserver_event FOR EACH ROW EXECUTE FUNCTION public.event_machine_update_notify();


--
-- Name: maasserver_fabric fabric_fabric_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER fabric_fabric_create_notify AFTER INSERT ON public.maasserver_fabric FOR EACH ROW EXECUTE FUNCTION public.fabric_create_notify();


--
-- Name: maasserver_fabric fabric_fabric_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER fabric_fabric_delete_notify AFTER DELETE ON public.maasserver_fabric FOR EACH ROW EXECUTE FUNCTION public.fabric_delete_notify();


--
-- Name: maasserver_fabric fabric_fabric_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER fabric_fabric_machine_update_notify AFTER UPDATE ON public.maasserver_fabric FOR EACH ROW EXECUTE FUNCTION public.fabric_machine_update_notify();


--
-- Name: maasserver_fabric fabric_fabric_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER fabric_fabric_update_notify AFTER UPDATE ON public.maasserver_fabric FOR EACH ROW EXECUTE FUNCTION public.fabric_update_notify();


--
-- Name: maasserver_filesystem filesystem_nd_filesystem_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER filesystem_nd_filesystem_link_notify AFTER INSERT ON public.maasserver_filesystem FOR EACH ROW EXECUTE FUNCTION public.nd_filesystem_link_notify();


--
-- Name: maasserver_filesystem filesystem_nd_filesystem_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER filesystem_nd_filesystem_unlink_notify AFTER DELETE ON public.maasserver_filesystem FOR EACH ROW EXECUTE FUNCTION public.nd_filesystem_unlink_notify();


--
-- Name: maasserver_filesystem filesystem_nd_filesystem_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER filesystem_nd_filesystem_update_notify AFTER UPDATE ON public.maasserver_filesystem FOR EACH ROW EXECUTE FUNCTION public.nd_filesystem_update_notify();


--
-- Name: maasserver_filesystemgroup filesystemgroup_nd_filesystemgroup_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER filesystemgroup_nd_filesystemgroup_link_notify AFTER INSERT ON public.maasserver_filesystemgroup FOR EACH ROW EXECUTE FUNCTION public.nd_filesystemgroup_link_notify();


--
-- Name: maasserver_filesystemgroup filesystemgroup_nd_filesystemgroup_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER filesystemgroup_nd_filesystemgroup_unlink_notify AFTER DELETE ON public.maasserver_filesystemgroup FOR EACH ROW EXECUTE FUNCTION public.nd_filesystemgroup_unlink_notify();


--
-- Name: maasserver_filesystemgroup filesystemgroup_nd_filesystemgroup_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER filesystemgroup_nd_filesystemgroup_update_notify AFTER UPDATE ON public.maasserver_filesystemgroup FOR EACH ROW EXECUTE FUNCTION public.nd_filesystemgroup_update_notify();


--
-- Name: maasserver_interface interface_interface_pod_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_interface_pod_notify AFTER INSERT OR DELETE OR UPDATE ON public.maasserver_interface FOR EACH ROW EXECUTE FUNCTION public.interface_pod_notify();


--
-- Name: maasserver_interface_ip_addresses interface_ip_addresses_nd_sipaddress_dns_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_ip_addresses_nd_sipaddress_dns_link_notify AFTER INSERT ON public.maasserver_interface_ip_addresses FOR EACH ROW EXECUTE FUNCTION public.nd_sipaddress_dns_link_notify();


--
-- Name: maasserver_interface_ip_addresses interface_ip_addresses_nd_sipaddress_dns_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_ip_addresses_nd_sipaddress_dns_unlink_notify AFTER DELETE ON public.maasserver_interface_ip_addresses FOR EACH ROW EXECUTE FUNCTION public.nd_sipaddress_dns_unlink_notify();


--
-- Name: maasserver_interface_ip_addresses interface_ip_addresses_nd_sipaddress_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_ip_addresses_nd_sipaddress_link_notify AFTER INSERT ON public.maasserver_interface_ip_addresses FOR EACH ROW EXECUTE FUNCTION public.nd_sipaddress_link_notify();


--
-- Name: maasserver_interface_ip_addresses interface_ip_addresses_nd_sipaddress_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_ip_addresses_nd_sipaddress_unlink_notify AFTER DELETE ON public.maasserver_interface_ip_addresses FOR EACH ROW EXECUTE FUNCTION public.nd_sipaddress_unlink_notify();


--
-- Name: maasserver_interface interface_nd_interface_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_nd_interface_link_notify AFTER INSERT ON public.maasserver_interface FOR EACH ROW EXECUTE FUNCTION public.nd_interface_link_notify();


--
-- Name: maasserver_interface interface_nd_interface_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_nd_interface_unlink_notify AFTER DELETE ON public.maasserver_interface FOR EACH ROW EXECUTE FUNCTION public.nd_interface_unlink_notify();


--
-- Name: maasserver_interface interface_nd_interface_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER interface_nd_interface_update_notify AFTER UPDATE ON public.maasserver_interface FOR EACH ROW EXECUTE FUNCTION public.nd_interface_update_notify();


--
-- Name: maasserver_iprange iprange_iprange_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER iprange_iprange_create_notify AFTER INSERT ON public.maasserver_iprange FOR EACH ROW EXECUTE FUNCTION public.iprange_create_notify();


--
-- Name: maasserver_iprange iprange_iprange_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER iprange_iprange_delete_notify AFTER DELETE ON public.maasserver_iprange FOR EACH ROW EXECUTE FUNCTION public.iprange_delete_notify();


--
-- Name: maasserver_iprange iprange_iprange_subnet_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER iprange_iprange_subnet_delete_notify AFTER DELETE ON public.maasserver_iprange FOR EACH ROW EXECUTE FUNCTION public.iprange_subnet_delete_notify();


--
-- Name: maasserver_iprange iprange_iprange_subnet_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER iprange_iprange_subnet_insert_notify AFTER INSERT ON public.maasserver_iprange FOR EACH ROW EXECUTE FUNCTION public.iprange_subnet_insert_notify();


--
-- Name: maasserver_iprange iprange_iprange_subnet_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER iprange_iprange_subnet_update_notify AFTER UPDATE ON public.maasserver_iprange FOR EACH ROW EXECUTE FUNCTION public.iprange_subnet_update_notify();


--
-- Name: maasserver_iprange iprange_iprange_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER iprange_iprange_update_notify AFTER UPDATE ON public.maasserver_iprange FOR EACH ROW EXECUTE FUNCTION public.iprange_update_notify();


--
-- Name: maasserver_neighbour neighbour_neighbour_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER neighbour_neighbour_create_notify AFTER INSERT ON public.maasserver_neighbour FOR EACH ROW EXECUTE FUNCTION public.neighbour_create_notify();


--
-- Name: maasserver_neighbour neighbour_neighbour_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER neighbour_neighbour_delete_notify AFTER DELETE ON public.maasserver_neighbour FOR EACH ROW EXECUTE FUNCTION public.neighbour_delete_notify();


--
-- Name: maasserver_neighbour neighbour_neighbour_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER neighbour_neighbour_update_notify AFTER UPDATE ON public.maasserver_neighbour FOR EACH ROW EXECUTE FUNCTION public.neighbour_update_notify();


--
-- Name: maasserver_node node_device_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_device_create_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW WHEN ((new.node_type = 1)) EXECUTE FUNCTION public.device_create_notify();


--
-- Name: maasserver_node node_device_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_device_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW WHEN ((old.node_type = 1)) EXECUTE FUNCTION public.device_delete_notify();


--
-- Name: maasserver_node node_device_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_device_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN (((new.node_type = 1) AND (((new.architecture)::text IS DISTINCT FROM (old.architecture)::text) OR (new.bmc_id IS DISTINCT FROM old.bmc_id) OR (new.cpu_count IS DISTINCT FROM old.cpu_count) OR (new.cpu_speed IS DISTINCT FROM old.cpu_speed) OR (new.current_commissioning_script_set_id IS DISTINCT FROM old.current_commissioning_script_set_id) OR (new.current_installation_script_set_id IS DISTINCT FROM old.current_installation_script_set_id) OR (new.current_testing_script_set_id IS DISTINCT FROM old.current_testing_script_set_id) OR (new.description IS DISTINCT FROM old.description) OR ((new.distro_series)::text IS DISTINCT FROM (old.distro_series)::text) OR (new.domain_id IS DISTINCT FROM old.domain_id) OR ((new.error)::text IS DISTINCT FROM (old.error)::text) OR ((new.hostname)::text IS DISTINCT FROM (old.hostname)::text) OR ((new.hwe_kernel)::text IS DISTINCT FROM (old.hwe_kernel)::text) OR (new.instance_power_parameters IS DISTINCT FROM old.instance_power_parameters) OR (new.last_image_sync IS DISTINCT FROM old.last_image_sync) OR ((new.license_key)::text IS DISTINCT FROM (old.license_key)::text) OR (new.locked IS DISTINCT FROM old.locked) OR ((new.min_hwe_kernel)::text IS DISTINCT FROM (old.min_hwe_kernel)::text) OR ((new.osystem)::text IS DISTINCT FROM (old.osystem)::text) OR (new.owner_id IS DISTINCT FROM old.owner_id) OR (new.parent_id IS DISTINCT FROM old.parent_id) OR (new.pool_id IS DISTINCT FROM old.pool_id) OR ((new.power_state)::text IS DISTINCT FROM (old.power_state)::text) OR (new.status IS DISTINCT FROM old.status) OR (new.swap_size IS DISTINCT FROM old.swap_size) OR (new.zone_id IS DISTINCT FROM old.zone_id)))) EXECUTE FUNCTION public.device_update_notify();


--
-- Name: maasserver_node node_machine_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_machine_create_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW WHEN ((new.node_type = 0)) EXECUTE FUNCTION public.machine_create_notify();


--
-- Name: maasserver_node node_machine_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_machine_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW WHEN ((old.node_type = 0)) EXECUTE FUNCTION public.machine_delete_notify();


--
-- Name: maasserver_node node_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_machine_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN (((new.node_type = 0) AND (((new.architecture)::text IS DISTINCT FROM (old.architecture)::text) OR (new.bmc_id IS DISTINCT FROM old.bmc_id) OR (new.cpu_count IS DISTINCT FROM old.cpu_count) OR (new.cpu_speed IS DISTINCT FROM old.cpu_speed) OR (new.current_commissioning_script_set_id IS DISTINCT FROM old.current_commissioning_script_set_id) OR (new.current_installation_script_set_id IS DISTINCT FROM old.current_installation_script_set_id) OR (new.current_testing_script_set_id IS DISTINCT FROM old.current_testing_script_set_id) OR (new.description IS DISTINCT FROM old.description) OR ((new.distro_series)::text IS DISTINCT FROM (old.distro_series)::text) OR (new.domain_id IS DISTINCT FROM old.domain_id) OR ((new.error)::text IS DISTINCT FROM (old.error)::text) OR ((new.hostname)::text IS DISTINCT FROM (old.hostname)::text) OR ((new.hwe_kernel)::text IS DISTINCT FROM (old.hwe_kernel)::text) OR (new.instance_power_parameters IS DISTINCT FROM old.instance_power_parameters) OR (new.last_image_sync IS DISTINCT FROM old.last_image_sync) OR ((new.license_key)::text IS DISTINCT FROM (old.license_key)::text) OR (new.locked IS DISTINCT FROM old.locked) OR ((new.min_hwe_kernel)::text IS DISTINCT FROM (old.min_hwe_kernel)::text) OR ((new.osystem)::text IS DISTINCT FROM (old.osystem)::text) OR (new.owner_id IS DISTINCT FROM old.owner_id) OR (new.parent_id IS DISTINCT FROM old.parent_id) OR (new.pool_id IS DISTINCT FROM old.pool_id) OR ((new.power_state)::text IS DISTINCT FROM (old.power_state)::text) OR (new.status IS DISTINCT FROM old.status) OR (new.swap_size IS DISTINCT FROM old.swap_size) OR (new.zone_id IS DISTINCT FROM old.zone_id)))) EXECUTE FUNCTION public.machine_update_notify();


--
-- Name: maasserver_node node_node_pod_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_pod_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW EXECUTE FUNCTION public.node_pod_delete_notify();


--
-- Name: maasserver_node node_node_pod_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_pod_insert_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW EXECUTE FUNCTION public.node_pod_insert_notify();


--
-- Name: maasserver_node node_node_pod_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_pod_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN ((((new.architecture)::text IS DISTINCT FROM (old.architecture)::text) OR (new.bmc_id IS DISTINCT FROM old.bmc_id) OR (new.cpu_count IS DISTINCT FROM old.cpu_count) OR (new.cpu_speed IS DISTINCT FROM old.cpu_speed) OR (new.current_commissioning_script_set_id IS DISTINCT FROM old.current_commissioning_script_set_id) OR (new.current_installation_script_set_id IS DISTINCT FROM old.current_installation_script_set_id) OR (new.current_testing_script_set_id IS DISTINCT FROM old.current_testing_script_set_id) OR (new.description IS DISTINCT FROM old.description) OR ((new.distro_series)::text IS DISTINCT FROM (old.distro_series)::text) OR (new.domain_id IS DISTINCT FROM old.domain_id) OR ((new.error)::text IS DISTINCT FROM (old.error)::text) OR ((new.hostname)::text IS DISTINCT FROM (old.hostname)::text) OR ((new.hwe_kernel)::text IS DISTINCT FROM (old.hwe_kernel)::text) OR (new.instance_power_parameters IS DISTINCT FROM old.instance_power_parameters) OR (new.last_image_sync IS DISTINCT FROM old.last_image_sync) OR ((new.license_key)::text IS DISTINCT FROM (old.license_key)::text) OR (new.locked IS DISTINCT FROM old.locked) OR ((new.min_hwe_kernel)::text IS DISTINCT FROM (old.min_hwe_kernel)::text) OR ((new.osystem)::text IS DISTINCT FROM (old.osystem)::text) OR (new.owner_id IS DISTINCT FROM old.owner_id) OR (new.parent_id IS DISTINCT FROM old.parent_id) OR (new.pool_id IS DISTINCT FROM old.pool_id) OR ((new.power_state)::text IS DISTINCT FROM (old.power_state)::text) OR (new.status IS DISTINCT FROM old.status) OR (new.swap_size IS DISTINCT FROM old.swap_size) OR (new.zone_id IS DISTINCT FROM old.zone_id))) EXECUTE FUNCTION public.node_pod_update_notify();


--
-- Name: maasserver_node node_node_type_change_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_type_change_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN ((new.node_type IS DISTINCT FROM old.node_type)) EXECUTE FUNCTION public.node_type_change_notify();


--
-- Name: maasserver_node node_node_vmcluster_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_vmcluster_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW EXECUTE FUNCTION public.node_vmcluster_delete_notify();


--
-- Name: maasserver_node node_node_vmcluster_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_vmcluster_insert_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW EXECUTE FUNCTION public.node_vmcluster_insert_notify();


--
-- Name: maasserver_node node_node_vmcluster_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_node_vmcluster_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW EXECUTE FUNCTION public.node_vmcluster_update_notify();


--
-- Name: maasserver_node node_rack_controller_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_rack_controller_create_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW WHEN ((new.node_type = 2)) EXECUTE FUNCTION public.rack_controller_create_notify();


--
-- Name: maasserver_node node_rack_controller_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_rack_controller_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW WHEN ((old.node_type = 2)) EXECUTE FUNCTION public.rack_controller_delete_notify();


--
-- Name: maasserver_node node_rack_controller_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_rack_controller_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN (((new.node_type = 2) AND (((new.architecture)::text IS DISTINCT FROM (old.architecture)::text) OR (new.bmc_id IS DISTINCT FROM old.bmc_id) OR (new.cpu_count IS DISTINCT FROM old.cpu_count) OR (new.cpu_speed IS DISTINCT FROM old.cpu_speed) OR (new.current_commissioning_script_set_id IS DISTINCT FROM old.current_commissioning_script_set_id) OR (new.current_installation_script_set_id IS DISTINCT FROM old.current_installation_script_set_id) OR (new.current_testing_script_set_id IS DISTINCT FROM old.current_testing_script_set_id) OR (new.description IS DISTINCT FROM old.description) OR ((new.distro_series)::text IS DISTINCT FROM (old.distro_series)::text) OR (new.domain_id IS DISTINCT FROM old.domain_id) OR ((new.error)::text IS DISTINCT FROM (old.error)::text) OR ((new.hostname)::text IS DISTINCT FROM (old.hostname)::text) OR ((new.hwe_kernel)::text IS DISTINCT FROM (old.hwe_kernel)::text) OR (new.instance_power_parameters IS DISTINCT FROM old.instance_power_parameters) OR (new.last_image_sync IS DISTINCT FROM old.last_image_sync) OR ((new.license_key)::text IS DISTINCT FROM (old.license_key)::text) OR (new.locked IS DISTINCT FROM old.locked) OR ((new.min_hwe_kernel)::text IS DISTINCT FROM (old.min_hwe_kernel)::text) OR ((new.osystem)::text IS DISTINCT FROM (old.osystem)::text) OR (new.owner_id IS DISTINCT FROM old.owner_id) OR (new.parent_id IS DISTINCT FROM old.parent_id) OR (new.pool_id IS DISTINCT FROM old.pool_id) OR ((new.power_state)::text IS DISTINCT FROM (old.power_state)::text) OR (new.status IS DISTINCT FROM old.status) OR (new.swap_size IS DISTINCT FROM old.swap_size) OR (new.zone_id IS DISTINCT FROM old.zone_id)))) EXECUTE FUNCTION public.rack_controller_update_notify();


--
-- Name: maasserver_node node_region_and_rack_controller_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_region_and_rack_controller_create_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW WHEN ((new.node_type = 4)) EXECUTE FUNCTION public.region_and_rack_controller_create_notify();


--
-- Name: maasserver_node node_region_and_rack_controller_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_region_and_rack_controller_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW WHEN ((old.node_type = 4)) EXECUTE FUNCTION public.region_and_rack_controller_delete_notify();


--
-- Name: maasserver_node node_region_and_rack_controller_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_region_and_rack_controller_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN (((new.node_type = 4) AND (((new.architecture)::text IS DISTINCT FROM (old.architecture)::text) OR (new.bmc_id IS DISTINCT FROM old.bmc_id) OR (new.cpu_count IS DISTINCT FROM old.cpu_count) OR (new.cpu_speed IS DISTINCT FROM old.cpu_speed) OR (new.current_commissioning_script_set_id IS DISTINCT FROM old.current_commissioning_script_set_id) OR (new.current_installation_script_set_id IS DISTINCT FROM old.current_installation_script_set_id) OR (new.current_testing_script_set_id IS DISTINCT FROM old.current_testing_script_set_id) OR (new.description IS DISTINCT FROM old.description) OR ((new.distro_series)::text IS DISTINCT FROM (old.distro_series)::text) OR (new.domain_id IS DISTINCT FROM old.domain_id) OR ((new.error)::text IS DISTINCT FROM (old.error)::text) OR ((new.hostname)::text IS DISTINCT FROM (old.hostname)::text) OR ((new.hwe_kernel)::text IS DISTINCT FROM (old.hwe_kernel)::text) OR (new.instance_power_parameters IS DISTINCT FROM old.instance_power_parameters) OR (new.last_image_sync IS DISTINCT FROM old.last_image_sync) OR ((new.license_key)::text IS DISTINCT FROM (old.license_key)::text) OR (new.locked IS DISTINCT FROM old.locked) OR ((new.min_hwe_kernel)::text IS DISTINCT FROM (old.min_hwe_kernel)::text) OR ((new.osystem)::text IS DISTINCT FROM (old.osystem)::text) OR (new.owner_id IS DISTINCT FROM old.owner_id) OR (new.parent_id IS DISTINCT FROM old.parent_id) OR (new.pool_id IS DISTINCT FROM old.pool_id) OR ((new.power_state)::text IS DISTINCT FROM (old.power_state)::text) OR (new.status IS DISTINCT FROM old.status) OR (new.swap_size IS DISTINCT FROM old.swap_size) OR (new.zone_id IS DISTINCT FROM old.zone_id)))) EXECUTE FUNCTION public.region_and_rack_controller_update_notify();


--
-- Name: maasserver_node node_region_controller_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_region_controller_create_notify AFTER INSERT ON public.maasserver_node FOR EACH ROW WHEN ((new.node_type = 3)) EXECUTE FUNCTION public.region_controller_create_notify();


--
-- Name: maasserver_node node_region_controller_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_region_controller_delete_notify AFTER DELETE ON public.maasserver_node FOR EACH ROW WHEN ((old.node_type = 3)) EXECUTE FUNCTION public.region_controller_delete_notify();


--
-- Name: maasserver_node node_region_controller_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_region_controller_update_notify AFTER UPDATE ON public.maasserver_node FOR EACH ROW WHEN (((new.node_type = 3) AND (((new.architecture)::text IS DISTINCT FROM (old.architecture)::text) OR (new.bmc_id IS DISTINCT FROM old.bmc_id) OR (new.cpu_count IS DISTINCT FROM old.cpu_count) OR (new.cpu_speed IS DISTINCT FROM old.cpu_speed) OR (new.current_commissioning_script_set_id IS DISTINCT FROM old.current_commissioning_script_set_id) OR (new.current_installation_script_set_id IS DISTINCT FROM old.current_installation_script_set_id) OR (new.current_testing_script_set_id IS DISTINCT FROM old.current_testing_script_set_id) OR (new.description IS DISTINCT FROM old.description) OR ((new.distro_series)::text IS DISTINCT FROM (old.distro_series)::text) OR (new.domain_id IS DISTINCT FROM old.domain_id) OR ((new.error)::text IS DISTINCT FROM (old.error)::text) OR ((new.hostname)::text IS DISTINCT FROM (old.hostname)::text) OR ((new.hwe_kernel)::text IS DISTINCT FROM (old.hwe_kernel)::text) OR (new.instance_power_parameters IS DISTINCT FROM old.instance_power_parameters) OR (new.last_image_sync IS DISTINCT FROM old.last_image_sync) OR ((new.license_key)::text IS DISTINCT FROM (old.license_key)::text) OR (new.locked IS DISTINCT FROM old.locked) OR ((new.min_hwe_kernel)::text IS DISTINCT FROM (old.min_hwe_kernel)::text) OR ((new.osystem)::text IS DISTINCT FROM (old.osystem)::text) OR (new.owner_id IS DISTINCT FROM old.owner_id) OR (new.parent_id IS DISTINCT FROM old.parent_id) OR (new.pool_id IS DISTINCT FROM old.pool_id) OR ((new.power_state)::text IS DISTINCT FROM (old.power_state)::text) OR (new.status IS DISTINCT FROM old.status) OR (new.swap_size IS DISTINCT FROM old.swap_size) OR (new.zone_id IS DISTINCT FROM old.zone_id)))) EXECUTE FUNCTION public.region_controller_update_notify();


--
-- Name: maasserver_node_tags node_tags_machine_device_tag_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_tags_machine_device_tag_link_notify AFTER INSERT ON public.maasserver_node_tags FOR EACH ROW EXECUTE FUNCTION public.machine_device_tag_link_notify();


--
-- Name: maasserver_node_tags node_tags_machine_device_tag_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER node_tags_machine_device_tag_unlink_notify AFTER DELETE ON public.maasserver_node_tags FOR EACH ROW EXECUTE FUNCTION public.machine_device_tag_unlink_notify();


--
-- Name: maasserver_nodedevice nodedevice_nodedevice_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER nodedevice_nodedevice_create_notify AFTER INSERT ON public.maasserver_nodedevice FOR EACH ROW EXECUTE FUNCTION public.nodedevice_create_notify();


--
-- Name: maasserver_nodedevice nodedevice_nodedevice_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER nodedevice_nodedevice_delete_notify AFTER DELETE ON public.maasserver_nodedevice FOR EACH ROW EXECUTE FUNCTION public.nodedevice_delete_notify();


--
-- Name: maasserver_nodedevice nodedevice_nodedevice_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER nodedevice_nodedevice_update_notify AFTER UPDATE ON public.maasserver_nodedevice FOR EACH ROW EXECUTE FUNCTION public.nodedevice_update_notify();


--
-- Name: maasserver_nodemetadata nodemetadata_nodemetadata_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER nodemetadata_nodemetadata_link_notify AFTER INSERT ON public.maasserver_nodemetadata FOR EACH ROW EXECUTE FUNCTION public.nodemetadata_link_notify();


--
-- Name: maasserver_nodemetadata nodemetadata_nodemetadata_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER nodemetadata_nodemetadata_unlink_notify AFTER DELETE ON public.maasserver_nodemetadata FOR EACH ROW EXECUTE FUNCTION public.nodemetadata_unlink_notify();


--
-- Name: maasserver_nodemetadata nodemetadata_nodemetadata_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER nodemetadata_nodemetadata_update_notify AFTER UPDATE ON public.maasserver_nodemetadata FOR EACH ROW EXECUTE FUNCTION public.nodemetadata_update_notify();


--
-- Name: maasserver_notification notification_notification_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notification_notification_create_notify AFTER INSERT ON public.maasserver_notification FOR EACH ROW EXECUTE FUNCTION public.notification_create_notify();


--
-- Name: maasserver_notification notification_notification_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notification_notification_delete_notify AFTER DELETE ON public.maasserver_notification FOR EACH ROW EXECUTE FUNCTION public.notification_delete_notify();


--
-- Name: maasserver_notification notification_notification_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notification_notification_update_notify AFTER UPDATE ON public.maasserver_notification FOR EACH ROW EXECUTE FUNCTION public.notification_update_notify();


--
-- Name: maasserver_notificationdismissal notificationdismissal_notificationdismissal_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER notificationdismissal_notificationdismissal_create_notify AFTER INSERT ON public.maasserver_notificationdismissal FOR EACH ROW EXECUTE FUNCTION public.notificationdismissal_create_notify();


--
-- Name: maasserver_ownerdata ownerdata_ownerdata_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ownerdata_ownerdata_link_notify AFTER INSERT ON public.maasserver_ownerdata FOR EACH ROW EXECUTE FUNCTION public.ownerdata_link_notify();


--
-- Name: maasserver_ownerdata ownerdata_ownerdata_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ownerdata_ownerdata_unlink_notify AFTER DELETE ON public.maasserver_ownerdata FOR EACH ROW EXECUTE FUNCTION public.ownerdata_unlink_notify();


--
-- Name: maasserver_ownerdata ownerdata_ownerdata_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER ownerdata_ownerdata_update_notify AFTER UPDATE ON public.maasserver_ownerdata FOR EACH ROW EXECUTE FUNCTION public.ownerdata_update_notify();


--
-- Name: maasserver_packagerepository packagerepository_packagerepository_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER packagerepository_packagerepository_create_notify AFTER INSERT ON public.maasserver_packagerepository FOR EACH ROW EXECUTE FUNCTION public.packagerepository_create_notify();


--
-- Name: maasserver_packagerepository packagerepository_packagerepository_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER packagerepository_packagerepository_delete_notify AFTER DELETE ON public.maasserver_packagerepository FOR EACH ROW EXECUTE FUNCTION public.packagerepository_delete_notify();


--
-- Name: maasserver_packagerepository packagerepository_packagerepository_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER packagerepository_packagerepository_update_notify AFTER UPDATE ON public.maasserver_packagerepository FOR EACH ROW EXECUTE FUNCTION public.packagerepository_update_notify();


--
-- Name: maasserver_partition partition_nd_partition_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER partition_nd_partition_link_notify AFTER INSERT ON public.maasserver_partition FOR EACH ROW EXECUTE FUNCTION public.nd_partition_link_notify();


--
-- Name: maasserver_partition partition_nd_partition_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER partition_nd_partition_unlink_notify AFTER DELETE ON public.maasserver_partition FOR EACH ROW EXECUTE FUNCTION public.nd_partition_unlink_notify();


--
-- Name: maasserver_partition partition_nd_partition_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER partition_nd_partition_update_notify AFTER UPDATE ON public.maasserver_partition FOR EACH ROW EXECUTE FUNCTION public.nd_partition_update_notify();


--
-- Name: maasserver_partitiontable partitiontable_nd_partitiontable_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER partitiontable_nd_partitiontable_link_notify AFTER INSERT ON public.maasserver_partitiontable FOR EACH ROW EXECUTE FUNCTION public.nd_partitiontable_link_notify();


--
-- Name: maasserver_partitiontable partitiontable_nd_partitiontable_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER partitiontable_nd_partitiontable_unlink_notify AFTER DELETE ON public.maasserver_partitiontable FOR EACH ROW EXECUTE FUNCTION public.nd_partitiontable_unlink_notify();


--
-- Name: maasserver_partitiontable partitiontable_nd_partitiontable_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER partitiontable_nd_partitiontable_update_notify AFTER UPDATE ON public.maasserver_partitiontable FOR EACH ROW EXECUTE FUNCTION public.nd_partitiontable_update_notify();


--
-- Name: maasserver_physicalblockdevice physicalblockdevice_nd_physblockdevice_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER physicalblockdevice_nd_physblockdevice_update_notify AFTER UPDATE ON public.maasserver_physicalblockdevice FOR EACH ROW EXECUTE FUNCTION public.nd_physblockdevice_update_notify();


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
-- Name: maasserver_rbacsync rbacsync_sys_rbac_sync; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER rbacsync_sys_rbac_sync AFTER INSERT ON public.maasserver_rbacsync FOR EACH ROW EXECUTE FUNCTION public.sys_rbac_sync();


--
-- Name: maasserver_regionrackrpcconnection regionrackrpcconnection_sys_core_rpc_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER regionrackrpcconnection_sys_core_rpc_delete AFTER DELETE ON public.maasserver_regionrackrpcconnection FOR EACH ROW EXECUTE FUNCTION public.sys_core_rpc_delete();


--
-- Name: maasserver_regionrackrpcconnection regionrackrpcconnection_sys_core_rpc_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER regionrackrpcconnection_sys_core_rpc_insert AFTER INSERT ON public.maasserver_regionrackrpcconnection FOR EACH ROW EXECUTE FUNCTION public.sys_core_rpc_insert();


--
-- Name: maasserver_resourcepool resourcepool_sys_rbac_rpool_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER resourcepool_sys_rbac_rpool_delete AFTER DELETE ON public.maasserver_resourcepool FOR EACH ROW EXECUTE FUNCTION public.sys_rbac_rpool_delete();


--
-- Name: maasserver_resourcepool resourcepool_sys_rbac_rpool_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER resourcepool_sys_rbac_rpool_insert AFTER INSERT ON public.maasserver_resourcepool FOR EACH ROW EXECUTE FUNCTION public.sys_rbac_rpool_insert();


--
-- Name: maasserver_resourcepool resourcepool_sys_rbac_rpool_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER resourcepool_sys_rbac_rpool_update AFTER UPDATE ON public.maasserver_resourcepool FOR EACH ROW EXECUTE FUNCTION public.sys_rbac_rpool_update();


--
-- Name: maasserver_script script_script_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER script_script_create_notify AFTER INSERT ON public.maasserver_script FOR EACH ROW EXECUTE FUNCTION public.script_create_notify();


--
-- Name: maasserver_script script_script_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER script_script_delete_notify AFTER DELETE ON public.maasserver_script FOR EACH ROW EXECUTE FUNCTION public.script_delete_notify();


--
-- Name: maasserver_script script_script_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER script_script_update_notify AFTER UPDATE ON public.maasserver_script FOR EACH ROW EXECUTE FUNCTION public.script_update_notify();


--
-- Name: maasserver_scriptresult scriptresult_nd_scriptresult_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptresult_nd_scriptresult_link_notify AFTER INSERT ON public.maasserver_scriptresult FOR EACH ROW EXECUTE FUNCTION public.nd_scriptresult_link_notify();


--
-- Name: maasserver_scriptresult scriptresult_nd_scriptresult_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptresult_nd_scriptresult_unlink_notify AFTER DELETE ON public.maasserver_scriptresult FOR EACH ROW EXECUTE FUNCTION public.nd_scriptresult_unlink_notify();


--
-- Name: maasserver_scriptresult scriptresult_nd_scriptresult_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptresult_nd_scriptresult_update_notify AFTER UPDATE ON public.maasserver_scriptresult FOR EACH ROW EXECUTE FUNCTION public.nd_scriptresult_update_notify();


--
-- Name: maasserver_scriptresult scriptresult_scriptresult_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptresult_scriptresult_create_notify AFTER INSERT ON public.maasserver_scriptresult FOR EACH ROW EXECUTE FUNCTION public.scriptresult_create_notify();


--
-- Name: maasserver_scriptresult scriptresult_scriptresult_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptresult_scriptresult_delete_notify AFTER DELETE ON public.maasserver_scriptresult FOR EACH ROW EXECUTE FUNCTION public.scriptresult_delete_notify();


--
-- Name: maasserver_scriptresult scriptresult_scriptresult_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptresult_scriptresult_update_notify AFTER UPDATE ON public.maasserver_scriptresult FOR EACH ROW EXECUTE FUNCTION public.scriptresult_update_notify();


--
-- Name: maasserver_scriptset scriptset_nd_scriptset_link_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptset_nd_scriptset_link_notify AFTER INSERT ON public.maasserver_scriptset FOR EACH ROW EXECUTE FUNCTION public.nd_scriptset_link_notify();


--
-- Name: maasserver_scriptset scriptset_nd_scriptset_unlink_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER scriptset_nd_scriptset_unlink_notify AFTER DELETE ON public.maasserver_scriptset FOR EACH ROW EXECUTE FUNCTION public.nd_scriptset_unlink_notify();


--
-- Name: maasserver_service service_service_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER service_service_create_notify AFTER INSERT ON public.maasserver_service FOR EACH ROW EXECUTE FUNCTION public.service_create_notify();


--
-- Name: maasserver_service service_service_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER service_service_delete_notify AFTER DELETE ON public.maasserver_service FOR EACH ROW EXECUTE FUNCTION public.service_delete_notify();


--
-- Name: maasserver_service service_service_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER service_service_update_notify AFTER UPDATE ON public.maasserver_service FOR EACH ROW EXECUTE FUNCTION public.service_update_notify();


--
-- Name: maasserver_space space_space_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER space_space_create_notify AFTER INSERT ON public.maasserver_space FOR EACH ROW EXECUTE FUNCTION public.space_create_notify();


--
-- Name: maasserver_space space_space_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER space_space_delete_notify AFTER DELETE ON public.maasserver_space FOR EACH ROW EXECUTE FUNCTION public.space_delete_notify();


--
-- Name: maasserver_space space_space_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER space_space_machine_update_notify AFTER UPDATE ON public.maasserver_space FOR EACH ROW EXECUTE FUNCTION public.space_machine_update_notify();


--
-- Name: maasserver_space space_space_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER space_space_update_notify AFTER UPDATE ON public.maasserver_space FOR EACH ROW EXECUTE FUNCTION public.space_update_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_domain_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_domain_delete_notify AFTER DELETE ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_domain_delete_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_domain_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_domain_insert_notify AFTER INSERT ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_domain_insert_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_domain_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_domain_update_notify AFTER UPDATE ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_domain_update_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_machine_update_notify AFTER UPDATE ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_machine_update_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_subnet_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_subnet_delete_notify AFTER DELETE ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_subnet_delete_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_subnet_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_subnet_insert_notify AFTER INSERT ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_subnet_insert_notify();


--
-- Name: maasserver_staticipaddress staticipaddress_ipaddress_subnet_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticipaddress_ipaddress_subnet_update_notify AFTER UPDATE ON public.maasserver_staticipaddress FOR EACH ROW EXECUTE FUNCTION public.ipaddress_subnet_update_notify();


--
-- Name: maasserver_staticroute staticroute_staticroute_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticroute_staticroute_create_notify AFTER INSERT ON public.maasserver_staticroute FOR EACH ROW EXECUTE FUNCTION public.staticroute_create_notify();


--
-- Name: maasserver_staticroute staticroute_staticroute_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticroute_staticroute_delete_notify AFTER DELETE ON public.maasserver_staticroute FOR EACH ROW EXECUTE FUNCTION public.staticroute_delete_notify();


--
-- Name: maasserver_staticroute staticroute_staticroute_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER staticroute_staticroute_update_notify AFTER UPDATE ON public.maasserver_staticroute FOR EACH ROW EXECUTE FUNCTION public.staticroute_update_notify();


--
-- Name: maasserver_subnet subnet_subnet_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_subnet_create_notify AFTER INSERT ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.subnet_create_notify();


--
-- Name: maasserver_subnet subnet_subnet_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_subnet_delete_notify AFTER DELETE ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.subnet_delete_notify();


--
-- Name: maasserver_subnet subnet_subnet_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_subnet_machine_update_notify AFTER UPDATE ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.subnet_machine_update_notify();


--
-- Name: maasserver_subnet subnet_subnet_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_subnet_update_notify AFTER UPDATE ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.subnet_update_notify();


--
-- Name: maasserver_subnet subnet_sys_proxy_subnet_delete; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_sys_proxy_subnet_delete AFTER DELETE ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.sys_proxy_subnet_delete();


--
-- Name: maasserver_subnet subnet_sys_proxy_subnet_insert; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_sys_proxy_subnet_insert AFTER INSERT ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.sys_proxy_subnet_insert();


--
-- Name: maasserver_subnet subnet_sys_proxy_subnet_update; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER subnet_sys_proxy_subnet_update AFTER UPDATE ON public.maasserver_subnet FOR EACH ROW EXECUTE FUNCTION public.sys_proxy_subnet_update();


--
-- Name: maasserver_tag tag_tag_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tag_tag_create_notify AFTER INSERT ON public.maasserver_tag FOR EACH ROW EXECUTE FUNCTION public.tag_create_notify();


--
-- Name: maasserver_tag tag_tag_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tag_tag_delete_notify AFTER DELETE ON public.maasserver_tag FOR EACH ROW EXECUTE FUNCTION public.tag_delete_notify();


--
-- Name: maasserver_tag tag_tag_update_machine_device_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tag_tag_update_machine_device_notify AFTER UPDATE ON public.maasserver_tag FOR EACH ROW EXECUTE FUNCTION public.tag_update_machine_device_notify();


--
-- Name: maasserver_tag tag_tag_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tag_tag_update_notify AFTER UPDATE ON public.maasserver_tag FOR EACH ROW EXECUTE FUNCTION public.tag_update_notify();


--
-- Name: maasserver_virtualblockdevice virtualblockdevice_nd_virtblockdevice_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER virtualblockdevice_nd_virtblockdevice_update_notify AFTER UPDATE ON public.maasserver_virtualblockdevice FOR EACH ROW EXECUTE FUNCTION public.nd_virtblockdevice_update_notify();


--
-- Name: maasserver_vlan vlan_vlan_create_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vlan_vlan_create_notify AFTER INSERT ON public.maasserver_vlan FOR EACH ROW EXECUTE FUNCTION public.vlan_create_notify();


--
-- Name: maasserver_vlan vlan_vlan_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vlan_vlan_delete_notify AFTER DELETE ON public.maasserver_vlan FOR EACH ROW EXECUTE FUNCTION public.vlan_delete_notify();


--
-- Name: maasserver_vlan vlan_vlan_machine_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vlan_vlan_machine_update_notify AFTER UPDATE ON public.maasserver_vlan FOR EACH ROW EXECUTE FUNCTION public.vlan_machine_update_notify();


--
-- Name: maasserver_vlan vlan_vlan_subnet_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vlan_vlan_subnet_update_notify AFTER UPDATE ON public.maasserver_vlan FOR EACH ROW EXECUTE FUNCTION public.vlan_subnet_update_notify();


--
-- Name: maasserver_vlan vlan_vlan_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vlan_vlan_update_notify AFTER UPDATE ON public.maasserver_vlan FOR EACH ROW EXECUTE FUNCTION public.vlan_update_notify();


--
-- Name: maasserver_vmcluster vmcluster_vmcluster_delete_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vmcluster_vmcluster_delete_notify AFTER DELETE ON public.maasserver_vmcluster FOR EACH ROW EXECUTE FUNCTION public.vmcluster_delete_notify();


--
-- Name: maasserver_vmcluster vmcluster_vmcluster_insert_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vmcluster_vmcluster_insert_notify AFTER INSERT ON public.maasserver_vmcluster FOR EACH ROW EXECUTE FUNCTION public.vmcluster_insert_notify();


--
-- Name: maasserver_vmcluster vmcluster_vmcluster_update_notify; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER vmcluster_vmcluster_update_notify AFTER UPDATE ON public.maasserver_vmcluster FOR EACH ROW EXECUTE FUNCTION public.vmcluster_update_notify();


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
-- Name: maasserver_agent maasserver_agent_rack_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_agent
    ADD CONSTRAINT maasserver_agent_rack_id_fkey FOREIGN KEY (rack_id) REFERENCES public.maasserver_rack(id);


--
-- Name: maasserver_agent maasserver_agent_rackcontroller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_agent
    ADD CONSTRAINT maasserver_agent_rackcontroller_id_fkey FOREIGN KEY (rackcontroller_id) REFERENCES public.maasserver_node(id);


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
-- Name: maasserver_bootresource maasserver_bootresource_selection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresource
    ADD CONSTRAINT maasserver_bootresource_selection_id_fkey FOREIGN KEY (selection_id) REFERENCES public.maasserver_bootsourceselection(id);


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
-- Name: maasserver_bootsourceselectionlegacy maasserver_bootsourceselection_boot_source_id_b911aa0f_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselectionlegacy
    ADD CONSTRAINT maasserver_bootsourceselection_boot_source_id_b911aa0f_fk FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootsourceselection maasserver_bootsourceselection_boot_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_boot_source_id_fkey FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootsourceselection maasserver_bootsourceselection_legacyselection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_legacyselection_id_fkey FOREIGN KEY (legacyselection_id) REFERENCES public.maasserver_bootsourceselectionlegacy(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootstraptoken maasserver_bootstraptoken_rack_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootstraptoken
    ADD CONSTRAINT maasserver_bootstraptoken_rack_id_fkey FOREIGN KEY (rack_id) REFERENCES public.maasserver_rack(id);


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
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresource_ip_addresses_dnsresource_id_49f1115e_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresource_ip_addresses_dnsresource_id_49f1115e_fk FOREIGN KEY (dnsresource_id) REFERENCES public.maasserver_dnsresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresource_ip_staticipaddress_id_794f210e_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresource_ip_staticipaddress_id_794f210e_fk FOREIGN KEY (staticipaddress_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_forwarddnsserver_domains maasserver_forwarddnsserv_forwarddnsserver_id_c975e5df_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_forwarddnsserver_domains
    ADD CONSTRAINT maasserver_forwarddnsserv_forwarddnsserver_id_c975e5df_fk FOREIGN KEY (forwarddnsserver_id) REFERENCES public.maasserver_forwarddnsserver(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_globaldefault maasserver_globaldef_domain_id_11c3ee74_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_globaldefault
    ADD CONSTRAINT maasserver_globaldef_domain_id_11c3ee74_fk_maasserve FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_imagemanifest maasserver_imagemanifest_boot_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_imagemanifest
    ADD CONSTRAINT maasserver_imagemanifest_boot_source_id_fkey FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_interface_id_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_interface_id_fk_maasserve FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_ip_a_staticipaddress_id_5fa63951_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_ip_a_staticipaddress_id_5fa63951_fk FOREIGN KEY (staticipaddress_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_ip_addresses_interface_id_d3d873df_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_ip_addresses_interface_id_d3d873df_fk FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_node maasserver_node_boot_disk_id_db8131e9_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_boot_disk_id_db8131e9_fk FOREIGN KEY (boot_disk_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_node maasserver_node_current_deployment_0013_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_deployment_0013_fk_maasserve FOREIGN KEY (current_deployment_script_set_id) REFERENCES public.maasserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_node_tags maasserver_node_tags_node_id_a662a9f1_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_node_id_a662a9f1_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node_tags maasserver_node_tags_node_id_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_node_id_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node_tags maasserver_node_tags_tag_id_f4728372_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_tag_id_f4728372_fk FOREIGN KEY (tag_id) REFERENCES public.maasserver_tag(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_nodedevice maasserver_nodedevice_physical_blockdevice_id_7ce12336_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodedevice
    ADD CONSTRAINT maasserver_nodedevice_physical_blockdevice_id_7ce12336_fk FOREIGN KEY (physical_blockdevice_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_notificationdismissal maasserver_notificationdismissal_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal
    ADD CONSTRAINT maasserver_notificationdismissal_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_oidcrevokedtoken maasserver_oidcrevokedtoken_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_oidcrevokedtoken
    ADD CONSTRAINT maasserver_oidcrevokedtoken_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.maasserver_oidc_provider(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_oidcrevokedtoken maasserver_oidcrevokedtoken_user_email_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_oidcrevokedtoken
    ADD CONSTRAINT maasserver_oidcrevokedtoken_user_email_fkey FOREIGN KEY (user_email) REFERENCES public.auth_user(username) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_podhints_nodes maasserver_podhints_nodes_node_id_7e2e56a4_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes
    ADD CONSTRAINT maasserver_podhints_nodes_node_id_7e2e56a4_fk FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podhints_nodes maasserver_podhints_nodes_podhints_id_df1bafb3_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints_nodes
    ADD CONSTRAINT maasserver_podhints_nodes_podhints_id_df1bafb3_fk FOREIGN KEY (podhints_id) REFERENCES public.maasserver_podhints(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_refreshtoken maasserver_refreshtoken_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_refreshtoken
    ADD CONSTRAINT maasserver_refreshtoken_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.auth_user(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_reservedip maasserver_reservedi_subnet_id_548dd59f_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_reservedip
    ADD CONSTRAINT maasserver_reservedi_subnet_id_548dd59f_fk_maasserve FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_scriptresult maasserver_scriptresult_physical_blockdevice_id_6d159ece_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_scriptresult
    ADD CONSTRAINT maasserver_scriptresult_physical_blockdevice_id_6d159ece_fk FOREIGN KEY (physical_blockdevice_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_userprofile maasserver_userprofile_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.maasserver_oidc_provider(id) ON DELETE CASCADE DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_vlan maasserver_vlan_fabric_id_af5275c8_fk_maasserver_fabric_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_fabric_id_af5275c8_fk_maasserver_fabric_id FOREIGN KEY (fabric_id) REFERENCES public.maasserver_fabric(id) DEFERRABLE INITIALLY DEFERRED;


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

\unrestrict jDB4gdI1N8dbUCAC3vcdCvWs48TBU3tT39yhtb0ijqwqYnAc3QoCur8LfK1MnsD

