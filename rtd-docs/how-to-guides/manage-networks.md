# Manage networks

MAAS provides pre-configured [networks](explanation/networking.md) for convenience. You can reconfigure these networks to match your environment.

This page shows you how to:

- Manage subnets (the foundation of IP allocation).
- Create and use VLANs.
- Allocate and reserve IP addresses.
- Configure and maintain interfaces (NICs, bonds, bridges).
- Use network discovery to detect devices.
- Apply advanced patterns such as dual NICs and loopbacks.

## Cheat sheet: common networking commands

Here are the most common MAAS networking commands at a glance. Use this cheat sheet if you just need the basics. The sections below provide full detail and context.

```bash
# Subnets
maas $PROFILE subnets read
maas $PROFILE subnet update $SUBNET_CIDR managed=true

# VLANs
maas $PROFILE vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
maas $PROFILE interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID

# IP addresses
maas $PROFILE ipaddresses reserve ip=$IP_ADDRESS
maas $PROFILE ipranges create type=dynamic subnet=$SUBNET start_ip=$LOW end_ip=$HIGH

# Interfaces
maas $PROFILE interfaces read $SYSTEM_ID
maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID key=value...

# Routes
maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID subnet=$SUBNET_ID mode=STATIC ip_address=10.0.0.101

# Discovery
maas $PROFILE maas set-config name=network_discovery value=enabled
```

## Manage subnets

Subnets are the building blocks for all networking in MAAS. You’ll use them to assign addresses, set gateways, and control routing.

### View and edit subnets

UI
*Networking > Subnets > (Select subnet)*

CLI

```bash
maas $PROFILE subnets read
maas $PROFILE subnet read $SUBNET_ID
```

### Enable or disable subnet management

```bash
maas $PROFILE subnet update $SUBNET_CIDR managed=true   # enable
maas $PROFILE subnet update $SUBNET_CIDR managed=false  # disable
```

### Configure DNS servers

```bash
maas $PROFILE subnet update $SUBNET_CIDR dns_servers=$DNS_SERVER_IPS
```

### Add static routes

```bash
maas $PROFILE static-routes create source=$SOURCE_SUBNET destination=$DEST_SUBNET gateway_ip=$GATEWAY_IP
```

## Manage VLANs

VLANs let you segment networks for isolation, PXE booting, or multi-tenancy.

### Create a VLAN

```bash
maas $PROFILE vlans create $FABRIC_ID name=$VLAN_NAME vid=$VLAN_ID
```

### Assign a VLAN to an interface

```bash
maas $PROFILE interfaces create-vlan $SYSTEM_ID vlan=$VLAN_ID parent=$INTERFACE_ID
```

### Delete a VLAN

```bash
maas $PROFILE vlan delete $FABRIC_ID $VLAN_ID
```

## Manage IP addresses

You can reserve addresses for static or dynamic use.

### Reserve a single IP

```bash
maas $PROFILE ipaddresses reserve ip=$IP_ADDRESS_STATIC_SINGLE
```

### Reserve a dynamic range

```bash
maas $PROFILE ipranges create type=dynamic subnet=$SUBNET_ADDRESS   start_ip=$IP_DYNAMIC_RANGE_LOW end_ip=$IP_DYNAMIC_RANGE_HIGH
```

### Reserve a static range

```bash
maas $PROFILE ipranges create type=reserved subnet=$SUBNET_ADDRESS   start_ip=$IP_STATIC_RANGE_LOW end_ip=$IP_STATIC_RANGE_HIGH
```

### Configure static IP via netplan (post-deploy)

Edit `/etc/netplan/50-cloud-init.yaml`:

```yaml
network:
  ethernets:
    ens160:
      addresses:
        - 192.168.0.100/24
      gateway4: 192.168.0.1
      nameservers:
        addresses: [8.8.8.8, 8.8.4.4]
```

Apply with:

```bash
sudo netplan apply
```

## Manage interfaces

Interfaces control how machines connect to subnets. MAAS supports physical NICs, VLANs, bonds, and bridges. Most changes require the machine to be in `Ready` or `Broken` state.

### View and maintain interfaces

- List interfaces:

  ```bash
  maas $PROFILE interfaces read $SYSTEM_ID
  ```

- View one interface:

  ```bash
  maas $PROFILE interface read $SYSTEM_ID $INTERFACE_ID
  ```

- Update interface:

  ```bash
  maas $PROFILE interface update $SYSTEM_ID $INTERFACE_ID key=value...
  ```

- Delete interface:

  ```bash
  maas $PROFILE interface delete $SYSTEM_ID $INTERFACE_ID
  ```

### Common interface types

- Physical (detected during commissioning)
- VLAN (virtual interface tied to a parent NIC and VLAN ID)
- Bond (group NICs for redundancy or throughput)
- Bridge (share NICs with VMs/containers or route traffic)

Each has UI and CLI creation commands. See [interface reference](reference/cli-reference/interface.md) for details.

## Manage routes and links

- Disconnect interface:

  ```bash
  maas $PROFILE interface disconnect $SYSTEM_ID $INTERFACE_ID
  ```

- Link interface to subnet:

  ```bash
  maas $PROFILE interface link-subnet $SYSTEM_ID $INTERFACE_ID     mode=STATIC subnet=$SUBNET_ID ip_address=10.0.0.101
  ```

- Unlink interface:

  ```bash
  maas $PROFILE interface unlink-subnet $SYSTEM_ID $INTERFACE_ID
  ```

- Set default gateway:

  ```bash
  maas $PROFILE subnet update $SUBNET_CIDR gateway_ip=$MY_GATEWAY
  ```

## Tag interfaces

Tags help classify interfaces for automation (e.g., `"uplink"`, `"pxe"`).

- Add tag:

  ```bash
  maas $PROFILE interface add-tag $SYSTEM_ID $INTERFACE_ID tag=my-tag
  ```

- Remove tag:

  ```bash
  maas $PROFILE interface remove-tag $SYSTEM_ID $INTERFACE_ID tag=my-tag
  ```

## Manage network discovery

Use discovery to detect devices on connected subnets.

- Enable:

  ```bash
  maas $PROFILE maas set-config name=network_discovery value=enabled
  ```

- Disable:

  ```bash
  maas $PROFILE maas set-config name=network_discovery value=disabled
  ```

- Clear all discoveries:

  ```bash
  maas $PROFILE discoveries clear all=true
  ```

You can fine-tune discovery (force re-scan, use ping, slow scan, limit threads) and filter results by unknown IP or MAC. See CLI reference for full commands.

## Advanced: dual NICs and loopbacks

- Dual NICs: Assign private and public roles to different NICs (e.g., internal DHCP + external static IP). Configure in MAAS or via netplan.
- Loopbacks: Add a loopback interface with a dummy MAC (`00:00:00:00:00:00`). Useful for routing or HA testing.

## Verify your changes

- Check the UI: Machines > Network tab should reflect changes.
- Confirm CLI reads show the expected subnets, bonds, or bridges.
- Use `ping` or `ip addr` on deployed machines to confirm connectivity.

## Next steps

- Explore [about MAAS networking](explanation/networking.md) for deeper context.
- Investigate [how to tune MAAS network services](how-to-guides/manage-network-services.md) to improve performance or create special configurations.
- If you need redundancy, learn [how to manage high availability](how-to-guides/manage-high-availability.md).
