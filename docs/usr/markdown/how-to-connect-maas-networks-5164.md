> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/connecting-maas-networks" target = "_blank">Let us know.</a>*

## Basics  

Manage MAAS networks by setting gateways, routes, loopback, bridges, and bonds.  

### Set default gateway  

```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

### Add static routes  

**UI:**  
*Networking > Subnets > Subnet summary > Add static route > Fill fields > Save*  

**CLI:**  
```bash
maas admin static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
```

### Configure loopback  

After commissioning, manually add a loopback interface using a placeholder MAC (`00:00:00:00:00:00`).  

For automation, use `cloud-init`.  

### Create bridges  

**UI:**  
*Machines > Select Machine > Network > Create bridge > Configure > Save*  

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
*Select interfaces > Create bond > Choose mode*  

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

Detects connected devices, including non-deployables.  

**UI:**  
*Settings* → *Network* → Enable **Network Discovery**.  

**CLI:**  
```sh
maas $PROFILE maas set-config name=network_discovery value="enabled"
```

## DHCP management  

### Enable MAAS DHCP  

**UI:**  
*Subnets > VLAN > Reserved Ranges > Configure DHCP*  

**CLI:**  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True primary_rack=$PRIMARY_RACK
```

For DHCP HA:  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_TAG dhcp_on=True primary_rack=$PRIMARY_RACK secondary_rack=$SECONDARY_RACK
```

Set default gateway:  
```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

### Set up a DHCP relay  

**CLI:**  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_VID_SRC relay_vlan=$VLAN_ID_TARGET
```

## DHCP snippets  

**Create global snippet:**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION global_snippet=true
```

**Create subnet snippet:**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION subnet=$SUBNET_ID
```

**Create node snippet:**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION node=$NODE_ID
```

**List snippets:**  
```bash
maas $PROFILE dhcpsnippets read
```

**Update snippet:**  
```bash
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID enabled=false
```

**Delete snippet:**  
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

**Single IP:**  
```bash
maas $PROFILE ipaddresses reserve ip_address=$IP_STATIC_SINGLE
```

**Dynamic range:**  
```bash
maas $PROFILE ipranges create type=dynamic start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH
```

**Reserved range:**  
```bash
maas $PROFILE ipranges create type=reserved start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH
```

## VLANs  

### Create VLAN  

```bash
maas admin vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
```

### Assign VLAN to interface  

```bash
maas admin interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID
```

### Delete VLAN  

```bash
maas $PROFILE vlan delete $FABRIC_ID $VLAN_ID
```

## NTP management  

### Use external NTP  

**UI:**  
*Settings > Network services > NTP > External Only > Add NTP server > Save*  

**CLI:**  
```bash
maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
maas $PROFILE maas set-config name=ntp_external_only value=true
```

## DNS management  

### Set DNS server  

```bash
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_DNS_SERVER
```

### Create DNS records  

**A record:**  
```bash
maas $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV4ADDRESS
```

**AAAA record:**  
```bash
maas $PROFILE dnsresources create fqdn=$HOSTNAME.$DOMAIN ip_addresses=$IPV6ADDRESS
```

### Set CNAME record  

```bash
maas $PROFILE dnsresource-records create fqdn=$HOSTNAME.$DOMAIN rrtype=cname rrdata=$ALIAS
```

**Example:**  
```bash
maas $PROFILE dnsresource-records create fqdn=webserver.maas.io rrtype=cname rrdata=www
```

### Set MX record  

```bash
maas $PROFILE dnsresource-records create fqdn=$DOMAIN rrtype=mx rrdata='10 $MAIL_SERVER.$DOMAIN'
```

**Example:**  
```bash
maas $PROFILE dnsresource-records create fqdn=maas.io rrtype=mx rrdata='10 smtp.maas.io'
```

### Set DNS forwarder  

```bash
maas $PROFILE maas set-config name=upstream_dns value=$MY_UPSTREAM_DNS
```

