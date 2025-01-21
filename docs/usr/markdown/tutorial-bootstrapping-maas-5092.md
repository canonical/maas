> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/tutorial-bootstrapping-maas" target = "_blank">Let us know.</a>*
 
MAAS simplifies hardware management in data centres and clouds, offering scalable deployment.  This tutorial will take you through a typical MAAS usage scenario.

## Prerequisites

- Hardware meeting [minimum requirements](/t/reference-installation-requirements/6233).
- Knowledge of Ubuntu and basic Linux commands.
- Understanding of networking concepts.
- A MAAS server with internet access.
- Administrative rights for setup.

## Installation

1. Update and install dependencies:

```nohighlight
   sudo apt update
   sudo apt install snapd lxd lxd-client python3-lxc python3-openstackclient
```
2. Install MAAS:

```nohighlight
   sudo snap install maas
```
3. Install and configure PostgreSQL for MAAS:

```nohighlight
   sudo apt install postgresql postgresql-contrib
   sudo su - postgres
   psql
   CREATE USER maas WITH PASSWORD 'password';
   CREATE DATABASE maasdb OWNER maas;
   \q
   exit
```
   
4. Edit `/etc/postgresql/12/main/pg_hba.conf`, adding a line like the following, to allow the MAAS user to connect:

```nohighlight
    sudo vi /etc/postgresql/12/main/pg_hba.conf
    host    maasdb    maas    0/0     md5
```

5. Initialise MAAS:
```nohighlight
   sudo maas init region+rack --database-uri postgres://maas:password@localhost/maasdb
```

6. Make a note of the URL this command returns (similar to the following); you'll need it later:

```nohighlight
    http://<ip-address>:5240/MAAS
```
	
7. Visit the web UI at the noted URL and create an admin account; note that the email address can be anything:

```nohighlight
	sudo maas createadmin
```

MAAS is now installed.

## Configuration

1. Access MAAS at this address, where `$API_HOST` is the MAAS URL:

```nohighlight
    http://${API_HOST}:5240/MAAS
```
    
   Log in by using the login information you created when initialising MAAS.

2. In the web UI, go to *Settings > General* and set a forward DNS server, such as "8.8.8.8".

3. Under Images, select the Ubuntu release to sync; you can usually accept the default.

4. Under Accounts, import your SSH public key from Launchpad or GitHub, or upload your existing public key. Follow the on-screen instructions.

5. Review remaining configuration options (proxy usage, NTP, and so on).

MAAS can now manage and provision nodes.

## Network and DHCP configuration

1. Identify the LXD bridge IP address:

```
    ip addr show lxdbr0
```

2. In MAAS, go to Subnets and identify the VLAN for that subnet.

3. Select the VLAN and configure DHCP with the bridge IP as the gateway. 

MAAS now provides networking and DHCP for provisioning LXD virtual machines.

## Set up LXD

1. Install the LXD snap:

```nohighlight
    sudo snap install lxd
```

2. Initialise the LXD configuration:

```nohighlight
    sudo lxd init
```

    Choose appropriate options for networking, storage pools, and so on.

3. Disable LXD's built-in DHCP server:

```nohighlight
    lxc network set lxdbr0 ipv4.dhcp=false 
```

## Create a VM host

Create a LXD VM host with a MAAS-generated certificate:

1. Select *KVM* > *LXD* > *Add KVM*.

2. Enter a *Name* for the KVM host.

3. Optionally, select a non-default *Zone*.

4. Optionally, select a non-default *Resource pool*.

5. Enter the *LXD address* as the gateway address of the bridge for that LXD instance. For example, if `lxdbr0` has address `10.4.241.0`, the default gateway address is `10.4.241.1`.

6. Select *Generate new certificate*.

7. Select *Next*.

8. Select *Add trust to LXD via command line*.

9. Copy the bash command and certificate from the text box.

10. In a terminal, paste the copied command and make sure that it runs.

11. Select *Check authentication*. You'll switch screens; if all goes well, you'll see *Connected* with a green check-mark.

12. Select *Add new project* or *Select existing project*. Be aware that if you select an existing project, any virtual machines already in that project will begin to commission.

13. Select *Next*. You will drop out to a dashboard for the VM host.

MAAS now has a VM host which can support LXD virtual machines.

## Add a LXD VM

Add a virtual machine from the MAAS UI:

1. Select *KVM* > *LXD* > desired VM host > *Add VM*.

2. Optionally enter the *VM name*.

3. Select *Use any available core(s)* or *Pin VM to specific core(s)*, as needed. Enter specific core identities as appropriate.

4. Enter the *RAM* required.

5. Select *Show advanced* if you want to edit the *Domain*, *Zone*, *Resource pool*, or *Architecture*. Make those changes as needed.

6. Optionally *Define* interfaces.

7. Optionally *Add disks*.

8. Select *Compose machine* to create the virtual machine.

You can switch from here to the *Machine list* to watch the commissioning process in action.

## Acquire the VM

To acquire (or *allocate*) your new machine so that only you can deploy it, select your new VM when "Ready" > *Take action* > *Allocate* > confirm. MAAS is now ready to deploy your newly-created virtual machine.

## Deploy the VM

To deploy your VM directly from MAAS with the default options, select your allocated VM > *Deploy* > *Deploy*. The VM's status will change several times as MAAS steps through the process. When done, the status becomes the name of the deployed operating system (e.g. 'Ubuntu 18.04 LTS').

## After deployment

SSH into deployed machines with username `Ubuntu`. Feel free to explore the deployed VM.

## Further learning 

Dive deeper into MAAS features and in the [explanation](/t/explanation/6141), [how-to guides](/t/how-to-guides/6663), and [reference](/t/reference/6143) sections.
