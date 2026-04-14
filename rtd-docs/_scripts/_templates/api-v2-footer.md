## Power types

This is the list of the supported power types and their associated power parameters. Note that the list of usable power types for a particular rack controller might be a subset of this list if the rack controller in question is from an older version of MAAS.

### amt (Intel AMT)

Power parameters:

- power_pass (Power password).
- power_address (Power address).

### apc (American Power Conversion (APC) PDU)

Power parameters:

- power_address (IP for APC PDU).
- node_outlet (APC PDU node outlet number (1-16)).
- power_on_delay (Power ON outlet delay (seconds)). Default: '5'.
- pdu_type (PDU type). Choices: 'RPDU' (rPDU), 'MASTERSWITCH' (masterswitch) Default: 'RPDU'.

### dli (Digital Loggers, Inc. PDU)

Power parameters:

- outlet_id (Outlet ID).
- power_address (Power address).
- power_user (Power user).
- power_pass (Power password).

### eaton (Eaton PDU)

Power parameters:

- power_address (IP for Eaton PDU).
- node_outlet (Eaton PDU node outlet number (1-24)).
- power_on_delay (Power ON outlet delay (seconds)). Default: '5'.

### hmc (IBM Hardware Management Console (HMC) for PowerPC)

Power parameters:

- power_address (IP for HMC).
- power_user (HMC username).
- power_pass (HMC password).
- server_name (HMC Managed System server name).
- lpar (HMC logical partition).

### hmcz (IBM Hardware Management Console (HMC) for Z)

Power parameters:

- power_address (HMC Address).
- power_user (HMC username).
- power_pass (HMC password).
- power_partition_name (HMC partition name).

### ipmi (IPMI)

Power parameters:

- power_driver (Power driver). Choices: 'LAN' (LAN [IPMI 1.5]), 'LAN_2_0' (LAN_2_0 [IPMI 2.0]) Default: 'LAN_2_0'.
- power_boot_type (Power boot type). Choices: 'auto' (Automatic), 'legacy' (Legacy boot), 'efi' (EFI boot) Default: 'auto'.
- power_address (IP address).
- power_user (Power user).
- power_pass (Power password).
- k_g (K_g BMC key).
- cipher_suite_id (Cipher Suite ID). Choices: '17' (17 - HMAC-SHA256::HMAC_SHA256_128::AES-CBC-128), '3' (3 - HMAC-SHA1::HMAC-SHA1-96::AES-CBC-128), '' (freeipmi-tools default), '8' (8 - HMAC-MD5::HMAC-MD5-128::AES-CBC-128), '12' (12 - HMAC-MD5::MD5-128::AES-CBC-128) Default: '3'.
- privilege_level (Privilege Level). Choices: 'USER' (User), 'OPERATOR' (Operator), 'ADMIN' (Administrator) Default: 'OPERATOR'.
- workaround_flags (Workaround Flags). Choices: 'opensesspriv' (Opensesspriv), 'authcap' (Authcap), 'idzero' (Idzero), 'unexpectedauth' (Unexpectedauth), 'forcepermsg' (Forcepermsg), 'endianseq' (Endianseq), 'intel20' (Intel20), 'supermicro20' (Supermicro20), 'sun20' (Sun20), 'nochecksumcheck' (Nochecksumcheck), 'integritycheckvalue' (Integritycheckvalue), 'ipmiping' (Ipmiping), '' (None) Default: '['opensesspriv']'.
- mac_address (Power MAC).

### manual (Manual)

Power parameters:

### moonshot (HP Moonshot - iLO4 (IPMI))

Power parameters:

- power_address (Power address).
- power_user (Power user).
- power_pass (Power password).
- power_hwaddress (Power hardware address).

### mscm (HP Moonshot - iLO Chassis Manager)

Power parameters:

- power_address (IP for MSCM CLI API).
- power_user (MSCM CLI API user).
- power_pass (MSCM CLI API password).
- node_id (Node ID - Must adhere to cXnY format (X=cartridge number, Y=node number).).

### msftocs (Microsoft OCS - Chassis Manager)

Power parameters:

- power_address (Power address).
- power_port (Power port).
- power_user (Power user).
- power_pass (Power password).
- blade_id (Blade ID (Typically 1-24)).

### nova (OpenStack Nova)

Power parameters:

- nova_id (Host UUID).
- os_tenantname (Tenant name).
- os_username (Username).
- os_password (Password).
- os_authurl (Auth URL).

### openbmc (OpenBMC Power Driver)

Power parameters:

- power_address (OpenBMC address).
- power_user (OpenBMC user).
- power_pass (OpenBMC password).

### proxmox (Proxmox)

Power parameters:

- power_address (Proxmox host name or IP).
- power_user (Proxmox username, including realm).
- power_pass (Proxmox password, required if a token name and secret aren't given).
- power_token_name (Proxmox API token name).
- power_token_secret (Proxmox API token secret).
- power_vm_name (Node ID).
- power_verify_ssl (Verify SSL connections with system CA certificates). Choices: 'n' (No), 'y' (Yes) Default: 'n'.

### recs_box (Christmann RECS|Box Power Driver)

Power parameters:

- node_id (Node ID).
- power_address (Power address).
- power_port (Power port).
- power_user (Power user).
- power_pass (Power password).

### redfish (Redfish)

Power parameters:

- power_address (Redfish address).
- power_user (Redfish user).
- power_pass (Redfish password).
- node_id (Node ID).

### sm15k (SeaMicro 15000)

Power parameters:

- system_id (System ID).
- power_address (Power address).
- power_user (Power user).
- power_pass (Power password).
- power_control (Power control type). Choices: 'ipmi' (IPMI), 'restapi' (REST API v0.9), 'restapi2' (REST API v2.0) Default: 'ipmi'.

### ucsm (Cisco UCS Manager)

Power parameters:

- uuid (Server UUID).
- power_address (URL for XML API).
- power_user (API user).
- power_pass (API password).

### vmware (VMware)

Power parameters:

- power_vm_name (VM Name (if UUID unknown)).
- power_uuid (VM UUID (if known)).
- power_address (VMware IP).
- power_user (VMware username).
- power_pass (VMware password).
- power_port (VMware API port (optional)).
- power_protocol (VMware API protocol (optional)).

### webhook (Webhook)

Power parameters:

- power_on_uri (URI to power on the node).
- power_off_uri (URI to power off the node).
- power_query_uri (URI to query the nodes power status).
- power_on_regex (Regex to confirm the node is on). Default: 'status.*:.*running'.
- power_off_regex (Regex to confirm the node is off). Default: 'status.*:.*stopped'.
- power_user (Power user).
- power_pass (Power password).
- power_token (Power token, will be used in place of power_user and power_pass).
- power_verify_ssl (Verify SSL connections with system CA certificates). Choices: 'n' (No), 'y' (Yes) Default: 'n'.

### wedge (Facebook's Wedge)

Power parameters:

- power_address (IP address).
- power_user (Power user).
- power_pass (Power password).

### lxd (LXD (virtual systems))

Power parameters:

- power_address (LXD address).
- instance_name (Instance name).
- project (LXD project). Default: 'default'.
- password (LXD password (optional)).
- certificate (LXD certificate (optional)).
- key (LXD private key (optional)).

### virsh (Virsh (virtual systems))

Power parameters:

- power_address (Address).
- power_pass (Password (optional)).
- power_id (Virsh VM ID).

## Pod types

This is the list of the supported pod types and their associated parameters. Note that the list of usable pod types for a particular rack controller might be a subset of this list if the rack controller in question is from an older version of MAAS.

### lxd (LXD (virtual systems))

Parameters:

- power_address (LXD address).
- instance_name (Instance name).
- project (LXD project). Default: 'default'.
- password (LXD password (optional)).
- certificate (LXD certificate (optional)).
- key (LXD private key (optional)).

### virsh (Virsh (virtual systems))

Parameters:

- power_address (Address).
- power_pass (Password (optional)).
- power_id (Virsh VM ID).
