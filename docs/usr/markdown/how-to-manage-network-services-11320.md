MAAS-configured network services reduce friction by eliminating setup challenges.

## Manage DHCP
### Enable MAAS DHCP  

UI:**  
*Subnets > (Select VLAN) > Configure DHCP (Fill fields) > Configure DHCP*  

CLI:**  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_ID dhcp_on=True primary_rack=$PRIMARY_RACK
```

> *Note: Make sure you have the correct $VLAN_ID (vid in the help output).*

### Enable DHCP for HA

CLI**
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_ID dhcp_on=True primary_rack=$PRIMARY_RACK secondary_rack=$SECONDARY_RACK
```

> *Note: Make sure you have the correct $VLAN_ID (vid in the help output).*

### Set up a DHCP relay  

UI**
*Subnets > (Select VLAN) > Configure DHCP > Relay to another VLAN > (Select VLAN) >  Configure DHCP*

CLI:**  
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_VID_SRC relay_vlan=$VLAN_ID_TARGET
```

## Manage DHCP snippets

### Create snippets

UI**
*Settings > DHCP snippets > Add snippet > (Fill fields) > Save snippet*

CLI (global snippet)**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION global_snippet=true
```

CLI (subnet snippet)**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION subnet=$SUBNET_ID
```

CLI (node snippet)**  
```bash
maas $PROFILE dhcpsnippets create name=$DHCP_SNIPPET_NAME value=$DHCP_CONFIG description=$DESCRIPTION node=$NODE_ID
```

### List snippets

UI**
*Settings > DHCP snippets*

CLI**
```bash
maas $PROFILE dhcpsnippets read
```

### Update a snippet

UI**
*Settings > DHCP snippets > Actions > Pencil icon (edit) > (Edit snippet) > Save snippet*

```bash
maas $PROFILE dhcpsnippet update $DHCP_SNIPPET_ID enabled=false
```

### Delete a snippet

UI**
*Settings > DHCP snippets > Actions > Trash can icon (delete) > Delete*

CLI**
```bash
maas $PROFILE dhcpsnippet delete $DHCP_SNIPPET_ID
```

## Manage NTP

### Use external NTP  

UI:**  
*Settings > Network > NTP > (Fill in NTP address) > External Only > Save*  

CLI:**  
```bash
maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
maas $PROFILE maas set-config name=ntp_external_only value=true
```

## Manage DNS

Use the built-in, MAAS-configured DNS server to manage domains more efficiently. 

### Create a DNS resource

##### Prerequisites
- You have a running MAAS installation.
- You have administrative access to MAAS.
- You have at least one domain set up in MAAS.

##### Identify your domain
Each DNS resource needs a domain. You can find available domains in MAAS by running:
```sh
maas admin domains read
```
Look for the `id` or `name` of the domain you want to use.

##### Choose a hostname
Decide on the hostname for the new DNS record. You can either:
- Provide a fully qualified domain name (FQDN), e.g., `webserver.example.com`
- OR specify the `name` (hostname only) and the `domain` separately.

##### Assign an IP address (optional)
If you want to create an A (IPv4) or AAAA (IPv6) record, you need an IP address:
```sh
maas admin ipaddresses read
```
This lists available IP addresses in MAAS.

##### Create the DNS resource
Run the following command:
```sh
maas admin dnsresources create name=webserver domain=example.com ip_addresses=192.168.1.100
```
Alternatively, using an FQDN:
```sh
maas admin dnsresources create fqdn=webserver.example.com ip_addresses=192.168.1.100
```
This creates an A record for `webserver.example.com` pointing to `192.168.1.100`.

##### Verify the DNS resource
List all DNS resources:
```sh
maas admin dnsresources read
```
Ensure your new entry appears in the output.

### Set a DNS server  

UI**
*Settings > DNS > (Fill fields) > Save*

CLI**
```bash
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_DNS_SERVER
```

### Set a DNS forwarder  

CLI**
```bash
maas $PROFILE maas set-config name=upstream_dns value=$MY_UPSTREAM_DNS
```

