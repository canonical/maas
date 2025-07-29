MAAS-configured network services simplify deployment and reduce setup friction by automating DHCP, DNS, and time sync. But while enabling these services is straightforward, it helps to understand when, why, and how to configure them --- especially in environments where external services already exist or where high availability matters.

This guide walks through MAAS-managed DHCP, DNS, NTP, and network snippets, offering both UI and CLI examples ---  along with a quick breakdown of the risks and trade-offs for each.

MAAS can provide DHCP for each VLAN it manages, allowing automated address assignment during machine enlistment, commissioning, and deployment. This eliminates the need for an external DHCP server — but you must ensure **only one DHCP service** is active on any given subnet to avoid conflicts.

## Enable MAAS DHCP

Generally, only use this when MAAS is the only DHCP provider for the VLAN.  You can have more than one DHCP server, but there are some conditions.

**UI:**
*Subnets > (Select VLAN) > Configure DHCP > Fill in fields > Configure DHCP*

**CLI:**
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_ID dhcp_on=True primary_rack=$PRIMARY_RACK
```

Enabling MAAS DHCP on a VLAN already served by another DHCP server (like your router or a VM host) can lead to conflicts and failed deployments.   

### An example

Let's say you're using both MAAS DHCP and a relay from your corporate DHCP server.  You're suprised to find that machines PXE boot intermittently.  

In this case, the corporate DHCP server may not be setting DHCP Option 66 (TFTP server) or Option 67 (Network Boot Package filename).  As a result, if a machine accepts an offer from your DHCP relay, it has an IP address, but it can't go any farther because it doesn't know that it's supposed to do so.   To make this configuration work, you'd need to add the IP address of the TFTP server as Option 66 for your corporate DHCP server, and the name of a valid NBP file as Option 67.  

### Enable DHCP for HA

Use this approach when you want failover across two rack controllers.

```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_ID \
  dhcp_on=True primary_rack=$PRIMARY_RACK secondary_rack=$SECONDARY_RACK
```

This enables ISC DHCP failover between two racks. You’ll still need to configure lease syncing manually if you're customizing the DHCP config directly.

### Set up a DHCP relay

Use this when DHCP must be relayed from one VLAN to another — common in enterprise environments where routing rules or firewall policies segment traffic.

**UI:**
*Subnets > (Select VLAN) > Configure DHCP > Relay to another VLAN > Select > Configure*

**CLI:**
```bash
maas $PROFILE vlan update $FABRIC_ID $VLAN_VID_SRC relay_vlan=$VLAN_ID_TARGET
```

## Manage DHCP snippets

Use snippets to customize the DHCP configuration — globally, per-subnet, or per-node. This is useful when:

* You need to inject custom options (like PXE boot settings)
* You’re integrating with existing infrastructure
* You need fine-grained control over leases or classes

Note that malformed snippets can break DHCP service on the rack controller. Always test in a development environment first.

## Manage NTP

If your machines need to maintain accurate time (they usually do), MAAS can configure NTP automatically using its own services or upstream servers. This helps with:

* Certificate trust
* Coordinated logs
* PXE boot sanity

### Use External NTP

Use this when MAAS should not act as an NTP server (e.g., you're using chrony, or a centralized NTP pool).

```bash
maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
maas $PROFILE maas set-config name=ntp_external_only value=true
```

## Manage DNS

MAAS runs an internal DNS server to track nodes, domains, and records. This works best when MAAS owns the DNS zone (e.g., `maas.internal`) or when integrated into your broader DNS setup via forwarders.

### Create a DNS resource

Use this when you want MAAS to create an A or AAAA record for a node or IP.

You’ll need:

* A domain (from `maas domains read`)
* A hostname
* An IP address (or let MAAS pick one)

```bash
maas admin dnsresources create name=webserver domain=example.com ip_addresses=192.168.1.100
```

You can also use a full FQDN:

```bash
maas admin dnsresources create fqdn=webserver.example.com ip_addresses=192.168.1.100
```

### Set a DNS server for a subnet

This lets you override the default MAAS DNS for a specific subnet.

```bash
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_DNS_SERVER
```

### Set a DNS forwarder

Use this if MAAS should forward DNS queries it can’t resolve.

```bash
maas $PROFILE maas set-config name=upstream_dns value=$MY_UPSTREAM_DNS
```
