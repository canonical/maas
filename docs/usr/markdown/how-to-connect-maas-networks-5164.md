> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/connecting-maas-networks" target = "_blank">Let us know.</a>*

## Network discovery

Network discovery scans your environment to identify all connected devices, including non-deployable devices such as routers and switches. To enable or disable discovery:

* In the MAAS 3.4 UI, select *Networking* > *Network discovery* > *Configuration*; in the *Network discovery* drop-down, choose "Enabled" or "Disabled"; *Save* your changes.

* For all other MAAS UI versions, select *Canonical MAAS* > *Configuration*; in the *Network discovery* drop-down, choose "Enabled" or "Disabled"; *Save* your changes.

* In the MAAS CLI, enter the following command:

```nohighlight
    maas $PROFILE maas set-config name=network_discovery value="enabled"
```

## Managed allocation

Allocation of IP addresses and subnet routes can be MAAS-managed or manual.

* For the MAAS UI, choose *Subnets* > <subnet to be changed> > *Edit* > *Managed allocation* > *Save*.

* Using the CLI to toggle subnet management, enter this command, using the subnet ID in place of CIDR, if desired:

```nohighlight
    maas $PROFILE subnet update $SUBNET_CIDR managed=false|true
```

## Network panel (UI only)

In the MAAS UI, the network dashboard displays everything MAAS knows about its connected networks:

* In the 3.4 UI, select *Networking > Subnets* to access the dashboard. This view can also be filtered with the 'Filters' drop-down.

* For all other MAAS versions, select *Subnets* to access the dashboard. This view can also be filtered via the *Group by* drop-down.

While in the network panel:

* Select a subnet to view its details. 

* Subnet utilisation figures are near the bottom. 

* Near the bottom of the Subnet summary, you can manage reserved IP ranges. 

* At the very bottom of the Subnet summary, you can track DHCP snippets and used IP addresses.

## Static routes

You can create static IP routes as desired.

* With the MAAS 3.4 UI, select *Networking > Subnets* > <IP of subnet to be changed> > *Subnet summary* > *Add static route*; enter a *Gateway IP* address, *Destination* subnet, and routing *Metric*. Don't forget to *Save*.

* Using the UI for all other MAAS versions, choose *Add static route*; enter a *Gateway IP* address, *Destination* subnet, and routine *Metric*; click 'Add' to activate the route. Routes can be edited and removed using the icons to the right of each entry.

* With the CLI, it's simple create a static route between two subnets:

```nohighlight
    maas admin static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET \
    gateway_ip=$GATEWAY_IP
```

## Bridging

To configure a bridge with the MAAS UI, select *Machines* > machine > *Network* > hosting network > *Create bridge* > details > *Save interface*. You can then deploy machines using this bridge. Note that you can create an "Open switch" bridge if desired, and MAAS will create the netplan model for you.

You can also use the MAAS CLI/API to configure a bridge via the following procedure:

1. Select the interface on which you wish to configure the bridge. This example uses the boot interface, since the boot interface must be connected to a MAAS controlled network -- but any interface is allowed:

```nohighlight
        INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
```

2. Create the bridge:

```nohighlight
         BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
```

3. Select the subnet where you want the bridge (this should be a MAAS controlled subnet):

```nohighlight
        SUBNET_ID=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24" and .managed == true).id')
```

4. Connect the bridge to the subnet:

```nohighlight
          maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
```

## Bridging with Netplan

Building a bridge with netplan is independent of MAAS UI or CLI. You can configure a bridge like this:

1. Open your netplan configuration file. This should be in `/etc/netplan`. It could be called `50-cloud-init.yaml`, `netplan.yaml`, or something else.

2. Modify the file to add a bridge, using the following example as a guide:

```nohighlight
    network:
        bridges:
            br0:
                addresses:
                - 10.0.0.101/24
                gateway4: 10.0.0.1
                interfaces:
                - enp1s0
                mac address: 52:54:00:39:9d:f9
                mtu: 1500
                name servers:
                    addresses:
                    - 10.0.0.2
                    search:
                    - maas
                parameters:
                    forward-delay: 15
                    stp: false
        Ethernet's:
            enp1s0:
                match:
                    mac address: 52:54:00:39:9d:f9
                mtu: 1500
                set-name: enp1s0
            enp2s0:
                match:
                    mac address: 52:54:00:df:87:ac
                mtu: 1500
                set-name: enp2s0
            enp3s0:
                match:
                    mac address: 52:54:00:a7:ac:46
                mtu: 1500
                set-name: enp3s0
        version: 2
```
    
3. Apply the new configuration with `netplan apply`.

## Find fabric IDs (CLI)

You'll need the "fabric ID" to manipulate some networking parameters in the CLI. To determine a fabric ID based on a subnet address:

```nohighlight
    FABRIC_ID=$(maas $PROFILE subnet read $SUBNET_CIDR \
        | grep fabric | cut -d ' ' -f 10 | cut -d '"' -f 2)
```
    
This may come in handy when you need a fabric ID for other CLI calls.

## Set the default gateway (CLI)

To set the default gateway for a subnet, just use this command:

```nohighlight
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

## Set up DNS (CLI)

You can set the DNS server for a subnet very easily, with the CLI, like this:

```nohighlight
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_NAME SERVER
```

## List subnets (CLI)

From time to time, you may want to view the list of available subnets. Do that with the following command:

```nohighlight
maas admin subnets read | \
jq -r '(["FABRIC", "VLAN", "DHCP", "SUBNET"]
| (., map(length*"-"))),
(.[] | [.vlan.fabric, .vlan.name, .vlan.dhcp_on, .cidr])
| @tsv' \
| column -t
```

## View subnet details (CLI)

Via the CLI, you can view the details of an individual subnet with the command:

```nohighlight
maas $PROFILE subnet read $SUBNET_ID \
| jq -r '(["NAME","CIDR","GATEWAY","DNS","DISCOVERY","FABRIC","VLAN"]
| (., map(length*"-"))), ([.name,.cidr,.gateway_ip // "-", .allow_dns,.active_discovery,.vlan.name,.vlan.fabric]) | @tsv' | column -t
```

Look up the subnet ID like this:

```nohighlight
maas $PROFILE subnets read \
| jq -r '(["NAME", "SUBNET_ID"]
| (., map(length*"-"))), (.[] | [.name, .id]) | @tsv' \
| column -t | grep $SUBNET_NAME
```

For example, using the "admin" profile with a subnet name containing "192.168.123," find the subnet ID with this command:

```nohighlight
maas admin subnets read \
| jq -r '(["NAME", "SUBNET_ID"]
| (., map(length*"-"))), (.[] | [.name, .id]) | @tsv' \
| column -t | grep 192.168.123
```

## Edit machine interfaces

To edit a machine interface via the 3.4 UI, select *Machines* > machine > *Network* > interface > *Actions* > *Edit physical* > edit parameters > select *IP mode* > *Save interface*.

To edit a machine interface with the UI for all other MAAS versions, select *Machines* > machine > *Interfaces* > interface icon > *Edit Physical* > *IP mode* > *Save*.

To edit the IP assignment mode of a network interface with the CLI, perform the following steps:

1. Find the interface ID and subnet link ID with the command:

```nohighlight
    maas $PROFILE node read $SYSTEM_ID
```
    
2. Unlink the old interface:

```nohighlight
    maas $PROFILE interface unlink-subnet $SYSTEM_ID $INTERFACE_ID id=$SUBNET_LINK_ID
```
    
3. Link the new interface:

```nohighlight
    maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID mode=$IP_MODE subnet=$SUBNET_CIDR [$OPTIONS]
```
    
See [the glossary](/t/reference-maas-glossary/5416) for the definitions of reserved range types.

## Create bonds

To create bonds with the MAAS UI, select more than one interface > *Create bond* > rename bond > select mode as follows: 

-   **balance-rr**: Transmit packets in sequential order from the first available follower through to the last. This mode provides load balancing and fault tolerance.

-   **active-backup**: Only one follower in the bond is active. A different follower becomes active if, and only if, the active follower fails. The bond's MAC address is externally visible on only one port (network adaptor) to avoid confusing the switch.

-   **balance-xor**: Transmit based on the selected transmit hash policy. The default policy is simple, which means that an XOR operation selects packages. This XOR compares the source MAC address and the resultant XOR between the destination MAC address, the packet type identifier, and the modulo follower count.

-   **broadcast**: Transmit everything on all follower interfaces. This mode provides fault tolerance.

-   **802.3ad**: Creates aggregation groups that share the same speed and duplex settings. This mode utilises all followers in the active aggregation, following the IEEE 802.3ad specification.

-   **balance-tlb**: Adaptive transmit load balancing, channel bonding that does not require any special switch support.

-   **balance-alb**: Adaptive load balancing, includes balance-tlb plus receive load balancing (rlb) for IPV4 traffic. This mode does not require any special switch support. ARP negotiation achieves load balancing in this case.

Having selected a mode, to finish up, assign a *MAC address* > attach *Tags* > select *Primary* > *Save*.

> The MAC address defaults to the MAC address of the primary interface.

To create a bond with the MAAS CLI, execute the following command:

```nohighlight
maas $PROFILE interfaces create-bond $SYSTEM_ID name=$BOND_NAME \
parents=$IFACE1_ID mac_address=$MAC_ADDR \ 
parents=$IFACE2_ID bond_mode=$BOND_MODE \
bond_updelay=$BOND_UP bond_downdelay=$BOND_DOWN mtu=$MTU
```
Note that: 

- The `parents` parameters define which interfaces form the aggregate interface.

- The `bond_updelay` and `bond_downdelay` parameters specify the number of milliseconds to wait before either enabling or disabling a follower after a failure has been detected.

- There are a wide range of bond parameters you can choose when creating a bond:

| Parameter | Type and description |
|:----------|:---------------------|
| `mac_address`| Optional string. MAC address of the interface. |
| `tags`| Optional string. Tags for the interface. |
| `vlan`| Optional string. VLAN the interface is connected to. If not provided then the interface is considered disconnected. |
| `parents`| Required integer. Parent interface ids that make this bond. |
| `bond_miimon`| Optional integer. The link monitoring frequency in milliseconds. (Default: 100). |
| `bond_downdelay`| Optional integer. Specifies the time, in milliseconds, to wait before disabling a follower after a link failure has been detected. |
| `bond_updelay`| Optional integer. Specifies the time, in milliseconds, to wait before enabling a follower after a link recovery has been detected. |
| `bond_lacp_rate`| Optional string. Option specifying the rate at which to ask the link partner to transmit LACPDU packets in 802.3ad mode. Available options are ``fast`` or ``slow``. (Default: ``slow``). |
| `bond_xmit_hash_policy`| Optional string. The transmit hash policy to use for follower selection in balance-xor, 802.3ad, and tlb modes. Possible values are: ``layer2``, ``layer2+3``, ``layer3+4``, ``encap2+3``, ``encap3+4``. (Default: ``layer2``) |
| `bond_num_grat_arp`| Optional integer. The number of peer notifications (IPv4 ARP or IPv6 Neighbour Advertisements) to be issued after a failover. (Default: 1) |
| `mtu`| Optional integer. Maximum transmission unit. |
| `accept_ra`| Optional Boolean. Accept router advertisements. (IPv6 only) |
| `autoconf`| Optional Boolean. Perform stateless autoconfiguration. (IPv6 only) |
| `bond_mode`| Optional string. The operating mode of the bond. (Default: active-backup). |

- Supported bonding modes include:

| Mode | Behaviour |
|:-----|:---------|
|  `balance-rr`:| Transmit packets in sequential order from the first available follower through the last. This mode provides load balancing and fault tolerance. |
|  `active-backup`| Only one follower in the bond is active. A different follower becomes active if, and only if, the active follower fails. The bond's MAC address is externally visible on only one port (network adaptor) to avoid confusing the switch. |
|  `balance-xor`| Transmit based on the selected transmit hash policy. The default policy is a simple [(source MAC address XOR'd with destination MAC address XOR packet type ID) modulo follower count]. |
|  `broadcast`| Transmits everything on all follower interfaces. This mode provides fault tolerance. |
|  `802.3ad`| IEEE 802.3ad dynamic link aggregation. Creates aggregation groups that share the same speed and duplex settings. Uses all followers in the active aggregator according to the 802.3ad specification. |
|  `balance-tlb`| Adaptive transmit load balancing: channel bonding that does not require any special switch support. |
|  `balance-alb`| Adaptive load balancing: includes balance-tlb plus receive load balancing (rlb) for IPV4 traffic, and does not require any special switch support. The receive load balancing is achieved by ARP negotiation. |

## Create bridges

To create a bridge interface via the MAAS UI:

1. Select *Machines* > machine > *Network* > interface > *Create bridge*.

2. Define *Bridge type*, *MAC address*, *Fabric*, and *VLAN*.

3. Optionally define *Bridge name*, *Subnet*, *Tags* and turn on *STP*.

4. Register your new bridge by selecting *Save interface*.

To create a bridge interface with the CLI:

```nohighlight
maas $PROFILE interfaces create-bridge $SYSTEM_ID name=$BRIDGE_NAME \
parent=$IFACE_ID
```

Use `parent` to define the primary interface used for the bridge:

```nohighlight
maas admin interfaces create-bridge 4efwb4 name=bridged0 parent=4
```

The following parameters may be applied when creating a bridge:

- `name`: Optional string. Name of the interface.

- `mac_address`: Optional string. MAC address of the interface.

- `tags`: Optional string. Tags for the interface.

- `vlan`: Optional string. VLAN the interface is connected to.

- `parent`: Optional integer. Parent interface id for this bridge interface.

- `bridge_type`: Optional string. The type of bridge to create. Possible values are: ``standard``, ``ovs``.

- `bridge_stp`: Optional Boolean. Turn spanning tree protocol on or off. (Default: False).

- `bridge_fd`: Optional integer. Set bridge forward delay to time seconds. (Default: 15).

- `mtu`: Optional integer. Maximum transmission unit.

- `accept_ra`: Optional Boolean. Accept router advertisements. (IPv6 only)

- `autoconf`: Optional Boolean. Perform stateless autoconfiguration. (IPv6 only)

## Delete an interface (CLI)

Interfaces can only be deleted via the CLI. The "delete" command can be used to delete a bridge interface, a bond interface or a physical interface:

```nohighlight
maas $PROFILE interface delete $SYSTEM_ID $IFACE_ID
```

For example:

```nohighlight
maas admin interface delete 4efwb4 15
```

The following is output after the successful deletion of an interface:

```nohighlight
Success.
Machine-readable output follows:
```

Note that while the label is presented, there is no machine-readable output expected after the successful execution of the delete command.

## Assign an interface (CLI)

You can only assign an interface to a fabric with the MAAS CLI. This task is made easier with the aid of the `jq` utility. It filters the `maas` command (JSON formatted) output and prints it in the desired way, which allows you to view and compare data quickly. Go ahead and install it:

```nohighlight
sudo apt install jq
```

In summary, MAAS assigns an interface to a fabric by assigning it to a VLAN. First, we need to gather various bits of data.

List some information on all machines:

```nohighlight
maas $PROFILE machines read | jq ".[] | \
    {hostname:.hostname, system_id: .system_id, status:.status}" --compact-output
```

Example output:

```nohighlight
{"hostname":"machine1","system_id":"dfgnnd","status":4}
{"hostname":"machine2","system_id":"bkaf6e","status":6}
{"hostname":"machine4","system_id":"63wqky","status":6}
{"hostname":"machine3","system_id":"qwkmar","status":4}
```


You can only edit an interface when the corresponding machine has a status of 'Ready'. This state is numerically denoted by the integer '4'.


List some information for all interfaces on the machine in question (identified by its system id 'dfgnnd'):

```nohighlight
maas $PROFILE interfaces read dfgnnd | jq ".[] | \
    {id:.id, name:.name, mac:.mac_address, vid:.vlan.vid, fabric:.vlan.fabric}" --compact-output
```

Example output:

```nohighlight
{"id":8,"name":"eth0","mac":"52:54:00:01:01:01","vid":0,"fabric":"fabric-1"}
{"id":9,"name":"eth1","mac":"52:54:00:01:01:02","vid":null,"fabric":null}
```

List some information for all fabrics:

```nohighlight
maas $PROFILE fabrics read | jq ".[] | \
    {name:.name, vlans:.vlans[] | {id:.id, vid:.vid}}" --compact-output
```

Example output:

```nohighlight
{"name":"fabric-0","vlans":{"id":5001,"vid":0}}
{"name":"fabric-1","vlans":{"id":5002,"vid":0}}
{"name":"fabric-2","vlans":{"id":5003,"vid":0}}
```

This example will show how to move interface '8' (on machine 'dfgnnd') from 'fabric-1' to 'fabric-0'. Based on the gathered information, this will consist of changing the interface's VLAN from '5002' to '5001':

```nohighlight
maas $PROFILE interface update dfgnnd 8 vlan=5001 >/dev/null
```

Verify the operation by relisting information for the machine's interface:

```nohighlight
maas $PROFILE interfaces read dfgnnd | jq ".[] | \
    {id:.id, name:.name, mac:.mac_address, vid:.vlan.vid, fabric:.vlan.fabric}" --compact-output
```

The output shows that the interface is now on fabric-0:

```nohighlight
{"id":8,"name":"eth0","mac":"52:54:00:01:01:01","vid":0,"fabric":"fabric-0"}
{"id":9,"name":"eth1","mac":"52:54:00:01:01:02","vid":null,"fabric":null}
```

## Discover identifiers (CLI)

Interface identifiers can only be discovered via the MAAS CLI. The MAAS CLI uses a numeric interface identifier for many interface operations. Use the following command to retrieve the identifier(s):

```nohighlight
maas $PROFILE interfaces read $SYSTEM_ID
```

Look for either id or the number at the end of an interface's resource URI, such as **15** in the following example output:

```nohighlight
"id": 15,
"mac_address": "52:54:00:55:06:40",
...
"name": "ens9",
...
"resource_uri": "/MAAS/api/2.0/nodes/4efwb4/interfaces/15/"
```

## Create VLANs (CLI)

VLAN interfaces can only be created via the MAAS CLI. To create a VLAN interface, use the following syntax:

```nohighlight
maas $PROFILE vlans create $FABRIC_ID name=$NAME vid=$VLAN_ID
```

For example, the following command creates a VLAN called 'Storage network:

```nohighlight
maas admin vlans create 0 name="Storage network" vid=100
```

The above command generates the following output:

```nohighlight
Success.
Machine-readable output follows:
{
    "vid": 100,
    "mtu": 1500,
    "dhcp_on": false,
    "external_dhcp": null,
    "relay_vlan": null,
    "name": "Storage network",
    "space": "undefined",
    "fabric": "fabric-0",
    "id": 5004,
    "primary_rack": null,
    "fabric_id": 0,
    "secondary_rack": null,
    "resource_uri": "/MAAS/api/2.0/vlans/5004/"
}
```

Be aware that the $VLAN_ID parameter does not indicate a VLAN ID that corresponds to the VLAN tag. You must first create the VLAN and then associate it with the interface:

```nohighlight
maas $PROFILE interfaces create-vlan $SYSTEM_ID vlan=$OUTPUT_VLAN_ID \
parent=$IFACE_ID
```

**OUTPUT_VLAN_ID** corresponds to the id value output when MAAS created the VLAN.

The following example contains values that correspond to the output above:

```nohighlight
maas admin interfaces create-vlan 4efwb4 vlan=5004 parent=4
```

The above command generates the following output:

```nohighlight
Success.
Machine-readable output follows:
{
    "tags": [],
    "type": "vlan",
    "enabled": true,
    "system_id": "4efwb4",
    "id": 21,
    "children": [],
    "mac_address": "52:54:00:eb:f2:29",
    "params": {},
    "vlan": {
        "vid": 100,
        "mtu": 1500,
        "dhcp_on": false,
        "external_dhcp": null,
        "relay_vlan": null,
        "id": 5004,
        "secondary_rack": null,
        "fabric_id": 0,
        "space": "undefined",
        "fabric": "fabric-0",
        "name": "Storage network",
        "primary_rack": null,
        "resource_uri": "/MAAS/api/2.0/vlans/5004/"
    },
    "parents": [
        "ens3"
    ],
    "effective_mtu": 1500,
    "links": [
        {
            "id": 55,
            "mode": "link_up"
        }
    ],
    "discovered": null,
    "name": "ens3.100",
    "resource_uri": "/MAAS/api/2.0/nodes/4efwb4/interfaces/21/"
}
```

## Deleting VLANs (CLI)

VLAN interfaces can only be deleted via the MAAS CLI. The following command outlines the syntax required to delete a VLAN interface from the command line:

```nohighlight
maas $PROFILE vlan delete $FABRIC__ID $VLAN_ID
```

Using the values from previous examples, you executed this step as follows:

```nohighlight
maas admin vlan delete 0 100
```

## Set up proxies

MAAS lets you set up a proxy for managed machines to access web resources. Your choices:

1. Internal proxy (default)
2. External proxy
3. No proxy

Toggle these options and control proxy use by subnet. This section will show you how.

To toggle the proxy in the MAAS UI, go to *Settings* > *Network services* > *Proxy*, and choose:

- To enable the internal proxy, ensure that the checkbox adjacent to 'MAAS Built-in' is selected. This internal proxy is the default configuration.

- To enable an external proxy, activate the 'External' checkbox and use the new field that is displayed to define the proxy's URL (and port if necessary).

- An upstream cache peer can be defined by enabling the 'Peer' checkbox and entering the external proxy URL into the field. With this enabled, machines will be configured to use the MAAS built-in proxy to download cached APT packages.

- To prevent MAAS machines from using a proxy, enable the 'Don't use a proxy' checkbox.

You can also toggle proxies with the CLI. Enabling and disabling proxies in the CLI is done via a Boolean option ('true' or 'false'). The following command will disable proxying completely:

```nohighlight
maas $PROFILE maas set-config name=enable_http_proxy value=false
```

To set an external proxy, ensure proxying is enabled (see above) and then define it:

```nohighlight
maas $PROFILE maas set-config name=http_proxy value=$EXTERNAL_PROXY
```

For example,

```nohighlight
maas $PROFILE maas set-config name=enable_http_proxy value=true
maas $PROFILE maas set-config name=http_proxy value=http://squid.example.com:3128/
```

Enabling and disabling proxying per subnet is also done via a Boolean option ('true' or 'false'). Here is how you can disable proxying on a per-subnet basis:

```nohighlight
maas $PROFILE subnet update $SUBNET_CIDR allow_proxy=false
```

For example,

```nohighlight
maas $PROFILE subnet update 192.168.0.0/22 allow_proxy=false
```

**NOTE** that the proxy service will still be running.

## Sync time with NTP

MAAS provides managed NTP services (with [Chrony](https://chrony.tuxfamily.org/)**^**) for all region and rack controllers. This arrangement allows MAAS to both keep its controllers synchronised, and keep deployed machines synchronised as well. You can configure NTP on the 'Network services' tab of the 'Settings' page. 

The region controller configures the NTP service to keep its time synchronised from one or more external sources. By default, the MAAS region controller uses `ntp.ubuntu.com`. Rack controllers also configure the NTP service, synchronising their time with the region controllers. Rack controllers also configure DHCP with the correct NTP information, so that the DHCP servers can manage the NTP clients for the rack. Any machine on the network that obtains a DHCP lease from MAAS will benefit from NTP support.

## External NTP

External sites, such as an existing NTP infrastructure, can be used directly as a time source for both rack controllers and machines.

You can specify an external NTP site site with the MAAS UI by choosing the NTP server(s) and selecting the *External Only* option. To do so, go to *Settings* > *Network services* > *NTP* and enter the address of the desired NTP server.

Note that the region controller always uses an external site.

You can specify an external NTP server via the CLI, with two successive commands:

```nohighlight
maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
```

followed by:

```nohighlight
maas admin maas set-config name=ntp_external_only value=true
```