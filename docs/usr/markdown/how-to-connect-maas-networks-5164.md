> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/connecting-maas-networks" target = "_blank">Let us know.</a>*

## Network discovery

Network discovery scans your environment to identify all connected devices, including non-deployable devices such as routers and switches.

### UI
* **In MAAS 3.4 (and above) UI**:
   1. Navigate to **Networking > Network discovery > Configuration**.
   2. In the **Network discovery** drop-down, choose “Enabled” or “Disabled”.
   3. Save your changes.
   
* **All other versions**:
   1. Navigate to **Canonical MAAS > Configuration**.
   2. In the **Network discovery** drop-down, choose “Enabled” or “Disabled”.
   3. Save your changes.

### CLI
To enable network discovery via CLI:
```bash
maas $PROFILE maas set-config name=network_discovery value="enabled"
```

## Static routes

Static routes allow traffic between different subnets or through specific gateways.

### UI
* **In MAAS 3.4 (and above) UI**:
   1. Navigate to **Networking > Subnets > Subnet summary > Add static route**.
   2. Enter **Gateway IP address**, **Destination subnet**, and routing **Metric**.
   3. Save your changes.

* **For older versions**:
   1. Navigate to **Subnets > Add static route**.
   2. Enter the **Gateway IP address**, **Destination subnet**, and routing **Metric**.
   3. Click **Add** to save the route.

### CLI
To create a static route via CLI:
```bash
maas admin static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
```

## Configure loopback

Configuring the loopback interface (lo) is essential for advanced networking tasks such as Free Range Routing (FRR) and BGP.

* **Manually add the loopback interface**:
   - After commissioning a node, manually add the loopback interface in MAAS.
   - You may use a placeholder MAC address (e.g., 00:00:00:00:00:00) for the loopback interface.
   
* **Use post-deployment scripts**:
   - If needed, use tools like `cloud-init` to configure the loopback interface after deployment.

## Bridging

Bridges enable multiple network interfaces to act as one.

### UI

1. Navigate to **Machines > machine > Network > Create bridge**.
2. Configure details and save the interface.

### CLI

   ```bash
   INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
   BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
   SUBNET_ID=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24" and .managed == true).id')
   maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
   ```

## Bridging with [Netplan](https://netplan.readthedocs.io/en/stable/)

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

## Configure two NICs on one machine

To set up a machine with two NICs—one for a private subnet and one for the public internet—follow these steps.

### UI
1. **Detect both NICs**:
   - Ensure MAAS detects both network interfaces (e.g., `ens18` and `ens19`).
   
2. **Private NIC (ens18)**:
   - Set to **DHCP** on the private subnet (e.g., 192.168.10.0/24).
   
3. **Public NIC (ens19)**:
   - Manually configure or use DHCP for the public subnet (e.g., 192.168.1.0/24).

### Netplan Example
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

## VLANs

### Create VLANs
To create a VLAN:
```bash
maas admin vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
```

### Assign VLAN to an interface
To assign a VLAN to an interface:
```bash
maas admin interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID
```

### Delete VLANs
To delete a VLAN:
```bash
maas $PROFILE vlan delete $FABRIC_ID $VLAN_ID
```

## Set the default gateway

To set the default gateway for a subnet:
```bash
maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
```

## Set up DNS

To configure DNS servers:
```bash
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$MY_DNS_SERVER
```

## Create bonds

Bonds allow multiple network interfaces to act together for redundancy or performance.

### UI

1. **Select multiple interfaces** and choose **Create bond**.
2. **Choose a bond mode** such as:
   - **balance-rr**: Round-robin transmission.
   - **active-backup**: Only one active follower; failover to another upon failure.
   - **balance-xor**: Transmit based on hash policy.

### CLI
To create a bond via CLI:
```bash
maas $PROFILE interfaces create-bond $SYSTEM_ID name=$BOND_NAME parents=$IFACE1_ID,$IFACE2_ID bond_mode=$BOND_MODE
```

## Managing NTP

### Use external NTP
* **UI**:
   1. Go to **Settings > Network services > NTP**.
   2. Select **External Only** and enter your desired NTP server.

*  **CLI**:
   ```bash
   maas $PROFILE maas set-config name=ntp_servers value=$NTP_IP_ADDRESS
   maas $PROFILE maas set-config name=ntp_external_only value=true
   ```

## Netplan static IP configuration

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

## Create a reserved IP range

* **UI:**
    1. Navigate to *Subnets* > <subnet> > *Reserved Ranges* > *Add Reserved Range*.
    2. Define start/end IP address and purpose (optional).
    3. *Save* the results.
    4. Verify the new reserved range is now in the list.

* **CLI:**

```bash
maas $PROFILE ipranges create type=reserved start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH comment='Reserved range'
```

## Create a dynamic IP range

```bash
maas $PROFILE ipranges create type=dynamic start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH comment='Reserved dynamic range'
```

## Create a single reserved IP

```bash
maas $PROFILE ipaddresses reserve ip_address=$IP_STATIC_SINGLE
```

## Edit an IP range

* **UI:**
  1.  Select *Subnet* > *Edit reserved range*.
  2. Update and save.

* **CLI:**

 1. Find range ID: 
```bash
maas admin ipranges read
```
  2. Update range:

```bash
maas admin iprange update $ID start_ip="<start ip>" end_ip="<end ip>" comment="freeform comment"
```

## Delete an IP range

* Select *Subnet* > <subnet>.
* Select *Remove range*.