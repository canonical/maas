This guide provides step-by-step instructions for setting up, managing, and overseeing LXD VM hosts and virtual machines in MAAS.

## Setting up LXD for VM hosts

### Remove older LXD versions
```bash
sudo apt-get purge -y *lxd* *lxc*
sudo apt-get autoremove -y
```

### Install LXD
```bash
sudo snap install lxd
sudo snap refresh
```

### Initialize LXD
```bash
sudo lxd init
```
Follow prompts:
- Use clustering: `no`
- Storage back-end: `dir`
- Connect to MAAS: `no`
- Use existing bridge: `yes`
- Bridge name: `br0`
- Trust password: provide password

### Disable DHCP for LXD's bridge
```bash
lxc network set lxdbr0 dns.mode=none
lxc network set lxdbr0 ipv4.dhcp=false
lxc network set lxdbr0 ipv6.dhcp=false
```

## Adding a VM host

### Add VM host via UI
1. Navigate to *KVM* > *Add KVM*.
2. Enter required details like *Name*, *LXD address*, and select *Generate new certificate*.
3. Run the command to add trust to LXD.
4. Choose *Check authentication*.
5. Finalize by selecting *Add new project* or *Select existing project*.

### Add VM host via CLI
```bash
maas $PROFILE vm-host create type=lxd power_address=$LXD_ADDRESS project=$PROJECT_NAME
```

## Managing LXD projects

### Create a new LXD project via CLI
1. Generate API key:
   ```bash
   sudo maas apikey --generate --username admin
   ```
2. Log in:
   ```bash
   maas login admin http://$MAAS_URL/MAAS/api/2.0 $API_KEY
   ```
3. Create VM host with a specific project:
   ```bash
   maas admin vm-hosts create type=lxd power_address=$LXD_ADDRESS project=$PROJECT_NAME
   ```

### Create and compose a VM in a project
```bash
maas $PROFILE vm-host compose $VM_HOST_ID
```

### Move a VM between projects
```bash
lxc move $VM_NAME $VM_NAME --project default --target-project $PROJECT_NAME
```

## Overseeing individual VMs

### Add a VM via UI
1. Navigate to *KVM* > *VM host name* > *Add VM*.
2. Specify details like *Name*, *Cores*, *RAM*, and *Disks*.
3. Click *Compose machine*.

### Add a VM via CLI
```bash
maas $PROFILE vm-host compose $VM_HOST_ID cores=4 memory=8G disks=1:size=20G
```

### Delete a VM via CLI
```bash
maas $PROFILE machine delete $SYSTEM_ID
```

## Network configuration for VM hosts

### Set up a bridge via CLI
1. Create a bridge:
   ```bash
   INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)
   BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)
   ```
2. Connect the bridge to a subnet:
   ```bash
   maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"
   ```

### Set up a bridge with netplan
Edit `/etc/netplan/50-cloud-init.yaml` to configure the bridge, then apply:
```bash
sudo netplan apply
```