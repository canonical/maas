> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/how-to-manage-lxd-vms" target = "_blank">Let us know.</a>*  

This guide covers LXD VM host setup, management, and networking in MAAS.  

## Install & configure LXD

LXD setup is straightforward.

### Remove old LXD versions

```bash
sudo apt-get purge -y *lxd* *lxc*
sudo apt-get autoremove -y
```

### Install & initialize LXD

```bash
sudo snap install lxd
sudo snap refresh
sudo lxd init
```
- Clustering: `no`  
- Storage: `dir`  
- MAAS Connection: `no`  
- Existing Bridge: `yes` (`br0`)  
- Trust Password: Provide a password  

### Disable DHCP for LXD’s bridge

```bash
lxc network set lxdbr0 dns.mode=none
lxc network set lxdbr0 ipv4.dhcp=false
lxc network set lxdbr0 ipv6.dhcp=false
```

## Add a VM host  

**UI**
1. *KVM > LXD > Add LXD host > Enter Name, LXD address and select Generate new certificate*  
2. Run the provided command in the terminal to add trust.  
3. *Check authentication > Add new project | Select existing project > Save LXD host*.  

**CLI**
```bash
maas $PROFILE vm-hosts create type=lxd power_address=$LXD_ADDRESS project=$PROJECT_NAME
```

## Manage VMs

Virtual machines are needed for any VM host.

### Move VMs between projects  

  ```bash
  lxc move $VM_NAME $VM_NAME --project default --target-project $PROJECT_NAME
  ```

### Add VMs  

**UI**
*KVM > VM host name > Add VM > Name > Cores > RAM > Disks > Compose machine*  

**CLI**  
  ```bash
  maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G disks=1:size=20G
  ```

### Remove VMs

**UI**
*Machine > (Select machines) > Delete > Delete machine*

**CLI**
  ```bash
  maas $PROFILE machine delete $SYSTEM_ID
  ```

## Set up a bridge

You can set up bridges easliy at the command line or via Netplan.

### Configure a bridge at the command line
   ```bash
   INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
   BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
   maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
   ```

### Configure a bridge with Netplan

Edit `/etc/netplan/50-cloud-init.yaml`, then apply:
```bash
sudo netplan apply
```
