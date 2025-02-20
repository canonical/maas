> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-manage-maas-networks" target = "_blank">Let us know.</a>*

> *Learn more about [MAAS networking](https://maas.io/docs/about-maas-networking)*

## Routine network management  

Manage MAAS networks by setting gateways, routes, loopback, bridges, and bonds.  

### Set default gateway  

```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

### Add static routes  

**UI:**  
*Networking > Subnets > (Select subnet) > Add static route > Fill fields > Save*  

**CLI:**  
```bash
maas $PROFILE static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
```

### Configure loopback  

After commissioning, manually add a loopback interface using a placeholder MAC (`00:00:00:00:00:00`).  

For automation, use `cloud-init`.  

### Create bridges  

**UI:**  
*Machines > (Select machine) > Network > (Select interface) > Create bridge > (Configure details) > Save interface*  

**CLI:**  
```bash
INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
SUBNET_ID=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24" and .managed == true).id')
maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
```

#### Bridging via netplan  

Modify `/etc/netplan/50-cloud-init.yaml`:  
```yaml
network:
  bridges:
    br0:
      addresses:
        - 10.0.0.101/24
      gateway4: 10.0.0.1
      interfaces:
        - enp1s0
```
Apply:  
```bash
sudo netplan apply
```

### Create bonds  

**UI:**  
*Machines > (Select machine) > Network > (Select 2 physical interface) > Create bond > (Configure details) > Save interface*  

**CLI:**  
```bash
maas $PROFILE interfaces create-bond $SYSTEM_ID name=$BOND_NAME parents=$IFACE1_ID,$IFACE2_ID bond_mode=$BOND_MODE
```

Modes:  
- **balance-rr**: Round-robin  
- **active-backup**: Failover only  
- **balance-xor**: Hash-based  

## Two-NIC setup  

### UI steps  

- **NIC 1 (private subnet):** Set to DHCP (e.g., `192.168.10.0/24`).  
- **NIC 2 (public internet):** Set to DHCP/static (e.g., `192.168.1.0/24`).  

### Netplan example  

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

## Network discovery  

Network discovery detects connected devices, including non-deployables. 

> *Learn more about [network discovery](https://maas.io/docs/about-maas-networking#p-20679-network-discovery).*

### Turn discovery on

**UI:**  
*Networking > Network discovery > Configuration > Enabled*

**CLI:**  
```sh
maas $PROFILE maas set-config name=network_discovery value="enabled"
```

### Turn discovery off

**UI:**  
*Networking > Network discovery > Configuration > Disabled*

**CLI:**  
```sh
maas $PROFILE maas set-config name=network_discovery value="disabled"
```

## Subnets

> *Note: The following instructions are based on MAAS 3.4. For earlier versions, the UI element names may differ.*

### Examine subnets

**UI**
*Networking > Subnets > (Select subnet)*

**CLI**
 - List subnets:
    ```bash
    maas $PROFILE subnets read
    ```
  - Retrieve details of a specific subnet:
    ```bash
    maas $PROFILE subnet read $SUBNET_ID
    ```

### Toggle subnet management

**UI**
*Subnets > (Select subnet) > Edit > Managed allocation > Save*

**CLI**
  - Enable management:
    ```bash
    maas $PROFILE subnet update $SUBNET_CIDR managed=true
    ```
  - Disable management:
    ```bash
    maas $PROFILE subnet update $SUBNET_CIDR managed=false
    ```

### Set a default gateway

**UI**
*Subnets > (Select subnet) > Edit > Enter Gateway IP > Save*

**CLI**
  ```bash
  maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$GATEWAY_IP
  ```

### Configure DNS servers per subnet

**UI**
*Subnets > (Select subnet)j > Edit > DNS servers > Save*

**CLI**
  ```bash
  maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$DNS_SERVER_IPS
  ```

### Add static routes

**UI**
*Subnets > (Select subnet) > Static routes > Add static route > Enter Gateway IP > Enter Destination subnet > Enter (optional) Metric > Save*

**CLI**
  ```bash
  maas $PROFILE static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
  ```

## VLANs  

### Create VLAN

**UI**
*Subnets > Add > VLAN > (Fill fields) > Add VLAN*

**CLI**
```bash
maas $PROFILE vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
```

### Assign VLAN to interface  

**UI**
*Machines > (Select machine> > (Select physical interface) > Actions > Add VLAN*

**CLI**
```bash
maas $PROFILE interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID
```

### Delete VLAN  

**UI**
*Subnets* > (Select VLAN) > Delete VLAN > Delete VLAN*

**CLI**
```bash
maas $PROFILE vlan delete $FABRIC_ID $VLAN_ID
```

## DHCP management  

### Enable MAAS DHCP  

**UI:**  
*Subnets > (Select VLAN) > Configure DHCP (Fill fields) > Configure DHCP*  

**CLI:**  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True primary_rack=$PRIMARY_RACK
```

### Enable DHCP for HA

**CLI**
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True primary_rack=$PRIMARY_RACK secondary_rack=$SECONDARY_RACK
```

### Set default gateway

**UI**
*Subnets > (Select subnet) > Edit > (Set Gateway IP) > Set*

**CLI**
```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

### Set up a DHCP relay  

**UI**
*Subnets > (Select VLAN) > Configure DHCP > Relay to another VLAN > (Select VLAN) >  Configure DHCP*

**CLI:**  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_VID_SRC relay_vlan=$VLAN_ID_TARGET
```

## DHCP snippets

### Create snippets

**UI**
*Settings > DHCP snippets > Add snippet > (Fill fields) > Save snippet*

**CLI (global snippet)**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION global_snippet=true
```

**CLI (subnet snippet)**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION subnet=$SUBNET_ID
```

**CLI (node snippet)**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION node=$NODE_ID
```

### List snippets

**UI**
*Settings > DHCP snippets*

**CLI**
```bash
maas $PROFILE dhcpsnippets read
```

### Update a snippet

**UI**
*Settings > DHCP snippets > Actions > Pencil icon (edit) > (Edit snippet) > Save snippet*

```bash
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID enabled=false
```

### Delete a snippet

**UI**
*Settings > DHCP snippets > Actions > Trash can icon (delete) > Delete*

**CLI**
```bash
maas $PROFILE dhcpsnippet delete $DHCP_SNIPPET_ID
```

## IP management  

### Static IP via netplan  

Modify `/etc/netplan/50-cloud-init.yaml`:  
```yaml
network:
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

### Reserve IPs  

#### Reserve single IP

**CLI**
```bash
maas $PROFILE ipaddresses reserve ip=$IP_ADDRESS_STATIC_SINGLE
```

Reserve dynamic range

**UI**
*Subnets > (Select subnet> > (Scroll down> > Reserve range > Reserve dynamic range > (Fill fields) > Reserve*

**CLI**
```bash
maas $PROFILE ipranges create type=dynamic subnet=$SUBNET_ADDRESS start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH
```

**Reserved range:**

**UI**
*Subnets > (Select subnet> > (Scroll down) > Reserve range > Reserve range > (Fill fields) Reserve*

**CLI**
```bash
maas $PROFILE ipranges create type=reserved subnet=$SUBNET_ADDRESS start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH
```

## NTP management  

### Use external NTP  

**UI:**  
*Settings > Network > NTP > (Fill in NTP address) > External Only > Save*  

**CLI:**  
```bash
maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
maas $PROFILE maas set-config name=ntp_external_only value=true
```

## DNS management  

### Set DNS server  

**UI**
*Settings > DNS > (Fill fields) > Save*

**CLI**
```bash
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_DNS_SERVER
```

### Create DNS records  

#### A record

**CLI**
```bash
maas $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV4ADDRESS
```

#### AAAA record  
```bash
maas $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV6ADDRESS
```

### Set CNAME record  

**CLI**
```bash
maas $PROFILE dnsresource-records create fqdn=$HOSTNAME.$DOMAIN rrtype=cname rrdata=$ALIAS
```

For example:

**CLI**
```bash
maas $PROFILE dnsresource-records create fqdn=webserver.maas.io rrtype=cname rrdata=www
```

### Set MX record  

**CLI**
```bash
maas $PROFILE dnsresource-records create fqdn=$DOMAIN rrtype=mx rrdata='10 $MAIL_SERVER.$DOMAIN'
```

For example:

**CLI**
```bash
maas $PROFILE dnsresource-records create fqdn=maas.io rrtype=mx rrdata='10 smtp.maas.io'
```

### Set DNS forwarder  

**CLI**
```bash
maas $PROFILE maas set-config name=upstream_dns value=$MY_UPSTREAM_DNS
```
