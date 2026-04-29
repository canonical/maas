# Configure MAAS

This guide configures MAAS to enable the deployment of Machines. It assumes you have run the [install-maas](install-maas.md) guide previously and have the shell variable `PROFILE=<profile-name>` set.

## Configure DNS

Point MAAS to an upstream DNS server to resolve external hostnames. Use `8.8.8.8` for Google's public DNS server:

```bash
maas $PROFILE maas set-config name=upstream_dns value="8.8.8.8"
```

## Configure DHCP

In MAAS, rack controllers are responsible for serving DHCP leases to machines. To enable DHCP in MAAS, you need to pick a rack controller that will serve it. This rack controller must have a network interface that is connected to the VLAN of the subnet you want to boot machines from.

### Gather information

List all subnets in MAAS and identify the one you want to configure DHCP for:

```bash
maas $PROFILE subnets read | jq -r '
  ["subnet", "fabric ID", "vlan VID", "gateway IP"],
  (.[] | [ .cidr, (.vlan.fabric_id|tostring), (.vlan.vid|tostring), (.gateway_ip // "-")])
  | @tsv
' | column -t -s $'\t'
```

Set variables from your chosen subnet's output:

```bash
FABRIC_ID=<fabric_id>
VID=<vlan_vid>
SUBNET_CIDR=<subnet_cidr>
```

List the rack controllers that have an interface connected to the VLAN of your chosen subnet:

```bash
maas $PROFILE rack-controllers read | jq -r --argjson f "$FABRIC_ID" --argjson v "$VID" '
  (["SYSTEM_ID", "HOSTNAME"] | @tsv),
  (.[] | select(any(.interface_set[]; .vlan.fabric_id == $f and .vlan.vid == $v))
       | [.system_id, .hostname] | @tsv)
' | column -t -s $'\t'
```

Set the system ID of the rack controller you want to use:

```bash
PRIMARY_RACK_CONTROLLER=<system_id>
```

### Apply configuration

Assign a dynamic IP range to the subnet. Choose a start and end IP address within the subnet for MAAS to use for DHCP:

```bash
maas $PROFILE ipranges create subnet=$SUBNET_CIDR type=dynamic start_ip=<start_ip> end_ip=<end_ip>
```

Enable DHCP on the VLAN you selected:

```bash
maas $PROFILE vlan update $FABRIC_ID $VID dhcp_on=True primary_rack=$PRIMARY_RACK_CONTROLLER
```

Set the gateway IP for the subnet. This can be any IP address in the subnet, typically the first IP address in the range:

```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=<gateway_ip>
```

DHCP and gateway configuration is now complete for your subnet. Machines connected to this subnet will be able to automatically obtain IP addresses and network configuration via DHCP.
