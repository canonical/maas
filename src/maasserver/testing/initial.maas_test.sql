--
-- PostgreSQL database dump
--

-- Dumped from database version 10.7 (Ubuntu 10.7-0ubuntu0.18.04.1)
-- Dumped by pg_dump version 10.7 (Ubuntu 10.7-0ubuntu0.18.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(80) NOT NULL
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
    first_name character varying(30) NOT NULL,
    last_name character varying(30) NOT NULL,
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
-- Name: maasserver_bootsource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsource (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    url character varying(200) NOT NULL,
    keyring_filename character varying(4096) NOT NULL,
    keyring_data bytea NOT NULL
);


--
-- Name: maasserver_bootsourcecache; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsourcecache (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    os character varying(32) NOT NULL,
    arch character varying(32) NOT NULL,
    subarch character varying(32) NOT NULL,
    release character varying(32) NOT NULL,
    label character varying(32) NOT NULL,
    boot_source_id integer NOT NULL,
    release_codename character varying(255),
    release_title character varying(255),
    support_eol date,
    kflavor character varying(32),
    bootloader_type character varying(32),
    extra text NOT NULL
);


--
-- Name: maas_support__boot_source_cache; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__boot_source_cache AS
 SELECT bs.url,
    bsc.label,
    bsc.os,
    bsc.release,
    bsc.arch,
    bsc.subarch
   FROM (public.maasserver_bootsource bs
     LEFT JOIN public.maasserver_bootsourcecache bsc ON ((bsc.boot_source_id = bs.id)))
  ORDER BY bs.url, bsc.label, bsc.os, bsc.release, bsc.arch, bsc.subarch;


--
-- Name: maasserver_bootsourceselection; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootsourceselection (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    os character varying(20) NOT NULL,
    release character varying(20) NOT NULL,
    arches text[],
    subarches text[],
    labels text[],
    boot_source_id integer NOT NULL
);


--
-- Name: maas_support__boot_source_selections; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__boot_source_selections AS
 SELECT bs.url,
    bss.release,
    bss.arches,
    bss.subarches,
    bss.labels,
    bss.os
   FROM (public.maasserver_bootsource bs
     LEFT JOIN public.maasserver_bootsourceselection bss ON ((bss.boot_source_id = bs.id)));


--
-- Name: maasserver_config; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_config (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    value text
);


--
-- Name: maas_support__configuration__excluding_rpc_shared_secret; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__configuration__excluding_rpc_shared_secret AS
 SELECT maasserver_config.name,
    maasserver_config.value
   FROM public.maasserver_config
  WHERE ((maasserver_config.name)::text <> 'rpc_shared_secret'::text);


--
-- Name: maasserver_node; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_node (
    id integer NOT NULL,
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
    boot_interface_id integer,
    gateway_link_ipv4_id integer,
    gateway_link_ipv6_id integer,
    owner_id integer,
    parent_id integer,
    token_id integer,
    zone_id integer NOT NULL,
    boot_disk_id integer,
    node_type integer NOT NULL,
    domain_id integer,
    dns_process_id integer,
    bmc_id integer,
    address_ttl integer,
    status_expires timestamp with time zone,
    power_state_queried timestamp with time zone,
    url character varying(255) NOT NULL,
    managing_process_id integer,
    last_image_sync timestamp with time zone,
    previous_status integer NOT NULL,
    default_user character varying(32) NOT NULL,
    cpu_speed integer NOT NULL,
    current_commissioning_script_set_id integer,
    current_installation_script_set_id integer,
    current_testing_script_set_id integer,
    creation_type integer NOT NULL,
    install_rackd boolean NOT NULL,
    locked boolean NOT NULL,
    pool_id integer,
    skip_bmc_config boolean NOT NULL,
    instance_power_parameters jsonb NOT NULL,
    install_kvm boolean NOT NULL,
    hardware_uuid character varying(36),
    ephemeral_deploy boolean NOT NULL,
    description text NOT NULL,
    CONSTRAINT maasserver_node_address_ttl_check CHECK ((address_ttl >= 0))
);


--
-- Name: maas_support__device_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__device_overview AS
 SELECT node.hostname,
    node.system_id,
    parent.hostname AS parent
   FROM (public.maasserver_node node
     LEFT JOIN public.maasserver_node parent ON ((node.parent_id = parent.id)))
  WHERE (node.node_type = 1)
  ORDER BY node.hostname;


--
-- Name: maasserver_bmc; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bmc (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    power_type character varying(10) NOT NULL,
    ip_address_id integer,
    architectures text[],
    bmc_type integer NOT NULL,
    capabilities text[],
    cores integer NOT NULL,
    cpu_speed integer NOT NULL,
    local_disks integer NOT NULL,
    local_storage bigint NOT NULL,
    memory integer NOT NULL,
    name character varying(255) NOT NULL,
    iscsi_storage bigint NOT NULL,
    pool_id integer,
    zone_id integer NOT NULL,
    tags text[],
    cpu_over_commit_ratio double precision NOT NULL,
    memory_over_commit_ratio double precision NOT NULL,
    default_storage_pool_id integer,
    power_parameters jsonb NOT NULL,
    default_macvlan_mode character varying(32)
);


--
-- Name: maasserver_interface; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_interface (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    type character varying(20) NOT NULL,
    mac_address macaddr,
    ipv4_params text NOT NULL,
    ipv6_params text NOT NULL,
    params text NOT NULL,
    tags text[],
    enabled boolean NOT NULL,
    node_id integer,
    vlan_id integer,
    acquired boolean NOT NULL,
    mdns_discovery_state boolean NOT NULL,
    neighbour_discovery_state boolean NOT NULL,
    firmware_version character varying(255),
    product character varying(255),
    vendor character varying(255)
);


--
-- Name: maasserver_interface_ip_addresses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_interface_ip_addresses (
    id integer NOT NULL,
    interface_id integer NOT NULL,
    staticipaddress_id integer NOT NULL
);


--
-- Name: maasserver_staticipaddress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_staticipaddress (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet,
    alloc_type integer NOT NULL,
    subnet_id integer,
    user_id integer,
    lease_time integer NOT NULL
);


--
-- Name: maasserver_subnet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_subnet (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    cidr cidr NOT NULL,
    gateway_ip inet,
    dns_servers text[],
    vlan_id integer NOT NULL,
    rdns_mode integer NOT NULL,
    allow_proxy boolean NOT NULL,
    description text NOT NULL,
    active_discovery boolean NOT NULL,
    managed boolean NOT NULL,
    allow_dns boolean NOT NULL
);


--
-- Name: maas_support__ip_allocation; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__ip_allocation AS
 SELECT sip.ip,
        CASE
            WHEN (sip.alloc_type = 0) THEN 'AUTO'::bpchar
            WHEN (sip.alloc_type = 1) THEN 'STICKY'::bpchar
            WHEN (sip.alloc_type = 4) THEN 'USER_RESERVED'::bpchar
            WHEN (sip.alloc_type = 5) THEN 'DHCP'::bpchar
            WHEN (sip.alloc_type = 6) THEN 'DISCOVERED'::bpchar
            ELSE (sip.alloc_type)::character(1)
        END AS alloc_type,
    subnet.cidr,
    node.hostname,
    iface.id AS ifid,
    iface.name AS ifname,
    iface.type AS iftype,
    iface.mac_address,
    bmc.power_type
   FROM (((((public.maasserver_staticipaddress sip
     LEFT JOIN public.maasserver_subnet subnet ON ((subnet.id = sip.subnet_id)))
     LEFT JOIN public.maasserver_interface_ip_addresses ifip ON ((sip.id = ifip.staticipaddress_id)))
     LEFT JOIN public.maasserver_interface iface ON ((iface.id = ifip.interface_id)))
     LEFT JOIN public.maasserver_node node ON ((iface.node_id = node.id)))
     LEFT JOIN public.maasserver_bmc bmc ON ((bmc.ip_address_id = sip.id)))
  ORDER BY sip.ip;


--
-- Name: maasserver_licensekey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_licensekey (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    osystem character varying(255) NOT NULL,
    distro_series character varying(255) NOT NULL,
    license_key character varying(255) NOT NULL
);


--
-- Name: maas_support__license_keys_present__excluding_key_material; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__license_keys_present__excluding_key_material AS
 SELECT maasserver_licensekey.osystem,
    maasserver_licensekey.distro_series
   FROM public.maasserver_licensekey;


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
-- Name: maasserver_vlan; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_vlan (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256),
    vid integer NOT NULL,
    mtu integer NOT NULL,
    fabric_id integer NOT NULL,
    dhcp_on boolean NOT NULL,
    primary_rack_id integer,
    secondary_rack_id integer,
    external_dhcp inet,
    description text NOT NULL,
    relay_vlan_id integer,
    space_id integer
);


--
-- Name: maas_support__node_networking; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__node_networking AS
 SELECT node.hostname,
    iface.id AS ifid,
    iface.name,
    iface.type,
    iface.mac_address,
    sip.ip,
        CASE
            WHEN (sip.alloc_type = 0) THEN 'AUTO'::bpchar
            WHEN (sip.alloc_type = 1) THEN 'STICKY'::bpchar
            WHEN (sip.alloc_type = 4) THEN 'USER_RESERVED'::bpchar
            WHEN (sip.alloc_type = 5) THEN 'DHCP'::bpchar
            WHEN (sip.alloc_type = 6) THEN 'DISCOVERED'::bpchar
            ELSE (sip.alloc_type)::character(1)
        END AS alloc_type,
    subnet.cidr,
    vlan.vid,
    fabric.name AS fabric
   FROM ((((((public.maasserver_interface iface
     LEFT JOIN public.maasserver_interface_ip_addresses ifip ON ((ifip.interface_id = iface.id)))
     LEFT JOIN public.maasserver_staticipaddress sip ON ((ifip.staticipaddress_id = sip.id)))
     LEFT JOIN public.maasserver_subnet subnet ON ((sip.subnet_id = subnet.id)))
     LEFT JOIN public.maasserver_node node ON ((node.id = iface.node_id)))
     LEFT JOIN public.maasserver_vlan vlan ON ((vlan.id = subnet.vlan_id)))
     LEFT JOIN public.maasserver_fabric fabric ON ((fabric.id = vlan.fabric_id)))
  ORDER BY node.hostname, iface.name, sip.alloc_type;


--
-- Name: maas_support__node_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maas_support__node_overview AS
 SELECT maasserver_node.hostname,
    maasserver_node.system_id,
    maasserver_node.cpu_count AS cpu,
    maasserver_node.memory
   FROM public.maasserver_node
  WHERE (maasserver_node.node_type = 0)
  ORDER BY maasserver_node.hostname;


--
-- Name: maasserver_sshkey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_sshkey (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key text NOT NULL,
    user_id integer NOT NULL,
    keysource_id integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    id_path character varying(4096),
    size bigint NOT NULL,
    block_size integer NOT NULL,
    tags text[],
    node_id integer NOT NULL
);


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_blockdevice_id_seq
    AS integer
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
-- Name: maasserver_bmc_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bmc_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    routable boolean NOT NULL,
    bmc_id integer NOT NULL,
    rack_controller_id integer NOT NULL
);


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bmcroutablerackcontrollerrelationship_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    rtype integer NOT NULL,
    name character varying(255) NOT NULL,
    architecture character varying(255) NOT NULL,
    extra text NOT NULL,
    kflavor character varying(32),
    bootloader_type character varying(32),
    rolling boolean NOT NULL
);


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresource_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    filename character varying(255) NOT NULL,
    filetype character varying(20) NOT NULL,
    extra text NOT NULL,
    largefile_id integer NOT NULL,
    resource_set_id integer NOT NULL
);


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresourcefile_id_seq
    AS integer
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
-- Name: maasserver_bootresourceset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_bootresourceset (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    version character varying(255) NOT NULL,
    label character varying(255) NOT NULL,
    resource_id integer NOT NULL
);


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootresourceset_id_seq
    AS integer
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
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootsource_id_seq
    AS integer
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
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootsourcecache_id_seq
    AS integer
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
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_bootsourceselection_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL
);


--
-- Name: maasserver_cacheset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_cacheset_id_seq
    AS integer
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
-- Name: maasserver_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_config_id_seq
    AS integer
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
    node_id integer NOT NULL,
    version character varying(255),
    interfaces text NOT NULL,
    interface_update_hints text NOT NULL
);


--
-- Name: maasserver_dhcpsnippet; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_dhcpsnippet (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    enabled boolean NOT NULL,
    node_id integer,
    subnet_id integer,
    value_id integer NOT NULL
);


--
-- Name: maasserver_dhcpsnippet_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dhcpsnippet_id_seq
    AS integer
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
-- Name: maasserver_mdns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_mdns (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet,
    hostname character varying(256),
    count integer NOT NULL,
    interface_id integer NOT NULL
);


--
-- Name: maasserver_neighbour; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_neighbour (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet,
    "time" integer NOT NULL,
    vid integer,
    count integer NOT NULL,
    mac_address macaddr,
    interface_id integer NOT NULL
);


--
-- Name: maasserver_rdns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_rdns (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet NOT NULL,
    hostname character varying(256),
    hostnames text NOT NULL,
    observer_id integer NOT NULL
);


--
-- Name: maasserver_discovery; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_discovery AS
 SELECT DISTINCT ON (neigh.mac_address, neigh.ip) neigh.id,
    replace(encode((((rtrim((neigh.ip)::text, '/32'::text) || ','::text) || (neigh.mac_address)::text))::bytea, 'base64'::text), chr(10), ''::text) AS discovery_id,
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
     JOIN public.maasserver_node node ON ((node.id = iface.node_id)))
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    rrtype character varying(8) NOT NULL,
    rrdata text NOT NULL,
    dnsresource_id integer NOT NULL,
    ttl integer,
    CONSTRAINT maasserver_dnsdata_ttl_check CHECK ((ttl >= 0))
);


--
-- Name: maasserver_dnsdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dnsdata_id_seq
    AS integer
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
    id integer NOT NULL,
    serial bigint NOT NULL,
    created timestamp with time zone NOT NULL,
    source character varying(255) NOT NULL
);


--
-- Name: maasserver_dnspublication_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_dnspublication_id_seq
    AS integer
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
    id integer NOT NULL,
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
    AS integer
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
    dnsresource_id integer NOT NULL,
    staticipaddress_id integer NOT NULL
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    action text NOT NULL,
    description text NOT NULL,
    node_id integer,
    type_id integer NOT NULL,
    node_hostname character varying(255) NOT NULL,
    username character varying(32) NOT NULL,
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
    AS integer
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
    id integer NOT NULL,
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
    AS integer
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
    AS integer
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
-- Name: maasserver_fannetwork; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_fannetwork (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    "overlay" cidr NOT NULL,
    underlay cidr NOT NULL,
    dhcp boolean,
    host_reserve integer,
    bridge character varying(255),
    off boolean,
    CONSTRAINT maasserver_fannetwork_host_reserve_check CHECK ((host_reserve >= 0))
);


--
-- Name: maasserver_fannetwork_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_fannetwork_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_fannetwork_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.maasserver_fannetwork_id_seq OWNED BY public.maasserver_fannetwork.id;


--
-- Name: maasserver_filestorage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_filestorage (
    id integer NOT NULL,
    filename character varying(255) NOT NULL,
    content text NOT NULL,
    key character varying(36) NOT NULL,
    owner_id integer
);


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_filestorage_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid character varying(36) NOT NULL,
    fstype character varying(20) NOT NULL,
    label character varying(255),
    create_params character varying(255),
    mount_point character varying(255),
    mount_options character varying(255),
    acquired boolean NOT NULL,
    block_device_id integer,
    cache_set_id integer,
    filesystem_group_id integer,
    partition_id integer,
    node_id integer
);


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_filesystem_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid character varying(36) NOT NULL,
    group_type character varying(20) NOT NULL,
    name character varying(255) NOT NULL,
    create_params character varying(255),
    cache_mode character varying(20),
    cache_set_id integer
);


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_filesystemgroup_id_seq
    AS integer
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
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    child_id integer NOT NULL,
    parent_id integer NOT NULL
);


--
-- Name: maasserver_interfacerelationship_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_interfacerelationship_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    type character varying(20) NOT NULL,
    start_ip inet NOT NULL,
    end_ip inet NOT NULL,
    comment character varying(255),
    subnet_id integer NOT NULL,
    user_id integer
);


--
-- Name: maasserver_iprange_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_iprange_id_seq
    AS integer
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
-- Name: maasserver_iscsiblockdevice; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_iscsiblockdevice (
    blockdevice_ptr_id integer NOT NULL,
    target character varying(4096) NOT NULL
);


--
-- Name: maasserver_keysource; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_keysource (
    id integer NOT NULL,
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
    AS integer
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
    id integer NOT NULL,
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
    AS integer
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
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_licensekey_id_seq
    AS integer
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
    AS integer
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
    AS integer
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
    AS integer
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
    node_id integer NOT NULL,
    tag_id integer NOT NULL
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
-- Name: maasserver_nodegrouptorackcontroller; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodegrouptorackcontroller (
    id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    subnet_id integer NOT NULL
);


--
-- Name: maasserver_nodegrouptorackcontroller_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodegrouptorackcontroller_id_seq
    AS integer
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
-- Name: maasserver_nodemetadata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_nodemetadata (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key character varying(64) NOT NULL,
    value text NOT NULL,
    node_id integer NOT NULL
);


--
-- Name: maasserver_nodemetadata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_nodemetadata_id_seq
    AS integer
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
-- Name: maasserver_notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_notification (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ident character varying(40),
    users boolean NOT NULL,
    admins boolean NOT NULL,
    message text NOT NULL,
    context text NOT NULL,
    user_id integer,
    category character varying(10) NOT NULL
);


--
-- Name: maasserver_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_notification_id_seq
    AS integer
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
    id integer NOT NULL,
    notification_id integer NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: maasserver_notificationdismissal_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_notificationdismissal_id_seq
    AS integer
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
-- Name: maasserver_ownerdata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_ownerdata (
    id integer NOT NULL,
    key character varying(255) NOT NULL,
    value text NOT NULL,
    node_id integer NOT NULL
);


--
-- Name: maasserver_ownerdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_ownerdata_id_seq
    AS integer
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
    id integer NOT NULL,
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
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid character varying(36),
    size bigint NOT NULL,
    bootable boolean NOT NULL,
    partition_table_id integer NOT NULL,
    tags text[]
);


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_partition_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    table_type character varying(20) NOT NULL,
    block_device_id integer NOT NULL
);


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_partitiontable_id_seq
    AS integer
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
    blockdevice_ptr_id integer NOT NULL,
    model character varying(255) NOT NULL,
    serial character varying(255) NOT NULL,
    firmware_version character varying(255),
    storage_pool_id integer
);


--
-- Name: maasserver_podhints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_podhints (
    id integer NOT NULL,
    cores integer NOT NULL,
    memory integer NOT NULL,
    local_storage bigint NOT NULL,
    local_disks integer NOT NULL,
    pod_id integer NOT NULL,
    cpu_speed integer NOT NULL,
    iscsi_storage bigint NOT NULL
);


--
-- Name: maasserver_podhints_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_podhints_id_seq
    AS integer
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
-- Name: maasserver_podhost; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.maasserver_podhost AS
 SELECT (((pod.id)::bigint << 32) | (node.id)::bigint) AS id,
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
     LEFT JOIN public.maasserver_node node ON ((node.id = if.node_id)));


--
-- Name: maasserver_podstoragepool; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_podstoragepool (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    pool_id character varying(255) NOT NULL,
    pool_type character varying(255) NOT NULL,
    path character varying(4095) NOT NULL,
    storage bigint NOT NULL,
    pod_id integer NOT NULL
);


--
-- Name: maasserver_podstoragepool_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_podstoragepool_id_seq
    AS integer
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
    id integer NOT NULL,
    resource_type character varying(255) NOT NULL,
    sync_id character varying(255) NOT NULL
);


--
-- Name: maasserver_rbaclastsync_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_rbaclastsync_id_seq
    AS integer
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
    id integer NOT NULL,
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
    AS integer
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
    AS integer
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
-- Name: maasserver_regioncontrollerprocess; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_regioncontrollerprocess (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    pid integer NOT NULL,
    region_id integer NOT NULL
);


--
-- Name: maasserver_regioncontrollerprocess_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_regioncontrollerprocess_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    address inet NOT NULL,
    port integer NOT NULL,
    process_id integer NOT NULL
);


--
-- Name: maasserver_regioncontrollerprocessendpoint_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_regioncontrollerprocessendpoint_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    endpoint_id integer NOT NULL,
    rack_controller_id integer NOT NULL
);


--
-- Name: maasserver_regionrackrpcconnection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_regionrackrpcconnection_id_seq
    AS integer
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
    material bytea NOT NULL,
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
 SELECT if_left.node_id AS left_node_id,
    if_left.id AS left_interface_id,
    subnet_left.id AS left_subnet_id,
    vlan_left.id AS left_vlan_id,
    sip_left.ip AS left_ip,
    if_right.node_id AS right_node_id,
    if_right.id AS right_interface_id,
    subnet_right.id AS right_subnet_id,
    vlan_right.id AS right_vlan_id,
    sip_right.ip AS right_ip,
    vlan_left.space_id,
        CASE
            WHEN (if_left.node_id = if_right.node_id) THEN 0
            WHEN (subnet_left.id = subnet_right.id) THEN 1
            WHEN (vlan_left.id = vlan_right.id) THEN 2
            WHEN (vlan_left.space_id IS NOT NULL) THEN 3
            ELSE 4
        END AS metric
   FROM (((((((((public.maasserver_interface if_left
     JOIN public.maasserver_interface_ip_addresses ifia_left ON ((if_left.id = ifia_left.interface_id)))
     JOIN public.maasserver_staticipaddress sip_left ON ((ifia_left.staticipaddress_id = sip_left.id)))
     JOIN public.maasserver_subnet subnet_left ON ((sip_left.subnet_id = subnet_left.id)))
     JOIN public.maasserver_vlan vlan_left ON ((subnet_left.vlan_id = vlan_left.id)))
     JOIN public.maasserver_vlan vlan_right ON ((NOT (vlan_left.space_id IS DISTINCT FROM vlan_right.space_id))))
     JOIN public.maasserver_subnet subnet_right ON ((vlan_right.id = subnet_right.vlan_id)))
     JOIN public.maasserver_staticipaddress sip_right ON ((subnet_right.id = sip_right.subnet_id)))
     JOIN public.maasserver_interface_ip_addresses ifia_right ON ((sip_right.id = ifia_right.staticipaddress_id)))
     JOIN public.maasserver_interface if_right ON ((ifia_right.interface_id = if_right.id)))
  WHERE (if_left.enabled AND (sip_left.ip IS NOT NULL) AND if_right.enabled AND (sip_right.ip IS NOT NULL) AND (family(sip_left.ip) = family(sip_right.ip)));


--
-- Name: maasserver_service; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_service (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    status character varying(10) NOT NULL,
    status_info character varying(255) NOT NULL,
    node_id integer NOT NULL
);


--
-- Name: maasserver_service_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_service_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256),
    description text NOT NULL
);


--
-- Name: maasserver_space_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_space_id_seq
    AS integer
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
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    key text NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_sslkey_id_seq
    AS integer
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
    AS integer
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
    id integer NOT NULL,
    gateway_ip inet NOT NULL,
    metric integer NOT NULL,
    destination_id integer NOT NULL,
    source_id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    CONSTRAINT maasserver_staticroute_metric_check CHECK ((metric >= 0))
);


--
-- Name: maasserver_staticroute_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_staticroute_id_seq
    AS integer
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
    AS integer
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
-- Name: maasserver_switch; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_switch (
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    nos_driver character varying(64) NOT NULL,
    nos_parameters text NOT NULL,
    node_id integer NOT NULL
);


--
-- Name: maasserver_tag; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_tag (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    definition text NOT NULL,
    comment text NOT NULL,
    kernel_opts text
);


--
-- Name: maasserver_tag_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_tag_id_seq
    AS integer
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
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    filename character varying(64) NOT NULL,
    default_version_id integer NOT NULL,
    version_id integer
);


--
-- Name: maasserver_template_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_template_id_seq
    AS integer
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
    id integer NOT NULL,
    user_id integer NOT NULL,
    completed_intro boolean NOT NULL,
    auth_last_check timestamp with time zone,
    is_local boolean NOT NULL
);


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_userprofile_id_seq
    AS integer
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
-- Name: maasserver_versionedtextfile; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_versionedtextfile (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    data text,
    comment character varying(255),
    previous_version_id integer
);


--
-- Name: maasserver_versionedtextfile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_versionedtextfile_id_seq
    AS integer
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
    blockdevice_ptr_id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    filesystem_group_id integer NOT NULL
);


--
-- Name: maasserver_vlan_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_vlan_id_seq
    AS integer
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
-- Name: maasserver_zone; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.maasserver_zone (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    description text NOT NULL
);


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.maasserver_zone_id_seq
    AS integer
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
-- Name: metadataserver_nodekey; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metadataserver_nodekey (
    id integer NOT NULL,
    key character varying(18) NOT NULL,
    node_id integer NOT NULL,
    token_id integer NOT NULL
);


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_nodekey_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_nodekey_id_seq OWNED BY public.metadataserver_nodekey.id;


--
-- Name: metadataserver_nodeuserdata; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metadataserver_nodeuserdata (
    id integer NOT NULL,
    data text NOT NULL,
    node_id integer NOT NULL
);


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_nodeuserdata_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_nodeuserdata_id_seq OWNED BY public.metadataserver_nodeuserdata.id;


--
-- Name: metadataserver_script; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metadataserver_script (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    tags text[],
    script_type integer NOT NULL,
    timeout interval NOT NULL,
    destructive boolean NOT NULL,
    "default" boolean NOT NULL,
    script_id integer NOT NULL,
    title character varying(255) NOT NULL,
    hardware_type integer NOT NULL,
    packages text NOT NULL,
    parallel integer NOT NULL,
    parameters text NOT NULL,
    results text NOT NULL,
    for_hardware character varying(255)[] NOT NULL,
    may_reboot boolean NOT NULL,
    recommission boolean NOT NULL
);


--
-- Name: metadataserver_script_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_script_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_script_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_script_id_seq OWNED BY public.metadataserver_script.id;


--
-- Name: metadataserver_scriptresult; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metadataserver_scriptresult (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    status integer NOT NULL,
    exit_status integer,
    script_name character varying(255),
    stdout text NOT NULL,
    stderr text NOT NULL,
    result text NOT NULL,
    script_id integer,
    script_set_id integer NOT NULL,
    script_version_id integer,
    output text NOT NULL,
    ended timestamp with time zone,
    started timestamp with time zone,
    parameters text NOT NULL,
    physical_blockdevice_id integer,
    suppressed boolean NOT NULL
);


--
-- Name: metadataserver_scriptresult_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_scriptresult_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_scriptresult_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_scriptresult_id_seq OWNED BY public.metadataserver_scriptresult.id;


--
-- Name: metadataserver_scriptset; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.metadataserver_scriptset (
    id integer NOT NULL,
    last_ping timestamp with time zone,
    result_type integer NOT NULL,
    node_id integer NOT NULL,
    power_state_before_transition character varying(10) NOT NULL,
    requested_scripts text[]
);


--
-- Name: metadataserver_scriptset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.metadataserver_scriptset_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_scriptset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.metadataserver_scriptset_id_seq OWNED BY public.metadataserver_scriptset.id;


--
-- Name: piston3_consumer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.piston3_consumer (
    id integer NOT NULL,
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
    AS integer
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
    id integer NOT NULL,
    token_key character varying(18) NOT NULL,
    consumer_key character varying(18) NOT NULL,
    key character varying(255) NOT NULL
);


--
-- Name: piston3_nonce_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.piston3_nonce_id_seq
    AS integer
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
    id integer NOT NULL,
    key character varying(18) NOT NULL,
    secret character varying(32) NOT NULL,
    verifier character varying(10) NOT NULL,
    token_type integer NOT NULL,
    "timestamp" integer NOT NULL,
    is_approved boolean NOT NULL,
    callback character varying(255),
    callback_confirmed boolean NOT NULL,
    consumer_id integer NOT NULL,
    user_id integer
);


--
-- Name: piston3_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.piston3_token_id_seq
    AS integer
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
-- Name: maasserver_fannetwork id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fannetwork ALTER COLUMN id SET DEFAULT nextval('public.maasserver_fannetwork_id_seq'::regclass);


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
-- Name: maasserver_nodegrouptorackcontroller id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodegrouptorackcontroller ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodegrouptorackcontroller_id_seq'::regclass);


--
-- Name: maasserver_nodemetadata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodemetadata ALTER COLUMN id SET DEFAULT nextval('public.maasserver_nodemetadata_id_seq'::regclass);


--
-- Name: maasserver_notification id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notification ALTER COLUMN id SET DEFAULT nextval('public.maasserver_notification_id_seq'::regclass);


--
-- Name: maasserver_notificationdismissal id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal ALTER COLUMN id SET DEFAULT nextval('public.maasserver_notificationdismissal_id_seq'::regclass);


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
-- Name: maasserver_vlan id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan ALTER COLUMN id SET DEFAULT nextval('public.maasserver_vlan_id_seq'::regclass);


--
-- Name: maasserver_zone id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_zone ALTER COLUMN id SET DEFAULT nextval('public.maasserver_zone_id_seq'::regclass);


--
-- Name: metadataserver_nodekey id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey ALTER COLUMN id SET DEFAULT nextval('public.metadataserver_nodekey_id_seq'::regclass);


--
-- Name: metadataserver_nodeuserdata id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodeuserdata ALTER COLUMN id SET DEFAULT nextval('public.metadataserver_nodeuserdata_id_seq'::regclass);


--
-- Name: metadataserver_script id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_script ALTER COLUMN id SET DEFAULT nextval('public.metadataserver_script_id_seq'::regclass);


--
-- Name: metadataserver_scriptresult id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptresult ALTER COLUMN id SET DEFAULT nextval('public.metadataserver_scriptresult_id_seq'::regclass);


--
-- Name: metadataserver_scriptset id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptset ALTER COLUMN id SET DEFAULT nextval('public.metadataserver_scriptset_id_seq'::regclass);


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
4	Can add group	2	add_group
5	Can change group	2	change_group
6	Can delete group	2	delete_group
7	Can add user	3	add_user
8	Can change user	3	change_user
9	Can delete user	3	delete_user
10	Can add content type	4	add_contenttype
11	Can change content type	4	change_contenttype
12	Can delete content type	4	delete_contenttype
13	Can add session	5	add_session
14	Can change session	5	change_session
15	Can delete session	5	delete_session
16	Can add site	6	add_site
17	Can change site	6	change_site
18	Can delete site	6	delete_site
19	Can add block device	7	add_blockdevice
20	Can change block device	7	change_blockdevice
21	Can delete block device	7	delete_blockdevice
22	Can add boot resource	8	add_bootresource
23	Can change boot resource	8	change_bootresource
24	Can delete boot resource	8	delete_bootresource
25	Can add boot resource file	9	add_bootresourcefile
26	Can change boot resource file	9	change_bootresourcefile
27	Can delete boot resource file	9	delete_bootresourcefile
28	Can add boot resource set	10	add_bootresourceset
29	Can change boot resource set	10	change_bootresourceset
30	Can delete boot resource set	10	delete_bootresourceset
31	Can add boot source	11	add_bootsource
32	Can change boot source	11	change_bootsource
33	Can delete boot source	11	delete_bootsource
34	Can add boot source cache	12	add_bootsourcecache
35	Can change boot source cache	12	change_bootsourcecache
36	Can delete boot source cache	12	delete_bootsourcecache
37	Can add boot source selection	13	add_bootsourceselection
38	Can change boot source selection	13	change_bootsourceselection
39	Can delete boot source selection	13	delete_bootsourceselection
40	Can add cache set	14	add_cacheset
41	Can change cache set	14	change_cacheset
42	Can delete cache set	14	delete_cacheset
43	Can add config	15	add_config
44	Can change config	15	change_config
45	Can delete config	15	delete_config
46	Can add Event record	16	add_event
47	Can change Event record	16	change_event
48	Can delete Event record	16	delete_event
49	Can add Event type	17	add_eventtype
50	Can change Event type	17	change_eventtype
51	Can delete Event type	17	delete_eventtype
52	Can add Fabric	18	add_fabric
53	Can change Fabric	18	change_fabric
54	Can delete Fabric	18	delete_fabric
55	Can add Fan Network	19	add_fannetwork
56	Can change Fan Network	19	change_fannetwork
57	Can delete Fan Network	19	delete_fannetwork
58	Can add file storage	20	add_filestorage
59	Can change file storage	20	change_filestorage
60	Can delete file storage	20	delete_filestorage
61	Can add filesystem	21	add_filesystem
62	Can change filesystem	21	change_filesystem
63	Can delete filesystem	21	delete_filesystem
64	Can add filesystem group	22	add_filesystemgroup
65	Can change filesystem group	22	change_filesystemgroup
66	Can delete filesystem group	22	delete_filesystemgroup
67	Can add Interface	23	add_interface
68	Can change Interface	23	change_interface
69	Can delete Interface	23	delete_interface
70	Can add interface relationship	24	add_interfacerelationship
71	Can change interface relationship	24	change_interfacerelationship
72	Can delete interface relationship	24	delete_interfacerelationship
73	Can add large file	25	add_largefile
74	Can change large file	25	change_largefile
75	Can delete large file	25	delete_largefile
76	Can add license key	26	add_licensekey
77	Can change license key	26	change_licensekey
78	Can delete license key	26	delete_licensekey
79	Can add node	27	add_node
80	Can change node	27	change_node
81	Can delete node	27	delete_node
82	Can add partition	28	add_partition
83	Can change partition	28	change_partition
84	Can delete partition	28	delete_partition
85	Can add partition table	29	add_partitiontable
86	Can change partition table	29	change_partitiontable
87	Can delete partition table	29	delete_partitiontable
88	Can add Space	30	add_space
89	Can change Space	30	change_space
90	Can delete Space	30	delete_space
91	Can add SSH key	31	add_sshkey
92	Can change SSH key	31	change_sshkey
93	Can delete SSH key	31	delete_sshkey
94	Can add SSL key	32	add_sslkey
95	Can change SSL key	32	change_sslkey
96	Can delete SSL key	32	delete_sslkey
97	Can add Static IP Address	33	add_staticipaddress
98	Can change Static IP Address	33	change_staticipaddress
99	Can delete Static IP Address	33	delete_staticipaddress
100	Can add subnet	34	add_subnet
101	Can change subnet	34	change_subnet
102	Can delete subnet	34	delete_subnet
103	Can add tag	35	add_tag
104	Can change tag	35	change_tag
105	Can delete tag	35	delete_tag
106	Can add user profile	36	add_userprofile
107	Can change user profile	36	change_userprofile
108	Can delete user profile	36	delete_userprofile
109	Can add VLAN	37	add_vlan
110	Can change VLAN	37	change_vlan
111	Can delete VLAN	37	delete_vlan
112	Can add Physical zone	38	add_zone
113	Can change Physical zone	38	change_zone
114	Can delete Physical zone	38	delete_zone
115	Can add physical block device	39	add_physicalblockdevice
116	Can change physical block device	39	change_physicalblockdevice
117	Can delete physical block device	39	delete_physicalblockdevice
118	Can add virtual block device	40	add_virtualblockdevice
119	Can change virtual block device	40	change_virtualblockdevice
120	Can delete virtual block device	40	delete_virtualblockdevice
121	Can add bcache	22	add_bcache
122	Can change bcache	22	change_bcache
123	Can delete bcache	22	delete_bcache
124	Can add Bond	23	add_bondinterface
125	Can change Bond	23	change_bondinterface
126	Can delete Bond	23	delete_bondinterface
127	Can add device	27	add_device
128	Can change device	27	change_device
129	Can delete device	27	delete_device
130	Can add Physical interface	23	add_physicalinterface
131	Can change Physical interface	23	change_physicalinterface
132	Can delete Physical interface	23	delete_physicalinterface
133	Can add raid	22	add_raid
134	Can change raid	22	change_raid
135	Can delete raid	22	delete_raid
136	Can add Unknown interface	23	add_unknowninterface
137	Can change Unknown interface	23	change_unknowninterface
138	Can delete Unknown interface	23	delete_unknowninterface
139	Can add VLAN interface	23	add_vlaninterface
140	Can change VLAN interface	23	change_vlaninterface
141	Can delete VLAN interface	23	delete_vlaninterface
142	Can add volume group	22	add_volumegroup
143	Can change volume group	22	change_volumegroup
144	Can delete volume group	22	delete_volumegroup
145	Can add machine	27	add_machine
146	Can change machine	27	change_machine
147	Can delete machine	27	delete_machine
148	Can add rack controller	27	add_rackcontroller
149	Can change rack controller	27	change_rackcontroller
150	Can delete rack controller	27	delete_rackcontroller
151	Can add DNSResource	41	add_dnsresource
152	Can change DNSResource	41	change_dnsresource
153	Can delete DNSResource	41	delete_dnsresource
154	Can add Domain	42	add_domain
155	Can change Domain	42	change_domain
156	Can delete Domain	42	delete_domain
157	Can add region controller process	43	add_regioncontrollerprocess
158	Can change region controller process	43	change_regioncontrollerprocess
159	Can delete region controller process	43	delete_regioncontrollerprocess
160	Can add region controller process endpoint	44	add_regioncontrollerprocessendpoint
161	Can change region controller process endpoint	44	change_regioncontrollerprocessendpoint
162	Can delete region controller process endpoint	44	delete_regioncontrollerprocessendpoint
163	Can add region controller	27	add_regioncontroller
164	Can change region controller	27	change_regioncontroller
165	Can delete region controller	27	delete_regioncontroller
166	Can add bmc	45	add_bmc
167	Can change bmc	45	change_bmc
168	Can delete bmc	45	delete_bmc
169	Can add DNSData	46	add_dnsdata
170	Can change DNSData	46	change_dnsdata
171	Can delete DNSData	46	delete_dnsdata
172	Can add ip range	47	add_iprange
173	Can change ip range	47	change_iprange
174	Can delete ip range	47	delete_iprange
175	Can add node group to rack controller	48	add_nodegrouptorackcontroller
176	Can change node group to rack controller	48	change_nodegrouptorackcontroller
177	Can delete node group to rack controller	48	delete_nodegrouptorackcontroller
178	Can add region rack rpc connection	49	add_regionrackrpcconnection
179	Can change region rack rpc connection	49	change_regionrackrpcconnection
180	Can delete region rack rpc connection	49	delete_regionrackrpcconnection
181	Can add service	50	add_service
182	Can change service	50	change_service
183	Can delete service	50	delete_service
184	Can add Template	51	add_template
185	Can change Template	51	change_template
186	Can delete Template	51	delete_template
187	Can add VersionedTextFile	52	add_versionedtextfile
188	Can change VersionedTextFile	52	change_versionedtextfile
189	Can delete VersionedTextFile	52	delete_versionedtextfile
190	Can add bmc routable rack controller relationship	53	add_bmcroutablerackcontrollerrelationship
191	Can change bmc routable rack controller relationship	53	change_bmcroutablerackcontrollerrelationship
192	Can delete bmc routable rack controller relationship	53	delete_bmcroutablerackcontrollerrelationship
193	Can add dhcp snippet	54	add_dhcpsnippet
194	Can change dhcp snippet	54	change_dhcpsnippet
195	Can delete dhcp snippet	54	delete_dhcpsnippet
196	Can add child interface	23	add_childinterface
197	Can change child interface	23	change_childinterface
198	Can delete child interface	23	delete_childinterface
199	Can add Bridge	23	add_bridgeinterface
200	Can change Bridge	23	change_bridgeinterface
201	Can delete Bridge	23	delete_bridgeinterface
202	Can add owner data	55	add_ownerdata
203	Can change owner data	55	change_ownerdata
204	Can delete owner data	55	delete_ownerdata
205	Can add controller	27	add_controller
206	Can change controller	27	change_controller
207	Can delete controller	27	delete_controller
208	Can add dns publication	56	add_dnspublication
209	Can change dns publication	56	change_dnspublication
210	Can delete dns publication	56	delete_dnspublication
211	Can add package repository	57	add_packagerepository
212	Can change package repository	57	change_packagerepository
213	Can delete package repository	57	delete_packagerepository
214	Can add mDNS binding	58	add_mdns
215	Can change mDNS binding	58	change_mdns
216	Can delete mDNS binding	58	delete_mdns
217	Can add Neighbour	59	add_neighbour
218	Can change Neighbour	59	change_neighbour
219	Can delete Neighbour	59	delete_neighbour
220	Can add static route	60	add_staticroute
221	Can change static route	60	change_staticroute
222	Can delete static route	60	delete_staticroute
223	Can add Key Source	61	add_keysource
224	Can change Key Source	61	change_keysource
225	Can delete Key Source	61	delete_keysource
226	Can add Discovery	62	add_discovery
227	Can change Discovery	62	change_discovery
228	Can delete Discovery	62	delete_discovery
229	Can add Reverse-DNS entry	63	add_rdns
230	Can change Reverse-DNS entry	63	change_rdns
231	Can delete Reverse-DNS entry	63	delete_rdns
232	Can add notification	64	add_notification
233	Can change notification	64	change_notification
234	Can delete notification	64	delete_notification
235	Can add notification dismissal	65	add_notificationdismissal
236	Can change notification dismissal	65	change_notificationdismissal
237	Can delete notification dismissal	65	delete_notificationdismissal
238	Can add pod hints	66	add_podhints
239	Can change pod hints	66	change_podhints
240	Can delete pod hints	66	delete_podhints
241	Can add pod	45	add_pod
242	Can change pod	45	change_pod
243	Can delete pod	45	delete_pod
244	Can add iscsi block device	67	add_iscsiblockdevice
245	Can change iscsi block device	67	change_iscsiblockdevice
246	Can delete iscsi block device	67	delete_iscsiblockdevice
247	Can add Switch	68	add_switch
248	Can change Switch	68	change_switch
249	Can delete Switch	68	delete_switch
250	Can add ControllerInfo	69	add_controllerinfo
251	Can change ControllerInfo	69	change_controllerinfo
252	Can delete ControllerInfo	69	delete_controllerinfo
253	Can add NodeMetadata	70	add_nodemetadata
254	Can change NodeMetadata	70	change_nodemetadata
255	Can delete NodeMetadata	70	delete_nodemetadata
256	Can add resource pool	71	add_resourcepool
257	Can change resource pool	71	change_resourcepool
258	Can delete resource pool	71	delete_resourcepool
259	Can add root key	72	add_rootkey
260	Can change root key	72	change_rootkey
261	Can delete root key	72	delete_rootkey
262	Can add global default	73	add_globaldefault
263	Can change global default	73	change_globaldefault
264	Can delete global default	73	delete_globaldefault
265	Can add pod storage pool	74	add_podstoragepool
266	Can change pod storage pool	74	change_podstoragepool
267	Can delete pod storage pool	74	delete_podstoragepool
268	Can add rbac sync	75	add_rbacsync
269	Can change rbac sync	75	change_rbacsync
270	Can delete rbac sync	75	delete_rbacsync
271	Can add rbac last sync	76	add_rbaclastsync
272	Can change rbac last sync	76	change_rbaclastsync
273	Can delete rbac last sync	76	delete_rbaclastsync
274	Can add vmfs	22	add_vmfs
275	Can change vmfs	22	change_vmfs
276	Can delete vmfs	22	delete_vmfs
277	Can add node key	93	add_nodekey
278	Can change node key	93	change_nodekey
279	Can delete node key	93	delete_nodekey
280	Can add node user data	94	add_nodeuserdata
281	Can change node user data	94	change_nodeuserdata
282	Can delete node user data	94	delete_nodeuserdata
283	Can add script	95	add_script
284	Can change script	95	change_script
285	Can delete script	95	delete_script
286	Can add script result	96	add_scriptresult
287	Can change script result	96	change_scriptresult
288	Can delete script result	96	delete_scriptresult
289	Can add script set	97	add_scriptset
290	Can change script set	97	change_scriptset
291	Can delete script set	97	delete_scriptset
292	Can add consumer	98	add_consumer
293	Can change consumer	98	change_consumer
294	Can delete consumer	98	delete_consumer
295	Can add nonce	99	add_nonce
296	Can change nonce	99	change_nonce
297	Can delete nonce	99	delete_nonce
298	Can add token	100	add_token
299	Can change token	100	change_token
300	Can delete token	100	delete_token
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
41	maasserver	dnsresource
42	maasserver	domain
43	maasserver	regioncontrollerprocess
44	maasserver	regioncontrollerprocessendpoint
45	maasserver	bmc
46	maasserver	dnsdata
47	maasserver	iprange
48	maasserver	nodegrouptorackcontroller
49	maasserver	regionrackrpcconnection
50	maasserver	service
51	maasserver	template
52	maasserver	versionedtextfile
53	maasserver	bmcroutablerackcontrollerrelationship
54	maasserver	dhcpsnippet
55	maasserver	ownerdata
56	maasserver	dnspublication
57	maasserver	packagerepository
58	maasserver	mdns
59	maasserver	neighbour
60	maasserver	staticroute
61	maasserver	keysource
62	maasserver	discovery
63	maasserver	rdns
64	maasserver	notification
65	maasserver	notificationdismissal
66	maasserver	podhints
67	maasserver	iscsiblockdevice
68	maasserver	switch
69	maasserver	controllerinfo
70	maasserver	nodemetadata
71	maasserver	resourcepool
72	maasserver	rootkey
73	maasserver	globaldefault
74	maasserver	podstoragepool
75	maasserver	rbacsync
76	maasserver	rbaclastsync
77	maasserver	bcache
78	maasserver	bondinterface
79	maasserver	device
80	maasserver	physicalinterface
81	maasserver	raid
82	maasserver	unknowninterface
83	maasserver	vlaninterface
84	maasserver	volumegroup
85	maasserver	machine
86	maasserver	rackcontroller
87	maasserver	regioncontroller
88	maasserver	childinterface
89	maasserver	bridgeinterface
90	maasserver	controller
91	maasserver	pod
92	maasserver	vmfs
93	metadataserver	nodekey
94	metadataserver	nodeuserdata
95	metadataserver	script
96	metadataserver	scriptresult
97	metadataserver	scriptset
98	piston3	consumer
99	piston3	nonce
100	piston3	token
\.


--
-- Data for Name: django_migrations; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.django_migrations (id, app, name, applied) FROM stdin;
1	contenttypes	0001_initial	2019-04-16 17:36:55.501914+00
2	auth	0001_initial	2019-04-16 17:36:55.524324+00
3	auth	0002_auto_20151119_1629	2019-04-16 17:36:55.612211+00
4	auth	0003_django_1_11_update	2019-04-16 17:36:55.624772+00
5	auth	0004_user_email_allow_null	2019-04-16 17:36:55.630658+00
6	contenttypes	0002_remove_content_type_name	2019-04-16 17:36:55.640941+00
7	piston3	0001_initial	2019-04-16 17:36:55.664582+00
8	maasserver	0001_initial	2019-04-16 17:36:56.524727+00
9	metadataserver	0001_initial	2019-04-16 17:36:56.691448+00
10	maasserver	0002_remove_candidate_name_model	2019-04-16 17:36:56.695131+00
11	maasserver	0003_add_node_type_to_node	2019-04-16 17:36:56.720313+00
12	maasserver	0004_migrate_installable_to_node_type	2019-04-16 17:36:56.773+00
13	maasserver	0005_delete_installable_from_node	2019-04-16 17:36:56.792103+00
14	maasserver	0006_add_lease_time_to_staticipaddress	2019-04-16 17:36:56.813389+00
15	maasserver	0007_create_node_proxy_models	2019-04-16 17:36:56.817239+00
16	maasserver	0008_use_new_arrayfield	2019-04-16 17:36:56.874798+00
17	maasserver	0009_remove_routers_field_from_node	2019-04-16 17:36:56.890968+00
18	maasserver	0010_add_dns_models	2019-04-16 17:36:56.963439+00
19	maasserver	0011_domain_data	2019-04-16 17:36:57.047973+00
20	maasserver	0012_drop_dns_fields	2019-04-16 17:36:57.178856+00
21	maasserver	0013_remove_boot_type_from_node	2019-04-16 17:36:57.198101+00
22	maasserver	0014_add_region_models	2019-04-16 17:36:57.311805+00
23	maasserver	0015_add_bmc_model	2019-04-16 17:36:57.38435+00
24	maasserver	0016_migrate_power_data_node_to_bmc	2019-04-16 17:36:57.428096+00
25	maasserver	0017_remove_node_power_type	2019-04-16 17:36:57.447126+00
26	maasserver	0018_add_dnsdata	2019-04-16 17:36:57.498685+00
27	maasserver	0019_add_iprange	2019-04-16 17:36:57.525608+00
28	maasserver	0020_nodegroup_to_rackcontroller	2019-04-16 17:36:57.676312+00
29	maasserver	0021_nodegroupinterface_to_iprange	2019-04-16 17:36:57.716365+00
30	maasserver	0022_extract_ip_for_bmcs	2019-04-16 17:36:57.767014+00
31	maasserver	0023_add_ttl_field	2019-04-16 17:36:57.867868+00
32	maasserver	0024_remove_nodegroupinterface	2019-04-16 17:36:58.271861+00
33	maasserver	0025_create_node_system_id_sequence	2019-04-16 17:36:58.27726+00
34	maasserver	0026_create_zone_serial_sequence	2019-04-16 17:36:58.281644+00
35	maasserver	0027_replace_static_range_with_admin_reserved_ranges	2019-04-16 17:36:58.327235+00
36	maasserver	0028_update_default_vlan_on_interface_and_subnet	2019-04-16 17:36:58.386472+00
37	maasserver	0029_add_rdns_mode	2019-04-16 17:36:58.401049+00
38	maasserver	0030_drop_all_old_funcs	2019-04-16 17:36:58.443815+00
39	maasserver	0031_add_region_rack_rpc_conn_model	2019-04-16 17:36:58.61988+00
40	maasserver	0032_loosen_vlan	2019-04-16 17:36:58.673017+00
41	maasserver	0033_iprange_minor_changes	2019-04-16 17:36:58.740017+00
42	maasserver	0034_rename_mount_params_as_mount_options	2019-04-16 17:36:58.757097+00
43	maasserver	0035_convert_ether_wake_to_manual_power_type	2019-04-16 17:36:58.799252+00
44	maasserver	0036_add_service_model	2019-04-16 17:36:58.844134+00
45	maasserver	0037_node_last_image_sync	2019-04-16 17:36:58.865274+00
46	maasserver	0038_filesystem_ramfs_tmpfs_support	2019-04-16 17:36:58.915884+00
47	maasserver	0039_create_template_and_versionedtextfile_models	2019-04-16 17:36:58.939744+00
48	maasserver	0040_fix_id_seq	2019-04-16 17:36:58.942561+00
49	maasserver	0041_change_bmc_on_delete_to_set_null	2019-04-16 17:36:58.970527+00
50	maasserver	0042_add_routable_rack_controllers_to_bmc	2019-04-16 17:36:59.109347+00
51	maasserver	0043_dhcpsnippet	2019-04-16 17:36:59.144385+00
52	maasserver	0044_remove_di_bootresourcefiles	2019-04-16 17:36:59.201353+00
53	maasserver	0045_add_node_to_filesystem	2019-04-16 17:36:59.240419+00
54	maasserver	0046_add_bridge_interface_type	2019-04-16 17:36:59.265746+00
55	maasserver	0047_fix_spelling_of_degraded	2019-04-16 17:36:59.329345+00
56	maasserver	0048_add_subnet_allow_proxy	2019-04-16 17:36:59.342215+00
57	maasserver	0049_add_external_dhcp_present_to_vlan	2019-04-16 17:36:59.430811+00
58	maasserver	0050_modify_external_dhcp_on_vlan	2019-04-16 17:36:59.640234+00
59	maasserver	0051_space_fabric_unique	2019-04-16 17:36:59.740465+00
60	maasserver	0052_add_codename_title_eol_to_bootresourcecache	2019-04-16 17:36:59.761803+00
61	maasserver	0053_add_ownerdata_model	2019-04-16 17:36:59.812833+00
62	maasserver	0054_controller	2019-04-16 17:36:59.817516+00
63	maasserver	0055_dns_publications	2019-04-16 17:36:59.822889+00
64	maasserver	0056_zone_serial_ownership	2019-04-16 17:36:59.827238+00
65	maasserver	0057_initial_dns_publication	2019-04-16 17:36:59.876357+00
66	maasserver	0058_bigger_integer_for_dns_publication_serial	2019-04-16 17:36:59.883775+00
67	maasserver	0056_add_description_to_fabric_and_space	2019-04-16 17:36:59.99166+00
68	maasserver	0057_merge	2019-04-16 17:36:59.993223+00
69	maasserver	0059_merge	2019-04-16 17:36:59.995233+00
70	maasserver	0060_amt_remove_mac_address	2019-04-16 17:37:00.046534+00
71	maasserver	0061_maas_nodegroup_worker_to_maas	2019-04-16 17:37:00.186102+00
72	maasserver	0062_fix_bootsource_daily_label	2019-04-16 17:37:00.239049+00
73	maasserver	0063_remove_orphaned_bmcs_and_ips	2019-04-16 17:37:00.290026+00
74	maasserver	0064_remove_unneeded_event_triggers	2019-04-16 17:37:00.341201+00
75	maasserver	0065_larger_osystem_and_distro_series	2019-04-16 17:37:00.404157+00
76	maasserver	0066_allow_squashfs	2019-04-16 17:37:00.412484+00
77	maasserver	0067_add_size_to_largefile	2019-04-16 17:37:00.468827+00
78	maasserver	0068_drop_node_system_id_sequence	2019-04-16 17:37:00.47158+00
79	maasserver	0069_add_previous_node_status_to_node	2019-04-16 17:37:00.498723+00
80	maasserver	0070_allow_null_vlan_on_interface	2019-04-16 17:37:00.530503+00
81	maasserver	0071_ntp_server_to_ntp_servers	2019-04-16 17:37:00.533156+00
82	maasserver	0072_packagerepository	2019-04-16 17:37:00.539127+00
83	maasserver	0073_migrate_package_repositories	2019-04-16 17:37:00.674315+00
84	maasserver	0072_update_status_and_previous_status	2019-04-16 17:37:00.840657+00
85	maasserver	0074_merge	2019-04-16 17:37:00.841837+00
86	maasserver	0075_modify_packagerepository	2019-04-16 17:37:00.862177+00
87	maasserver	0076_interface_discovery_rescue_mode	2019-04-16 17:37:01.092169+00
88	maasserver	0077_static_routes	2019-04-16 17:37:01.135068+00
89	maasserver	0078_remove_packagerepository_description	2019-04-16 17:37:01.140089+00
90	maasserver	0079_add_keysource_model	2019-04-16 17:37:01.194301+00
91	maasserver	0080_change_packagerepository_url_type	2019-04-16 17:37:01.199039+00
92	maasserver	0081_allow_larger_bootsourcecache_fields	2019-04-16 17:37:01.224346+00
93	maasserver	0082_add_kflavor	2019-04-16 17:37:01.43096+00
94	maasserver	0083_device_discovery	2019-04-16 17:37:01.467246+00
95	maasserver	0084_add_default_user_to_node_model	2019-04-16 17:37:01.501023+00
96	maasserver	0085_no_intro_on_upgrade	2019-04-16 17:37:01.551578+00
97	maasserver	0086_remove_powerpc_from_ports_arches	2019-04-16 17:37:01.602206+00
98	maasserver	0087_add_completed_intro_to_userprofile	2019-04-16 17:37:01.617141+00
99	maasserver	0088_remove_node_disable_ipv4	2019-04-16 17:37:01.645487+00
100	maasserver	0089_active_discovery	2019-04-16 17:37:01.698768+00
101	maasserver	0090_bootloaders	2019-04-16 17:37:01.720966+00
102	maasserver	0091_v2_to_v3	2019-04-16 17:37:01.786127+00
103	maasserver	0092_rolling	2019-04-16 17:37:01.793135+00
104	maasserver	0093_add_rdns_model	2019-04-16 17:37:01.939918+00
105	maasserver	0094_add_unmanaged_subnets	2019-04-16 17:37:01.955615+00
106	maasserver	0095_vlan_relay_vlan	2019-04-16 17:37:01.985536+00
107	maasserver	0096_set_default_vlan_field	2019-04-16 17:37:02.016516+00
108	maasserver	0097_node_chassis_storage_hints	2019-04-16 17:37:02.17322+00
109	maasserver	0098_add_space_to_vlan	2019-04-16 17:37:02.204595+00
110	maasserver	0099_set_default_vlan_field	2019-04-16 17:37:02.236778+00
111	maasserver	0100_migrate_spaces_from_subnet_to_vlan	2019-04-16 17:37:02.289853+00
112	maasserver	0101_filesystem_btrfs_support	2019-04-16 17:37:02.314024+00
113	maasserver	0102_remove_space_from_subnet	2019-04-16 17:37:02.356748+00
114	maasserver	0103_notifications	2019-04-16 17:37:02.50474+00
115	maasserver	0104_notifications_dismissals	2019-04-16 17:37:02.539849+00
116	metadataserver	0002_script_models	2019-04-16 17:37:02.755999+00
117	maasserver	0105_add_script_sets_to_node_model	2019-04-16 17:37:02.867701+00
118	maasserver	0106_testing_status	2019-04-16 17:37:02.927317+00
119	maasserver	0107_chassis_to_pods	2019-04-16 17:37:03.351328+00
120	maasserver	0108_generate_bmc_names	2019-04-16 17:37:03.406471+00
121	maasserver	0109_bmc_names_unique	2019-04-16 17:37:03.429658+00
122	maasserver	0110_notification_category	2019-04-16 17:37:03.444753+00
123	maasserver	0111_remove_component_error	2019-04-16 17:37:03.448566+00
124	maasserver	0112_update_notification	2019-04-16 17:37:03.518698+00
125	maasserver	0113_set_filepath_limit_to_linux_max	2019-04-16 17:37:03.662862+00
126	maasserver	0114_node_dynamic_to_creation_type	2019-04-16 17:37:03.724841+00
127	maasserver	0115_additional_boot_resource_filetypes	2019-04-16 17:37:03.738009+00
128	maasserver	0116_add_disabled_components_for_mirrors	2019-04-16 17:37:03.747253+00
129	maasserver	0117_add_iscsi_block_device	2019-04-16 17:37:03.778613+00
130	maasserver	0118_add_iscsi_storage_pod	2019-04-16 17:37:03.82572+00
131	maasserver	0119_set_default_vlan_field	2019-04-16 17:37:03.871722+00
132	maasserver	0120_bootsourcecache_extra	2019-04-16 17:37:03.87989+00
133	maasserver	0121_relax_staticipaddress_unique_constraint	2019-04-16 17:37:03.921315+00
134	maasserver	0122_make_virtualblockdevice_uuid_editable	2019-04-16 17:37:03.933793+00
135	maasserver	0123_make_iprange_comment_default_to_empty_string	2019-04-16 17:37:03.950462+00
136	maasserver	0124_staticipaddress_address_family_index	2019-04-16 17:37:03.95353+00
137	maasserver	0125_add_switch_model	2019-04-16 17:37:03.987396+00
138	maasserver	0126_add_controllerinfo_model	2019-04-16 17:37:04.078359+00
139	maasserver	0127_nodemetadata	2019-04-16 17:37:04.136094+00
140	maasserver	0128_events_created_index	2019-04-16 17:37:04.139414+00
141	maasserver	0129_add_install_rackd_flag	2019-04-16 17:37:04.170553+00
142	maasserver	0130_node_locked_flag	2019-04-16 17:37:04.202194+00
143	maasserver	0131_update_event_model_for_audit_logs	2019-04-16 17:37:04.469151+00
144	maasserver	0132_consistent_model_name_validation	2019-04-16 17:37:04.510766+00
145	maasserver	0133_add_resourcepool_model	2019-04-16 17:37:04.516263+00
146	maasserver	0134_create_default_resourcepool	2019-04-16 17:37:04.57699+00
147	maasserver	0135_add_pool_reference_to_node	2019-04-16 17:37:04.671845+00
148	maasserver	0136_add_user_role_models	2019-04-16 17:37:04.713715+00
149	maasserver	0137_create_default_roles	2019-04-16 17:37:04.791035+00
150	maasserver	0138_add_ip_and_user_agent_to_event_model	2019-04-16 17:37:04.849801+00
151	maasserver	0139_add_endpoint_and_increase_user_agent_length_for_event	2019-04-16 17:37:05.04435+00
152	maasserver	0140_add_usergroup_model	2019-04-16 17:37:05.117957+00
153	maasserver	0141_add_default_usergroup	2019-04-16 17:37:05.178319+00
154	maasserver	0142_pod_default_resource_pool	2019-04-16 17:37:05.270875+00
155	maasserver	0143_blockdevice_firmware	2019-04-16 17:37:05.282841+00
156	maasserver	0144_filesystem_zfsroot_support	2019-04-16 17:37:05.304294+00
157	maasserver	0145_interface_firmware	2019-04-16 17:37:05.374242+00
158	maasserver	0146_add_rootkey	2019-04-16 17:37:05.379243+00
159	maasserver	0147_pod_zones	2019-04-16 17:37:05.415598+00
160	maasserver	0148_add_tags_on_pods	2019-04-16 17:37:05.447827+00
161	maasserver	0149_userprofile_auth_last_check	2019-04-16 17:37:05.461514+00
162	maasserver	0150_add_pod_commit_ratios	2019-04-16 17:37:05.510538+00
163	maasserver	0151_userprofile_is_local	2019-04-16 17:37:05.526674+00
164	maasserver	0152_add_usergroup_local	2019-04-16 17:37:05.543247+00
165	maasserver	0153_add_skip_bmc_config	2019-04-16 17:37:05.575709+00
166	maasserver	0154_link_usergroup_role	2019-04-16 17:37:05.837148+00
167	maasserver	0155_add_globaldefaults_model	2019-04-16 17:37:05.98717+00
168	maasserver	0156_drop_ssh_unique_key_index	2019-04-16 17:37:06.013039+00
169	maasserver	0157_drop_usergroup_and_role	2019-04-16 17:37:06.282489+00
170	maasserver	0158_pod_default_pool_to_pod	2019-04-16 17:37:06.331371+00
171	maasserver	0159_userprofile_auth_last_check_no_now_default	2019-04-16 17:37:06.516823+00
172	maasserver	0160_pool_only_for_machines	2019-04-16 17:37:06.574181+00
173	maasserver	0161_pod_storage_pools	2019-04-16 17:37:06.707258+00
174	maasserver	0162_storage_pools_notification	2019-04-16 17:37:06.788267+00
175	maasserver	0163_create_new_power_parameters_with_jsonfield	2019-04-16 17:37:06.857672+00
176	maasserver	0164_copy_over_existing_power_parameters	2019-04-16 17:37:06.920072+00
177	maasserver	0165_remove_and_rename_power_parameters	2019-04-16 17:37:07.1754+00
178	maasserver	0166_auto_select_s390x_extra_arches	2019-04-16 17:37:07.236168+00
179	maasserver	0167_add_pod_host	2019-04-16 17:37:07.278091+00
180	maasserver	0168_add_pod_default_macvlan_mode	2019-04-16 17:37:07.310484+00
181	maasserver	0169_find_pod_host	2019-04-16 17:37:07.311622+00
182	maasserver	0170_add_subnet_allow_dns	2019-04-16 17:37:07.325742+00
183	maasserver	0171_remove_pod_host	2019-04-16 17:37:07.369634+00
184	maasserver	0172_partition_tags	2019-04-16 17:37:07.382005+00
185	maasserver	0173_add_node_install_kvm	2019-04-16 17:37:07.421282+00
186	maasserver	0174_add_user_id_and_node_system_id_for_events	2019-04-16 17:37:07.481066+00
187	maasserver	0175_copy_user_id_and_node_system_id_for_events	2019-04-16 17:37:07.541046+00
188	maasserver	0176_rename_user_id_migrate_to_user_id_for_events	2019-04-16 17:37:07.608531+00
189	maasserver	0177_remove_unique_together_on_bmc	2019-04-16 17:37:07.638324+00
190	maasserver	0178_break_apart_linked_bmcs	2019-04-16 17:37:07.697226+00
191	maasserver	0179_rbacsync	2019-04-16 17:37:07.702617+00
192	maasserver	0180_rbaclastsync	2019-04-16 17:37:07.709333+00
193	maasserver	0181_packagerepository_disable_sources	2019-04-16 17:37:07.869781+00
194	maasserver	0182_remove_duplicate_null_ips	2019-04-16 17:37:07.87898+00
195	maasserver	0183_node_uuid	2019-04-16 17:37:07.912023+00
196	maasserver	0184_add_ephemeral_deploy_setting_to_node	2019-04-16 17:37:07.952222+00
197	maasserver	0185_vmfs6	2019-04-16 17:37:07.992201+00
198	maasserver	0186_node_description	2019-04-16 17:37:08.028878+00
199	metadataserver	0003_remove_noderesult	2019-04-16 17:37:08.08989+00
200	metadataserver	0004_aborted_script_status	2019-04-16 17:37:08.100884+00
201	metadataserver	0005_store_powerstate_on_scriptset_creation	2019-04-16 17:37:08.1223+00
202	metadataserver	0006_scriptresult_combined_output	2019-04-16 17:37:08.137487+00
203	metadataserver	0007_migrate-commissioningscripts	2019-04-16 17:37:08.198422+00
204	metadataserver	0008_remove-commissioningscripts	2019-04-16 17:37:08.203058+00
205	metadataserver	0009_remove_noderesult_schema	2019-04-16 17:37:08.208025+00
206	metadataserver	0010_scriptresult_time_and_script_title	2019-04-16 17:37:08.242006+00
207	metadataserver	0011_script_metadata	2019-04-16 17:37:08.302883+00
208	metadataserver	0012_store_script_results	2019-04-16 17:37:08.325377+00
209	metadataserver	0013_scriptresult_physicalblockdevice	2019-04-16 17:37:08.409689+00
210	metadataserver	0014_rename_dhcp_unconfigured_ifaces	2019-04-16 17:37:08.469905+00
211	metadataserver	0015_migrate_storage_tests	2019-04-16 17:37:08.530112+00
212	metadataserver	0016_script_model_fw_update_and_hw_config	2019-04-16 17:37:08.56081+00
213	metadataserver	0017_store_requested_scripts	2019-04-16 17:37:08.76682+00
214	metadataserver	0018_script_result_skipped	2019-04-16 17:37:08.781929+00
215	metadataserver	0019_add_script_result_suppressed	2019-04-16 17:37:08.800124+00
216	piston3	0002_auto_20151209_1652	2019-04-16 17:37:08.812509+00
217	sessions	0001_initial	2019-04-16 17:37:08.817576+00
218	sites	0001_initial	2019-04-16 17:37:08.822308+00
219	sites	0002_alter_domain_unique	2019-04-16 17:37:08.828947+00
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

COPY public.maasserver_blockdevice (id, created, updated, name, id_path, size, block_size, tags, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bmc; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bmc (id, created, updated, power_type, ip_address_id, architectures, bmc_type, capabilities, cores, cpu_speed, local_disks, local_storage, memory, name, iscsi_storage, pool_id, zone_id, tags, cpu_over_commit_ratio, memory_over_commit_ratio, default_storage_pool_id, power_parameters, default_macvlan_mode) FROM stdin;
\.


--
-- Data for Name: maasserver_bmcroutablerackcontrollerrelationship; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bmcroutablerackcontrollerrelationship (id, created, updated, routable, bmc_id, rack_controller_id) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresource (id, created, updated, rtype, name, architecture, extra, kflavor, bootloader_type, rolling) FROM stdin;
\.


--
-- Data for Name: maasserver_bootresourcefile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_bootresourcefile (id, created, updated, filename, filetype, extra, largefile_id, resource_set_id) FROM stdin;
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

COPY public.maasserver_controllerinfo (created, updated, node_id, version, interfaces, interface_update_hints) FROM stdin;
\.


--
-- Data for Name: maasserver_dhcpsnippet; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_dhcpsnippet (id, created, updated, name, description, enabled, node_id, subnet_id, value_id) FROM stdin;
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
1	1	2019-04-16 17:36:59.875074+00	Initial publication
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
0	2019-04-16 17:36:57.007061+00	2019-04-16 17:36:57.007061+00	maas	t	\N
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
0	2019-04-16 17:37:03.858242+00	2019-04-16 17:37:03.86234+00	fabric-0	\N	
\.


--
-- Data for Name: maasserver_fannetwork; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_fannetwork (id, created, updated, name, "overlay", underlay, dhcp, host_reserve, bridge, off) FROM stdin;
\.


--
-- Data for Name: maasserver_filestorage; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_filestorage (id, filename, content, key, owner_id) FROM stdin;
\.


--
-- Data for Name: maasserver_filesystem; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_filesystem (id, created, updated, uuid, fstype, label, create_params, mount_point, mount_options, acquired, block_device_id, cache_set_id, filesystem_group_id, partition_id, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_filesystemgroup; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_filesystemgroup (id, created, updated, uuid, group_type, name, create_params, cache_mode, cache_set_id) FROM stdin;
\.


--
-- Data for Name: maasserver_globaldefault; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_globaldefault (id, created, updated, domain_id) FROM stdin;
0	2019-04-16 17:37:05.925692+00	2019-04-16 17:37:05.928476+00	0
\.


--
-- Data for Name: maasserver_interface; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_interface (id, created, updated, name, type, mac_address, ipv4_params, ipv6_params, params, tags, enabled, node_id, vlan_id, acquired, mdns_discovery_state, neighbour_discovery_state, firmware_version, product, vendor) FROM stdin;
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
-- Data for Name: maasserver_iscsiblockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_iscsiblockdevice (blockdevice_ptr_id, target) FROM stdin;
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

COPY public.maasserver_node (id, created, updated, system_id, hostname, status, bios_boot_method, osystem, distro_series, architecture, min_hwe_kernel, hwe_kernel, agent_name, error_description, cpu_count, memory, swap_size, power_state, power_state_updated, error, netboot, license_key, boot_cluster_ip, enable_ssh, skip_networking, skip_storage, boot_interface_id, gateway_link_ipv4_id, gateway_link_ipv6_id, owner_id, parent_id, token_id, zone_id, boot_disk_id, node_type, domain_id, dns_process_id, bmc_id, address_ttl, status_expires, power_state_queried, url, managing_process_id, last_image_sync, previous_status, default_user, cpu_speed, current_commissioning_script_set_id, current_installation_script_set_id, current_testing_script_set_id, creation_type, install_rackd, locked, pool_id, skip_bmc_config, instance_power_parameters, install_kvm, hardware_uuid, ephemeral_deploy, description) FROM stdin;
\.


--
-- Data for Name: maasserver_node_tags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_node_tags (id, node_id, tag_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodegrouptorackcontroller; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodegrouptorackcontroller (id, uuid, subnet_id) FROM stdin;
\.


--
-- Data for Name: maasserver_nodemetadata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_nodemetadata (id, created, updated, key, value, node_id) FROM stdin;
\.


--
-- Data for Name: maasserver_notification; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_notification (id, created, updated, ident, users, admins, message, context, user_id, category) FROM stdin;
\.


--
-- Data for Name: maasserver_notificationdismissal; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_notificationdismissal (id, notification_id, user_id) FROM stdin;
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
1	2019-04-16 17:37:00.58845+00	2019-04-16 17:37:00.58845+00	main_archive	http://archive.ubuntu.com/ubuntu	{}	{amd64,i386}		t	t	{}	{}	{}	t
2	2019-04-16 17:37:00.58845+00	2019-04-16 17:37:00.58845+00	ports_archive	http://ports.ubuntu.com/ubuntu-ports	{}	{armhf,arm64,ppc64el,s390x}		t	t	{}	{}	{}	t
\.


--
-- Data for Name: maasserver_partition; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_partition (id, created, updated, uuid, size, bootable, partition_table_id, tags) FROM stdin;
\.


--
-- Data for Name: maasserver_partitiontable; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_partitiontable (id, created, updated, table_type, block_device_id) FROM stdin;
\.


--
-- Data for Name: maasserver_physicalblockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_physicalblockdevice (blockdevice_ptr_id, model, serial, firmware_version, storage_pool_id) FROM stdin;
\.


--
-- Data for Name: maasserver_podhints; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_podhints (id, cores, memory, local_storage, local_disks, pod_id, cpu_speed, iscsi_storage) FROM stdin;
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
0	2019-04-16 17:37:04.573624+00	2019-04-16 17:37:04.573624+00	default	Default pool
\.


--
-- Data for Name: maasserver_rootkey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_rootkey (created, updated, id, material, expiration) FROM stdin;
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

COPY public.maasserver_staticipaddress (id, created, updated, ip, alloc_type, subnet_id, user_id, lease_time) FROM stdin;
\.


--
-- Data for Name: maasserver_staticroute; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_staticroute (id, gateway_ip, metric, destination_id, source_id, created, updated) FROM stdin;
\.


--
-- Data for Name: maasserver_subnet; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_subnet (id, created, updated, name, cidr, gateway_ip, dns_servers, vlan_id, rdns_mode, allow_proxy, description, active_discovery, managed, allow_dns) FROM stdin;
\.


--
-- Data for Name: maasserver_switch; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_switch (created, updated, nos_driver, nos_parameters, node_id) FROM stdin;
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
-- Data for Name: maasserver_vlan; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_vlan (id, created, updated, name, vid, mtu, fabric_id, dhcp_on, primary_rack_id, secondary_rack_id, external_dhcp, description, relay_vlan_id, space_id) FROM stdin;
5001	2019-04-16 17:37:03.866778+00	2019-04-16 17:37:03.866778+00	Default VLAN	0	1500	0	f	\N	\N	\N		\N	\N
\.


--
-- Data for Name: maasserver_zone; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.maasserver_zone (id, created, updated, name, description) FROM stdin;
1	2019-04-16 17:36:56.031348+00	2019-04-16 17:36:56.031348+00	default	
\.


--
-- Data for Name: metadataserver_nodekey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metadataserver_nodekey (id, key, node_id, token_id) FROM stdin;
\.


--
-- Data for Name: metadataserver_nodeuserdata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metadataserver_nodeuserdata (id, data, node_id) FROM stdin;
\.


--
-- Data for Name: metadataserver_script; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metadataserver_script (id, created, updated, name, description, tags, script_type, timeout, destructive, "default", script_id, title, hardware_type, packages, parallel, parameters, results, for_hardware, may_reboot, recommission) FROM stdin;
\.


--
-- Data for Name: metadataserver_scriptresult; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metadataserver_scriptresult (id, created, updated, status, exit_status, script_name, stdout, stderr, result, script_id, script_set_id, script_version_id, output, ended, started, parameters, physical_blockdevice_id, suppressed) FROM stdin;
\.


--
-- Data for Name: metadataserver_scriptset; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.metadataserver_scriptset (id, last_ping, result_type, node_id, power_state_before_transition, requested_scripts) FROM stdin;
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

SELECT pg_catalog.setval('public.auth_permission_id_seq', 300, true);


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

SELECT pg_catalog.setval('public.django_content_type_id_seq', 100, true);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.django_migrations_id_seq', 219, true);


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
-- Name: maasserver_fannetwork_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_fannetwork_id_seq', 1, false);


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

SELECT pg_catalog.setval('public.maasserver_notification_id_seq', 1, true);


--
-- Name: maasserver_notificationdismissal_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_notificationdismissal_id_seq', 1, false);


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
-- Name: maasserver_vlan_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_vlan_id_seq', 5001, true);


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_zone_id_seq', 1, true);


--
-- Name: maasserver_zone_serial_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.maasserver_zone_serial_seq', 3, true);


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
-- Name: maasserver_blockdevice maasserver_blockdevice_node_id_name_1dddf3d0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_node_id_name_1dddf3d0_uniq UNIQUE (node_id, name);


--
-- Name: maasserver_blockdevice maasserver_blockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bmc maasserver_bmc_name_144ffd80_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_name_144ffd80_uniq UNIQUE (name);


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
-- Name: maasserver_bootresource maasserver_bootresource_name_architecture_57af8656_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresource
    ADD CONSTRAINT maasserver_bootresource_name_architecture_57af8656_uniq UNIQUE (name, architecture);


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
-- Name: maasserver_fannetwork maasserver_fannetwork_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fannetwork
    ADD CONSTRAINT maasserver_fannetwork_name_key UNIQUE (name);


--
-- Name: maasserver_fannetwork maasserver_fannetwork_overlay_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fannetwork
    ADD CONSTRAINT maasserver_fannetwork_overlay_key UNIQUE ("overlay");


--
-- Name: maasserver_fannetwork maasserver_fannetwork_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fannetwork
    ADD CONSTRAINT maasserver_fannetwork_pkey PRIMARY KEY (id);


--
-- Name: maasserver_fannetwork maasserver_fannetwork_underlay_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_fannetwork
    ADD CONSTRAINT maasserver_fannetwork_underlay_key UNIQUE (underlay);


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
-- Name: maasserver_filesystemgroup maasserver_filesystemgroup_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystemgroup
    ADD CONSTRAINT maasserver_filesystemgroup_uuid_key UNIQUE (uuid);


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
-- Name: maasserver_iscsiblockdevice maasserver_iscsiblockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iscsiblockdevice
    ADD CONSTRAINT maasserver_iscsiblockdevice_pkey PRIMARY KEY (blockdevice_ptr_id);


--
-- Name: maasserver_iscsiblockdevice maasserver_iscsiblockdevice_target_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iscsiblockdevice
    ADD CONSTRAINT maasserver_iscsiblockdevice_target_key UNIQUE (target);


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
-- Name: maasserver_node maasserver_node_dns_process_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_dns_process_id_key UNIQUE (dns_process_id);


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
-- Name: maasserver_partition maasserver_partition_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition
    ADD CONSTRAINT maasserver_partition_pkey PRIMARY KEY (id);


--
-- Name: maasserver_partition maasserver_partition_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition
    ADD CONSTRAINT maasserver_partition_uuid_key UNIQUE (uuid);


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
-- Name: maasserver_switch maasserver_switch_node_id_c75634bb_pk; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_switch
    ADD CONSTRAINT maasserver_switch_node_id_c75634bb_pk PRIMARY KEY (node_id);


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
-- Name: maasserver_virtualblockdevice maasserver_virtualblockdevice_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualblockdevice_uuid_key UNIQUE (uuid);


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
-- Name: metadataserver_nodekey metadataserver_nodekey_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_key_key UNIQUE (key);


--
-- Name: metadataserver_nodekey metadataserver_nodekey_node_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_node_id_key UNIQUE (node_id);


--
-- Name: metadataserver_nodekey metadataserver_nodekey_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_nodekey metadataserver_nodekey_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_token_id_key UNIQUE (token_id);


--
-- Name: metadataserver_nodeuserdata metadataserver_nodeuserdata_node_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_node_id_key UNIQUE (node_id);


--
-- Name: metadataserver_nodeuserdata metadataserver_nodeuserdata_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_script metadataserver_script_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_script
    ADD CONSTRAINT metadataserver_script_name_key UNIQUE (name);


--
-- Name: metadataserver_script metadataserver_script_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_script
    ADD CONSTRAINT metadataserver_script_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_script metadataserver_script_script_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_script
    ADD CONSTRAINT metadataserver_script_script_id_key UNIQUE (script_id);


--
-- Name: metadataserver_scriptresult metadataserver_scriptresult_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptresult
    ADD CONSTRAINT metadataserver_scriptresult_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_scriptset metadataserver_scriptset_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptset
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
-- Name: piston3_token piston3_token_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token
    ADD CONSTRAINT piston3_token_pkey PRIMARY KEY (id);


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
-- Name: maasserver_blockdevice_node_id_bdedcfca; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_blockdevice_node_id_bdedcfca ON public.maasserver_blockdevice USING btree (node_id);


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
-- Name: maasserver_bmc_name_144ffd80_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_bmc_name_144ffd80_like ON public.maasserver_bmc USING btree (name varchar_pattern_ops);


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
-- Name: maasserver_fannetwork_name_fe247f07_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_fannetwork_name_fe247f07_like ON public.maasserver_fannetwork USING btree (name varchar_pattern_ops);


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
-- Name: maasserver_filesystem_node_id_2263663a; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_node_id_2263663a ON public.maasserver_filesystem USING btree (node_id);


--
-- Name: maasserver_filesystem_partition_id_6174cd8b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystem_partition_id_6174cd8b ON public.maasserver_filesystem USING btree (partition_id);


--
-- Name: maasserver_filesystemgroup_cache_set_id_608e115e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystemgroup_cache_set_id_608e115e ON public.maasserver_filesystemgroup USING btree (cache_set_id);


--
-- Name: maasserver_filesystemgroup_uuid_8867d00a_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_filesystemgroup_uuid_8867d00a_like ON public.maasserver_filesystemgroup USING btree (uuid varchar_pattern_ops);


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
-- Name: maasserver_interface_node_id_692ef434; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_interface_node_id_692ef434 ON public.maasserver_interface USING btree (node_id);


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
-- Name: maasserver_iscsiblockdevice_target_86aa694a_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_iscsiblockdevice_target_86aa694a_like ON public.maasserver_iscsiblockdevice USING btree (target varchar_pattern_ops);


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
-- Name: maasserver_node_current_installation_script_set_id_a6e40738; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_current_installation_script_set_id_a6e40738 ON public.maasserver_node USING btree (current_installation_script_set_id);


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
-- Name: maasserver_node_token_id_544f49f8; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_token_id_544f49f8 ON public.maasserver_node USING btree (token_id);


--
-- Name: maasserver_node_zone_id_97213f69; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_node_zone_id_97213f69 ON public.maasserver_node USING btree (zone_id);


--
-- Name: maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodegrouptorackcontroller_subnet_id_8ed96f7b ON public.maasserver_nodegrouptorackcontroller USING btree (subnet_id);


--
-- Name: maasserver_nodemetadata_node_id_4350cc04; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_nodemetadata_node_id_4350cc04 ON public.maasserver_nodemetadata USING btree (node_id);


--
-- Name: maasserver_notification_ident; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_notification_ident ON public.maasserver_notification USING btree (ident) WHERE (ident IS NOT NULL);


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
-- Name: maasserver_partition_uuid_22931ba0_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_partition_uuid_22931ba0_like ON public.maasserver_partition USING btree (uuid varchar_pattern_ops);


--
-- Name: maasserver_partitiontable_block_device_id_ee132cc5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_partitiontable_block_device_id_ee132cc5 ON public.maasserver_partitiontable USING btree (block_device_id);


--
-- Name: maasserver_physicalblockdevice_storage_pool_id_f0053704; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_physicalblockdevice_storage_pool_id_f0053704 ON public.maasserver_physicalblockdevice USING btree (storage_pool_id);


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
-- Name: maasserver_staticipaddress__discovered_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX maasserver_staticipaddress__discovered_unique ON public.maasserver_staticipaddress USING btree (ip) WHERE (alloc_type <> 6);


--
-- Name: maasserver_staticipaddress__ip_family; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticipaddress__ip_family ON public.maasserver_staticipaddress USING btree (family(ip));


--
-- Name: maasserver_staticipaddress_subnet_id_b30d84c3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_staticipaddress_subnet_id_b30d84c3 ON public.maasserver_staticipaddress USING btree (subnet_id);


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
-- Name: maasserver_versionedtextfile_previous_version_id_8c3734e6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_versionedtextfile_previous_version_id_8c3734e6 ON public.maasserver_versionedtextfile USING btree (previous_version_id);


--
-- Name: maasserver_virtualblockdevice_filesystem_group_id_405a7fc4; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualblockdevice_filesystem_group_id_405a7fc4 ON public.maasserver_virtualblockdevice USING btree (filesystem_group_id);


--
-- Name: maasserver_virtualblockdevice_uuid_f094d740_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_virtualblockdevice_uuid_f094d740_like ON public.maasserver_virtualblockdevice USING btree (uuid varchar_pattern_ops);


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
-- Name: maasserver_zone_name_a0aef207_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX maasserver_zone_name_a0aef207_like ON public.maasserver_zone USING btree (name varchar_pattern_ops);


--
-- Name: metadataserver_nodekey_key_2a0a84be_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_nodekey_key_2a0a84be_like ON public.metadataserver_nodekey USING btree (key varchar_pattern_ops);


--
-- Name: metadataserver_script_name_b2be1ba5_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_script_name_b2be1ba5_like ON public.metadataserver_script USING btree (name varchar_pattern_ops);


--
-- Name: metadataserver_scriptresult_physical_blockdevice_id_c728b2ad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_physical_blockdevice_id_c728b2ad ON public.metadataserver_scriptresult USING btree (physical_blockdevice_id);


--
-- Name: metadataserver_scriptresult_script_id_c5ff7318; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_script_id_c5ff7318 ON public.metadataserver_scriptresult USING btree (script_id);


--
-- Name: metadataserver_scriptresult_script_set_id_625a037b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_script_set_id_625a037b ON public.metadataserver_scriptresult USING btree (script_set_id);


--
-- Name: metadataserver_scriptresult_script_version_id_932ffdd1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptresult_script_version_id_932ffdd1 ON public.metadataserver_scriptresult USING btree (script_version_id);


--
-- Name: metadataserver_scriptset_node_id_72b6537b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX metadataserver_scriptset_node_id_72b6537b ON public.metadataserver_scriptset USING btree (node_id);


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
-- Name: maasserver_blockdevice maasserver_blockdevice_node_id_bdedcfca_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_node_id_bdedcfca_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmc maasserver_bmc_default_storage_pool_5f48762b_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_default_storage_pool_5f48762b_fk_maasserve FOREIGN KEY (default_storage_pool_id) REFERENCES public.maasserver_podstoragepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmc maasserver_bmc_ip_address_id_79362d14_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmc
    ADD CONSTRAINT maasserver_bmc_ip_address_id_79362d14_fk_maasserve FOREIGN KEY (ip_address_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_bmcroutablerackcontrollerrelationship maasserver_bmcroutab_bmc_id_27dedd10_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmcroutablerackcontrollerrelationship
    ADD CONSTRAINT maasserver_bmcroutab_bmc_id_27dedd10_fk_maasserve FOREIGN KEY (bmc_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bmcroutablerackcontrollerrelationship maasserver_bmcroutab_rack_controller_id_1a3ffa6e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bmcroutablerackcontrollerrelationship
    ADD CONSTRAINT maasserver_bmcroutab_rack_controller_id_1a3ffa6e_fk_maasserve FOREIGN KEY (rack_controller_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourcefile maasserver_bootresou_largefile_id_cf035187_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresou_largefile_id_cf035187_fk_maasserve FOREIGN KEY (largefile_id) REFERENCES public.maasserver_largefile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourceset maasserver_bootresou_resource_id_c320a639_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourceset
    ADD CONSTRAINT maasserver_bootresou_resource_id_c320a639_fk_maasserve FOREIGN KEY (resource_id) REFERENCES public.maasserver_bootresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootresourcefile maasserver_bootresou_resource_set_id_2fd093ab_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresou_resource_set_id_2fd093ab_fk_maasserve FOREIGN KEY (resource_set_id) REFERENCES public.maasserver_bootresourceset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootsourcecache maasserver_bootsourc_boot_source_id_73abe4d2_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourcecache
    ADD CONSTRAINT maasserver_bootsourc_boot_source_id_73abe4d2_fk_maasserve FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_bootsourceselection maasserver_bootsourc_boot_source_id_b911aa0f_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourc_boot_source_id_b911aa0f_fk_maasserve FOREIGN KEY (boot_source_id) REFERENCES public.maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_controllerinfo maasserver_controlle_node_id_e38255a5_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_controllerinfo
    ADD CONSTRAINT maasserver_controlle_node_id_e38255a5_fk_maasserve FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnipp_subnet_id_f626b848_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnipp_subnet_id_f626b848_fk_maasserve FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnipp_value_id_58a6a467_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnipp_value_id_58a6a467_fk_maasserve FOREIGN KEY (value_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dhcpsnippet maasserver_dhcpsnippet_node_id_8f31c564_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dhcpsnippet
    ADD CONSTRAINT maasserver_dhcpsnippet_node_id_8f31c564_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsdata maasserver_dnsdata_dnsresource_id_9a9b5788_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsdata
    ADD CONSTRAINT maasserver_dnsdata_dnsresource_id_9a9b5788_fk_maasserve FOREIGN KEY (dnsresource_id) REFERENCES public.maasserver_dnsresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresour_dnsresource_id_49f1115e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresour_dnsresource_id_49f1115e_fk_maasserve FOREIGN KEY (dnsresource_id) REFERENCES public.maasserver_dnsresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource maasserver_dnsresour_domain_id_c5abb245_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource
    ADD CONSTRAINT maasserver_dnsresour_domain_id_c5abb245_fk_maasserve FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_dnsresource_ip_addresses maasserver_dnsresour_staticipaddress_id_794f210e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_dnsresource_ip_addresses
    ADD CONSTRAINT maasserver_dnsresour_staticipaddress_id_794f210e_fk_maasserve FOREIGN KEY (staticipaddress_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_event maasserver_event_node_id_dd4495a7_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_event
    ADD CONSTRAINT maasserver_event_node_id_dd4495a7_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_event maasserver_event_type_id_702a532f_fk_maasserver_eventtype_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_event
    ADD CONSTRAINT maasserver_event_type_id_702a532f_fk_maasserver_eventtype_id FOREIGN KEY (type_id) REFERENCES public.maasserver_eventtype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filestorage maasserver_filestorage_owner_id_24d47e43_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_owner_id_24d47e43_fk_auth_user_id FOREIGN KEY (owner_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesyste_block_device_id_5d3ba742_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesyste_block_device_id_5d3ba742_fk_maasserve FOREIGN KEY (block_device_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystemgroup maasserver_filesyste_cache_set_id_608e115e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystemgroup
    ADD CONSTRAINT maasserver_filesyste_cache_set_id_608e115e_fk_maasserve FOREIGN KEY (cache_set_id) REFERENCES public.maasserver_cacheset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesyste_cache_set_id_f87650ce_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesyste_cache_set_id_f87650ce_fk_maasserve FOREIGN KEY (cache_set_id) REFERENCES public.maasserver_cacheset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesyste_filesystem_group_id_9bc05fe7_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesyste_filesystem_group_id_9bc05fe7_fk_maasserve FOREIGN KEY (filesystem_group_id) REFERENCES public.maasserver_filesystemgroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesyste_partition_id_6174cd8b_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesyste_partition_id_6174cd8b_fk_maasserve FOREIGN KEY (partition_id) REFERENCES public.maasserver_partition(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_filesystem maasserver_filesystem_node_id_2263663a_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_node_id_2263663a_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_globaldefault maasserver_globaldef_domain_id_11c3ee74_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_globaldefault
    ADD CONSTRAINT maasserver_globaldef_domain_id_11c3ee74_fk_maasserve FOREIGN KEY (domain_id) REFERENCES public.maasserver_domain(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interfacerelationship maasserver_interface_child_id_7be5401e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interfacerelationship
    ADD CONSTRAINT maasserver_interface_child_id_7be5401e_fk_maasserve FOREIGN KEY (child_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_interface_id_d3d873df_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_interface_id_d3d873df_fk_maasserve FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface maasserver_interface_node_id_692ef434_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_node_id_692ef434_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interfacerelationship maasserver_interface_parent_id_d3c77c37_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interfacerelationship
    ADD CONSTRAINT maasserver_interface_parent_id_d3c77c37_fk_maasserve FOREIGN KEY (parent_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface_ip_addresses maasserver_interface_staticipaddress_id_5fa63951_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface_ip_addresses
    ADD CONSTRAINT maasserver_interface_staticipaddress_id_5fa63951_fk_maasserve FOREIGN KEY (staticipaddress_id) REFERENCES public.maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_interface maasserver_interface_vlan_id_5f39995d_fk_maasserver_vlan_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_interface
    ADD CONSTRAINT maasserver_interface_vlan_id_5f39995d_fk_maasserver_vlan_id FOREIGN KEY (vlan_id) REFERENCES public.maasserver_vlan(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_iprange maasserver_iprange_subnet_id_de83b8f1_fk_maasserver_subnet_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iprange
    ADD CONSTRAINT maasserver_iprange_subnet_id_de83b8f1_fk_maasserver_subnet_id FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_iprange maasserver_iprange_user_id_5d0f7718_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iprange
    ADD CONSTRAINT maasserver_iprange_user_id_5d0f7718_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_iscsiblockdevice maasserver_iscsibloc_blockdevice_ptr_id_9ac939f1_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_iscsiblockdevice
    ADD CONSTRAINT maasserver_iscsibloc_blockdevice_ptr_id_9ac939f1_fk_maasserve FOREIGN KEY (blockdevice_ptr_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_mdns maasserver_mdns_interface_id_ef297041_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_mdns
    ADD CONSTRAINT maasserver_mdns_interface_id_ef297041_fk_maasserve FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_neighbour maasserver_neighbour_interface_id_dd458d65_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_neighbour
    ADD CONSTRAINT maasserver_neighbour_interface_id_dd458d65_fk_maasserve FOREIGN KEY (interface_id) REFERENCES public.maasserver_interface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_bmc_id_a2d33e12_fk_maasserver_bmc_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_bmc_id_a2d33e12_fk_maasserver_bmc_id FOREIGN KEY (bmc_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_node maasserver_node_current_commissionin_9ae2ec39_fk_metadatas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_commissionin_9ae2ec39_fk_metadatas FOREIGN KEY (current_commissioning_script_set_id) REFERENCES public.metadataserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_installation_a6e40738_fk_metadatas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_installation_a6e40738_fk_metadatas FOREIGN KEY (current_installation_script_set_id) REFERENCES public.metadataserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_current_testing_scri_4636f4f9_fk_metadatas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_current_testing_scri_4636f4f9_fk_metadatas FOREIGN KEY (current_testing_script_set_id) REFERENCES public.metadataserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_node maasserver_node_parent_id_d0ac1fac_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_parent_id_d0ac1fac_fk_maasserver_node_id FOREIGN KEY (parent_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_pool_id_42cdfac9_fk_maasserver_resourcepool_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_pool_id_42cdfac9_fk_maasserver_resourcepool_id FOREIGN KEY (pool_id) REFERENCES public.maasserver_resourcepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node_tags maasserver_node_tags_node_id_a662a9f1_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_node_id_a662a9f1_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node_tags maasserver_node_tags_tag_id_f4728372_fk_maasserver_tag_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_tag_id_f4728372_fk_maasserver_tag_id FOREIGN KEY (tag_id) REFERENCES public.maasserver_tag(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_token_id_544f49f8_fk_piston3_token_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_token_id_544f49f8_fk_piston3_token_id FOREIGN KEY (token_id) REFERENCES public.piston3_token(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_node maasserver_node_zone_id_97213f69_fk_maasserver_zone_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_node
    ADD CONSTRAINT maasserver_node_zone_id_97213f69_fk_maasserver_zone_id FOREIGN KEY (zone_id) REFERENCES public.maasserver_zone(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodegrouptorackcontroller maasserver_nodegroup_subnet_id_8ed96f7b_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodegrouptorackcontroller
    ADD CONSTRAINT maasserver_nodegroup_subnet_id_8ed96f7b_fk_maasserve FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_nodemetadata maasserver_nodemetadata_node_id_4350cc04_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_nodemetadata
    ADD CONSTRAINT maasserver_nodemetadata_node_id_4350cc04_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_notificationdismissal maasserver_notificat_notification_id_fe4f68d4_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_notificationdismissal
    ADD CONSTRAINT maasserver_notificat_notification_id_fe4f68d4_fk_maasserve FOREIGN KEY (notification_id) REFERENCES public.maasserver_notification(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_ownerdata maasserver_ownerdata_node_id_4ec53011_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_ownerdata
    ADD CONSTRAINT maasserver_ownerdata_node_id_4ec53011_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_partitiontable maasserver_partition_block_device_id_ee132cc5_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partitiontable
    ADD CONSTRAINT maasserver_partition_block_device_id_ee132cc5_fk_maasserve FOREIGN KEY (block_device_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_partition maasserver_partition_partition_table_id_c94faed6_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_partition
    ADD CONSTRAINT maasserver_partition_partition_table_id_c94faed6_fk_maasserve FOREIGN KEY (partition_table_id) REFERENCES public.maasserver_partitiontable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_physicalblockdevice maasserver_physicalb_blockdevice_ptr_id_6ca192fb_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_physicalblockdevice
    ADD CONSTRAINT maasserver_physicalb_blockdevice_ptr_id_6ca192fb_fk_maasserve FOREIGN KEY (blockdevice_ptr_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_physicalblockdevice maasserver_physicalb_storage_pool_id_f0053704_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_physicalblockdevice
    ADD CONSTRAINT maasserver_physicalb_storage_pool_id_f0053704_fk_maasserve FOREIGN KEY (storage_pool_id) REFERENCES public.maasserver_podstoragepool(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podhints maasserver_podhints_pod_id_42c87c40_fk_maasserver_bmc_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podhints
    ADD CONSTRAINT maasserver_podhints_pod_id_42c87c40_fk_maasserver_bmc_id FOREIGN KEY (pod_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_podstoragepool maasserver_podstoragepool_pod_id_11db94aa_fk_maasserver_bmc_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_podstoragepool
    ADD CONSTRAINT maasserver_podstoragepool_pod_id_11db94aa_fk_maasserver_bmc_id FOREIGN KEY (pod_id) REFERENCES public.maasserver_bmc(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_rdns maasserver_rdns_observer_id_85a64c6b_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_rdns
    ADD CONSTRAINT maasserver_rdns_observer_id_85a64c6b_fk_maasserver_node_id FOREIGN KEY (observer_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regioncontrollerprocessendpoint maasserver_regioncon_process_id_2bf84625_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocessendpoint
    ADD CONSTRAINT maasserver_regioncon_process_id_2bf84625_fk_maasserve FOREIGN KEY (process_id) REFERENCES public.maasserver_regioncontrollerprocess(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regioncontrollerprocess maasserver_regioncon_region_id_ee210efa_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regioncontrollerprocess
    ADD CONSTRAINT maasserver_regioncon_region_id_ee210efa_fk_maasserve FOREIGN KEY (region_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regionrackrpcconnection maasserver_regionrac_endpoint_id_9e6814b4_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection
    ADD CONSTRAINT maasserver_regionrac_endpoint_id_9e6814b4_fk_maasserve FOREIGN KEY (endpoint_id) REFERENCES public.maasserver_regioncontrollerprocessendpoint(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_regionrackrpcconnection maasserver_regionrac_rack_controller_id_7f5b60af_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_regionrackrpcconnection
    ADD CONSTRAINT maasserver_regionrac_rack_controller_id_7f5b60af_fk_maasserve FOREIGN KEY (rack_controller_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_service maasserver_service_node_id_891637d4_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_service
    ADD CONSTRAINT maasserver_service_node_id_891637d4_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_sshkey maasserver_sshkey_keysource_id_701e0769_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_sshkey
    ADD CONSTRAINT maasserver_sshkey_keysource_id_701e0769_fk_maasserve FOREIGN KEY (keysource_id) REFERENCES public.maasserver_keysource(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_staticipaddress maasserver_staticipa_subnet_id_b30d84c3_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipa_subnet_id_b30d84c3_fk_maasserve FOREIGN KEY (subnet_id) REFERENCES public.maasserver_subnet(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_subnet maasserver_subnet_vlan_id_d4e96e9a_fk_maasserver_vlan_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_subnet
    ADD CONSTRAINT maasserver_subnet_vlan_id_d4e96e9a_fk_maasserver_vlan_id FOREIGN KEY (vlan_id) REFERENCES public.maasserver_vlan(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_switch maasserver_switch_node_id_c75634bb_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_switch
    ADD CONSTRAINT maasserver_switch_node_id_c75634bb_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_template maasserver_template_default_version_id_10647fcf_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template
    ADD CONSTRAINT maasserver_template_default_version_id_10647fcf_fk_maasserve FOREIGN KEY (default_version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_template maasserver_template_version_id_78c8754e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_template
    ADD CONSTRAINT maasserver_template_version_id_78c8754e_fk_maasserve FOREIGN KEY (version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_userprofile maasserver_userprofile_user_id_dc73fcb9_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_user_id_dc73fcb9_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_versionedtextfile maasserver_versioned_previous_version_id_8c3734e6_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_versionedtextfile
    ADD CONSTRAINT maasserver_versioned_previous_version_id_8c3734e6_fk_maasserve FOREIGN KEY (previous_version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualblockdevice maasserver_virtualbl_blockdevice_ptr_id_a5827040_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualbl_blockdevice_ptr_id_a5827040_fk_maasserve FOREIGN KEY (blockdevice_ptr_id) REFERENCES public.maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_virtualblockdevice maasserver_virtualbl_filesystem_group_id_405a7fc4_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualbl_filesystem_group_id_405a7fc4_fk_maasserve FOREIGN KEY (filesystem_group_id) REFERENCES public.maasserver_filesystemgroup(id) DEFERRABLE INITIALLY DEFERRED;


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
-- Name: maasserver_vlan maasserver_vlan_relay_vlan_id_c026b672_fk_maasserver_vlan_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_relay_vlan_id_c026b672_fk_maasserver_vlan_id FOREIGN KEY (relay_vlan_id) REFERENCES public.maasserver_vlan(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_secondary_rack_id_3b97d19a_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_secondary_rack_id_3b97d19a_fk_maasserve FOREIGN KEY (secondary_rack_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: maasserver_vlan maasserver_vlan_space_id_5e1dc51f_fk_maasserver_space_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.maasserver_vlan
    ADD CONSTRAINT maasserver_vlan_space_id_5e1dc51f_fk_maasserver_space_id FOREIGN KEY (space_id) REFERENCES public.maasserver_space(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_nodekey metadataserver_nodekey_node_id_d16c985e_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_node_id_d16c985e_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_nodekey metadataserver_nodekey_token_id_e6cac4c9_fk_piston3_token_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_token_id_e6cac4c9_fk_piston3_token_id FOREIGN KEY (token_id) REFERENCES public.piston3_token(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_nodeuserdata metadataserver_nodeu_node_id_40aa2a4e_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeu_node_id_40aa2a4e_fk_maasserve FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_scriptresult metadataserver_scrip_physical_blockdevice_c728b2ad_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptresult
    ADD CONSTRAINT metadataserver_scrip_physical_blockdevice_c728b2ad_fk_maasserve FOREIGN KEY (physical_blockdevice_id) REFERENCES public.maasserver_physicalblockdevice(blockdevice_ptr_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_script metadataserver_scrip_script_id_422cbda8_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_script
    ADD CONSTRAINT metadataserver_scrip_script_id_422cbda8_fk_maasserve FOREIGN KEY (script_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_scriptresult metadataserver_scrip_script_id_c5ff7318_fk_metadatas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptresult
    ADD CONSTRAINT metadataserver_scrip_script_id_c5ff7318_fk_metadatas FOREIGN KEY (script_id) REFERENCES public.metadataserver_script(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_scriptresult metadataserver_scrip_script_set_id_625a037b_fk_metadatas; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptresult
    ADD CONSTRAINT metadataserver_scrip_script_set_id_625a037b_fk_metadatas FOREIGN KEY (script_set_id) REFERENCES public.metadataserver_scriptset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_scriptresult metadataserver_scrip_script_version_id_932ffdd1_fk_maasserve; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptresult
    ADD CONSTRAINT metadataserver_scrip_script_version_id_932ffdd1_fk_maasserve FOREIGN KEY (script_version_id) REFERENCES public.maasserver_versionedtextfile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: metadataserver_scriptset metadataserver_scriptset_node_id_72b6537b_fk_maasserver_node_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.metadataserver_scriptset
    ADD CONSTRAINT metadataserver_scriptset_node_id_72b6537b_fk_maasserver_node_id FOREIGN KEY (node_id) REFERENCES public.maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston3_consumer piston3_consumer_user_id_ede69093_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_consumer
    ADD CONSTRAINT piston3_consumer_user_id_ede69093_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston3_token piston3_token_consumer_id_b178993d_fk_piston3_consumer_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token
    ADD CONSTRAINT piston3_token_consumer_id_b178993d_fk_piston3_consumer_id FOREIGN KEY (consumer_id) REFERENCES public.piston3_consumer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston3_token piston3_token_user_id_e5cd818c_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.piston3_token
    ADD CONSTRAINT piston3_token_user_id_e5cd818c_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

