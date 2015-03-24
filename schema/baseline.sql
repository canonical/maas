--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE auth_group (
    id integer NOT NULL,
    name character varying(80) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_group_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE auth_group_id_seq OWNED BY auth_group.id;


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE auth_group_permissions (
    id integer NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE auth_group_permissions_id_seq OWNED BY auth_group_permissions.id;


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE auth_permission (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_permission_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE auth_permission_id_seq OWNED BY auth_permission.id;


--
-- Name: auth_user; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE auth_user (
    id integer NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone NOT NULL,
    is_superuser boolean NOT NULL,
    username character varying(30) NOT NULL,
    first_name character varying(30) NOT NULL,
    last_name character varying(30) NOT NULL,
    email character varying(75) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL
);


--
-- Name: auth_user_groups; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE auth_user_groups (
    id integer NOT NULL,
    user_id integer NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE auth_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE auth_user_groups_id_seq OWNED BY auth_user_groups.id;


--
-- Name: auth_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE auth_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE auth_user_id_seq OWNED BY auth_user.id;


--
-- Name: auth_user_user_permissions; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE auth_user_user_permissions (
    id integer NOT NULL,
    user_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE auth_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE auth_user_user_permissions_id_seq OWNED BY auth_user_user_permissions.id;


--
-- Name: django_admin_log; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE django_admin_log (
    id integer NOT NULL,
    action_time timestamp with time zone NOT NULL,
    user_id integer NOT NULL,
    content_type_id integer,
    object_id text,
    object_repr character varying(200) NOT NULL,
    action_flag smallint NOT NULL,
    change_message text NOT NULL,
    CONSTRAINT django_admin_log_action_flag_check CHECK ((action_flag >= 0))
);


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE django_admin_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE django_admin_log_id_seq OWNED BY django_admin_log.id;


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE django_content_type (
    id integer NOT NULL,
    name character varying(100) NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_content_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE django_content_type_id_seq OWNED BY django_content_type.id;


--
-- Name: django_session; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE django_session (
    session_key character varying(40) NOT NULL,
    session_data text NOT NULL,
    expire_date timestamp with time zone NOT NULL
);


--
-- Name: django_site; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE django_site (
    id integer NOT NULL,
    domain character varying(100) NOT NULL,
    name character varying(50) NOT NULL
);


--
-- Name: django_site_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE django_site_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: django_site_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE django_site_id_seq OWNED BY django_site.id;


--
-- Name: maasserver_blockdevice; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_blockdevice (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    node_id integer NOT NULL,
    name character varying(255) NOT NULL,
    path character varying(100) NOT NULL,
    size bigint NOT NULL,
    block_size integer NOT NULL,
    tags text[],
    id_path character varying(100)
);


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_blockdevice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_blockdevice_id_seq OWNED BY maasserver_blockdevice.id;


--
-- Name: maasserver_bootresource; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_bootresource (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    rtype integer NOT NULL,
    name character varying(255) NOT NULL,
    architecture character varying(255) NOT NULL,
    extra text NOT NULL
);


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_bootresource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_bootresource_id_seq OWNED BY maasserver_bootresource.id;


--
-- Name: maasserver_bootresourcefile; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_bootresourcefile (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    resource_set_id integer NOT NULL,
    largefile_id integer NOT NULL,
    filename character varying(255) NOT NULL,
    filetype character varying(20) NOT NULL,
    extra text NOT NULL
);


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_bootresourcefile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_bootresourcefile_id_seq OWNED BY maasserver_bootresourcefile.id;


--
-- Name: maasserver_bootresourceset; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_bootresourceset (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    resource_id integer NOT NULL,
    version character varying(255) NOT NULL,
    label character varying(255) NOT NULL
);


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_bootresourceset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_bootresourceset_id_seq OWNED BY maasserver_bootresourceset.id;


--
-- Name: maasserver_bootsource; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_bootsource (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    url character varying(200) NOT NULL,
    keyring_filename character varying(100) NOT NULL,
    keyring_data bytea NOT NULL
);


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_bootsource_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_bootsource_id_seq OWNED BY maasserver_bootsource.id;


--
-- Name: maasserver_bootsourcecache; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_bootsourcecache (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    boot_source_id integer NOT NULL,
    os character varying(20) NOT NULL,
    arch character varying(20) NOT NULL,
    subarch character varying(20) NOT NULL,
    release character varying(20) NOT NULL,
    label character varying(20) NOT NULL
);


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_bootsourcecache_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_bootsourcecache_id_seq OWNED BY maasserver_bootsourcecache.id;


--
-- Name: maasserver_bootsourceselection; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_bootsourceselection (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    boot_source_id integer NOT NULL,
    release character varying(20) NOT NULL,
    arches text[],
    subarches text[],
    labels text[],
    os character varying(20) NOT NULL
);


--
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_bootsourceselection_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_bootsourceselection_id_seq OWNED BY maasserver_bootsourceselection.id;


--
-- Name: maasserver_candidatename; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_candidatename (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    "position" integer NOT NULL
);


--
-- Name: maasserver_candidatename_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_candidatename_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_candidatename_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_candidatename_id_seq OWNED BY maasserver_candidatename.id;


--
-- Name: maasserver_componenterror; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_componenterror (
    id integer NOT NULL,
    component character varying(40) NOT NULL,
    error character varying(1000) NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL
);


--
-- Name: maasserver_componenterror_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_componenterror_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_componenterror_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_componenterror_id_seq OWNED BY maasserver_componenterror.id;


--
-- Name: maasserver_config; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_config (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    value text
);


--
-- Name: maasserver_config_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_config_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_config_id_seq OWNED BY maasserver_config.id;


--
-- Name: maasserver_dhcplease; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_dhcplease (
    id integer NOT NULL,
    nodegroup_id integer NOT NULL,
    ip inet NOT NULL,
    mac macaddr NOT NULL
);


--
-- Name: maasserver_dhcplease_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_dhcplease_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_dhcplease_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_dhcplease_id_seq OWNED BY maasserver_dhcplease.id;


--
-- Name: maasserver_downloadprogress; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_downloadprogress (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    nodegroup_id integer NOT NULL,
    filename character varying(255) NOT NULL,
    size integer,
    bytes_downloaded integer,
    error character varying(1000) NOT NULL
);


--
-- Name: maasserver_downloadprogress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_downloadprogress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_downloadprogress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_downloadprogress_id_seq OWNED BY maasserver_downloadprogress.id;


--
-- Name: maasserver_event; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_event (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    type_id integer NOT NULL,
    node_id integer NOT NULL,
    description text NOT NULL
);


--
-- Name: maasserver_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_event_id_seq OWNED BY maasserver_event.id;


--
-- Name: maasserver_eventtype; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_eventtype (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(255) NOT NULL,
    level integer NOT NULL,
    description character varying(255) NOT NULL
);


--
-- Name: maasserver_eventtype_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_eventtype_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_eventtype_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_eventtype_id_seq OWNED BY maasserver_eventtype.id;


--
-- Name: maasserver_filestorage; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_filestorage (
    id integer NOT NULL,
    filename character varying(255) NOT NULL,
    content text NOT NULL,
    owner_id integer,
    key character varying(36) NOT NULL
);


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_filestorage_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_filestorage_id_seq OWNED BY maasserver_filestorage.id;


--
-- Name: maasserver_filesystem; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_filesystem (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid character varying(36) NOT NULL,
    fstype character varying(20) NOT NULL,
    partition_id integer,
    block_device_id integer,
    create_params character varying(255),
    mount_point character varying(255),
    mount_params character varying(255),
    filesystem_group_id integer
);


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_filesystem_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_filesystem_id_seq OWNED BY maasserver_filesystem.id;


--
-- Name: maasserver_filesystemgroup; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_filesystemgroup (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    uuid character varying(36) NOT NULL,
    group_type character varying(20) NOT NULL,
    name character varying(255) NOT NULL,
    create_params character varying(255)
);


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_filesystemgroup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_filesystemgroup_id_seq OWNED BY maasserver_filesystemgroup.id;


--
-- Name: maasserver_largefile; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_largefile (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    sha256 character varying(64) NOT NULL,
    total_size bigint NOT NULL,
    content oid NOT NULL
);


--
-- Name: maasserver_largefile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_largefile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_largefile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_largefile_id_seq OWNED BY maasserver_largefile.id;


--
-- Name: maasserver_licensekey; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_licensekey (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    osystem character varying(255) NOT NULL,
    distro_series character varying(255) NOT NULL,
    license_key character varying(255) NOT NULL
);


--
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_licensekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_licensekey_id_seq OWNED BY maasserver_licensekey.id;


--
-- Name: maasserver_macaddress; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_macaddress (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    mac_address macaddr NOT NULL,
    node_id integer,
    cluster_interface_id integer
);


--
-- Name: maasserver_macaddress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_macaddress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_macaddress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_macaddress_id_seq OWNED BY maasserver_macaddress.id;


--
-- Name: maasserver_macaddress_networks; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_macaddress_networks (
    id integer NOT NULL,
    macaddress_id integer NOT NULL,
    network_id integer NOT NULL
);


--
-- Name: maasserver_macaddress_networks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_macaddress_networks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_macaddress_networks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_macaddress_networks_id_seq OWNED BY maasserver_macaddress_networks.id;


--
-- Name: maasserver_macstaticipaddresslink; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_macstaticipaddresslink (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    mac_address_id integer NOT NULL,
    ip_address_id integer NOT NULL,
    nic_alias integer
);


--
-- Name: maasserver_macstaticipaddresslink_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_macstaticipaddresslink_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_macstaticipaddresslink_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_macstaticipaddresslink_id_seq OWNED BY maasserver_macstaticipaddresslink.id;


--
-- Name: maasserver_network; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_network (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    ip inet NOT NULL,
    netmask inet NOT NULL,
    vlan_tag smallint,
    description text NOT NULL,
    default_gateway inet,
    dns_servers character varying(255),
    CONSTRAINT maasserver_network_vlan_tag_check CHECK ((vlan_tag >= 0))
);


--
-- Name: maasserver_network_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_network_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_network_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_network_id_seq OWNED BY maasserver_network.id;


--
-- Name: maasserver_node; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_node (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    system_id character varying(41) NOT NULL,
    hostname character varying(255) NOT NULL,
    status integer NOT NULL,
    owner_id integer,
    architecture character varying(31),
    power_type character varying(10) NOT NULL,
    token_id integer,
    error character varying(255) NOT NULL,
    power_parameters text NOT NULL,
    netboot boolean NOT NULL,
    nodegroup_id integer,
    distro_series character varying(20) NOT NULL,
    cpu_count integer NOT NULL,
    memory integer NOT NULL,
    routers macaddr[],
    agent_name character varying(255),
    zone_id integer NOT NULL,
    osystem character varying(20) NOT NULL,
    license_key character varying(30),
    boot_type character varying(20) NOT NULL,
    error_description text NOT NULL,
    power_state character varying(10) NOT NULL,
    disable_ipv4 boolean NOT NULL,
    pxe_mac_id integer,
    installable boolean NOT NULL,
    parent_id integer,
    swap_size bigint
);


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_node_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_node_id_seq OWNED BY maasserver_node.id;


--
-- Name: maasserver_node_tags; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_node_tags (
    id integer NOT NULL,
    node_id integer NOT NULL,
    tag_id integer NOT NULL
);


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_node_tags_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_node_tags_id_seq OWNED BY maasserver_node_tags.id;


--
-- Name: maasserver_nodegroup; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_nodegroup (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(80) NOT NULL,
    api_token_id integer NOT NULL,
    api_key character varying(18) NOT NULL,
    dhcp_key character varying(255) NOT NULL,
    uuid character varying(36) NOT NULL,
    status integer NOT NULL,
    cluster_name character varying(100) NOT NULL,
    maas_url character varying(255) NOT NULL,
    default_disable_ipv4 boolean NOT NULL
);


--
-- Name: maasserver_nodegroup_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_nodegroup_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodegroup_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_nodegroup_id_seq OWNED BY maasserver_nodegroup.id;


--
-- Name: maasserver_nodegroupinterface; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_nodegroupinterface (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet NOT NULL,
    nodegroup_id integer NOT NULL,
    management integer NOT NULL,
    interface character varying(255) NOT NULL,
    subnet_mask inet,
    broadcast_ip inet,
    router_ip inet,
    ip_range_low inet,
    ip_range_high inet,
    foreign_dhcp_ip inet,
    static_ip_range_low inet,
    static_ip_range_high inet,
    name character varying(255) NOT NULL
);


--
-- Name: maasserver_nodegroupinterface_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_nodegroupinterface_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_nodegroupinterface_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_nodegroupinterface_id_seq OWNED BY maasserver_nodegroupinterface.id;


--
-- Name: maasserver_partition; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_partition (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    partition_table_id integer NOT NULL,
    uuid character varying(36),
    start_offset bigint NOT NULL,
    size bigint NOT NULL,
    bootable boolean NOT NULL
);


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_partition_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_partition_id_seq OWNED BY maasserver_partition.id;


--
-- Name: maasserver_partitiontable; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_partitiontable (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    table_type character varying(20) NOT NULL,
    block_device_id integer NOT NULL
);


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_partitiontable_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_partitiontable_id_seq OWNED BY maasserver_partitiontable.id;


--
-- Name: maasserver_physicalblockdevice; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_physicalblockdevice (
    blockdevice_ptr_id integer NOT NULL,
    model character varying(255) NOT NULL,
    serial character varying(255) NOT NULL
);


--
-- Name: maasserver_sshkey; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_sshkey (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    user_id integer NOT NULL,
    key text NOT NULL
);


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_sshkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_sshkey_id_seq OWNED BY maasserver_sshkey.id;


--
-- Name: maasserver_sslkey; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_sslkey (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    user_id integer NOT NULL,
    key text NOT NULL
);


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_sslkey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_sslkey_id_seq OWNED BY maasserver_sslkey.id;


--
-- Name: maasserver_staticipaddress; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_staticipaddress (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    ip inet NOT NULL,
    alloc_type integer NOT NULL,
    user_id integer
);


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_staticipaddress_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_staticipaddress_id_seq OWNED BY maasserver_staticipaddress.id;


--
-- Name: maasserver_tag; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_tag (
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

CREATE SEQUENCE maasserver_tag_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_tag_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_tag_id_seq OWNED BY maasserver_tag.id;


--
-- Name: maasserver_userprofile; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_userprofile (
    id integer NOT NULL,
    user_id integer NOT NULL
);


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_userprofile_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_userprofile_id_seq OWNED BY maasserver_userprofile.id;


--
-- Name: maasserver_virtualblockdevice; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_virtualblockdevice (
    blockdevice_ptr_id integer NOT NULL,
    uuid character varying(36) NOT NULL,
    filesystem_group_id integer NOT NULL
);


--
-- Name: maasserver_zone; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE maasserver_zone (
    id integer NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    name character varying(256) NOT NULL,
    description text NOT NULL
);


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_zone_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE maasserver_zone_id_seq OWNED BY maasserver_zone.id;


--
-- Name: maasserver_zone_serial_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE maasserver_zone_serial_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 4294967295
    CACHE 1
    CYCLE;


--
-- Name: metadataserver_commissioningscript; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE metadataserver_commissioningscript (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content text NOT NULL
);


--
-- Name: metadataserver_commissioningscript_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE metadataserver_commissioningscript_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_commissioningscript_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE metadataserver_commissioningscript_id_seq OWNED BY metadataserver_commissioningscript.id;


--
-- Name: metadataserver_nodekey; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE metadataserver_nodekey (
    id integer NOT NULL,
    node_id integer NOT NULL,
    token_id integer NOT NULL,
    key character varying(18) NOT NULL
);


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE metadataserver_nodekey_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE metadataserver_nodekey_id_seq OWNED BY metadataserver_nodekey.id;


--
-- Name: metadataserver_noderesult; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE metadataserver_noderesult (
    id integer NOT NULL,
    node_id integer NOT NULL,
    name character varying(255) NOT NULL,
    created timestamp with time zone NOT NULL,
    updated timestamp with time zone NOT NULL,
    script_result integer NOT NULL,
    data text NOT NULL,
    result_type integer NOT NULL
);


--
-- Name: metadataserver_noderesult_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE metadataserver_noderesult_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_noderesult_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE metadataserver_noderesult_id_seq OWNED BY metadataserver_noderesult.id;


--
-- Name: metadataserver_nodeuserdata; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE metadataserver_nodeuserdata (
    id integer NOT NULL,
    node_id integer NOT NULL,
    data text NOT NULL
);


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE metadataserver_nodeuserdata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE metadataserver_nodeuserdata_id_seq OWNED BY metadataserver_nodeuserdata.id;


--
-- Name: piston_consumer; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE piston_consumer (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    key character varying(18) NOT NULL,
    secret character varying(32) NOT NULL,
    status character varying(16) NOT NULL,
    user_id integer
);


--
-- Name: piston_consumer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE piston_consumer_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piston_consumer_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE piston_consumer_id_seq OWNED BY piston_consumer.id;


--
-- Name: piston_nonce; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE piston_nonce (
    id integer NOT NULL,
    token_key character varying(18) NOT NULL,
    consumer_key character varying(18) NOT NULL,
    key character varying(255) NOT NULL
);


--
-- Name: piston_nonce_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE piston_nonce_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piston_nonce_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE piston_nonce_id_seq OWNED BY piston_nonce.id;


--
-- Name: piston_token; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE piston_token (
    id integer NOT NULL,
    key character varying(18) NOT NULL,
    secret character varying(32) NOT NULL,
    verifier character varying(10) NOT NULL,
    token_type integer NOT NULL,
    "timestamp" integer NOT NULL,
    is_approved boolean NOT NULL,
    user_id integer,
    consumer_id integer NOT NULL,
    callback character varying(255),
    callback_confirmed boolean NOT NULL
);


--
-- Name: piston_token_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE piston_token_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: piston_token_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE piston_token_id_seq OWNED BY piston_token.id;


--
-- Name: south_migrationhistory; Type: TABLE; Schema: public; Owner: -; Tablespace: 
--

CREATE TABLE south_migrationhistory (
    id integer NOT NULL,
    app_name character varying(255) NOT NULL,
    migration character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: south_migrationhistory_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE south_migrationhistory_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: south_migrationhistory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE south_migrationhistory_id_seq OWNED BY south_migrationhistory.id;


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_group ALTER COLUMN id SET DEFAULT nextval('auth_group_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_group_permissions ALTER COLUMN id SET DEFAULT nextval('auth_group_permissions_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_permission ALTER COLUMN id SET DEFAULT nextval('auth_permission_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user ALTER COLUMN id SET DEFAULT nextval('auth_user_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user_groups ALTER COLUMN id SET DEFAULT nextval('auth_user_groups_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user_user_permissions ALTER COLUMN id SET DEFAULT nextval('auth_user_user_permissions_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY django_admin_log ALTER COLUMN id SET DEFAULT nextval('django_admin_log_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY django_content_type ALTER COLUMN id SET DEFAULT nextval('django_content_type_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY django_site ALTER COLUMN id SET DEFAULT nextval('django_site_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_blockdevice ALTER COLUMN id SET DEFAULT nextval('maasserver_blockdevice_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootresource ALTER COLUMN id SET DEFAULT nextval('maasserver_bootresource_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootresourcefile ALTER COLUMN id SET DEFAULT nextval('maasserver_bootresourcefile_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootresourceset ALTER COLUMN id SET DEFAULT nextval('maasserver_bootresourceset_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootsource ALTER COLUMN id SET DEFAULT nextval('maasserver_bootsource_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootsourcecache ALTER COLUMN id SET DEFAULT nextval('maasserver_bootsourcecache_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootsourceselection ALTER COLUMN id SET DEFAULT nextval('maasserver_bootsourceselection_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_candidatename ALTER COLUMN id SET DEFAULT nextval('maasserver_candidatename_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_componenterror ALTER COLUMN id SET DEFAULT nextval('maasserver_componenterror_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_config ALTER COLUMN id SET DEFAULT nextval('maasserver_config_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_dhcplease ALTER COLUMN id SET DEFAULT nextval('maasserver_dhcplease_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_downloadprogress ALTER COLUMN id SET DEFAULT nextval('maasserver_downloadprogress_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_event ALTER COLUMN id SET DEFAULT nextval('maasserver_event_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_eventtype ALTER COLUMN id SET DEFAULT nextval('maasserver_eventtype_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filestorage ALTER COLUMN id SET DEFAULT nextval('maasserver_filestorage_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filesystem ALTER COLUMN id SET DEFAULT nextval('maasserver_filesystem_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filesystemgroup ALTER COLUMN id SET DEFAULT nextval('maasserver_filesystemgroup_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_largefile ALTER COLUMN id SET DEFAULT nextval('maasserver_largefile_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_licensekey ALTER COLUMN id SET DEFAULT nextval('maasserver_licensekey_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macaddress ALTER COLUMN id SET DEFAULT nextval('maasserver_macaddress_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macaddress_networks ALTER COLUMN id SET DEFAULT nextval('maasserver_macaddress_networks_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macstaticipaddresslink ALTER COLUMN id SET DEFAULT nextval('maasserver_macstaticipaddresslink_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_network ALTER COLUMN id SET DEFAULT nextval('maasserver_network_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node ALTER COLUMN id SET DEFAULT nextval('maasserver_node_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node_tags ALTER COLUMN id SET DEFAULT nextval('maasserver_node_tags_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_nodegroup ALTER COLUMN id SET DEFAULT nextval('maasserver_nodegroup_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_nodegroupinterface ALTER COLUMN id SET DEFAULT nextval('maasserver_nodegroupinterface_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_partition ALTER COLUMN id SET DEFAULT nextval('maasserver_partition_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_partitiontable ALTER COLUMN id SET DEFAULT nextval('maasserver_partitiontable_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_sshkey ALTER COLUMN id SET DEFAULT nextval('maasserver_sshkey_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_sslkey ALTER COLUMN id SET DEFAULT nextval('maasserver_sslkey_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_staticipaddress ALTER COLUMN id SET DEFAULT nextval('maasserver_staticipaddress_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_tag ALTER COLUMN id SET DEFAULT nextval('maasserver_tag_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_userprofile ALTER COLUMN id SET DEFAULT nextval('maasserver_userprofile_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_zone ALTER COLUMN id SET DEFAULT nextval('maasserver_zone_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_commissioningscript ALTER COLUMN id SET DEFAULT nextval('metadataserver_commissioningscript_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_nodekey ALTER COLUMN id SET DEFAULT nextval('metadataserver_nodekey_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_noderesult ALTER COLUMN id SET DEFAULT nextval('metadataserver_noderesult_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_nodeuserdata ALTER COLUMN id SET DEFAULT nextval('metadataserver_nodeuserdata_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY piston_consumer ALTER COLUMN id SET DEFAULT nextval('piston_consumer_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY piston_nonce ALTER COLUMN id SET DEFAULT nextval('piston_nonce_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY piston_token ALTER COLUMN id SET DEFAULT nextval('piston_token_id_seq'::regclass);


--
-- Name: id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY south_migrationhistory ALTER COLUMN id SET DEFAULT nextval('south_migrationhistory_id_seq'::regclass);


--
-- Data for Name: auth_group; Type: TABLE DATA; Schema: public; Owner: -
--

COPY auth_group (id, name) FROM stdin;
\.


--
-- Name: auth_group_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('auth_group_id_seq', 1, false);


--
-- Data for Name: auth_group_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY auth_group_permissions (id, group_id, permission_id) FROM stdin;
\.


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('auth_group_permissions_id_seq', 1, false);


--
-- Data for Name: auth_permission; Type: TABLE DATA; Schema: public; Owner: -
--

COPY auth_permission (id, name, content_type_id, codename) FROM stdin;
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
19	Can add nonce	7	add_nonce
20	Can change nonce	7	change_nonce
21	Can delete nonce	7	delete_nonce
22	Can add consumer	8	add_consumer
23	Can change consumer	8	change_consumer
24	Can delete consumer	8	delete_consumer
25	Can add token	9	add_token
26	Can change token	9	change_token
27	Can delete token	9	delete_token
28	Can add migration history	10	add_migrationhistory
29	Can change migration history	10	change_migrationhistory
30	Can delete migration history	10	delete_migrationhistory
31	Can add log entry	11	add_logentry
32	Can change log entry	11	change_logentry
33	Can delete log entry	11	delete_logentry
34	Can add block device	12	add_blockdevice
35	Can change block device	12	change_blockdevice
36	Can delete block device	12	delete_blockdevice
37	Can add boot resource	13	add_bootresource
38	Can change boot resource	13	change_bootresource
39	Can delete boot resource	13	delete_bootresource
40	Can add boot resource set	14	add_bootresourceset
41	Can change boot resource set	14	change_bootresourceset
42	Can delete boot resource set	14	delete_bootresourceset
43	Can add large file	15	add_largefile
44	Can change large file	15	change_largefile
45	Can delete large file	15	delete_largefile
46	Can add boot resource file	16	add_bootresourcefile
47	Can change boot resource file	16	change_bootresourcefile
48	Can delete boot resource file	16	delete_bootresourcefile
49	Can add boot source	17	add_bootsource
50	Can change boot source	17	change_bootsource
51	Can delete boot source	17	delete_bootsource
52	Can add boot source cache	18	add_bootsourcecache
53	Can change boot source cache	18	change_bootsourcecache
54	Can delete boot source cache	18	delete_bootsourcecache
55	Can add boot source selection	19	add_bootsourceselection
56	Can change boot source selection	19	change_bootsourceselection
57	Can delete boot source selection	19	delete_bootsourceselection
58	Can add Candidate name	20	add_candidatename
59	Can change Candidate name	20	change_candidatename
60	Can delete Candidate name	20	delete_candidatename
61	Can add component error	21	add_componenterror
62	Can change component error	21	change_componenterror
63	Can delete component error	21	delete_componenterror
64	Can add config	22	add_config
65	Can change config	22	change_config
66	Can delete config	22	delete_config
67	Can add mac static ip address link	23	add_macstaticipaddresslink
68	Can change mac static ip address link	23	change_macstaticipaddresslink
69	Can delete mac static ip address link	23	delete_macstaticipaddresslink
70	Can add network	24	add_network
71	Can change network	24	change_network
72	Can delete network	24	delete_network
73	Can add node group	25	add_nodegroup
74	Can change node group	25	change_nodegroup
75	Can delete node group	25	delete_nodegroup
76	Can add node group interface	26	add_nodegroupinterface
77	Can change node group interface	26	change_nodegroupinterface
78	Can delete node group interface	26	delete_nodegroupinterface
79	Can add Static IP Address	27	add_staticipaddress
80	Can change Static IP Address	27	change_staticipaddress
81	Can delete Static IP Address	27	delete_staticipaddress
82	Can add MAC address	28	add_macaddress
83	Can change MAC address	28	change_macaddress
84	Can delete MAC address	28	delete_macaddress
85	Can add dhcp lease	29	add_dhcplease
86	Can change dhcp lease	29	change_dhcplease
87	Can delete dhcp lease	29	delete_dhcplease
88	Can add download progress	30	add_downloadprogress
89	Can change download progress	30	change_downloadprogress
90	Can delete download progress	30	delete_downloadprogress
91	Can add Event type	31	add_eventtype
92	Can change Event type	31	change_eventtype
93	Can delete Event type	31	delete_eventtype
94	Can add license key	32	add_licensekey
95	Can change license key	32	change_licensekey
96	Can delete license key	32	delete_licensekey
97	Can add physical block device	33	add_physicalblockdevice
98	Can change physical block device	33	change_physicalblockdevice
99	Can delete physical block device	33	delete_physicalblockdevice
100	Can add tag	34	add_tag
101	Can change tag	34	change_tag
102	Can delete tag	34	delete_tag
103	Can add Physical zone	35	add_zone
104	Can change Physical zone	35	change_zone
105	Can delete Physical zone	35	delete_zone
106	Can add node	36	add_node
107	Can change node	36	change_node
108	Can delete node	36	delete_node
109	Can add Event record	37	add_event
110	Can change Event record	37	change_event
111	Can delete Event record	37	delete_event
112	Can add file storage	38	add_filestorage
113	Can change file storage	38	change_filestorage
114	Can delete file storage	38	delete_filestorage
115	Can add filesystem group	39	add_filesystemgroup
116	Can change filesystem group	39	change_filesystemgroup
117	Can delete filesystem group	39	delete_filesystemgroup
118	Can add partition table	40	add_partitiontable
119	Can change partition table	40	change_partitiontable
120	Can delete partition table	40	delete_partitiontable
121	Can add partition	41	add_partition
122	Can change partition	41	change_partition
123	Can delete partition	41	delete_partition
124	Can add filesystem	42	add_filesystem
125	Can change filesystem	42	change_filesystem
126	Can delete filesystem	42	delete_filesystem
127	Can add SSH key	43	add_sshkey
128	Can change SSH key	43	change_sshkey
129	Can delete SSH key	43	delete_sshkey
130	Can add SSL key	44	add_sslkey
131	Can change SSL key	44	change_sslkey
132	Can delete SSL key	44	delete_sslkey
133	Can add user profile	45	add_userprofile
134	Can change user profile	45	change_userprofile
135	Can delete user profile	45	delete_userprofile
136	Can add virtual block device	46	add_virtualblockdevice
137	Can change virtual block device	46	change_virtualblockdevice
138	Can delete virtual block device	46	delete_virtualblockdevice
139	Can add node result	47	add_noderesult
140	Can change node result	47	change_noderesult
141	Can delete node result	47	delete_noderesult
142	Can add commissioning script	48	add_commissioningscript
143	Can change commissioning script	48	change_commissioningscript
144	Can delete commissioning script	48	delete_commissioningscript
145	Can add node key	49	add_nodekey
146	Can change node key	49	change_nodekey
147	Can delete node key	49	delete_nodekey
148	Can add node user data	50	add_nodeuserdata
149	Can change node user data	50	change_nodeuserdata
150	Can delete node user data	50	delete_nodeuserdata
\.


--
-- Name: auth_permission_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('auth_permission_id_seq', 150, true);


--
-- Data for Name: auth_user; Type: TABLE DATA; Schema: public; Owner: -
--

COPY auth_user (id, password, last_login, is_superuser, username, first_name, last_name, email, is_staff, is_active, date_joined) FROM stdin;
1	!	2012-02-16 00:00:00+00	f	maas-init-node	Node initializer	Special user		f	f	2012-02-16 00:00:00+00
\.


--
-- Data for Name: auth_user_groups; Type: TABLE DATA; Schema: public; Owner: -
--

COPY auth_user_groups (id, user_id, group_id) FROM stdin;
\.


--
-- Name: auth_user_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('auth_user_groups_id_seq', 1, false);


--
-- Name: auth_user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('auth_user_id_seq', 1, true);


--
-- Data for Name: auth_user_user_permissions; Type: TABLE DATA; Schema: public; Owner: -
--

COPY auth_user_user_permissions (id, user_id, permission_id) FROM stdin;
\.


--
-- Name: auth_user_user_permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('auth_user_user_permissions_id_seq', 1, false);


--
-- Data for Name: django_admin_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY django_admin_log (id, action_time, user_id, content_type_id, object_id, object_repr, action_flag, change_message) FROM stdin;
\.


--
-- Name: django_admin_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('django_admin_log_id_seq', 1, false);


--
-- Data for Name: django_content_type; Type: TABLE DATA; Schema: public; Owner: -
--

COPY django_content_type (id, name, app_label, model) FROM stdin;
1	permission	auth	permission
2	group	auth	group
3	user	auth	user
4	content type	contenttypes	contenttype
5	session	sessions	session
6	site	sites	site
7	nonce	piston	nonce
8	consumer	piston	consumer
9	token	piston	token
10	migration history	south	migrationhistory
11	log entry	admin	logentry
12	block device	maasserver	blockdevice
13	boot resource	maasserver	bootresource
14	boot resource set	maasserver	bootresourceset
15	large file	maasserver	largefile
16	boot resource file	maasserver	bootresourcefile
17	boot source	maasserver	bootsource
18	boot source cache	maasserver	bootsourcecache
19	boot source selection	maasserver	bootsourceselection
20	Candidate name	maasserver	candidatename
21	component error	maasserver	componenterror
22	config	maasserver	config
23	mac static ip address link	maasserver	macstaticipaddresslink
24	network	maasserver	network
25	node group	maasserver	nodegroup
26	node group interface	maasserver	nodegroupinterface
27	Static IP Address	maasserver	staticipaddress
28	MAC address	maasserver	macaddress
29	dhcp lease	maasserver	dhcplease
30	download progress	maasserver	downloadprogress
31	Event type	maasserver	eventtype
32	license key	maasserver	licensekey
33	physical block device	maasserver	physicalblockdevice
34	tag	maasserver	tag
35	Physical zone	maasserver	zone
36	node	maasserver	node
37	Event record	maasserver	event
38	file storage	maasserver	filestorage
39	filesystem group	maasserver	filesystemgroup
40	partition table	maasserver	partitiontable
41	partition	maasserver	partition
42	filesystem	maasserver	filesystem
43	SSH key	maasserver	sshkey
44	SSL key	maasserver	sslkey
45	user profile	maasserver	userprofile
46	virtual block device	maasserver	virtualblockdevice
47	node result	metadataserver	noderesult
48	commissioning script	metadataserver	commissioningscript
49	node key	metadataserver	nodekey
50	node user data	metadataserver	nodeuserdata
\.


--
-- Name: django_content_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('django_content_type_id_seq', 50, true);


--
-- Data for Name: django_session; Type: TABLE DATA; Schema: public; Owner: -
--

COPY django_session (session_key, session_data, expire_date) FROM stdin;
\.


--
-- Data for Name: django_site; Type: TABLE DATA; Schema: public; Owner: -
--

COPY django_site (id, domain, name) FROM stdin;
1	example.com	example.com
\.


--
-- Name: django_site_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('django_site_id_seq', 1, true);


--
-- Data for Name: maasserver_blockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_blockdevice (id, created, updated, node_id, name, path, size, block_size, tags, id_path) FROM stdin;
\.


--
-- Name: maasserver_blockdevice_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_blockdevice_id_seq', 1, false);


--
-- Data for Name: maasserver_bootresource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_bootresource (id, created, updated, rtype, name, architecture, extra) FROM stdin;
\.


--
-- Name: maasserver_bootresource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_bootresource_id_seq', 1, false);


--
-- Data for Name: maasserver_bootresourcefile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_bootresourcefile (id, created, updated, resource_set_id, largefile_id, filename, filetype, extra) FROM stdin;
\.


--
-- Name: maasserver_bootresourcefile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_bootresourcefile_id_seq', 1, false);


--
-- Data for Name: maasserver_bootresourceset; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_bootresourceset (id, created, updated, resource_id, version, label) FROM stdin;
\.


--
-- Name: maasserver_bootresourceset_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_bootresourceset_id_seq', 1, false);


--
-- Data for Name: maasserver_bootsource; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_bootsource (id, created, updated, url, keyring_filename, keyring_data) FROM stdin;
\.


--
-- Name: maasserver_bootsource_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_bootsource_id_seq', 1, false);


--
-- Data for Name: maasserver_bootsourcecache; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_bootsourcecache (id, created, updated, boot_source_id, os, arch, subarch, release, label) FROM stdin;
\.


--
-- Name: maasserver_bootsourcecache_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_bootsourcecache_id_seq', 1, false);


--
-- Data for Name: maasserver_bootsourceselection; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_bootsourceselection (id, created, updated, boot_source_id, release, arches, subarches, labels, os) FROM stdin;
\.


--
-- Name: maasserver_bootsourceselection_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_bootsourceselection_id_seq', 1, false);


--
-- Data for Name: maasserver_candidatename; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_candidatename (id, name, "position") FROM stdin;
1	abandoned	1
2	able	1
3	absolute	1
4	academic	1
5	acceptable	1
6	acclaimed	1
7	accomplished	1
8	accurate	1
9	aching	1
10	acidic	1
11	acrobatic	1
12	active	1
13	actual	1
14	adept	1
15	admirable	1
16	admired	1
17	adolescent	1
18	adorable	1
19	adored	1
20	advanced	1
21	adventurous	1
22	affectionate	1
23	afraid	1
24	aged	1
25	aggravating	1
26	aggressive	1
27	agile	1
28	agitated	1
29	agonizing	1
30	agreeable	1
31	ajar	1
32	alarmed	1
33	alarming	1
34	alert	1
35	alienated	1
36	alive	1
37	all	1
38	altruistic	1
39	amazing	1
40	ambitious	1
41	ample	1
42	amused	1
43	amusing	1
44	anchored	1
45	ancient	1
46	angelic	1
47	angry	1
48	anguished	1
49	animated	1
50	annual	1
51	another	1
52	antique	1
53	anxious	1
54	any	1
55	apprehensive	1
56	appropriate	1
57	apt	1
58	arctic	1
59	arid	1
60	aromatic	1
61	artistic	1
62	ashamed	1
63	assured	1
64	astonishing	1
65	athletic	1
66	attached	1
67	attentive	1
68	attractive	1
69	austere	1
70	authentic	1
71	authorized	1
72	automatic	1
73	avaricious	1
74	average	1
75	aware	1
76	awesome	1
77	awful	1
78	awkward	1
79	babyish	1
80	back	1
81	bad	1
82	baggy	1
83	bare	1
84	barren	1
85	basic	1
86	beautiful	1
87	belated	1
88	beloved	1
89	beneficial	1
90	best	1
91	better	1
92	bewitched	1
93	big	1
94	biodegradable	1
95	bitesize	1
96	bitter	1
97	black	1
98	bland	1
99	blank	1
100	blaring	1
101	bleak	1
102	blind	1
103	blissful	1
104	blond	1
105	blue	1
106	blushing	1
107	bogus	1
108	boiling	1
109	bold	1
110	bony	1
111	boring	1
112	bossy	1
113	both	1
114	bouncy	1
115	bountiful	1
116	bowed	1
117	brave	1
118	breakable	1
119	brief	1
120	bright	1
121	brilliant	1
122	brisk	1
123	broken	1
124	bronze	1
125	brown	1
126	bruised	1
127	bubbly	1
128	bulky	1
129	bumpy	1
130	buoyant	1
131	burdensome	1
132	burly	1
133	bustling	1
134	busy	1
135	buttery	1
136	buzzing	1
137	calculating	1
138	calm	1
139	candid	1
140	canine	1
141	capital	1
142	carefree	1
143	careful	1
144	careless	1
145	caring	1
146	cautious	1
147	cavernous	1
148	celebrated	1
149	charming	1
150	cheap	1
151	cheerful	1
152	cheery	1
153	chief	1
154	chilly	1
155	chubby	1
156	circular	1
157	classic	1
158	clean	1
159	clear	1
160	clever	1
161	close	1
162	closed	1
163	cloudy	1
164	clueless	1
165	clumsy	1
166	cluttered	1
167	coarse	1
168	cold	1
169	colorful	1
170	colorless	1
171	colossal	1
172	comfortable	1
173	common	1
174	compassionate	1
175	competent	1
176	complete	1
177	complex	1
178	complicated	1
179	composed	1
180	concerned	1
181	concrete	1
182	confused	1
183	conscious	1
184	considerate	1
185	constant	1
186	content	1
187	conventional	1
188	cooked	1
189	cool	1
190	cooperative	1
191	coordinated	1
192	corny	1
193	corrupt	1
194	costly	1
195	courageous	1
196	courteous	1
197	crafty	1
198	crazy	1
199	creamy	1
200	creative	1
201	creepy	1
202	criminal	1
203	crisp	1
204	critical	1
205	crooked	1
206	crowded	1
207	cruel	1
208	crushing	1
209	cuddly	1
210	cultivated	1
211	cultured	1
212	cumbersome	1
213	curly	1
214	curvy	1
215	cute	1
216	cylindrical	1
217	damaged	1
218	damp	1
219	dangerous	1
220	dapper	1
221	daring	1
222	dark	1
223	darling	1
224	dazzling	1
225	dead	1
226	deadly	1
227	deafening	1
228	dear	1
229	dearest	1
230	decent	1
231	decimal	1
232	decisive	1
233	deep	1
234	defenseless	1
235	defensive	1
236	defiant	1
237	deficient	1
238	definite	1
239	definitive	1
240	delayed	1
241	delectable	1
242	delicious	1
243	delightful	1
244	delirious	1
245	demanding	1
246	dense	1
247	dental	1
248	dependable	1
249	dependent	1
250	descriptive	1
251	deserted	1
252	detailed	1
253	determined	1
254	devoted	1
255	different	1
256	difficult	1
257	digital	1
258	diligent	1
259	dim	1
260	dimpled	1
261	dimwitted	1
262	direct	1
263	dirty	1
264	disastrous	1
265	discrete	1
266	disfigured	1
267	disguised	1
268	disgusting	1
269	dishonest	1
270	disloyal	1
271	dismal	1
272	distant	1
273	distinct	1
274	distorted	1
275	dizzy	1
276	dopey	1
277	doting	1
278	double	1
279	downright	1
280	drab	1
281	drafty	1
282	dramatic	1
283	dreary	1
284	droopy	1
285	dry	1
286	dual	1
287	dull	1
288	dutiful	1
289	each	1
290	eager	1
291	early	1
292	earnest	1
293	easy	1
294	easygoing	1
295	ecstatic	1
296	edible	1
297	educated	1
298	elaborate	1
299	elastic	1
300	elated	1
301	elderly	1
302	electric	1
303	elegant	1
304	elementary	1
305	elliptical	1
306	embarrassed	1
307	embellished	1
308	eminent	1
309	emotional	1
310	empty	1
311	enchanted	1
312	enchanting	1
313	energetic	1
314	enlightened	1
315	enormous	1
316	enraged	1
317	entire	1
318	envious	1
319	equal	1
320	equatorial	1
321	essential	1
322	esteemed	1
323	ethical	1
324	euphoric	1
325	even	1
326	evergreen	1
327	everlasting	1
328	every	1
329	evil	1
330	exalted	1
331	excellent	1
332	excitable	1
333	excited	1
334	exciting	1
335	exemplary	1
336	exhausted	1
337	exotic	1
338	expensive	1
339	experienced	1
340	expert	1
341	extraneous	1
342	extroverted	1
343	fabulous	1
344	failing	1
345	faint	1
346	fair	1
347	faithful	1
348	fake	1
349	false	1
350	familiar	1
351	famous	1
352	fancy	1
353	fantastic	1
354	far	1
355	faraway	1
356	fast	1
357	fat	1
358	fatal	1
359	fatherly	1
360	favorable	1
361	favorite	1
362	fearful	1
363	fearless	1
364	feisty	1
365	feline	1
366	female	1
367	feminine	1
368	few	1
369	fickle	1
370	filthy	1
371	fine	1
372	finished	1
373	firm	1
374	first	1
375	firsthand	1
376	fitting	1
377	fixed	1
378	flaky	1
379	flamboyant	1
380	flashy	1
381	flat	1
382	flawed	1
383	flawless	1
384	flickering	1
385	flimsy	1
386	flippant	1
387	flowery	1
388	fluffy	1
389	fluid	1
390	flustered	1
391	focused	1
392	fond	1
393	foolhardy	1
394	foolish	1
395	forceful	1
396	forked	1
397	formal	1
398	forsaken	1
399	forthright	1
400	fortunate	1
401	fragrant	1
402	frail	1
403	frank	1
404	frayed	1
405	free	1
406	french	1
407	frequent	1
408	fresh	1
409	friendly	1
410	frightened	1
411	frightening	1
412	frigid	1
413	frilly	1
414	frivolous	1
415	frizzy	1
416	front	1
417	frosty	1
418	frozen	1
419	frugal	1
420	fruitful	1
421	full	1
422	fumbling	1
423	functional	1
424	funny	1
425	fussy	1
426	fuzzy	1
427	gargantuan	1
428	gaseous	1
429	general	1
430	generous	1
431	gentle	1
432	genuine	1
433	giant	1
434	giddy	1
435	gifted	1
436	gigantic	1
437	giving	1
438	glamorous	1
439	glaring	1
440	glass	1
441	gleaming	1
442	gleeful	1
443	glistening	1
444	glittering	1
445	gloomy	1
446	glorious	1
447	glossy	1
448	glum	1
449	golden	1
450	good	1
451	gorgeous	1
452	graceful	1
453	gracious	1
454	grand	1
455	grandiose	1
456	granular	1
457	grateful	1
458	grave	1
459	gray	1
460	great	1
461	greedy	1
462	green	1
463	gregarious	1
464	grim	1
465	grimy	1
466	gripping	1
467	grizzled	1
468	gross	1
469	grotesque	1
470	grouchy	1
471	grounded	1
472	growing	1
473	growling	1
474	grown	1
475	grubby	1
476	gruesome	1
477	grumpy	1
478	guilty	1
479	gullible	1
480	gummy	1
481	hairy	1
482	half	1
483	handmade	1
484	handsome	1
485	handy	1
486	happy	1
487	hard	1
488	harmful	1
489	harmless	1
490	harmonious	1
491	harsh	1
492	hasty	1
493	hateful	1
494	haunting	1
495	healthy	1
496	heartfelt	1
497	hearty	1
498	heavenly	1
499	heavy	1
500	hefty	1
501	helpful	1
502	helpless	1
503	hidden	1
504	hideous	1
505	high	1
506	hilarious	1
507	hoarse	1
508	hollow	1
509	homely	1
510	honest	1
511	honorable	1
512	honored	1
513	hopeful	1
514	horrible	1
515	hospitable	1
516	hot	1
517	huge	1
518	humble	1
519	humiliating	1
520	humming	1
521	humongous	1
522	hungry	1
523	hurtful	1
524	husky	1
525	icky	1
526	icy	1
527	ideal	1
528	idealistic	1
529	identical	1
530	idiotic	1
531	idle	1
532	idolized	1
533	ignorant	1
534	ill	1
535	illegal	1
536	illiterate	1
537	illustrious	1
538	imaginary	1
539	imaginative	1
540	immaculate	1
541	immaterial	1
542	immediate	1
543	immense	1
544	impartial	1
545	impassioned	1
546	impeccable	1
547	imperfect	1
548	imperturbable	1
549	impish	1
550	impolite	1
551	important	1
552	impossible	1
553	impractical	1
554	impressionable	1
555	impressive	1
556	improbable	1
557	impure	1
558	inborn	1
559	incomparable	1
560	incompatible	1
561	incomplete	1
562	inconsequential	1
563	incredible	1
564	indelible	1
565	indolent	1
566	inexperienced	1
567	infamous	1
568	infantile	1
569	infatuated	1
570	inferior	1
571	infinite	1
572	informal	1
573	innocent	1
574	insecure	1
575	insidious	1
576	insignificant	1
577	insistent	1
578	instructive	1
579	insubstantial	1
580	intelligent	1
581	intent	1
582	intentional	1
583	interesting	1
584	internal	1
585	international	1
586	intrepid	1
587	ironclad	1
588	irresponsible	1
589	irritating	1
590	itchy	1
591	jaded	1
592	jagged	1
593	jaunty	1
594	jealous	1
595	jittery	1
596	joint	1
597	jolly	1
598	jovial	1
599	joyful	1
600	joyous	1
601	jubilant	1
602	judicious	1
603	juicy	1
604	jumbo	1
605	jumpy	1
606	junior	1
607	juvenile	1
608	kaleidoscopic	1
609	keen	1
610	key	1
611	kind	1
612	kindhearted	1
613	kindly	1
614	klutzy	1
615	knobby	1
616	knotty	1
617	knowing	1
618	knowledgeable	1
619	known	1
620	kooky	1
621	kosher	1
622	lame	1
623	lanky	1
624	large	1
625	last	1
626	lasting	1
627	late	1
628	lavish	1
629	lawful	1
630	lazy	1
631	leading	1
632	leafy	1
633	lean	1
634	left	1
635	legal	1
636	legitimate	1
637	light	1
638	lighthearted	1
639	likable	1
640	likely	1
641	limited	1
642	limp	1
643	limping	1
644	linear	1
645	lined	1
646	liquid	1
647	little	1
648	live	1
649	lively	1
650	livid	1
651	loathsome	1
652	lone	1
653	lonely	1
654	long	1
655	loose	1
656	lopsided	1
657	lost	1
658	loud	1
659	lovable	1
660	lovely	1
661	loving	1
662	low	1
663	loyal	1
664	lucky	1
665	lumbering	1
666	luminous	1
667	lumpy	1
668	lustrous	1
669	luxurious	1
670	mad	1
671	magnificent	1
672	majestic	1
673	major	1
674	male	1
675	mammoth	1
676	married	1
677	marvelous	1
678	masculine	1
679	massive	1
680	mature	1
681	meager	1
682	mealy	1
683	mean	1
684	measly	1
685	meaty	1
686	medical	1
687	mediocre	1
688	medium	1
689	meek	1
690	mellow	1
691	melodic	1
692	memorable	1
693	menacing	1
694	merry	1
695	messy	1
696	metallic	1
697	mild	1
698	milky	1
699	mindless	1
700	miniature	1
701	minor	1
702	minty	1
703	miserable	1
704	miserly	1
705	misguided	1
706	misty	1
707	mixed	1
708	modern	1
709	modest	1
710	moist	1
711	monstrous	1
712	monthly	1
713	monumental	1
714	moral	1
715	mortified	1
716	motherly	1
717	motionless	1
718	mountainous	1
719	muddy	1
720	muffled	1
721	multicolored	1
722	mundane	1
723	murky	1
724	mushy	1
725	musty	1
726	muted	1
727	mysterious	1
728	naive	1
729	narrow	1
730	nasty	1
731	natural	1
732	naughty	1
733	nautical	1
734	near	1
735	neat	1
736	necessary	1
737	needy	1
738	negative	1
739	neglected	1
740	negligible	1
741	neighboring	1
742	nervous	1
743	new	1
744	next	1
745	nice	1
746	nifty	1
747	nimble	1
748	nippy	1
749	nocturnal	1
750	noisy	1
751	nonstop	1
752	normal	1
753	notable	1
754	noted	1
755	noteworthy	1
756	novel	1
757	noxious	1
758	numb	1
759	nutritious	1
760	nutty	1
761	obedient	1
762	obese	1
763	oblong	1
764	obvious	1
765	occasional	1
766	odd	1
767	oddball	1
768	offbeat	1
769	offensive	1
770	official	1
771	oily	1
772	old	1
773	overlooked	1
774	only	1
775	open	1
776	optimal	1
777	optimistic	1
778	opulent	1
779	orange	1
780	orderly	1
781	ordinary	1
782	organic	1
783	original	1
784	ornate	1
785	ornery	1
786	other	1
787	our	1
788	outgoing	1
789	outlandish	1
790	outlying	1
791	outrageous	1
792	outstanding	1
793	oval	1
794	overcooked	1
795	overdue	1
796	overjoyed	1
797	palatable	1
798	pale	1
799	paltry	1
800	parallel	1
801	parched	1
802	partial	1
803	passionate	1
804	past	1
805	pastel	1
806	peaceful	1
807	peppery	1
808	perfect	1
809	perfumed	1
810	periodic	1
811	perky	1
812	personal	1
813	pertinent	1
814	pesky	1
815	pessimistic	1
816	petty	1
817	phony	1
818	physical	1
819	piercing	1
820	pink	1
821	pitiful	1
822	plain	1
823	plaintive	1
824	plastic	1
825	playful	1
826	pleasant	1
827	pleased	1
828	pleasing	1
829	plump	1
830	plush	1
831	pointed	1
832	pointless	1
833	poised	1
834	polished	1
835	polite	1
836	political	1
837	poor	1
838	popular	1
839	portly	1
840	posh	1
841	positive	1
842	possible	1
843	potable	1
844	powerful	1
845	powerless	1
846	practical	1
847	precious	1
848	present	1
849	prestigious	1
850	pretty	1
851	previous	1
852	pricey	1
853	prickly	1
854	primary	1
855	prime	1
856	pristine	1
857	private	1
858	prize	1
859	probable	1
860	productive	1
861	profitable	1
862	profuse	1
863	proper	1
864	proud	1
865	prudent	1
866	punctual	1
867	pungent	1
868	puny	1
869	pure	1
870	purple	1
871	pushy	1
872	putrid	1
873	puzzled	1
874	puzzling	1
875	quaint	1
876	qualified	1
877	quarrelsome	1
878	quarterly	1
879	queasy	1
880	querulous	1
881	questionable	1
882	quick	1
883	quiet	1
884	quintessential	1
885	quirky	1
886	quixotic	1
887	quizzical	1
888	radiant	1
889	ragged	1
890	rapid	1
891	rare	1
892	rash	1
893	raw	1
894	ready	1
895	real	1
896	realistic	1
897	reasonable	1
898	recent	1
899	reckless	1
900	rectangular	1
901	red	1
902	reflecting	1
903	regal	1
904	regular	1
905	reliable	1
906	relieved	1
907	remarkable	1
908	remorseful	1
909	remote	1
910	repentant	1
911	repulsive	1
912	required	1
913	respectful	1
914	responsible	1
915	revolving	1
916	rewarding	1
917	rich	1
918	right	1
919	rigid	1
920	ringed	1
921	ripe	1
922	roasted	1
923	robust	1
924	rosy	1
925	rotating	1
926	rotten	1
927	rough	1
928	round	1
929	rowdy	1
930	royal	1
931	rubbery	1
932	ruddy	1
933	rude	1
934	rundown	1
935	runny	1
936	rural	1
937	rusty	1
938	sad	1
939	safe	1
940	salty	1
941	same	1
942	sandy	1
943	sane	1
944	sarcastic	1
945	sardonic	1
946	satisfied	1
947	scaly	1
948	scarce	1
949	scared	1
950	scary	1
951	scented	1
952	scholarly	1
953	scientific	1
954	scornful	1
955	scratchy	1
956	scrawny	1
957	second	1
958	secondary	1
959	secret	1
960	selfish	1
961	sentimental	1
962	separate	1
963	serene	1
964	serious	1
965	serpentine	1
966	several	1
967	severe	1
968	shabby	1
969	shadowy	1
970	shady	1
971	shallow	1
972	shameful	1
973	shameless	1
974	sharp	1
975	shimmering	1
976	shiny	1
977	shocked	1
978	shocking	1
979	shoddy	1
980	short	1
981	showy	1
982	shrill	1
983	shy	1
984	sick	1
985	silent	1
986	silky	1
987	silly	1
988	silver	1
989	similar	1
990	simple	1
991	simplistic	1
992	sinful	1
993	single	1
994	sizzling	1
995	skeletal	1
996	skinny	1
997	sleepy	1
998	slight	1
999	slim	1
1000	slimy	1
1001	slippery	1
1002	slow	1
1003	slushy	1
1004	small	1
1005	smart	1
1006	smoggy	1
1007	smooth	1
1008	smug	1
1009	snappy	1
1010	snarling	1
1011	sneaky	1
1012	sniveling	1
1013	snoopy	1
1014	sociable	1
1015	soft	1
1016	soggy	1
1017	solid	1
1018	somber	1
1019	some	1
1020	sophisticated	1
1021	sore	1
1022	sorrowful	1
1023	soulful	1
1024	soupy	1
1025	sour	1
1026	spanish	1
1027	sparkling	1
1028	sparse	1
1029	specific	1
1030	spectacular	1
1031	speedy	1
1032	spherical	1
1033	spicy	1
1034	spiffy	1
1035	spirited	1
1036	spiteful	1
1037	splendid	1
1038	spotless	1
1039	spotted	1
1040	spry	1
1041	square	1
1042	squeaky	1
1043	squiggly	1
1044	stable	1
1045	staid	1
1046	stained	1
1047	stale	1
1048	standard	1
1049	starchy	1
1050	stark	1
1051	starry	1
1052	steel	1
1053	steep	1
1054	sticky	1
1055	stiff	1
1056	stimulating	1
1057	stingy	1
1058	stormy	1
1059	straight	1
1060	strange	1
1061	strict	1
1062	strident	1
1063	striking	1
1064	striped	1
1065	strong	1
1066	studious	1
1067	stunning	1
1068	stupendous	1
1069	stupid	1
1070	sturdy	1
1071	stylish	1
1072	subdued	1
1073	submissive	1
1074	substantial	1
1075	subtle	1
1076	suburban	1
1077	sudden	1
1078	sugary	1
1079	sunny	1
1080	super	1
1081	superb	1
1082	superficial	1
1083	superior	1
1084	supportive	1
1085	surprised	1
1086	suspicious	1
1087	svelte	1
1088	sweaty	1
1089	sweet	1
1090	sweltering	1
1091	swift	1
1092	sympathetic	1
1093	talkative	1
1094	tall	1
1095	tame	1
1096	tan	1
1097	tangible	1
1098	tart	1
1099	tasty	1
1100	tattered	1
1101	taut	1
1102	tedious	1
1103	teeming	1
1104	tempting	1
1105	tender	1
1106	tense	1
1107	tepid	1
1108	terrible	1
1109	terrific	1
1110	testy	1
1111	thankful	1
1112	that	1
1113	these	1
1114	thick	1
1115	thin	1
1116	third	1
1117	thirsty	1
1118	this	1
1119	thorny	1
1120	thorough	1
1121	those	1
1122	thoughtful	1
1123	threadbare	1
1124	thrifty	1
1125	thunderous	1
1126	tidy	1
1127	tight	1
1128	timely	1
1129	tinted	1
1130	tiny	1
1131	tired	1
1132	torn	1
1133	total	1
1134	tough	1
1135	tragic	1
1136	trained	1
1137	traumatic	1
1138	treasured	1
1139	tremendous	1
1140	triangular	1
1141	tricky	1
1142	trifling	1
1143	trim	1
1144	trivial	1
1145	troubled	1
1146	true	1
1147	trusting	1
1148	trustworthy	1
1149	trusty	1
1150	truthful	1
1151	tubby	1
1152	turbulent	1
1153	twin	1
1154	ugly	1
1155	ultimate	1
1156	unacceptable	1
1157	unaware	1
1158	uncomfortable	1
1159	uncommon	1
1160	unconscious	1
1161	understated	1
1162	unequaled	1
1163	uneven	1
1164	unfinished	1
1165	unfit	1
1166	unfolded	1
1167	unfortunate	1
1168	unhappy	1
1169	unhealthy	1
1170	uniform	1
1171	unimportant	1
1172	unique	1
1173	united	1
1174	unkempt	1
1175	unknown	1
1176	unlawful	1
1177	unlined	1
1178	unlucky	1
1179	unnatural	1
1180	unpleasant	1
1181	unrealistic	1
1182	unripe	1
1183	unruly	1
1184	unselfish	1
1185	unsightly	1
1186	unsteady	1
1187	unsung	1
1188	untidy	1
1189	untimely	1
1190	untried	1
1191	untrue	1
1192	unused	1
1193	unusual	1
1194	unwelcome	1
1195	unwieldy	1
1196	unwilling	1
1197	unwitting	1
1198	unwritten	1
1199	upbeat	1
1200	upright	1
1201	upset	1
1202	urban	1
1203	usable	1
1204	used	1
1205	useful	1
1206	useless	1
1207	utilized	1
1208	utter	1
1209	vacant	1
1210	vague	1
1211	vain	1
1212	valid	1
1213	valuable	1
1214	vapid	1
1215	variable	1
1216	vast	1
1217	velvety	1
1218	venerated	1
1219	vengeful	1
1220	verifiable	1
1221	vibrant	1
1222	vicious	1
1223	victorious	1
1224	vigilant	1
1225	vigorous	1
1226	villainous	1
1227	violent	1
1228	violet	1
1229	virtual	1
1230	virtuous	1
1231	visible	1
1232	vital	1
1233	vivacious	1
1234	vivid	1
1235	voluminous	1
1236	wan	1
1237	warlike	1
1238	warm	1
1239	warmhearted	1
1240	warped	1
1241	wary	1
1242	wasteful	1
1243	watchful	1
1244	waterlogged	1
1245	watery	1
1246	wavy	1
1247	weak	1
1248	wealthy	1
1249	weary	1
1250	webbed	1
1251	wee	1
1252	weekly	1
1253	weepy	1
1254	weighty	1
1255	weird	1
1256	welcome	1
1257	wet	1
1258	which	1
1259	whimsical	1
1260	whirlwind	1
1261	whispered	1
1262	white	1
1263	whole	1
1264	whopping	1
1265	wicked	1
1266	wide	1
1267	wiggly	1
1268	wild	1
1269	willing	1
1270	wilted	1
1271	winding	1
1272	windy	1
1273	winged	1
1274	wiry	1
1275	wise	1
1276	witty	1
1277	wobbly	1
1278	woeful	1
1279	wonderful	1
1280	wooden	1
1281	woozy	1
1282	wordy	1
1283	worldly	1
1284	worn	1
1285	worried	1
1286	worrisome	1
1287	worse	1
1288	worst	1
1289	worthless	1
1290	worthwhile	1
1291	worthy	1
1292	wrathful	1
1293	wretched	1
1294	writhing	1
1295	wrong	1
1296	wry	1
1297	yawning	1
1298	yearly	1
1299	yellow	1
1300	yellowish	1
1301	young	1
1302	youthful	1
1303	yummy	1
1304	zany	1
1305	zealous	1
1306	zesty	1
1307	zigzag	1
1308	account	2
1309	achiever	2
1310	acoustics	2
1311	act	2
1312	action	2
1313	activity	2
1314	actor	2
1315	addition	2
1316	adjustment	2
1317	advertisement	2
1318	advice	2
1319	aftermath	2
1320	afternoon	2
1321	afterthought	2
1322	agreement	2
1323	air	2
1324	airplane	2
1325	airport	2
1326	alarm	2
1327	alley	2
1328	amount	2
1329	amusement	2
1330	anger	2
1331	angle	2
1332	animal	2
1333	answer	2
1334	ant	2
1335	ants	2
1336	apparatus	2
1337	apparel	2
1338	apple	2
1339	apples	2
1340	appliance	2
1341	approval	2
1342	arch	2
1343	argument	2
1344	arithmetic	2
1345	arm	2
1346	army	2
1347	art	2
1348	attack	2
1349	attempt	2
1350	attention	2
1351	attraction	2
1352	aunt	2
1353	authority	2
1354	babies	2
1355	baby	2
1356	back	2
1357	badge	2
1358	bag	2
1359	bait	2
1360	balance	2
1361	ball	2
1362	balloon	2
1363	balls	2
1364	banana	2
1365	band	2
1366	base	2
1367	baseball	2
1368	basin	2
1369	basket	2
1370	basketball	2
1371	bat	2
1372	bath	2
1373	battle	2
1374	bead	2
1375	beam	2
1376	bean	2
1377	bear	2
1378	bears	2
1379	beast	2
1380	bed	2
1381	bedroom	2
1382	beds	2
1383	bee	2
1384	beef	2
1385	beetle	2
1386	beggar	2
1387	beginner	2
1388	behavior	2
1389	belief	2
1390	believe	2
1391	bell	2
1392	bells	2
1393	berry	2
1394	bike	2
1395	bikes	2
1396	bird	2
1397	birds	2
1398	birth	2
1399	birthday	2
1400	bit	2
1401	bite	2
1402	blade	2
1403	blood	2
1404	blow	2
1405	board	2
1406	boat	2
1407	boats	2
1408	body	2
1409	bomb	2
1410	bone	2
1411	book	2
1412	books	2
1413	boot	2
1414	border	2
1415	bottle	2
1416	boundary	2
1417	box	2
1418	boy	2
1419	boys	2
1420	brain	2
1421	brake	2
1422	branch	2
1423	brass	2
1424	bread	2
1425	breakfast	2
1426	breath	2
1427	brick	2
1428	bridge	2
1429	brother	2
1430	brothers	2
1431	brush	2
1432	bubble	2
1433	bucket	2
1434	building	2
1435	bulb	2
1436	bun	2
1437	burn	2
1438	burst	2
1439	bushes	2
1440	business	2
1441	butter	2
1442	button	2
1443	cabbage	2
1444	cable	2
1445	cactus	2
1446	cake	2
1447	cakes	2
1448	calculator	2
1449	calendar	2
1450	camera	2
1451	camp	2
1452	can	2
1453	cannon	2
1454	canvas	2
1455	cap	2
1456	caption	2
1457	car	2
1458	card	2
1459	care	2
1460	carpenter	2
1461	carriage	2
1462	cars	2
1463	cart	2
1464	cast	2
1465	cat	2
1466	cats	2
1467	cattle	2
1468	cause	2
1469	cave	2
1470	celery	2
1471	cellar	2
1472	cemetery	2
1473	cent	2
1474	chain	2
1475	chair	2
1476	chairs	2
1477	chalk	2
1478	chance	2
1479	change	2
1480	channel	2
1481	cheese	2
1482	cherries	2
1483	cherry	2
1484	chess	2
1485	chicken	2
1486	chickens	2
1487	children	2
1488	chin	2
1489	church	2
1490	circle	2
1491	clam	2
1492	class	2
1493	clock	2
1494	clocks	2
1495	cloth	2
1496	cloud	2
1497	clouds	2
1498	clover	2
1499	club	2
1500	coach	2
1501	coal	2
1502	coast	2
1503	coat	2
1504	cobweb	2
1505	coil	2
1506	collar	2
1507	color	2
1508	comb	2
1509	comfort	2
1510	committee	2
1511	company	2
1512	comparison	2
1513	competition	2
1514	condition	2
1515	connection	2
1516	control	2
1517	cook	2
1518	copper	2
1519	copy	2
1520	cord	2
1521	cork	2
1522	corn	2
1523	cough	2
1524	country	2
1525	cover	2
1526	cow	2
1527	cows	2
1528	crack	2
1529	cracker	2
1530	crate	2
1531	crayon	2
1532	cream	2
1533	creator	2
1534	creature	2
1535	credit	2
1536	crib	2
1537	crime	2
1538	crook	2
1539	crow	2
1540	crowd	2
1541	crown	2
1542	crush	2
1543	cry	2
1544	cub	2
1545	cup	2
1546	current	2
1547	curtain	2
1548	curve	2
1549	cushion	2
1550	dad	2
1551	daughter	2
1552	day	2
1553	death	2
1554	debt	2
1555	decision	2
1556	deer	2
1557	degree	2
1558	design	2
1559	desire	2
1560	desk	2
1561	destruction	2
1562	detail	2
1563	development	2
1564	digestion	2
1565	dime	2
1566	dinner	2
1567	dinosaurs	2
1568	direction	2
1569	dirt	2
1570	discovery	2
1571	discussion	2
1572	disease	2
1573	disgust	2
1574	distance	2
1575	distribution	2
1576	division	2
1577	dock	2
1578	doctor	2
1579	dog	2
1580	dogs	2
1581	doll	2
1582	dolls	2
1583	donkey	2
1584	door	2
1585	downtown	2
1586	drain	2
1587	drawer	2
1588	dress	2
1589	drink	2
1590	driving	2
1591	drop	2
1592	drug	2
1593	drum	2
1594	duck	2
1595	ducks	2
1596	dust	2
1597	ear	2
1598	earth	2
1599	earthquake	2
1600	edge	2
1601	education	2
1602	effect	2
1603	egg	2
1604	eggnog	2
1605	eggs	2
1606	elbow	2
1607	end	2
1608	engine	2
1609	error	2
1610	event	2
1611	example	2
1612	exchange	2
1613	existence	2
1614	expansion	2
1615	experience	2
1616	expert	2
1617	eye	2
1618	eyes	2
1619	face	2
1620	fact	2
1621	fairies	2
1622	fall	2
1623	family	2
1624	fan	2
1625	fang	2
1626	farm	2
1627	farmer	2
1628	father	2
1629	faucet	2
1630	fear	2
1631	feast	2
1632	feather	2
1633	feeling	2
1634	feet	2
1635	fiction	2
1636	field	2
1637	fifth	2
1638	fight	2
1639	finger	2
1640	fire	2
1641	fireman	2
1642	fish	2
1643	flag	2
1644	flame	2
1645	flavor	2
1646	flesh	2
1647	flight	2
1648	flock	2
1649	floor	2
1650	flower	2
1651	flowers	2
1652	fly	2
1653	fog	2
1654	fold	2
1655	food	2
1656	foot	2
1657	force	2
1658	fork	2
1659	form	2
1660	fowl	2
1661	frame	2
1662	friction	2
1663	friend	2
1664	friends	2
1665	frog	2
1666	frogs	2
1667	front	2
1668	fruit	2
1669	fuel	2
1670	furniture	2
1671	game	2
1672	garden	2
1673	gate	2
1674	geese	2
1675	ghost	2
1676	giants	2
1677	giraffe	2
1678	girl	2
1679	girls	2
1680	glass	2
1681	glove	2
1682	glue	2
1683	goat	2
1684	gold	2
1685	goldfish	2
1686	goose	2
1687	government	2
1688	governor	2
1689	grade	2
1690	grain	2
1691	grandfather	2
1692	grandmother	2
1693	grape	2
1694	grass	2
1695	grip	2
1696	ground	2
1697	group	2
1698	growth	2
1699	guide	2
1700	guitar	2
1701	gun	2
1702	hair	2
1703	haircut	2
1704	hall	2
1705	hammer	2
1706	hand	2
1707	hands	2
1708	harbor	2
1709	harmony	2
1710	hat	2
1711	hate	2
1712	head	2
1713	health	2
1714	hearing	2
1715	heart	2
1716	heat	2
1717	help	2
1718	hen	2
1719	hill	2
1720	history	2
1721	hobbies	2
1722	hole	2
1723	holiday	2
1724	home	2
1725	honey	2
1726	hook	2
1727	hope	2
1728	horn	2
1729	horse	2
1730	horses	2
1731	hose	2
1732	hospital	2
1733	hot	2
1734	hour	2
1735	house	2
1736	houses	2
1737	humor	2
1738	hydrant	2
1739	ice	2
1740	icicle	2
1741	idea	2
1742	impulse	2
1743	income	2
1744	increase	2
1745	industry	2
1746	ink	2
1747	insect	2
1748	instrument	2
1749	insurance	2
1750	interest	2
1751	invention	2
1752	iron	2
1753	island	2
1754	jail	2
1755	jam	2
1756	jar	2
1757	jeans	2
1758	jelly	2
1759	jellyfish	2
1760	jewel	2
1761	join	2
1762	joke	2
1763	journey	2
1764	judge	2
1765	juice	2
1766	jump	2
1767	kettle	2
1768	key	2
1769	kick	2
1770	kiss	2
1771	kite	2
1772	kitten	2
1773	kittens	2
1774	kitty	2
1775	knee	2
1776	knife	2
1777	knot	2
1778	knowledge	2
1779	laborer	2
1780	lace	2
1781	ladybug	2
1782	lake	2
1783	lamp	2
1784	land	2
1785	language	2
1786	laugh	2
1787	lawyer	2
1788	lead	2
1789	leaf	2
1790	learning	2
1791	leather	2
1792	leg	2
1793	legs	2
1794	letter	2
1795	letters	2
1796	lettuce	2
1797	level	2
1798	library	2
1799	lift	2
1800	light	2
1801	limit	2
1802	line	2
1803	linen	2
1804	lip	2
1805	liquid	2
1806	list	2
1807	lizards	2
1808	loaf	2
1809	lock	2
1810	locket	2
1811	look	2
1812	loss	2
1813	love	2
1814	low	2
1815	lumber	2
1816	lunch	2
1817	lunchroom	2
1818	machine	2
1819	magic	2
1820	maid	2
1821	mailbox	2
1822	man	2
1823	manager	2
1824	map	2
1825	marble	2
1826	mark	2
1827	market	2
1828	mask	2
1829	mass	2
1830	match	2
1831	meal	2
1832	measure	2
1833	meat	2
1834	meeting	2
1835	memory	2
1836	men	2
1837	metal	2
1838	mice	2
1839	middle	2
1840	milk	2
1841	mind	2
1842	mine	2
1843	minister	2
1844	mint	2
1845	minute	2
1846	mist	2
1847	mitten	2
1848	mom	2
1849	money	2
1850	monkey	2
1851	month	2
1852	moon	2
1853	morning	2
1854	mother	2
1855	motion	2
1856	mountain	2
1857	mouth	2
1858	move	2
1859	muscle	2
1860	music	2
1861	nail	2
1862	name	2
1863	nation	2
1864	neck	2
1865	need	2
1866	needle	2
1867	nerve	2
1868	nest	2
1869	net	2
1870	news	2
1871	night	2
1872	noise	2
1873	north	2
1874	nose	2
1875	note	2
1876	notebook	2
1877	number	2
1878	nut	2
1879	oatmeal	2
1880	observation	2
1881	ocean	2
1882	offer	2
1883	office	2
1884	oil	2
1885	operation	2
1886	opinion	2
1887	orange	2
1888	oranges	2
1889	order	2
1890	organization	2
1891	ornament	2
1892	oven	2
1893	owl	2
1894	owner	2
1895	page	2
1896	pail	2
1897	pain	2
1898	paint	2
1899	pan	2
1900	pancake	2
1901	paper	2
1902	parcel	2
1903	parent	2
1904	park	2
1905	part	2
1906	partner	2
1907	party	2
1908	passenger	2
1909	paste	2
1910	patch	2
1911	payment	2
1912	peace	2
1913	pear	2
1914	pen	2
1915	pencil	2
1916	person	2
1917	pest	2
1918	pet	2
1919	pets	2
1920	pickle	2
1921	picture	2
1922	pie	2
1923	pies	2
1924	pig	2
1925	pigs	2
1926	pin	2
1927	pipe	2
1928	pizzas	2
1929	place	2
1930	plane	2
1931	planes	2
1932	plant	2
1933	plantation	2
1934	plants	2
1935	plastic	2
1936	plate	2
1937	play	2
1938	playground	2
1939	pleasure	2
1940	plot	2
1941	plough	2
1942	pocket	2
1943	point	2
1944	poison	2
1945	police	2
1946	polish	2
1947	pollution	2
1948	popcorn	2
1949	porter	2
1950	position	2
1951	pot	2
1952	potato	2
1953	powder	2
1954	power	2
1955	price	2
1956	print	2
1957	prison	2
1958	process	2
1959	produce	2
1960	profit	2
1961	property	2
1962	prose	2
1963	protest	2
1964	pull	2
1965	pump	2
1966	punishment	2
1967	purpose	2
1968	push	2
1969	quarter	2
1970	quartz	2
1971	queen	2
1972	question	2
1973	quicksand	2
1974	quiet	2
1975	quill	2
1976	quilt	2
1977	quince	2
1978	quiver	2
1979	rabbit	2
1980	rabbits	2
1981	rail	2
1982	railway	2
1983	rain	2
1984	rainstorm	2
1985	rake	2
1986	range	2
1987	rat	2
1988	rate	2
1989	ray	2
1990	reaction	2
1991	reading	2
1992	reason	2
1993	receipt	2
1994	recess	2
1995	record	2
1996	regret	2
1997	relation	2
1998	religion	2
1999	representative	2
2000	request	2
2001	respect	2
2002	rest	2
2003	reward	2
2004	rhythm	2
2005	rice	2
2006	riddle	2
2007	rifle	2
2008	ring	2
2009	rings	2
2010	river	2
2011	road	2
2012	robin	2
2013	rock	2
2014	rod	2
2015	roll	2
2016	roof	2
2017	room	2
2018	root	2
2019	rose	2
2020	route	2
2021	rub	2
2022	rule	2
2023	run	2
2024	sack	2
2025	sail	2
2026	salt	2
2027	sand	2
2028	scale	2
2029	scarecrow	2
2030	scarf	2
2031	scene	2
2032	scent	2
2033	school	2
2034	science	2
2035	scissors	2
2036	screw	2
2037	sea	2
2038	seashore	2
2039	seat	2
2040	secretary	2
2041	seed	2
2042	selection	2
2043	self	2
2044	sense	2
2045	servant	2
2046	shade	2
2047	shake	2
2048	shame	2
2049	shape	2
2050	sheep	2
2051	sheet	2
2052	shelf	2
2053	ship	2
2054	shirt	2
2055	shock	2
2056	shoe	2
2057	shoes	2
2058	shop	2
2059	show	2
2060	side	2
2061	sidewalk	2
2062	sign	2
2063	silk	2
2064	silver	2
2065	sink	2
2066	sister	2
2067	sisters	2
2068	size	2
2069	skate	2
2070	skin	2
2071	skirt	2
2072	sky	2
2073	slave	2
2074	sleep	2
2075	sleet	2
2076	slip	2
2077	slope	2
2078	smash	2
2079	smell	2
2080	smile	2
2081	smoke	2
2082	snail	2
2083	snails	2
2084	snake	2
2085	snakes	2
2086	sneeze	2
2087	snow	2
2088	soap	2
2089	society	2
2090	sock	2
2091	soda	2
2092	sofa	2
2093	son	2
2094	song	2
2095	songs	2
2096	sort	2
2097	sound	2
2098	soup	2
2099	space	2
2100	spade	2
2101	spark	2
2102	spiders	2
2103	sponge	2
2104	spoon	2
2105	spot	2
2106	spring	2
2107	spy	2
2108	square	2
2109	squirrel	2
2110	stage	2
2111	stamp	2
2112	star	2
2113	start	2
2114	statement	2
2115	station	2
2116	steam	2
2117	steel	2
2118	stem	2
2119	step	2
2120	stew	2
2121	stick	2
2122	sticks	2
2123	stitch	2
2124	stocking	2
2125	stomach	2
2126	stone	2
2127	stop	2
2128	store	2
2129	story	2
2130	stove	2
2131	stranger	2
2132	straw	2
2133	stream	2
2134	street	2
2135	stretch	2
2136	string	2
2137	structure	2
2138	substance	2
2139	sugar	2
2140	suggestion	2
2141	suit	2
2142	summer	2
2143	sun	2
2144	support	2
2145	surprise	2
2146	sweater	2
2147	swim	2
2148	swing	2
2149	system	2
2150	table	2
2151	tail	2
2152	talk	2
2153	tank	2
2154	taste	2
2155	tax	2
2156	teaching	2
2157	team	2
2158	teeth	2
2159	temper	2
2160	tendency	2
2161	tent	2
2162	territory	2
2163	test	2
2164	texture	2
2165	theory	2
2166	thing	2
2167	things	2
2168	thought	2
2169	thread	2
2170	thrill	2
2171	throat	2
2172	throne	2
2173	thumb	2
2174	thunder	2
2175	ticket	2
2176	tiger	2
2177	time	2
2178	tin	2
2179	title	2
2180	toad	2
2181	toe	2
2182	toes	2
2183	tomatoes	2
2184	tongue	2
2185	tooth	2
2186	toothbrush	2
2187	toothpaste	2
2188	top	2
2189	touch	2
2190	town	2
2191	toy	2
2192	toys	2
2193	trade	2
2194	trail	2
2195	train	2
2196	trains	2
2197	tramp	2
2198	transport	2
2199	tray	2
2200	treatment	2
2201	tree	2
2202	trees	2
2203	trick	2
2204	trip	2
2205	trouble	2
2206	trousers	2
2207	truck	2
2208	trucks	2
2209	tub	2
2210	turkey	2
2211	turn	2
2212	twig	2
2213	twist	2
2214	umbrella	2
2215	uncle	2
2216	underwear	2
2217	unit	2
2218	use	2
2219	vacation	2
2220	value	2
2221	van	2
2222	vase	2
2223	vegetable	2
2224	veil	2
2225	vein	2
2226	verse	2
2227	vessel	2
2228	vest	2
2229	view	2
2230	visitor	2
2231	voice	2
2232	volcano	2
2233	volleyball	2
2234	voyage	2
2235	walk	2
2236	wall	2
2237	war	2
2238	wash	2
2239	waste	2
2240	watch	2
2241	water	2
2242	wave	2
2243	waves	2
2244	wax	2
2245	way	2
2246	wealth	2
2247	weather	2
2248	week	2
2249	weight	2
2250	wheel	2
2251	whip	2
2252	whistle	2
2253	wilderness	2
2254	wind	2
2255	window	2
2256	wine	2
2257	wing	2
2258	winter	2
2259	wire	2
2260	wish	2
2261	woman	2
2262	women	2
2263	wood	2
2264	wool	2
2265	word	2
2266	work	2
2267	worm	2
2268	wound	2
2269	wren	2
2270	wrench	2
2271	wrist	2
2272	writer	2
2273	writing	2
2274	yak	2
2275	yam	2
2276	yard	2
2277	yarn	2
2278	year	2
2279	yoke	2
2280	zebra	2
2281	zephyr	2
2282	zinc	2
2283	zipper	2
2284	zoo	2
\.


--
-- Name: maasserver_candidatename_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_candidatename_id_seq', 2284, true);


--
-- Data for Name: maasserver_componenterror; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_componenterror (id, component, error, created, updated) FROM stdin;
\.


--
-- Name: maasserver_componenterror_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_componenterror_id_seq', 1, false);


--
-- Data for Name: maasserver_config; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_config (id, name, value) FROM stdin;
\.


--
-- Name: maasserver_config_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_config_id_seq', 1, false);


--
-- Data for Name: maasserver_dhcplease; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_dhcplease (id, nodegroup_id, ip, mac) FROM stdin;
\.


--
-- Name: maasserver_dhcplease_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_dhcplease_id_seq', 1, false);


--
-- Data for Name: maasserver_downloadprogress; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_downloadprogress (id, created, updated, nodegroup_id, filename, size, bytes_downloaded, error) FROM stdin;
\.


--
-- Name: maasserver_downloadprogress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_downloadprogress_id_seq', 1, false);


--
-- Data for Name: maasserver_event; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_event (id, created, updated, type_id, node_id, description) FROM stdin;
\.


--
-- Name: maasserver_event_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_event_id_seq', 1, false);


--
-- Data for Name: maasserver_eventtype; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_eventtype (id, created, updated, name, level, description) FROM stdin;
\.


--
-- Name: maasserver_eventtype_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_eventtype_id_seq', 1, false);


--
-- Data for Name: maasserver_filestorage; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_filestorage (id, filename, content, owner_id, key) FROM stdin;
\.


--
-- Name: maasserver_filestorage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_filestorage_id_seq', 1, false);


--
-- Data for Name: maasserver_filesystem; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_filesystem (id, created, updated, uuid, fstype, partition_id, block_device_id, create_params, mount_point, mount_params, filesystem_group_id) FROM stdin;
\.


--
-- Name: maasserver_filesystem_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_filesystem_id_seq', 1, false);


--
-- Data for Name: maasserver_filesystemgroup; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_filesystemgroup (id, created, updated, uuid, group_type, name, create_params) FROM stdin;
\.


--
-- Name: maasserver_filesystemgroup_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_filesystemgroup_id_seq', 1, false);


--
-- Data for Name: maasserver_largefile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_largefile (id, created, updated, sha256, total_size, content) FROM stdin;
\.


--
-- Name: maasserver_largefile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_largefile_id_seq', 1, false);


--
-- Data for Name: maasserver_licensekey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_licensekey (id, created, updated, osystem, distro_series, license_key) FROM stdin;
\.


--
-- Name: maasserver_licensekey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_licensekey_id_seq', 1, false);


--
-- Data for Name: maasserver_macaddress; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_macaddress (id, created, updated, mac_address, node_id, cluster_interface_id) FROM stdin;
\.


--
-- Name: maasserver_macaddress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_macaddress_id_seq', 1, false);


--
-- Data for Name: maasserver_macaddress_networks; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_macaddress_networks (id, macaddress_id, network_id) FROM stdin;
\.


--
-- Name: maasserver_macaddress_networks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_macaddress_networks_id_seq', 1, false);


--
-- Data for Name: maasserver_macstaticipaddresslink; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_macstaticipaddresslink (id, created, updated, mac_address_id, ip_address_id, nic_alias) FROM stdin;
\.


--
-- Name: maasserver_macstaticipaddresslink_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_macstaticipaddresslink_id_seq', 1, false);


--
-- Data for Name: maasserver_network; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_network (id, name, ip, netmask, vlan_tag, description, default_gateway, dns_servers) FROM stdin;
\.


--
-- Name: maasserver_network_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_network_id_seq', 1, false);


--
-- Data for Name: maasserver_node; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_node (id, created, updated, system_id, hostname, status, owner_id, architecture, power_type, token_id, error, power_parameters, netboot, nodegroup_id, distro_series, cpu_count, memory, routers, agent_name, zone_id, osystem, license_key, boot_type, error_description, power_state, disable_ipv4, pxe_mac_id, installable, parent_id, swap_size) FROM stdin;
\.


--
-- Name: maasserver_node_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_node_id_seq', 1, false);


--
-- Data for Name: maasserver_node_tags; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_node_tags (id, node_id, tag_id) FROM stdin;
\.


--
-- Name: maasserver_node_tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_node_tags_id_seq', 1, false);


--
-- Data for Name: maasserver_nodegroup; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_nodegroup (id, created, updated, name, api_token_id, api_key, dhcp_key, uuid, status, cluster_name, maas_url, default_disable_ipv4) FROM stdin;
\.


--
-- Name: maasserver_nodegroup_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_nodegroup_id_seq', 1, false);


--
-- Data for Name: maasserver_nodegroupinterface; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_nodegroupinterface (id, created, updated, ip, nodegroup_id, management, interface, subnet_mask, broadcast_ip, router_ip, ip_range_low, ip_range_high, foreign_dhcp_ip, static_ip_range_low, static_ip_range_high, name) FROM stdin;
\.


--
-- Name: maasserver_nodegroupinterface_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_nodegroupinterface_id_seq', 1, false);


--
-- Data for Name: maasserver_partition; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_partition (id, created, updated, partition_table_id, uuid, start_offset, size, bootable) FROM stdin;
\.


--
-- Name: maasserver_partition_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_partition_id_seq', 1, false);


--
-- Data for Name: maasserver_partitiontable; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_partitiontable (id, created, updated, table_type, block_device_id) FROM stdin;
\.


--
-- Name: maasserver_partitiontable_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_partitiontable_id_seq', 1, false);


--
-- Data for Name: maasserver_physicalblockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_physicalblockdevice (blockdevice_ptr_id, model, serial) FROM stdin;
\.


--
-- Data for Name: maasserver_sshkey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_sshkey (id, created, updated, user_id, key) FROM stdin;
\.


--
-- Name: maasserver_sshkey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_sshkey_id_seq', 1, false);


--
-- Data for Name: maasserver_sslkey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_sslkey (id, created, updated, user_id, key) FROM stdin;
\.


--
-- Name: maasserver_sslkey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_sslkey_id_seq', 1, false);


--
-- Data for Name: maasserver_staticipaddress; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_staticipaddress (id, created, updated, ip, alloc_type, user_id) FROM stdin;
\.


--
-- Name: maasserver_staticipaddress_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_staticipaddress_id_seq', 1, false);


--
-- Data for Name: maasserver_tag; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_tag (id, created, updated, name, definition, comment, kernel_opts) FROM stdin;
\.


--
-- Name: maasserver_tag_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_tag_id_seq', 1, false);


--
-- Data for Name: maasserver_userprofile; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_userprofile (id, user_id) FROM stdin;
\.


--
-- Name: maasserver_userprofile_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_userprofile_id_seq', 1, false);


--
-- Data for Name: maasserver_virtualblockdevice; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_virtualblockdevice (blockdevice_ptr_id, uuid, filesystem_group_id) FROM stdin;
\.


--
-- Data for Name: maasserver_zone; Type: TABLE DATA; Schema: public; Owner: -
--

COPY maasserver_zone (id, created, updated, name, description) FROM stdin;
1	2015-03-24 11:52:26.456633+00	2015-03-24 11:52:26.456633+00	default	
\.


--
-- Name: maasserver_zone_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_zone_id_seq', 1, true);


--
-- Name: maasserver_zone_serial_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('maasserver_zone_serial_seq', 1, false);


--
-- Data for Name: metadataserver_commissioningscript; Type: TABLE DATA; Schema: public; Owner: -
--

COPY metadataserver_commissioningscript (id, name, content) FROM stdin;
\.


--
-- Name: metadataserver_commissioningscript_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('metadataserver_commissioningscript_id_seq', 1, false);


--
-- Data for Name: metadataserver_nodekey; Type: TABLE DATA; Schema: public; Owner: -
--

COPY metadataserver_nodekey (id, node_id, token_id, key) FROM stdin;
\.


--
-- Name: metadataserver_nodekey_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('metadataserver_nodekey_id_seq', 1, false);


--
-- Data for Name: metadataserver_noderesult; Type: TABLE DATA; Schema: public; Owner: -
--

COPY metadataserver_noderesult (id, node_id, name, created, updated, script_result, data, result_type) FROM stdin;
\.


--
-- Name: metadataserver_noderesult_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('metadataserver_noderesult_id_seq', 1, false);


--
-- Data for Name: metadataserver_nodeuserdata; Type: TABLE DATA; Schema: public; Owner: -
--

COPY metadataserver_nodeuserdata (id, node_id, data) FROM stdin;
\.


--
-- Name: metadataserver_nodeuserdata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('metadataserver_nodeuserdata_id_seq', 1, false);


--
-- Data for Name: piston_consumer; Type: TABLE DATA; Schema: public; Owner: -
--

COPY piston_consumer (id, name, description, key, secret, status, user_id) FROM stdin;
\.


--
-- Name: piston_consumer_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('piston_consumer_id_seq', 1, false);


--
-- Data for Name: piston_nonce; Type: TABLE DATA; Schema: public; Owner: -
--

COPY piston_nonce (id, token_key, consumer_key, key) FROM stdin;
\.


--
-- Name: piston_nonce_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('piston_nonce_id_seq', 1, false);


--
-- Data for Name: piston_token; Type: TABLE DATA; Schema: public; Owner: -
--

COPY piston_token (id, key, secret, verifier, token_type, "timestamp", is_approved, user_id, consumer_id, callback, callback_confirmed) FROM stdin;
\.


--
-- Name: piston_token_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('piston_token_id_seq', 1, false);


--
-- Data for Name: south_migrationhistory; Type: TABLE DATA; Schema: public; Owner: -
--

COPY south_migrationhistory (id, app_name, migration, applied) FROM stdin;
1	maasserver	0001_initial	2015-03-24 11:52:24.014909+00
2	maasserver	0002_add_token_to_node	2015-03-24 11:52:24.034237+00
3	maasserver	0002_macaddress_unique	2015-03-24 11:52:24.050639+00
4	maasserver	0003_rename_sshkeys	2015-03-24 11:52:24.071714+00
5	maasserver	0004_add_node_error	2015-03-24 11:52:24.093358+00
6	maasserver	0005_sshkey_user_and_key_unique_together	2015-03-24 11:52:24.110504+00
7	maasserver	0006_increase_filestorage_filename_length	2015-03-24 11:52:24.148311+00
8	maasserver	0007_common_info_created_add_time	2015-03-24 11:52:24.213237+00
9	maasserver	0008_node_power_address	2015-03-24 11:52:24.236234+00
10	maasserver	0009_add_nodegroup	2015-03-24 11:52:24.267047+00
11	maasserver	0010_add_node_netboot	2015-03-24 11:52:24.291639+00
12	maasserver	0011_add_dns_zone_serial_sequence	2015-03-24 11:52:24.312526+00
13	maasserver	0012_DHCPLease	2015-03-24 11:52:24.337498+00
14	maasserver	0013_connect_node_node_group	2015-03-24 11:52:24.359625+00
15	maasserver	0014_nodegroup_dhcp_settings_are_optional	2015-03-24 11:52:24.441187+00
16	maasserver	0016_node_nodegroup_not_null	2015-03-24 11:52:24.474897+00
17	maasserver	0017_add_dhcp_key_to_nodegroup	2015-03-24 11:52:24.499985+00
18	maasserver	0018_activate_worker_user	2015-03-24 11:52:24.592191+00
19	maasserver	0019_add_nodegroup_dhcp_interface	2015-03-24 11:52:24.614667+00
20	maasserver	0020_nodegroup_dhcp_interfaces_is_plural	2015-03-24 11:52:24.642409+00
21	maasserver	0021_add_uuid_to_nodegroup	2015-03-24 11:52:24.674991+00
22	maasserver	0022_add_status_to_nodegroup	2015-03-24 11:52:24.705221+00
23	maasserver	0023_add_bootimage_model	2015-03-24 11:52:24.729718+00
24	maasserver	0024_add_nodegroupinterface	2015-03-24 11:52:24.766035+00
25	maasserver	0025_remove_unused_fields_in_nodegroup	2015-03-24 11:52:24.794009+00
26	maasserver	0026_add_node_distro_series	2015-03-24 11:52:24.824418+00
27	maasserver	0027_add_tag_table	2015-03-24 11:52:24.862192+00
28	maasserver	0028_add_node_hardware_details	2015-03-24 11:52:24.897179+00
29	maasserver	0029_zone_sharing	2015-03-24 11:52:24.931357+00
30	maasserver	0030_ip_address_to_generic_ip_address	2015-03-24 11:52:25.033985+00
31	maasserver	0031_node_architecture_field_size	2015-03-24 11:52:25.082065+00
32	maasserver	0032_node_subarch	2015-03-24 11:52:25.109089+00
33	maasserver	0033_component_error	2015-03-24 11:52:25.1433+00
34	maasserver	0034_timestamp_component_error	2015-03-24 11:52:25.175392+00
35	maasserver	0035_add_nodegroup_cluster_name	2015-03-24 11:52:25.216169+00
36	maasserver	0036_populate_nodegroup_cluster_name	2015-03-24 11:52:25.245011+00
37	maasserver	0037_nodegroup_cluster_name_unique	2015-03-24 11:52:25.274144+00
38	maasserver	0038_nodegroupinterface_ip_range_fix	2015-03-24 11:52:25.317605+00
39	maasserver	0039_add_filestorage_content	2015-03-24 11:52:25.36166+00
40	maasserver	0039_add_nodegroup_to_bootimage	2015-03-24 11:52:25.39814+00
41	maasserver	0040_make_filestorage_data_not_null	2015-03-24 11:52:25.440356+00
42	maasserver	0041_remove_filestorage_data	2015-03-24 11:52:25.4688+00
43	maasserver	0042_fix_039_conflict	2015-03-24 11:52:25.499189+00
44	maasserver	0043_unique_hostname_preparation	2015-03-24 11:52:25.529011+00
45	maasserver	0044_node_hostname_unique	2015-03-24 11:52:25.558334+00
46	maasserver	0045_add_tag_kernel_opts	2015-03-24 11:52:25.589734+00
47	maasserver	0046_add_nodegroup_maas_url	2015-03-24 11:52:25.622832+00
48	maasserver	0047_add_owner_to_filestorage	2015-03-24 11:52:25.664065+00
49	maasserver	0048_add_key_to_filestorage	2015-03-24 11:52:25.803293+00
50	maasserver	0049_filestorage_key_unique	2015-03-24 11:52:25.838545+00
51	maasserver	0050_shared_to_per_tenant_storage	2015-03-24 11:52:25.888705+00
52	maasserver	0051_bigger_distro_series_name	2015-03-24 11:52:25.932506+00
53	maasserver	0052_add_node_storage	2015-03-24 11:52:25.975228+00
54	maasserver	0053_node_routers	2015-03-24 11:52:26.015291+00
55	maasserver	0054_download_progress	2015-03-24 11:52:26.053688+00
56	maasserver	0055_nullable_bytes_downloaded	2015-03-24 11:52:26.099722+00
57	maasserver	0056_netboot_off_for_allocated_nodes	2015-03-24 11:52:26.134647+00
58	maasserver	0057_remove_hardware_details	2015-03-24 11:52:26.176079+00
59	maasserver	0058_add_agent_name_to_node	2015-03-24 11:52:26.241309+00
60	maasserver	0059_dhcp_detection_model	2015-03-24 11:52:26.293003+00
61	maasserver	0060_add_zone_object	2015-03-24 11:52:26.339369+00
62	maasserver	0061_add_ref_from_node_to_zone	2015-03-24 11:52:26.378743+00
63	maasserver	0062_add_vlan_model	2015-03-24 11:52:26.419908+00
64	maasserver	0063_create_default_zone	2015-03-24 11:52:26.459373+00
65	maasserver	0064_set_default_zone	2015-03-24 11:52:26.502467+00
66	maasserver	0065_set_default_zone_as_model_default	2015-03-24 11:52:26.557128+00
67	maasserver	0066_rename_vlan_add_link_node_network	2015-03-24 11:52:26.608007+00
68	maasserver	0067_default_commissioning_trusty	2015-03-24 11:52:26.651116+00
69	maasserver	0068_network_description_textfield	2015-03-24 11:52:26.705372+00
70	maasserver	0069_add_mac_network_relation	2015-03-24 11:52:26.756028+00
71	maasserver	0070_drop_network_node_relation	2015-03-24 11:52:26.797933+00
72	maasserver	0071_drop_after_commissioning_action	2015-03-24 11:52:26.839979+00
73	maasserver	0072_remove_ipmi_autodetect	2015-03-24 11:52:26.878631+00
74	maasserver	0073_add_label_to_bootimage	2015-03-24 11:52:27.061949+00
75	maasserver	0074_boot_images_timestamp	2015-03-24 11:52:27.109844+00
76	maasserver	0075_add_boot_resource_models	2015-03-24 11:52:27.171786+00
77	maasserver	0076_add_osystem_to_bootimage	2015-03-24 11:52:27.235866+00
78	maasserver	0077_remove_null_for_bootsourceselection_release	2015-03-24 11:52:27.302059+00
79	maasserver	0078_add_osystem_to_node	2015-03-24 11:52:27.369142+00
80	maasserver	0079_supported_subarches_for_bootimage	2015-03-24 11:52:27.424918+00
81	maasserver	0080_binary_to_editablebinary_in_bootsource	2015-03-24 11:52:27.493803+00
82	maasserver	0081_ipaddress_table_and_static_dhcp_ranges	2015-03-24 11:52:27.557704+00
83	maasserver	0082_cluster_interface_for_macaddress	2015-03-24 11:52:27.610517+00
84	maasserver	0083_add_license_key_to_node	2015-03-24 11:52:27.669034+00
85	maasserver	0084_add_ssl_key_model	2015-03-24 11:52:27.732198+00
86	maasserver	0085_add_user_to_staticipaddress	2015-03-24 11:52:27.789481+00
87	maasserver	0086_add_xinstall_path_and_type_to_bootimage	2015-03-24 11:52:27.848385+00
88	maasserver	0087_add_licensekey_model	2015-03-24 11:52:27.912495+00
89	maasserver	0088_ip_to_custom_field	2015-03-24 11:52:28.141405+00
90	maasserver	0088_z_backport_trunk_0099	2015-03-24 11:52:28.196246+00
91	maasserver	0089_create_nodegroupinterface_name	2015-03-24 11:52:28.255669+00
92	maasserver	0090_initialise_nodegroupinterface_name	2015-03-24 11:52:28.320546+00
93	maasserver	0091_add_boot_type_to_node	2015-03-24 11:52:28.37928+00
94	maasserver	0092_populate_node_boot_type	2015-03-24 11:52:28.453062+00
95	maasserver	0093_add_eventtype_and_event	2015-03-24 11:52:28.536046+00
96	maasserver	0094_add_error_description	2015-03-24 11:52:28.761675+00
97	maasserver	0095_add_event_description	2015-03-24 11:52:28.8269+00
98	maasserver	0096_add_power_state_to_node	2015-03-24 11:52:28.90724+00
99	maasserver	0097_add_largefile_model	2015-03-24 11:52:28.985698+00
100	maasserver	0098_add_bootresource_models	2015-03-24 11:52:29.070725+00
101	maasserver	0099_convert_cluster_interfaces_to_networks	2015-03-24 11:52:29.148445+00
102	maasserver	0100_remove_cluster_from_bootsrouce	2015-03-24 11:52:29.221901+00
103	maasserver	0100_remove_duplicate_bootsource_urls	2015-03-24 11:52:29.297165+00
104	maasserver	0101_make_bootsource_url_unique	2015-03-24 11:52:29.371626+00
105	maasserver	0102_candidate_name	2015-03-24 11:52:29.451341+00
106	maasserver	0103_candidate_names	2015-03-24 11:52:29.59619+00
107	maasserver	0104_add_node_disable_ipv4	2015-03-24 11:52:29.670197+00
108	maasserver	0105_remove_rtype_from_uniqueness_on_boot_resource	2015-03-24 11:52:29.756014+00
109	maasserver	0106_add_os_to_boot_source_selection	2015-03-24 11:52:29.838857+00
110	maasserver	0107_add_default_gateway_to_network	2015-03-24 11:52:29.907426+00
111	maasserver	0108_migrate_allocated_netboot	2015-03-24 11:52:29.995117+00
112	maasserver	0109_networks_dns_servers	2015-03-24 11:52:30.086839+00
113	maasserver	0110_deployed_state_compat	2015-03-24 11:52:30.158715+00
114	maasserver	0111_add_nodegroup_default_disable_ipv4	2015-03-24 11:52:30.238678+00
115	maasserver	0112_remove_boot_image_model	2015-03-24 11:52:30.526586+00
116	maasserver	0113_add_boot_source_cache_model	2015-03-24 11:52:30.614772+00
117	maasserver	0114_add_pxe_mac_to_node	2015-03-24 11:52:30.692776+00
118	maasserver	0115_unique_boot_source_selections	2015-03-24 11:52:30.773587+00
119	maasserver	0116_unique_boot_source_selections	2015-03-24 11:52:30.859414+00
120	maasserver	0117_delete_duplicate_config	2015-03-24 11:52:30.95422+00
121	maasserver	0118_config_key_unique	2015-03-24 11:52:31.036361+00
122	maasserver	0119_migrate_invalid_network_names	2015-03-24 11:52:31.112392+00
123	maasserver	0120_make_macaddress_node_nullable	2015-03-24 11:52:31.199034+00
124	maasserver	0121_recompute_storage_size	2015-03-24 11:52:31.288436+00
125	maasserver	0122_add_eventtype_level_index	2015-03-24 11:52:31.377686+00
126	maasserver	0123_add_physical_block_device_to_node	2015-03-24 11:52:31.475502+00
127	maasserver	0124_add_tags_to_block_device	2015-03-24 11:52:31.559401+00
128	maasserver	0125_add_installable_field_on_node	2015-03-24 11:52:31.660856+00
129	maasserver	0126_replace_storage_field_on_node	2015-03-24 11:52:31.741407+00
130	maasserver	0127_add_node_parent	2015-03-24 11:52:31.834708+00
131	maasserver	0128_add_id_path_to_blockdevice	2015-03-24 11:52:31.9364+00
132	maasserver	0129_add_partition_table_model	2015-03-24 11:52:32.044591+00
133	maasserver	0130_add_partition_model	2015-03-24 11:52:32.137847+00
134	maasserver	0131_add_filesystem_model	2015-03-24 11:52:32.236732+00
135	maasserver	0132_add_filesystem_group_model	2015-03-24 11:52:32.337383+00
136	maasserver	0133_add_virtual_block_device_model	2015-03-24 11:52:32.443244+00
137	maasserver	0134_specify_swap_size	2015-03-24 11:52:32.549972+00
138	metadataserver	0001_initial	2015-03-24 11:52:36.318817+00
139	metadataserver	0002_add_nodecommissionresult	2015-03-24 11:52:36.339176+00
140	metadataserver	0003_populate_hardware_details	2015-03-24 11:52:36.358072+00
141	metadataserver	0004_add_commissioningscript	2015-03-24 11:52:36.381947+00
142	metadataserver	0005_nodecommissionresult_add_timestamp	2015-03-24 11:52:36.409035+00
143	metadataserver	0006_nodecommissionresult_add_status	2015-03-24 11:52:36.433945+00
144	metadataserver	0007_nodecommissionresult_change_name_size	2015-03-24 11:52:36.478967+00
145	metadataserver	0008_rename_lshw_commissioning_output	2015-03-24 11:52:36.50093+00
146	metadataserver	0009_delete_status	2015-03-24 11:52:36.532548+00
147	metadataserver	0010_add_script_result	2015-03-24 11:52:36.557515+00
148	metadataserver	0011_commission_result_binary_data_col	2015-03-24 11:52:36.582627+00
149	metadataserver	0012_commission_result_binary_data_recode	2015-03-24 11:52:36.607968+00
150	metadataserver	0013_commission_result_drop_old_data_col	2015-03-24 11:52:36.635507+00
151	metadataserver	0014_commission_result_rename_data_bin_col	2015-03-24 11:52:36.665185+00
152	metadataserver	0015_rename_nodecommissionresult_add_result_type	2015-03-24 11:52:36.695781+00
\.


--
-- Name: south_migrationhistory_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('south_migrationhistory_id_seq', 152, true);


--
-- Name: auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions_group_id_permission_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_key UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission_content_type_id_codename_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_key UNIQUE (content_type_id, codename);


--
-- Name: auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user_email_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user
    ADD CONSTRAINT auth_user_email_key UNIQUE (email);


--
-- Name: auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups_user_id_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_key UNIQUE (user_id, group_id);


--
-- Name: auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions_user_id_permission_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_key UNIQUE (user_id, permission_id);


--
-- Name: auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type_app_label_model_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_key UNIQUE (app_label, model);


--
-- Name: django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: django_site_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY django_site
    ADD CONSTRAINT django_site_pkey PRIMARY KEY (id);


--
-- Name: maasserver_blockdevice_node_id_592ca9f8196573db_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_node_id_592ca9f8196573db_uniq UNIQUE (node_id, path);


--
-- Name: maasserver_blockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_blockdevice
    ADD CONSTRAINT maasserver_blockdevice_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresource_name_60e611bb5a9b3025_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootresource
    ADD CONSTRAINT maasserver_bootresource_name_60e611bb5a9b3025_uniq UNIQUE (name, architecture);


--
-- Name: maasserver_bootresource_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootresource
    ADD CONSTRAINT maasserver_bootresource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourcefi_resource_set_id_455527e9e6a2a677_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresourcefi_resource_set_id_455527e9e6a2a677_uniq UNIQUE (resource_set_id, filetype);


--
-- Name: maasserver_bootresourcefile_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootresourcefile
    ADD CONSTRAINT maasserver_bootresourcefile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourceset_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootresourceset
    ADD CONSTRAINT maasserver_bootresourceset_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootresourceset_resource_id_6f887d5055ee97de_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootresourceset
    ADD CONSTRAINT maasserver_bootresourceset_resource_id_6f887d5055ee97de_uniq UNIQUE (resource_id, version);


--
-- Name: maasserver_bootsource_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootsource
    ADD CONSTRAINT maasserver_bootsource_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootsource_url_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootsource
    ADD CONSTRAINT maasserver_bootsource_url_uniq UNIQUE (url);


--
-- Name: maasserver_bootsourcecache_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootsourcecache
    ADD CONSTRAINT maasserver_bootsourcecache_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootsourceselection_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_pkey PRIMARY KEY (id);


--
-- Name: maasserver_bootsourceselection_release_5b10fd8f5461406c_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_bootsourceselection
    ADD CONSTRAINT maasserver_bootsourceselection_release_5b10fd8f5461406c_uniq UNIQUE (release, boot_source_id, os);


--
-- Name: maasserver_candidatename_name_35017987245ade5e_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_candidatename
    ADD CONSTRAINT maasserver_candidatename_name_35017987245ade5e_uniq UNIQUE (name, "position");


--
-- Name: maasserver_candidatename_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_candidatename
    ADD CONSTRAINT maasserver_candidatename_pkey PRIMARY KEY (id);


--
-- Name: maasserver_componenterror_component_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_componenterror
    ADD CONSTRAINT maasserver_componenterror_component_key UNIQUE (component);


--
-- Name: maasserver_componenterror_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_componenterror
    ADD CONSTRAINT maasserver_componenterror_pkey PRIMARY KEY (id);


--
-- Name: maasserver_config_name_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_config
    ADD CONSTRAINT maasserver_config_name_uniq UNIQUE (name);


--
-- Name: maasserver_config_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_config
    ADD CONSTRAINT maasserver_config_pkey PRIMARY KEY (id);


--
-- Name: maasserver_dhcplease_ip_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_dhcplease
    ADD CONSTRAINT maasserver_dhcplease_ip_key UNIQUE (ip);


--
-- Name: maasserver_dhcplease_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_dhcplease
    ADD CONSTRAINT maasserver_dhcplease_pkey PRIMARY KEY (id);


--
-- Name: maasserver_downloadprogress_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_downloadprogress
    ADD CONSTRAINT maasserver_downloadprogress_pkey PRIMARY KEY (id);


--
-- Name: maasserver_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_event
    ADD CONSTRAINT maasserver_event_pkey PRIMARY KEY (id);


--
-- Name: maasserver_eventtype_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_eventtype
    ADD CONSTRAINT maasserver_eventtype_name_key UNIQUE (name);


--
-- Name: maasserver_eventtype_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_eventtype
    ADD CONSTRAINT maasserver_eventtype_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filestorage_key_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_key_uniq UNIQUE (key);


--
-- Name: maasserver_filestorage_owner_id_38e1c7833f3cd36b_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_owner_id_38e1c7833f3cd36b_uniq UNIQUE (owner_id, filename);


--
-- Name: maasserver_filestorage_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filestorage
    ADD CONSTRAINT maasserver_filestorage_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filesystem_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filesystem_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filesystem
    ADD CONSTRAINT maasserver_filesystem_uuid_key UNIQUE (uuid);


--
-- Name: maasserver_filesystemgroup_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filesystemgroup
    ADD CONSTRAINT maasserver_filesystemgroup_pkey PRIMARY KEY (id);


--
-- Name: maasserver_filesystemgroup_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_filesystemgroup
    ADD CONSTRAINT maasserver_filesystemgroup_uuid_key UNIQUE (uuid);


--
-- Name: maasserver_largefile_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_largefile
    ADD CONSTRAINT maasserver_largefile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_largefile_sha256_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_largefile
    ADD CONSTRAINT maasserver_largefile_sha256_key UNIQUE (sha256);


--
-- Name: maasserver_licensekey_osystem_6ab259f9bd629d4c_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_licensekey
    ADD CONSTRAINT maasserver_licensekey_osystem_6ab259f9bd629d4c_uniq UNIQUE (osystem, distro_series);


--
-- Name: maasserver_licensekey_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_licensekey
    ADD CONSTRAINT maasserver_licensekey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_macaddress_mac_address_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macaddress
    ADD CONSTRAINT maasserver_macaddress_mac_address_uniq UNIQUE (mac_address);


--
-- Name: maasserver_macaddress_netwo_macaddress_id_29ba4d009ac5c26d_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macaddress_networks
    ADD CONSTRAINT maasserver_macaddress_netwo_macaddress_id_29ba4d009ac5c26d_uniq UNIQUE (macaddress_id, network_id);


--
-- Name: maasserver_macaddress_networks_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macaddress_networks
    ADD CONSTRAINT maasserver_macaddress_networks_pkey PRIMARY KEY (id);


--
-- Name: maasserver_macaddress_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macaddress
    ADD CONSTRAINT maasserver_macaddress_pkey PRIMARY KEY (id);


--
-- Name: maasserver_macstaticipaddre_ip_address_id_7515cc1678e0f382_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macstaticipaddresslink
    ADD CONSTRAINT maasserver_macstaticipaddre_ip_address_id_7515cc1678e0f382_uniq UNIQUE (ip_address_id, mac_address_id);


--
-- Name: maasserver_macstaticipaddresslink_ip_address_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macstaticipaddresslink
    ADD CONSTRAINT maasserver_macstaticipaddresslink_ip_address_id_key UNIQUE (ip_address_id);


--
-- Name: maasserver_macstaticipaddresslink_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_macstaticipaddresslink
    ADD CONSTRAINT maasserver_macstaticipaddresslink_pkey PRIMARY KEY (id);


--
-- Name: maasserver_network_ip_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_network
    ADD CONSTRAINT maasserver_network_ip_key UNIQUE (ip);


--
-- Name: maasserver_network_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_network
    ADD CONSTRAINT maasserver_network_name_key UNIQUE (name);


--
-- Name: maasserver_network_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_network
    ADD CONSTRAINT maasserver_network_pkey PRIMARY KEY (id);


--
-- Name: maasserver_network_vlan_tag_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_network
    ADD CONSTRAINT maasserver_network_vlan_tag_key UNIQUE (vlan_tag);


--
-- Name: maasserver_node_hostname_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT maasserver_node_hostname_uniq UNIQUE (hostname);


--
-- Name: maasserver_node_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT maasserver_node_pkey PRIMARY KEY (id);


--
-- Name: maasserver_node_system_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT maasserver_node_system_id_key UNIQUE (system_id);


--
-- Name: maasserver_node_tags_node_id_29b00c86047a5d7_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_node_id_29b00c86047a5d7_uniq UNIQUE (node_id, tag_id);


--
-- Name: maasserver_node_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_node_tags
    ADD CONSTRAINT maasserver_node_tags_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodegroup_api_key_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroup
    ADD CONSTRAINT maasserver_nodegroup_api_key_key UNIQUE (api_key);


--
-- Name: maasserver_nodegroup_api_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroup
    ADD CONSTRAINT maasserver_nodegroup_api_token_id_key UNIQUE (api_token_id);


--
-- Name: maasserver_nodegroup_cluster_name_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroup
    ADD CONSTRAINT maasserver_nodegroup_cluster_name_uniq UNIQUE (cluster_name);


--
-- Name: maasserver_nodegroup_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroup
    ADD CONSTRAINT maasserver_nodegroup_pkey PRIMARY KEY (id);


--
-- Name: maasserver_nodegroup_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroup
    ADD CONSTRAINT maasserver_nodegroup_uuid_key UNIQUE (uuid);


--
-- Name: maasserver_nodegroupinterfac_nodegroup_id_670958f79d64f7fd_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroupinterface
    ADD CONSTRAINT maasserver_nodegroupinterfac_nodegroup_id_670958f79d64f7fd_uniq UNIQUE (nodegroup_id, name);


--
-- Name: maasserver_nodegroupinterface_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_nodegroupinterface
    ADD CONSTRAINT maasserver_nodegroupinterface_pkey PRIMARY KEY (id);


--
-- Name: maasserver_partition_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_partition
    ADD CONSTRAINT maasserver_partition_pkey PRIMARY KEY (id);


--
-- Name: maasserver_partition_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_partition
    ADD CONSTRAINT maasserver_partition_uuid_key UNIQUE (uuid);


--
-- Name: maasserver_partitiontable_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_partitiontable
    ADD CONSTRAINT maasserver_partitiontable_pkey PRIMARY KEY (id);


--
-- Name: maasserver_physicalblockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_physicalblockdevice
    ADD CONSTRAINT maasserver_physicalblockdevice_pkey PRIMARY KEY (blockdevice_ptr_id);


--
-- Name: maasserver_sshkey_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_sshkey
    ADD CONSTRAINT maasserver_sshkey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_sshkey_user_id_7fa282f08bf5538c_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_sshkey
    ADD CONSTRAINT maasserver_sshkey_user_id_7fa282f08bf5538c_uniq UNIQUE (user_id, key);


--
-- Name: maasserver_sslkey_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_sslkey
    ADD CONSTRAINT maasserver_sslkey_pkey PRIMARY KEY (id);


--
-- Name: maasserver_sslkey_user_id_700ecb7520fc3148_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_sslkey
    ADD CONSTRAINT maasserver_sslkey_user_id_700ecb7520fc3148_uniq UNIQUE (user_id, key);


--
-- Name: maasserver_staticipaddress_ip_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipaddress_ip_key UNIQUE (ip);


--
-- Name: maasserver_staticipaddress_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_staticipaddress
    ADD CONSTRAINT maasserver_staticipaddress_pkey PRIMARY KEY (id);


--
-- Name: maasserver_tag_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_tag
    ADD CONSTRAINT maasserver_tag_name_key UNIQUE (name);


--
-- Name: maasserver_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_tag
    ADD CONSTRAINT maasserver_tag_pkey PRIMARY KEY (id);


--
-- Name: maasserver_userprofile_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_pkey PRIMARY KEY (id);


--
-- Name: maasserver_userprofile_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_userprofile
    ADD CONSTRAINT maasserver_userprofile_user_id_key UNIQUE (user_id);


--
-- Name: maasserver_virtualblockdevice_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualblockdevice_pkey PRIMARY KEY (blockdevice_ptr_id);


--
-- Name: maasserver_virtualblockdevice_uuid_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_virtualblockdevice
    ADD CONSTRAINT maasserver_virtualblockdevice_uuid_key UNIQUE (uuid);


--
-- Name: maasserver_zone_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_zone
    ADD CONSTRAINT maasserver_zone_name_key UNIQUE (name);


--
-- Name: maasserver_zone_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY maasserver_zone
    ADD CONSTRAINT maasserver_zone_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_commissioningscript_name_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_commissioningscript
    ADD CONSTRAINT metadataserver_commissioningscript_name_key UNIQUE (name);


--
-- Name: metadataserver_commissioningscript_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_commissioningscript
    ADD CONSTRAINT metadataserver_commissioningscript_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_nodecommissionresu_node_id_13348d088d2494ae_uniq; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_noderesult
    ADD CONSTRAINT metadataserver_nodecommissionresu_node_id_13348d088d2494ae_uniq UNIQUE (node_id, name);


--
-- Name: metadataserver_nodecommissionresult_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_noderesult
    ADD CONSTRAINT metadataserver_nodecommissionresult_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_nodekey_key_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_key_key UNIQUE (key);


--
-- Name: metadataserver_nodekey_node_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_node_id_key UNIQUE (node_id);


--
-- Name: metadataserver_nodekey_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_pkey PRIMARY KEY (id);


--
-- Name: metadataserver_nodekey_token_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_nodekey
    ADD CONSTRAINT metadataserver_nodekey_token_id_key UNIQUE (token_id);


--
-- Name: metadataserver_nodeuserdata_node_id_key; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_node_id_key UNIQUE (node_id);


--
-- Name: metadataserver_nodeuserdata_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY metadataserver_nodeuserdata
    ADD CONSTRAINT metadataserver_nodeuserdata_pkey PRIMARY KEY (id);


--
-- Name: piston_consumer_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY piston_consumer
    ADD CONSTRAINT piston_consumer_pkey PRIMARY KEY (id);


--
-- Name: piston_nonce_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY piston_nonce
    ADD CONSTRAINT piston_nonce_pkey PRIMARY KEY (id);


--
-- Name: piston_token_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY piston_token
    ADD CONSTRAINT piston_token_pkey PRIMARY KEY (id);


--
-- Name: south_migrationhistory_pkey; Type: CONSTRAINT; Schema: public; Owner: -; Tablespace: 
--

ALTER TABLE ONLY south_migrationhistory
    ADD CONSTRAINT south_migrationhistory_pkey PRIMARY KEY (id);


--
-- Name: auth_group_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_group_name_like ON auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_group_permissions_group_id ON auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_group_permissions_permission_id ON auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_permission_content_type_id ON auth_permission USING btree (content_type_id);


--
-- Name: auth_user_email_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_user_email_like ON auth_user USING btree (email varchar_pattern_ops);


--
-- Name: auth_user_groups_group_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_user_groups_group_id ON auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_user_groups_user_id ON auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_user_user_permissions_permission_id ON auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_user_user_permissions_user_id ON auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX auth_user_username_like ON auth_user USING btree (username varchar_pattern_ops);


--
-- Name: django_admin_log_content_type_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX django_admin_log_content_type_id ON django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX django_admin_log_user_id ON django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX django_session_expire_date ON django_session USING btree (expire_date);


--
-- Name: django_session_session_key_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX django_session_session_key_like ON django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: maasserver_blockdevice_node_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_blockdevice_node_id ON maasserver_blockdevice USING btree (node_id);


--
-- Name: maasserver_bootresourcefile_largefile_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_bootresourcefile_largefile_id ON maasserver_bootresourcefile USING btree (largefile_id);


--
-- Name: maasserver_bootresourcefile_resource_set_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_bootresourcefile_resource_set_id ON maasserver_bootresourcefile USING btree (resource_set_id);


--
-- Name: maasserver_bootresourceset_resource_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_bootresourceset_resource_id ON maasserver_bootresourceset USING btree (resource_id);


--
-- Name: maasserver_bootsourcecache_boot_source_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_bootsourcecache_boot_source_id ON maasserver_bootsourcecache USING btree (boot_source_id);


--
-- Name: maasserver_bootsourceselection_boot_source_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_bootsourceselection_boot_source_id ON maasserver_bootsourceselection USING btree (boot_source_id);


--
-- Name: maasserver_candidatename_name; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_candidatename_name ON maasserver_candidatename USING btree (name);


--
-- Name: maasserver_candidatename_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_candidatename_name_like ON maasserver_candidatename USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_componenterror_component_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_componenterror_component_like ON maasserver_componenterror USING btree (component varchar_pattern_ops);


--
-- Name: maasserver_dhcplease_nodegroup_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_dhcplease_nodegroup_id ON maasserver_dhcplease USING btree (nodegroup_id);


--
-- Name: maasserver_downloadprogress_nodegroup_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_downloadprogress_nodegroup_id ON maasserver_downloadprogress USING btree (nodegroup_id);


--
-- Name: maasserver_event_node_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_event_node_id ON maasserver_event USING btree (node_id);


--
-- Name: maasserver_event_type_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_event_type_id ON maasserver_event USING btree (type_id);


--
-- Name: maasserver_eventtype_level; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_eventtype_level ON maasserver_eventtype USING btree (level);


--
-- Name: maasserver_eventtype_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_eventtype_name_like ON maasserver_eventtype USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_filestorage_filename_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filestorage_filename_like ON maasserver_filestorage USING btree (filename varchar_pattern_ops);


--
-- Name: maasserver_filestorage_owner_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filestorage_owner_id ON maasserver_filestorage USING btree (owner_id);


--
-- Name: maasserver_filesystem_block_device_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filesystem_block_device_id ON maasserver_filesystem USING btree (block_device_id);


--
-- Name: maasserver_filesystem_filesystem_group_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filesystem_filesystem_group_id ON maasserver_filesystem USING btree (filesystem_group_id);


--
-- Name: maasserver_filesystem_partition_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filesystem_partition_id ON maasserver_filesystem USING btree (partition_id);


--
-- Name: maasserver_filesystem_uuid_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filesystem_uuid_like ON maasserver_filesystem USING btree (uuid varchar_pattern_ops);


--
-- Name: maasserver_filesystemgroup_uuid_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_filesystemgroup_uuid_like ON maasserver_filesystemgroup USING btree (uuid varchar_pattern_ops);


--
-- Name: maasserver_largefile_sha256_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_largefile_sha256_like ON maasserver_largefile USING btree (sha256 varchar_pattern_ops);


--
-- Name: maasserver_macaddress_cluster_interface_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_macaddress_cluster_interface_id ON maasserver_macaddress USING btree (cluster_interface_id);


--
-- Name: maasserver_macaddress_networks_macaddress_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_macaddress_networks_macaddress_id ON maasserver_macaddress_networks USING btree (macaddress_id);


--
-- Name: maasserver_macaddress_networks_network_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_macaddress_networks_network_id ON maasserver_macaddress_networks USING btree (network_id);


--
-- Name: maasserver_macaddress_node_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_macaddress_node_id ON maasserver_macaddress USING btree (node_id);


--
-- Name: maasserver_macstaticipaddresslink_mac_address_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_macstaticipaddresslink_mac_address_id ON maasserver_macstaticipaddresslink USING btree (mac_address_id);


--
-- Name: maasserver_network_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_network_name_like ON maasserver_network USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_node_installable; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_installable ON maasserver_node USING btree (installable);


--
-- Name: maasserver_node_nodegroup_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_nodegroup_id ON maasserver_node USING btree (nodegroup_id);


--
-- Name: maasserver_node_owner_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_owner_id ON maasserver_node USING btree (owner_id);


--
-- Name: maasserver_node_parent_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_parent_id ON maasserver_node USING btree (parent_id);


--
-- Name: maasserver_node_pxe_mac_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_pxe_mac_id ON maasserver_node USING btree (pxe_mac_id);


--
-- Name: maasserver_node_system_id_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_system_id_like ON maasserver_node USING btree (system_id varchar_pattern_ops);


--
-- Name: maasserver_node_tags_node_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_tags_node_id ON maasserver_node_tags USING btree (node_id);


--
-- Name: maasserver_node_tags_tag_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_tags_tag_id ON maasserver_node_tags USING btree (tag_id);


--
-- Name: maasserver_node_token_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_token_id ON maasserver_node USING btree (token_id);


--
-- Name: maasserver_node_zone_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_node_zone_id ON maasserver_node USING btree (zone_id);


--
-- Name: maasserver_nodegroup_api_key_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_nodegroup_api_key_like ON maasserver_nodegroup USING btree (api_key varchar_pattern_ops);


--
-- Name: maasserver_nodegroup_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_nodegroup_name_like ON maasserver_nodegroup USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_nodegroup_uuid_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_nodegroup_uuid_like ON maasserver_nodegroup USING btree (uuid varchar_pattern_ops);


--
-- Name: maasserver_nodegroupinterface_nodegroup_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_nodegroupinterface_nodegroup_id ON maasserver_nodegroupinterface USING btree (nodegroup_id);


--
-- Name: maasserver_partition_partition_table_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_partition_partition_table_id ON maasserver_partition USING btree (partition_table_id);


--
-- Name: maasserver_partition_uuid_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_partition_uuid_like ON maasserver_partition USING btree (uuid varchar_pattern_ops);


--
-- Name: maasserver_partitiontable_block_device_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_partitiontable_block_device_id ON maasserver_partitiontable USING btree (block_device_id);


--
-- Name: maasserver_sshkey_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_sshkey_user_id ON maasserver_sshkey USING btree (user_id);


--
-- Name: maasserver_sslkey_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_sslkey_user_id ON maasserver_sslkey USING btree (user_id);


--
-- Name: maasserver_staticipaddress_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_staticipaddress_user_id ON maasserver_staticipaddress USING btree (user_id);


--
-- Name: maasserver_tag_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_tag_name_like ON maasserver_tag USING btree (name varchar_pattern_ops);


--
-- Name: maasserver_virtualblockdevice_filesystem_group_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_virtualblockdevice_filesystem_group_id ON maasserver_virtualblockdevice USING btree (filesystem_group_id);


--
-- Name: maasserver_virtualblockdevice_uuid_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_virtualblockdevice_uuid_like ON maasserver_virtualblockdevice USING btree (uuid varchar_pattern_ops);


--
-- Name: maasserver_zone_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX maasserver_zone_name_like ON maasserver_zone USING btree (name varchar_pattern_ops);


--
-- Name: metadataserver_commissioningscript_name_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX metadataserver_commissioningscript_name_like ON metadataserver_commissioningscript USING btree (name varchar_pattern_ops);


--
-- Name: metadataserver_nodecommissionresult_node_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX metadataserver_nodecommissionresult_node_id ON metadataserver_noderesult USING btree (node_id);


--
-- Name: metadataserver_nodekey_key_like; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX metadataserver_nodekey_key_like ON metadataserver_nodekey USING btree (key varchar_pattern_ops);


--
-- Name: piston_consumer_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX piston_consumer_user_id ON piston_consumer USING btree (user_id);


--
-- Name: piston_token_consumer_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX piston_token_consumer_id ON piston_token USING btree (consumer_id);


--
-- Name: piston_token_user_id; Type: INDEX; Schema: public; Owner: -; Tablespace: 
--

CREATE INDEX piston_token_user_id ON piston_token USING btree (user_id);


--
-- Name: api_token_id_refs_id_9a419722; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_nodegroup
    ADD CONSTRAINT api_token_id_refs_id_9a419722 FOREIGN KEY (api_token_id) REFERENCES piston_token(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_fkey FOREIGN KEY (group_id) REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions_permission_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_permission_id_fkey FOREIGN KEY (permission_id) REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: block_device_id_refs_id_0a156b9b; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_partitiontable
    ADD CONSTRAINT block_device_id_refs_id_0a156b9b FOREIGN KEY (block_device_id) REFERENCES maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: block_device_id_refs_id_a86aaf5b; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filesystem
    ADD CONSTRAINT block_device_id_refs_id_a86aaf5b FOREIGN KEY (block_device_id) REFERENCES maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: blockdevice_ptr_id_refs_id_31f1b3c8; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_virtualblockdevice
    ADD CONSTRAINT blockdevice_ptr_id_refs_id_31f1b3c8 FOREIGN KEY (blockdevice_ptr_id) REFERENCES maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: blockdevice_ptr_id_refs_id_d4eda0f7; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_physicalblockdevice
    ADD CONSTRAINT blockdevice_ptr_id_refs_id_d4eda0f7 FOREIGN KEY (blockdevice_ptr_id) REFERENCES maasserver_blockdevice(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: boot_source_id_refs_id_4f231e39; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootsourcecache
    ADD CONSTRAINT boot_source_id_refs_id_4f231e39 FOREIGN KEY (boot_source_id) REFERENCES maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: boot_source_id_refs_id_8a42329c; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootsourceselection
    ADD CONSTRAINT boot_source_id_refs_id_8a42329c FOREIGN KEY (boot_source_id) REFERENCES maasserver_bootsource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: cluster_interface_id_refs_id_dbde328b; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macaddress
    ADD CONSTRAINT cluster_interface_id_refs_id_dbde328b FOREIGN KEY (cluster_interface_id) REFERENCES maasserver_nodegroupinterface(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: content_type_id_refs_id_d043b34a; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_permission
    ADD CONSTRAINT content_type_id_refs_id_d043b34a FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log_content_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_fkey FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: filesystem_group_id_refs_id_698981d9; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filesystem
    ADD CONSTRAINT filesystem_group_id_refs_id_698981d9 FOREIGN KEY (filesystem_group_id) REFERENCES maasserver_filesystemgroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: filesystem_group_id_refs_id_7904c135; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_virtualblockdevice
    ADD CONSTRAINT filesystem_group_id_refs_id_7904c135 FOREIGN KEY (filesystem_group_id) REFERENCES maasserver_filesystemgroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: group_id_refs_id_f4b32aac; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_group_permissions
    ADD CONSTRAINT group_id_refs_id_f4b32aac FOREIGN KEY (group_id) REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: ip_address_id_refs_id_4aec33dd; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macstaticipaddresslink
    ADD CONSTRAINT ip_address_id_refs_id_4aec33dd FOREIGN KEY (ip_address_id) REFERENCES maasserver_staticipaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: largefile_id_refs_id_de742849; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootresourcefile
    ADD CONSTRAINT largefile_id_refs_id_de742849 FOREIGN KEY (largefile_id) REFERENCES maasserver_largefile(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: mac_address_id_refs_id_bab0ff98; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macstaticipaddresslink
    ADD CONSTRAINT mac_address_id_refs_id_bab0ff98 FOREIGN KEY (mac_address_id) REFERENCES maasserver_macaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: macaddress_id_refs_id_4fe5d103; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macaddress_networks
    ADD CONSTRAINT macaddress_id_refs_id_4fe5d103 FOREIGN KEY (macaddress_id) REFERENCES maasserver_macaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: network_id_refs_id_644aa525; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macaddress_networks
    ADD CONSTRAINT network_id_refs_id_644aa525 FOREIGN KEY (network_id) REFERENCES maasserver_network(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_296eaefb; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_nodekey
    ADD CONSTRAINT node_id_refs_id_296eaefb FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_45cc1cc8; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_event
    ADD CONSTRAINT node_id_refs_id_45cc1cc8 FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_4c5f081d; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_nodeuserdata
    ADD CONSTRAINT node_id_refs_id_4c5f081d FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_645973ad; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_blockdevice
    ADD CONSTRAINT node_id_refs_id_645973ad FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_7ce96c27; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_noderesult
    ADD CONSTRAINT node_id_refs_id_7ce96c27 FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_b7c30b46; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_macaddress
    ADD CONSTRAINT node_id_refs_id_b7c30b46 FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: node_id_refs_id_c0968715; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node_tags
    ADD CONSTRAINT node_id_refs_id_c0968715 FOREIGN KEY (node_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: nodegroup_id_refs_id_1d70da03; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_nodegroupinterface
    ADD CONSTRAINT nodegroup_id_refs_id_1d70da03 FOREIGN KEY (nodegroup_id) REFERENCES maasserver_nodegroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: nodegroup_id_refs_id_c33287a7; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT nodegroup_id_refs_id_c33287a7 FOREIGN KEY (nodegroup_id) REFERENCES maasserver_nodegroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: nodegroup_id_refs_id_d114f761; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_dhcplease
    ADD CONSTRAINT nodegroup_id_refs_id_d114f761 FOREIGN KEY (nodegroup_id) REFERENCES maasserver_nodegroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: nodegroup_id_refs_id_d3190fe5; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_downloadprogress
    ADD CONSTRAINT nodegroup_id_refs_id_d3190fe5 FOREIGN KEY (nodegroup_id) REFERENCES maasserver_nodegroup(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: owner_id_refs_id_bdce25f5; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filestorage
    ADD CONSTRAINT owner_id_refs_id_bdce25f5 FOREIGN KEY (owner_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: owner_id_refs_id_f10c6dfa; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT owner_id_refs_id_f10c6dfa FOREIGN KEY (owner_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: parent_id_refs_id_7b9252f8; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT parent_id_refs_id_7b9252f8 FOREIGN KEY (parent_id) REFERENCES maasserver_node(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: partition_id_refs_id_b118fd86; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_filesystem
    ADD CONSTRAINT partition_id_refs_id_b118fd86 FOREIGN KEY (partition_id) REFERENCES maasserver_partition(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: partition_table_id_refs_id_d65d5516; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_partition
    ADD CONSTRAINT partition_table_id_refs_id_d65d5516 FOREIGN KEY (partition_table_id) REFERENCES maasserver_partitiontable(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston_consumer_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY piston_consumer
    ADD CONSTRAINT piston_consumer_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston_token_consumer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY piston_token
    ADD CONSTRAINT piston_token_consumer_id_fkey FOREIGN KEY (consumer_id) REFERENCES piston_consumer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: piston_token_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY piston_token
    ADD CONSTRAINT piston_token_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: pxe_mac_id_refs_id_23f0e90a; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT pxe_mac_id_refs_id_23f0e90a FOREIGN KEY (pxe_mac_id) REFERENCES maasserver_macaddress(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: resource_id_refs_id_77c3774a; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootresourceset
    ADD CONSTRAINT resource_id_refs_id_77c3774a FOREIGN KEY (resource_id) REFERENCES maasserver_bootresource(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: resource_set_id_refs_id_fdf5102d; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_bootresourcefile
    ADD CONSTRAINT resource_set_id_refs_id_fdf5102d FOREIGN KEY (resource_set_id) REFERENCES maasserver_bootresourceset(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: tag_id_refs_id_4f099832; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node_tags
    ADD CONSTRAINT tag_id_refs_id_4f099832 FOREIGN KEY (tag_id) REFERENCES maasserver_tag(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: token_id_refs_id_25b3042f; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY metadataserver_nodekey
    ADD CONSTRAINT token_id_refs_id_25b3042f FOREIGN KEY (token_id) REFERENCES piston_token(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: token_id_refs_id_ba2c8372; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT token_id_refs_id_ba2c8372 FOREIGN KEY (token_id) REFERENCES piston_token(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: type_id_refs_id_c7ad5b7c; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_event
    ADD CONSTRAINT type_id_refs_id_c7ad5b7c FOREIGN KEY (type_id) REFERENCES maasserver_eventtype(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: user_id_refs_id_33e3eea7; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_sshkey
    ADD CONSTRAINT user_id_refs_id_33e3eea7 FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: user_id_refs_id_40c41112; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user_groups
    ADD CONSTRAINT user_id_refs_id_40c41112 FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: user_id_refs_id_4dc23c39; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY auth_user_user_permissions
    ADD CONSTRAINT user_id_refs_id_4dc23c39 FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: user_id_refs_id_5e967b50; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_staticipaddress
    ADD CONSTRAINT user_id_refs_id_5e967b50 FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: user_id_refs_id_5ea5ad24; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_sslkey
    ADD CONSTRAINT user_id_refs_id_5ea5ad24 FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: user_id_refs_id_648fff59; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_userprofile
    ADD CONSTRAINT user_id_refs_id_648fff59 FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: zone_id_refs_id_2e199727; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY maasserver_node
    ADD CONSTRAINT zone_id_refs_id_2e199727 FOREIGN KEY (zone_id) REFERENCES maasserver_zone(id) DEFERRABLE INITIALLY DEFERRED;


--
-- PostgreSQL database dump complete
--

