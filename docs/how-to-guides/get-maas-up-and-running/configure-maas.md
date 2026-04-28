# Configure MAAS

This guide configures MAAS to enable the deployment of Machines. It assumes you have run the [install-maas](install-maas.md) guide previously and have the shell variable `PROFILE=<profile-name>` set.

## Configure DNS

Point MAAS to an upstream DNS server to resolve external hostnames. Use `8.8.8.8` for Google's public DNS server:

```bash
maas $PROFILE maas set-config name=upstream_dns value="8.8.8.8"
```

## Configure DHCP

In MAAS, rack controllers are responsible for serving DHCP leases to machines. To enable DHCP in MAAS, you need need to pick a rack controller that will serve it. This rack controller must have a network interface that is connected to the VLAN of the subnet you want to boot machines from.

First, identify the subnet you would like to configure DHCP for, its corresponding fabric ID, and its VLAN VID from all available subnets in MAAS:

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

Assign a dynamic IP range to the subnet if one does not already exist:

```bash
START_IP=<start_ip>
END_IP=<end_ip>
maas $PROFILE ipranges create subnet=$SUBNET_CIDR type=dynamic start_ip=$START_IP end_ip=$END_IP
```

Identify the system ID of the rack controller that has an interface connected to the VLAN of your desired subnet:

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

Enable DHCP on the VLAN you selected:

```bash
maas $PROFILE vlan update $FABRIC_ID $VID dhcp_on=True primary_rack=$PRIMARY_RACK_CONTROLLER
```

Set the gateway IP for the subnet you selected, which can be any IP address in the subet, typically the first IP address in the range:

```bash
MY_GATEWAY=<gateway_ip>
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

You can now boot machines from the subnet you have configured DHCP and a gateway IP for.
