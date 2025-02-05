> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/connecting-maas-networks" target = "_blank">Let us know.</a>*

> See first: [Networking](https://maas.io/docs/about-maas-networking) | [Clouds](https://maas.io/docs/about-cloud-networking) | [DHCP](https://maas.io/docs/about-dhcp-in-maas)

This page explains how to manage and customize MAAS networks.

## Manage basic networking

MAAS adds some nuance to basic networking operations.

### Set the default gateway

The default gateway in MAAS is set per subnet and directs outbound traffic for machines without a more specific route.

**CLI**
   ```bash
   maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
   ```
### Static routes

Static routes allow traffic between different subnets or through specific gateways.

**UI (3.4 and above)**
*Networking > Subnets > Subnet summary > Add static route > [Fill in the fields] > Save*

**UI (3.3 and below)**
*Subnets > Add static route > [Fill in the fields] > Add*

**CLI**
  ```bash
   maas admin static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
   ```

### Configure loopback

Configuring the loopback interface (lo) is essential for advanced networking tasks such as Free Range Routing (FRR) and BGP.

*Manual addition* the loopback interface**
After commissioning a node, manually add the loopback interface in MAAS. You may use a placeholder MAC address (e.g., 00:00:00:00:00:00) for the loopback interface.
   
*Using post-deployment scripts**
If needed, use tools like `cloud-init` to configure the loopback interface after deployment.

### Bridging

Bridges enable multiple network interfaces to act as one.

**UI**
*Machines > [machine] > Network > Create bridge > [configure details] > Save*

**CLI**
   ```bash
   INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
   BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
   SUBNET_ID=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24" and .managed == true).id')
   maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
   ```

### Bridging with [Netplan](https://netplan.readthedocs.io/en/stable/)

Netplan configurations can be used to set up bridges outside of MAAS.

1. **Open the Netplan config file** (`/etc/netplan/50-cloud-init.yaml` or similar).
2. **Modify the file** to add a bridge:
   ```yaml
   network:
       bridges:
           br0:
               addresses:
               - 10.0.0.101/24
               gateway4: 10.0.0.1
              interfaces:
               - enp1s0
               macaddress: 52:54:00:39:9d:f9
   ```
3. **Apply the new configuration**:
   ```bash
   sudo netplan apply
   ```

### Create bonds

Bonds allow multiple network interfaces to act together for redundancy or performance.

**UI**
*Select multiple interfaces > choose Create bond > Choose bond mode*

**CLI**
  ```bash
  maas $PROFILE interfaces create-bond $SYSTEM_ID name=$BOND_NAME parents=$IFACE1_ID,$IFACE2_ID bond_mode=$BOND_MODE
  ```

Bond modes include:

   - **balance-rr**: Round-robin transmission.
   - **active-backup**: Only one active follower; failover to another upon failure.
   - **balance-xor**: Transmit based on hash policy.

### Configure two NICs on one machine

You can set up a machine with two NICs — one for a private subnet and one for the public internet.

**UI**
1. **Detect both NICs**:
   - Ensure MAAS detects both network interfaces (e.g., `ens18` and `ens19`).
   
2. **Private NIC (ens18)**:
   - Set to **DHCP** on the private subnet (e.g., 192.168.10.0/24).
   
3. **Public NIC (ens19)**:
   - Manually configure or use DHCP for the public subnet (e.g., 192.168.1.0/24).

#### Netplan Example
```yaml
network:
    version: 2
    ethernets:
        ens18:
            addresses:
            - 192.168.10.5/24
            gateway4: 192.168.10.1
        ens19:
            addresses:
            - 192.168.1.10/24
            gateway4: 192.168.1.1
            nameservers:
                addresses:
                - 8.8.8.8
                - 8.8.4.4
```

## Manage network discovery

Network discovery scans your environment to identify all connected devices, including non-deployable devices such as routers and switches.

**UI (MAAS 3.4 and above)**
*Networking > Network discovery > Configuration > [drop-down] > choose Enabled|Disabled > Save*
   
**UI (MAAS 3.3 and below)**
*Canonical MAAS > Configuration > Network discovery drop-down > choose Enabled|Disabled > Save*

**CLI**
  ```bash
  maas $PROFILE maas set-config name=network_discovery value="enabled"
  ```

## Manage DHCP
### Enable MAAS DHCP

**UI**
To enable MAAS-managed DHCP via the MAAS UI:

1. Select *Subnets* > <desired VLAN> > *Reserved ranges* > *Reserved dynamic range*.

2. Enter a *Start IP address* and an *End IP address*.

3. Select *Reserve* > *Configure DHCP*. You will see a new screen.

4. The options *MAAS provides DHCP* and *Provide DHCP from a rack controller* will be pre-selected.

5. If you accept these options, you may need to choose a *Rack controller*.

6. If you choose *Relay to another VLAN*, you will need to choose the target VLAN.

7. Under *Reserved dynamic range*, you may have to select a subnet from the drop-down.

8. Select *Configure DHCP* for your changes to be registered with MAAS.

**CLI**
To enable DHCP on a VLAN in a certain fabric, enter the following command:

```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True \
    primary_rack=$PRIMARY_RACK_CONTROLLER
```

To enable DHCP HA, you will need both a primary and a secondary controller:

```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True \
    primary_rack=$PRIMARY_RACK_CONTROLLER \
    secondary_rack=$SECONDARY_RACK_CONTROLLER 
```

>*Pro tip*: You must enable DHCP for PXE booting on the 'untagged' VLAN.

You will also need to set a default gateway:

```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```
### Set up a DHCP relay

**UI**
1. Ensure the target VLAN has DHCP enabled.

2. Set up the external relay. This relay is set up independently from MAAS. See [DHCP relay](/t/reference-maas-glossary/5416) for software suggestions.

3. Configure MAAS-managed DHCP as normal.

4. Navigate to the source VLAN page.

5. Select the *Relay DHCP* action. 

5. Fill in the fields in the resulting form. Note that the crucial setting is the target VLAN (*Relay VLAN*). 

6. Select *Relay DHCP* to finish.

**CLI**
To use the MAAS CLI to relay DHCP traffic for a VLAN (source) through another VLAN (target):

```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_VID_SRC relay_vlan=$VLAN_ID_TARGET
```

For example, to relay VLAN with vid 0 (on fabric-2) through VLAN with id 5002 :

```bash
maas $PROFILE vlan update 2 0 relay_van=5002
```

### Use DHCP snippets
### Managing DHCP snippets (UI) 

To manage snippets via the MAAS UI as an administrator, select *Settings >> DHCP snippets*.

### Search snippets (UI)

To search DHCP snippets, enter the text to match in *Search DHCP snippets*. MAAS will progressively update the list of snippets as you type your search terms.

### Add snippets (UI)

To add a snippet:

1. Select *Add snippet*.

2. Enter the *Snippet name*.

3. Optionally, check *Enabled* to enable the snippet now. Note that MAAS will not apply the snippet unless it is enabled.

4. Optionally, enter a *Description* for the snippet.

5. Optionally, choose a *Type* for the snippet from the drop-down (defaults to *Global*). This parameter sets the scope of the snippet. Note that if you choose a type other than global, you may need to choose the specific scope. For example, if you choose the *Subnet* type, you must identify the specific subnet to which this snippet applies.

6. Enter the *DHCP snippet*. This is not validated on entry.

7. Select *Save snippet* to register your changes with MAAS

### Edit snippets (UI)

To edit a snippet, select the pencil icon to the right of the snippet row and edit the fields as desired.

### Delete snippets (UI)

To delete a snippet, select the trash can icon to the right of the snippet. You will be asked to confirm; be aware that once confirmed, this action cannot be undone.

### Create global DHCP snippets (CLI)

To create a **global** snippet:

```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME \
    value=$DHCP_CONFIG description=$DHCP_SNIPPET_DESCRIPTION \
    global_snippet=true
```

### Create subnet snippets (CLI)

To create a **subnet** snippet:

```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME \
    value=$DHCP_CONFIG description=$DHCP_SNIPPET_DESCRIPTION \
    subnet=$SUBNET_ID
```

### Create node snippets (CLI)

To create a **node** snippet:

```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME \
    value=$DHCP_CONFIG description=$DHCP_SNIPPET_DESCRIPTION \
    node=$NODE_ID
```

### List snippets (CLI)

To list all snippets (and their characteristics) in the MAAS:

```bash
maas $PROFILE dhcpsnippets read
```

To list a specific snippet:

```bash
maas $PROFILE dhcpsnippet read id=$DHCP_SNIPPET_ID
```

The snippet name can also be used instead of its ID:

```bash
maas $PROFILE dhcpsnippet read name=$DHCP_SNIPPET_NAME
```

### Update snippets (CLI)

To update a DHCP snippet attribute:

```bash
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID <option=value>
```

You can also use a snippet name instead of its ID.

### Toggle a snippet (CLI)

Enabling and disabling a snippet is considered a snippet update and is done via a Boolean option ('true' or 'false'). You can disable a snippet like this:

```bash
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID enabled=false
```

When you disable a snippet, MAAS removes the text you added to the dhcpd.conf file when you created the snippet.

### Delete a snippet (CLI)

To delete a snippet:

```bash
maas $PROFILE dhcpsnippet delete $DHCP_SNIPPET_ID
```

You can also use a snippet name in place of its ID.

## Manage IP addresses
### Netplan static IP configuration

To configure a static IP with Netplan:

1. **Open the Netplan configuration file**:
   ```bash
   sudo nano /etc/netplan/50-cloud-init.yaml
   ```

2. **Modify the configuration**:
   ```yaml
   network:
       version: 2
       ethernets:
           ens160:
               addresses:
               - 192.168.0.100/24
               gateway4: 192.168.0.1
               nameservers:
                   addresses:
                   - 8.8.8.8
                   - 8.8.4.4
   ```

### Create IPs and ranges 
#### Create a single reserved IP

**CLI**
  ```bash
  maas $PROFILE ipaddresses reserve ip_address=$IP_STATIC_SINGLE
  ```

#### Create an IP range

**UI**
To create an IP range:

1. Select *Subnets*.

2. In the *SUBNET* column, choose the subnet for which you want to create an IP range.

3. Scroll down to *Reserved ranges*.

4. Select *Reserve range* and choose either *Reserve range* or *Reserve dynamic range*. Note that if you choose a dynamic range, MAAS will automatically provide DHCP for enlistment and commissioning provided that the associated VLAN has DHCP enabled. 

5. A window will appear, allowing you to enter a *Start IP address* and *End IP address*.

6. If you didn't select a dynamic range, you may optionally enter a *Purpose* for the range.

6. Select *Reserve* to register your choices with MAAS.

**CLI**
To create a range of dynamic IP addresses that will be used by MAAS for node enlistment, commissioning, and possibly deployment:

  ```bash
  maas $PROFILE ipranges create type=dynamic \
    start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH \
    comment='This is a reserved dynamic range'
  ```

#### Create a reserved IP range

**UI**
1. Navigate to *Subnets* > <subnet> > *Reserved Ranges* > *Add Reserved Range*.
2. Define start/end IP address and purpose (optional).
3. *Save* the results.
4. Verify the new reserved range is now in the list.

**CLI**
  ```bash
  maas $PROFILE ipranges create type=reserved start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH comment='Reserved range'
  ```

#### Create a dynamic IP range

**CLI**
  ```bash
  maas $PROFILE ipranges create type=dynamic start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH comment='Reserved dynamic range'
  ```

### Edit an IP range

**UI**
  1.  Select *Subnet* > *Edit reserved range*.
  2. Update and save.

**CLI**

 1. Find range ID: 
  ```bash
  maas admin ipranges read
  ```
  2. Update range:
  ```bash
  maas admin iprange update $ID start_ip="<start ip>" end_ip="<end ip>" comment="freeform comment"
  ```

### Delete an IP range

**UI**
*Subnet > <subnet> Remove range*

**CLI**
You can delete a range of IP addresses by deleting the addresses one by one. To remove a single reserved IP address:

  ```bash
  maas $PROFILE ipaddresses release ip=$IP_STATIC_SINGLE
  ```

### Extend IP range (UI)

**UI**
*Subnets > [subnet] > Reserve dynamic range* 

DHCP will be enabled automatically.

### Protect a range

To create a range of IP addresses that will not be used by MAAS:

**CLI**
  ```bash
  maas $PROFILE ipranges create type=reserved \
    start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH \
    comment='This is a reserved range'
  ```

### Protect an IP

To reserve a single IP address that will not be used by MAAS:

**CLI***
  ```bash
  maas $PROFILE ipaddresses reserve ip_address=$IP_STATIC_SINGLE
  ```

## Manage VLANs

MAAS allows tremendous flexibility in creating and using VLANs.

### Create VLANs

**CLI**
  ```bash
  maas admin vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
  ```

### Assign VLAN to an interface

**CLI**
  ```bash
  maas admin interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID
  ```

### Delete VLANs

**CLI**
  ```bash
  maas $PROFILE vlan delete $FABRIC_ID $VLAN_ID
  ```

## Manage NTP

Basic NTP is built into MAAS.

### Use external NTP

**UI**
*Settings > Network services > NTP > External Only > enter NTP server address > Save*

**CLI**
   ```bash
   maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
   maas $PROFILE maas set-config name=ntp_external_only value=true
   ```

## Manage DNS

MAAS provides a built-in DNS server.

### Configure DNS

**CLI**
  ```bash
  maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_DNS_SERVER
  ```

### Create A/AAAA DNS records

An administrator can create an A record when creating a DNS resource with an IPv4 address.

**CLI**
  ```bash
  mass $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV4ADDRESS
  ```

An administrator can also create an AAAA record when creating a DNS resource with an IPv6 address.

**CLI**
  ```bash
  mass $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV6ADDRESS
  ```

### Set CNAME DNS records

An administrator can set a DNS Alias (CNAME record) to an already existing DNS entry of a machine.

**CLI**
  ```bash
  mass $PROFILE dnsresource-records create fqdn=$HOSTNAME.$DOMAIN rrtype=cname rrdata=$ALIAS
  ```

For example, to set `webserver.maas.io` to alias to `www.maas.io`:

  ```bash
  maas $PROFILE dnsresource-records create fqdn=webserver.maas.io rrtype=cname rrdata=www
  ```

### Set ME DNS records

An administrator can set a DNS Mail Exchange pointer record (MX and value) to a domain.

**CLI**
  ```bash
  maas $PROFILE dnsresource-records create fqdn=$DOMAIN rrtype=mx rrdata='10 $MAIL_SERVER.$DOMAIN'
  ```

For example, to set the domain.name managed by MAAS to have an MX record and that you own the domain:

  ```bash
  maas $PROFILE dnsresource-records create fqdn=maas.io rrtype=mx rrdata='10 smtp.maas.io'
  ```

### Set a DNS forwarder

An administrator can also set a DNS forwarder.

**CLI**
  ```bash
  maas $PROFILE maas set-config name=upstream_dns value=$MY_UPSTREAM_DNS
  ```


