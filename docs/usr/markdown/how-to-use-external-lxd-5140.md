> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/managing-vm-hosts" target = "_blank">Let us know.</a>*

In order to deploy a VM host in your MAAS network, you first need to set up a bridge to connect between your VM host and MAAS itself. Once that's done, you can add and manage VM hosts -- and subsequently, create VMs to act as MAAS machines. 

To enable VM host networking features, MAAS must match the VM host IP address of a potential VM host with a known device (a machine or controller). For example, if a machine not known to MAAS is set up as a VM host, enhanced interface selection features will not be available.

> It's essential to enforce usage of IP addresses to avoid domain name conflicts, should different controllers resolve the same domain name with different IP addresses. You should also avoid using 127.0.0.1 when running multiple controllers, as it would confuse MAAS.

If you need some background on VM hosting, we have a [refresher](/t/how-to-deploy-virtual-machines/6500) available.

## Set up a bridge (UI)

To set up a VM host bridge with the Web UI, select *Machines* > VM host machine > *Network* > network to bridge > *Create bridge*. Fill in the necessary settings and finish with *Create bridge*.

## Set up a bridge (CLI)

You can also use the MAAS CLI/API to configure a VM host bridge, with the following procedure:

1. Select the interface you wish to configure the bridge on. This example uses the boot interface, since the boot interface must be connected to a MAAS controlled network -- but any interface is allowed:

        INTERFACE_ID=$(maas $PROFILE machine read $SYSTEM_ID | jq .boot_interface.id)

2. Create the bridge:

         BRIDGE_ID=$(maas $PROFILE interfaces create-bridge $SYSTEM_ID name=br0 parent=$INTERFACE_ID | jq .id)

3. Select the subnet where you want the bridge (this should be a MAAS controlled subnet):

        SUBNET_ID=$(maas $PROFILE subnets read | jq -r '.[] | select(.cidr == "10.0.0.0/24" and .managed == true).id')

4. Connect the bridge to the subnet:

          maas $PROFILE interface link-subnet $SYSTEM_ID $BRIDGE_ID subnet=$SUBNET_ID mode="STATIC" ip_address="10.0.0.101"

## Build a bridge (netplan)

You can also use netplan to configure a VM host bridge:

Open your netplan configuration file. This should be in `/etc/netplan`. It could be called `50-cloud-init.yaml`, `netplan.yaml`, or something else. Modify the file to add a bridge, using the example below to guide you:

```nohighlight
network:
    bridges:
        br0:
            addresses:
            - 10.0.0.101/24
            gateway4: 10.0.0.1
            interfaces:
            - enp1s0
            macaddress: 52:54:00:39:9d:f9
            mtu: 1500
            nameservers:
                addresses:
                - 10.0.0.2
                search:
                - maas
            parameters:
                forward-delay: 15
                stp: false
    ethernets:
        enp1s0:
            match:
                macaddress: 52:54:00:39:9d:f9
            mtu: 1500
            set-name: enp1s0
        enp2s0:
            match:
                macaddress: 52:54:00:df:87:ac
            mtu: 1500
            set-name: enp2s0
        enp3s0:
            match:
                macaddress: 52:54:00:a7:ac:46
            mtu: 1500
            set-name: enp3s0
    version: 2
```

Apply the new configuration with `netplan apply`.

## Build a bridge (libvirt)

It is also possible to use [libvirt](https://ubuntu.com/server/docs/virtualization-libvirt)**^** to configure a virtual bridge. This method will also work for LXD VM hosts running on Ubuntu. Be aware that other methods may be required if you are configuring LXD on an OS other than Ubuntu.

By default, libvirt creates a virtual bridge, `virbr0`, through which VMs communicate with each other and the Internet. DHCP, supplied by libvirt, automatically assigns an IP address to each VM. However, to enable network booting in MAAS, you’ll need to provide DHCP in MAAS and either:

- Disable DHCP on libvirt’s `default` network, or
- Create a new libvirt network `maas` with DHCP disabled.

You can set up such a `maas` network like this:

```nohighlight
cat << EOF > maas.xml
<network>
 <name>maas</name>
 <forward mode='nat'>
   <nat>
     <port start='1024' end='65535'/>
   </nat>
 </forward>
 <dns enable="no" />
 <bridge name='virbr1' stp='off' delay='0'/>
 <domain name='testnet'/>
 <ip address='172.16.99.1' netmask='255.255.255.0'>
 </ip>
</network>
EOF
virsh net-define maas.xml
```

Note that this network also has NAT port forwarding enabled to allow VMs to communicate with the Internet at large. Port forwarding is very useful in test environments.

## Set up SSH for libvirt

For MAAS to successfully communicate with libvirt on your VM host machine -- whether you're running from snap or package, or running rack controllers in LXD containers or on localhost -- this example command must succeed from every rack controller:

```nohighlight
virsh -c qemu+ssh://$USER@$VM_HOST_IP/system list --all
```

Here, `$USER` is a user on your VM host who is a member of the `libvirtd` Unix group on the VM host, and `$VM_HOST_IP` is the IP of your VM host. **Note** that insufficient permissions for `$USER` may cause the `virsh` command to fail with an error such as `failed to connect to the hypervisor`. Check the `$USER` group membership to make sure `$USER` is a member of the `libvirtd` group.

## Set up libvirt SSH (3.3,3.4 snap)

If you installed MAAS via snap, then create the needed SSH keys this way:

```nohighlight
sudo mkdir -p /var/snap/maas/current/root/.ssh
cd /var/snap/maas/current/root/.ssh
sudo ssh-keygen -f id_rsa
```

Finally, on the VM host, you'll need to add `id_rsa.pub` to the `authorized_keys` file in `/home/<vm-host-user-homedir-name>/.ssh/`,  where `<vm-host-user-homedir-name>` is the name of your VM host user.

## Set up libvirt SSH (3.3,3.4 deb)

The `maas` user on your rack controllers will issue all libvirt commands. Therefore, you'll need to set up SSH public keys on every rack controller for user `maas`. First create SSH keys on all rack controllers:

```nohighlight
$ sudo -i
root@maas:~$ mkdir -p /var/snap/maas/current/root/.ssh
root@maas:~$ cd /var/snap/maas/current/root/.ssh
root@maas:~$ ssh-keygen -f id_rsa
```

Next, add the contents of `~maas/.ssh/id_rsa.pub` to the VM host user's `~$USER/.ssh/authorized_keys`. To accomplish this, log into your VM host node, via SSH, from a host for which MAAS has a matching public SSH key.

## Set up libvirt SSH (3.2 snap)

If you installed MAAS via snap, then create the needed SSH keys this way:

```nohighlight
sudo mkdir -p /var/snap/maas/current/root/.ssh
cd /var/snap/maas/current/root/.ssh
sudo ssh-keygen -f id_rsa
```

Finally, on the VM host, you'll need to add `id_rsa.pub` to the `authorized_keys` file in `/home/<vm-host-user-homedir-name>/.ssh/`,  where `<vm-host-user-homedir-name>` is the name of your VM host user.

## Set up libvirt SSH (3.2 deb)

The `maas` user on your rack controllers will issue all libvirt commands. Therefore, you'll need to set up SSH public keys on every rack controller for user `maas`. First create SSH keys on all rack controllers:

```nohighlight
$ sudo -i
root@maas:~$ mkdir -p /var/snap/maas/current/root/.ssh
root@maas:~$ cd /var/snap/maas/current/root/.ssh
root@maas:~$ ssh-keygen -f id_rsa
```

Next, add the contents of `~maas/.ssh/id_rsa.pub` to the VM host user's `~$USER/.ssh/authorized_keys`. To accomplish this, log into your VM host node, via SSH, from a host for which MAAS has a matching public SSH key.

## Set up libvirt SSH (3.1 snap)

If you installed MAAS via snap, then create the needed SSH keys this way:

```nohighlight
sudo mkdir -p /var/snap/maas/current/root/.ssh
cd /var/snap/maas/current/root/.ssh
sudo ssh-keygen -f id_rsa
```

Finally, on the VM host, you'll need to add `id_rsa.pub` to the `authorized_keys` file in `/home/<vm-host-user-homedir-name>/.ssh/`,  where `<vm-host-user-homedir-name>` is the name of your VM host user.

## Set up libvirt SSH (3.1 deb)

The `maas` user on your rack controllers will issue all libvirt commands. Therefore, you'll need to set up SSH public keys on every rack controller for user `maas`. First create SSH keys on all rack controllers:

```nohighlight
$ sudo -i
root@maas:~$ mkdir -p /var/snap/maas/current/root/.ssh
root@maas:~$ cd /var/snap/maas/current/root/.ssh
root@maas:~$ ssh-keygen -f id_rsa
```

Next, add the contents of `~maas/.ssh/id_rsa.pub` to the VM host user's `~$USER/.ssh/authorized_keys`. To accomplish this, log into your VM host node, via SSH, from a host for which MAAS has a matching public SSH key.

## Set up libvirt SSH (3.0 snap)

If you installed MAAS via snap, then create the needed SSH keys this way:

```nohighlight
sudo mkdir -p /var/snap/maas/current/root/.ssh
cd /var/snap/maas/current/root/.ssh
sudo ssh-keygen -f id_rsa
```

Finally, on the VM host, you'll need to add `id_rsa.pub` to the `authorized_keys` file in `/home/<vm-host-user-homedir-name>/.ssh/`,  where `<vm-host-user-homedir-name>` is the name of your VM host user.

## Set up libvirt SSH (3.0 deb)

The `maas` user on your rack controllers will issue all libvirt commands. Therefore, you'll need to set up SSH public keys on every rack controller for user `maas`. First create SSH keys on all rack controllers:

```nohighlight
$ sudo -i
root@maas:~$ mkdir -p /var/snap/maas/current/root/.ssh
root@maas:~$ cd /var/snap/maas/current/root/.ssh
root@maas:~$ ssh-keygen -f id_rsa
```

Next, add the contents of `~maas/.ssh/id_rsa.pub` to the VM host user's `~$USER/.ssh/authorized_keys`. To accomplish this, log into your VM host node, via SSH, from a host for which MAAS has a matching public SSH key.

## Set up libvirt SSH (2.9 snap)

If you installed MAAS via snap, then create the needed SSH keys this way:

```nohighlight
sudo mkdir -p /var/snap/maas/current/root/.ssh
cd /var/snap/maas/current/root/.ssh
sudo ssh-keygen -f id_rsa
```

Finally, on the VM host, you'll need to add `id_rsa.pub` to the `authorized_keys` file in `/home/<vm-host-user-homedir-name>/.ssh/`,  where `<vm-host-user-homedir-name>` is the name of your VM host user.

## Set up libvirt SSH (2.9 deb)

The `maas` user on your rack controllers will issue all libvirt commands. Therefore, you'll need to set up SSH public keys on every rack controller for user `maas`. First create SSH keys on all rack controllers:

```nohighlight
$ sudo -i
root@maas:~$ mkdir -p /var/snap/maas/current/root/.ssh
root@maas:~$ cd /var/snap/maas/current/root/.ssh
root@maas:~$ ssh-keygen -f id_rsa
```

Next, add the contents of `~maas/.ssh/id_rsa.pub` to the VM host user's `~$USER/.ssh/authorized_keys`. To accomplish this, log into your VM host node, via SSH, from a host for which MAAS has a matching public SSH key.

## Add a LXD VM host (3.2++ UI)

To add a LXD VM host with a MAAS-generated certificate, select *KVM* > *LXD* > *Add KVM* and fill in the form:

- Enter a *Name* for the KVM host.

- Optionally, select a non-default *Zone*.

- Optionally, select a non-default *Resource pool*.

- Enter the *LXD address* as the gateway address of the bridge for that LXD instance. For example, if `lxdbr0` has address `10.4.241.0`, the default gateway address is `10.4.241.1`.

- Select *Generate new certificate* > *Next* > *Add trust to LXD via command line*.

- Copy the bash command and certificate from the text box, paste it in a terminal and make sure the command runs.

- Select *Check authentication*. You'll switch screens; if all goes well, you'll see *Connected* with a green check-mark.

- Select *Add new project* or *Select existing project*. Be aware that if you select an existing project, any VMs already in that project will begin to commission.

Finish by selecting *Next*. You will drop out to a dashboard for the VM host, from which you can then add virtual machines to this new VM host.

## How to add a LXD VM host using an existing certificate

To use your own existing certificate with a LXD VM host, select *KVM* > *LXD* > *Add KVM* and fill in the form:

- Enter a *Name* for the KVM host.

- Optionally, select a non-default *Zone*.

- Optionally, select a non-default *Resource pool*.

- Enter the *LXD address* as the gateway address of the bridge for that LXD instance. For example, if `lxdbr0` has address `10.4.241.0`, the default gateway address is `10.4.241.1`.

- Select *Provide certificate and private key*. The screen will extend.

- *Upload a certificate* or paste one in the certificate text box.

- *Upload a private key* or paste on in the private key text box.

- Select *Generate new certificate* > *Next* > *Add trust to LXD via command line*.

- Copy the bash command and certificate from the text box, paste it in a terminal and make sure the command runs.

- Select *Check authentication*. You'll switch screens; if all goes well, you'll see *Connected* with a green check-mark.

- Select *Add new project* or *Select existing project*. Be aware that if you select an existing project, any VMs already in that project will begin to commission.

Finish by selecting *Next*. You will drop out to a dashboard for the VM host, from which you can then add virtual machines to this new VM host.

## Delete a VM host

To delete a VM host, select *KVM* > VM host to delete > *KVM host settings* > *Danger zone* > *Remove KVM host*. You will need to confirm this choice. There is no way to recover the VM host after confirming.

## Add a VM host (3.0 UI)

To add a VM host, select *KVM* > *Add KVM* > *KVM host type*, and fill in the form:

- Enter a *Name* for the KVM host.

- Optionally, select a non-default *Zone*.

- Optionally, select a non-default *Resource pool*.

- If you chose the *LXD* host type, enter the *LXD address* as the gateway address of the bridge for that LXD instance. For example, if `lxdbr0` has address `10.4.241.0`, the default gateway address is `10.4.241.1`.

- If you chose the *virsh* host type, enter the *Virsh address*, which is of the form `qemu+ssh://<vm host IP>/system`.

- Enter any requested passwords, if needed.

- Select *Authenticate*. MAAS will drop to a KVM host screen.

You can then add virtual machines to this new VM host as desired.

## Add a VM host (3.0++ CLI)

To add a VM host via the CLI:

```nohighlight
maas $PROFILE vm-host create type=$VM_HOST_TYPE power_address=$POWER_ADDRESS \
    [power_user=$USERNAME] power_pass=$PASSWORD {project=$PROJECT} \
    [zone=$ZONE] [tags=$TAG1,$TAG2,...]
```

$VM_HOST_TYPE can currently take two values: `virsh` and `lxd`.

$POWER_ADDRESS typically looks like the following for libvirt:

    qemu+ssh://<vm host IP>/system

of like this for LXD (Beta):

    https://10.0.0.100:8443

Both $USERNAME and $PASSWORD are optional for the virsh power type. $ZONE and $TAGS are optional for all VM hosts.

The `power_...` parameters will vary with power type.

For example, to create a LXD VM host, enter the following:

```nohighlight
maas $PROFILE vm-hosts create type=lxd power_address=$LXD_BRIDGE_ADDRESS \
   power_pass=$LXD_TRUST_PASSWORD project=$PROJECT_NAME
```

Note that for LXD VM hosts, a project name is not optional. Project names cannot contain spaces or special characters. If you enter a project name which doesn't exist, MAAS will create the LXD project for you.

## Add a VM host (2.9 CLI)

To add a VM host via the 2.9 CLI:

```nohighlight
maas $PROFILE vm-host create type=$VM_HOST_TYPE power_address=$POWER_ADDRESS \
    [power_user=$USERNAME] [power_pass=$PASSWORD] [zone=$ZONE] \
    [tags=$TAG1,$TAG2,...]
```

$VM_HOST_TYPE can currently take three values: `rsd`, `virsh`, and `lxd`.

$POWER_ADDRESS typically looks like the following for libvirt:

    qemu+ssh://<vm host IP>/system

of like this for LXD (Beta):

    https://10.0.0.100:8443

Both $USERNAME and $PASSWORD are optional for the virsh power type. $ZONE and $TAGS are optional for all VM hosts.

The `power_...` parameters will vary with power type. See the [API reference](/docs/api#power-types) for a listing of available power types.

## Some examples

For example, to create an RSD VM host, enter:

```nohighlight
maas $PROFILE vm-hosts create type=rsd power_address=10.3.0.1:8443 \
    power_user=admin power_pass=admin
```

To create a KVM host, enter the following:

```nohighlight
maas $PROFILE vm-hosts create type=virsh power_address=qemu+ssh://ubuntu@192.168.1.2/system
```
MAAS will automatically discover and store the resources your VM host contains. Any existing machines will also appear on the 'Machines' page, and MAAS will automatically attempt to commission them.

## Configure a VM host (UI)

To configure a VM host, select *KVM* > *LXD* > VM host to configure > *KVM host settings* and fill out the form:

- Optionally set *KVM configuration* > *Zone* by selecting from the drop-down.

- Optionally set the *KVM configuration* > *Resource pool* by selecting from the drop-down.

- Optionally add or change *KVM configuration* > (Tags*.

- Optionally change the *KVM configuration* > *CPU overcommit* ratio by moving the slider.

- Optionally change the *KVM configuration* > *Memory overcommit* ratio by moving the slider.

If you've made changes to this point, select *KVM configuration* > *Save changes*. MAAS will save the *KVM configuration* changes, but will not switch screens. If you need to change the *Authentication* > *Certificate*, at this point, you may do so. Make sure to choose *Update certificate* to register your changes.

If you want to remove this KVM host, choose *Danger zone* > *Remove KVM host*. You will need to confirm this choice.

## List VM hosts (CLI)

Using the CLI, it's possible to update the configuration of a VM host. You can change these configurable parameters with an `update` command -- but first, you'll want to know how to check the values of configurable parameters, both before and after the change.

To begin, you can list your available KVM-hosts with the following command:

```nohighlight
maas admin vm-hosts read | jq -r '(["ID, "VM-HOST","SYSID","CORES",
"USED","RAM", "USED","STORAGE", "USED"] | (., map(length*"-"))),
(.[]| [.id,.name,.host.system_id,.total.cores, .used.cores, .total.memory, .used.memory,.total.local_storage, .used.local_storage])
| @tsv' | column -t
```

## List VM host params (CLI)

There are just a few parameters that you can change for a VM host. You can list these, on a per-host basis, using the following two-step procedure:

1. Run the command above to get the VM host ID (different from the System ID, see the first column in the listing).

2. Enter the following command to list configurable parameters:

```nohighlight
maas admin vm-host read $ID | jq -r '(["ID","NAME","POOL","ZONE",
"CPU-O/C", "RAM-O/C", "TAGS"] | (., map(length*"-"))), (.| [.id,.name,
.pool.name, .zone.name,.cpu_over_commit_ratio, 
.memory_over_commit_ratio, .tags[]]) | @tsv' | column -t
```

where $ID is the ID (not System ID) of the VM-host.

## Change VM host name (CLI)

You can change the VM host's name very simply, with this command:

    maas admin vm-host update $ID name=$NEW_NAME

where $ID is the VM host's ID (not System ID), and $NEW_NAME is the new name you want to assign. You can check that the change was successful by just printing out the ID and name, like this:

```nohighlight
maas admin vm-host read $ID | jq -r '(["ID","NAME"] 
| (., map(length*"-"))), (.| [.id,.name]) 
| @tsv' | column -t
```

## Change VM host pool (CLI)

You can also change the VM host's pool with a simple command:

```nohighlight
maas admin vm-host update $ID pool=$VALID_POOL
```

where $ID is the VM host's ID (not System ID), and $VALID_POOL is the name of a pool that already exists. If you mention a pool you haven't created yet, you'll get an error like this:

```nohighlight
{"pool": ["Select a valid choice. That choice is not one of the available choices."]}
```

```nohighlight
maas admin resource-pools read | jq -r '.[] | (.name)'
```

If you really want to set your VM host to a new one, you just need to create a new one with this command:

```nohighlight
maas admin resource-pools create name=$NEW_POOL_NAME
```

Then double-check it with `catvmpools`, and assign your VM host to it using the earlier command. 

## List VM host resources (CLI)

```nohighlight
maas $PROFILE vm-hosts read
```

A portion of the sample output:

``` no-highlight
        "id": 93,
        "capabilities": [
            "composable",
            "fixed_local_storage",
            "iscsi_storage"
        ],
        "name": "civil-hermit",
```

## List single VM host resources (CLI)

To list an individual VM host's resources:

```nohighlight
maas $PROFILE vm-host read $VM_HOST_ID
```

## Update VM host config (CLI)

Update overcommit ratios for a KVM host:

```nohighlight
maas $PROFILE vm-host update $VM_HOST_ID power_address=qemu+ssh://ubuntu@192.168.1.2/system \
        power_pass=example cpu_over_commit_ratio=2.5 memory_over_commit_ratio=10.0
```

Update the default storage pool used by a KVM host:

```nohighlight
maas $PROFILE vm-host update $VM_HOST_ID power_address=qemu+ssh://ubuntu@192.168.1.2/system \
        power_pass=example default_storage_pool=pool2
```

## VM host connection params (CLI)

To list a VM host's connection parameters:

```nohighlight
maas $PROFILE vm-host parameters $VM_HOST_ID
```

Example output:

```no-highlight
{
    "power_address": "10.3.0.1:8443",
    "power_pass": "admin",
    "power_user": "admin"
}
```

## LXD clusters (3.1++)

MAAS takes advantage of the existing LXD clustering capability. LXD clusters within the context of MAAS are a way of viewing and managing existing VM host clusters and composing VMs within said cluster. MAAS will not create a new cluster, but will discover an existing cluster when you provide the info for adding a single clustered host.

## Add LXD clusters (3.1++)

MAAS assumes you have already configured a cluster within the context of LXD. You then need to configure this cluster with a single trust MAAS will use to communicate with said cluster. 

The process of adding a LXD cluster is [identical to the procedure for adding a LXD VM host](#heading--adding-a-vm-host). The only difference is that the name you provide will be used for the cluster instead of the individual host. 

MAAS will then connect to the provided host and discover the other hosts within the cluster, and rename the initially defined host with the cluster member name configured in LXD. The VM host will show up as a *Cluster* on the dashboard. 

## Compose VMs in LXD clusters (3.1++)

To compose VMs in a LXD cluster, follow the procedure for [adding a VM to a VM host](/t/how-to-manage-virtual-machines/5148). 

## Delete LXD clusters (3.1++)

To delete a LXD cluster, [delete any VM host within the cluster](#heading--deleting-a-vm-host).

> This will delete the cluster and **all** members within the cluster. Make sure that's what you want to do.