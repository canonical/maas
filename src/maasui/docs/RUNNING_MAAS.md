# How to set up a local MAAS with LXD

Having a locally running MAAS where you can deploy your own virtual machines can be useful for testing things in the UI.
This tutorial will take you through the process of setting up MAAS in a LXD container.

## Prerequisites

- Hardware that meets the [minimum requirements](https://maas.io/docs/reference-installation-requirements)
- Knowledge of Ubuntu and basic Linux commands

### Install and configure LXD

1. Install LXD

```sh
sudo snap install lxd
```

2. Initialize LXD

```sh
sudo lxd init --auto
```

You can remove the `--auto` flag if you want to go through the initialization steps yourself - the defaults are fine
for this setup.

3. Set the HTTPS address for LXD

```sh
lxc config set core.https_address [::]:8443
```

4. Configure your firewall

```sh
sudo ufw allow in on lxdbr0
sudo ufw route allow in on lxdbr0
sudo ufw route allow out on lxdbr0
```

---

## Choose Your Setup Type

Now you need to decide what type of MAAS setup you want:

- [KVM Managing Instance](#kvm-managing-instance): A MAAS setup that can provision virtual machines on your host system
- [Sample Data Demo Instance](#sample-data-demo-instance): A MAAS setup with pre-populated sample data for testing and
  demonstration

---

## KVM Managing Instance

This setup enables MAAS to provision virtual machines on your host system.

### Create KVM network and profile

5. Create and configure the `maas-kvm` network for VM provisioning

```sh
lxc network create maas-kvm
lxc network edit maas-kvm
```

Paste the following config, and save

```yaml
name: maas-kvm
description: ""
type: bridge
managed: true
status: Created
config:
  ipv4.address: 10.20.0.1/24
  ipv4.dhcp: "false"
  ipv4.nat: "true"
  ipv6.address: none
used_by: [ ]
locations:
  - none
```

> _NOTE: Make sure to add the same firewall rules as `lxdbr0` to all additional networks, including `maas-kvm`._

6. Create and edit the `maas-container` profile

```sh
lxc profile create maas-container
lxc profile edit maas-container
```

Paste the following config, and save

```yaml
name: maas-container
description: MAAS region container
config: { }
devices:
  eth0:
    network: lxdbr0
    type: nic
  eth1:
    network: maas-kvm
    type: nic
  root:
    path: /
    pool: default
    type: disk
```

### Launch and configure container

7. Launch an Ubuntu container with the `maas-container` profile

```sh
lxc launch ubuntu:noble maas-kvm -p default -p maas-container
```

8. Enter the shell for the container, and switch to the `ubuntu` user

```shell
lxc exec maas-kvm -- su ubuntu
```

9. Inside the container, create a netplan config to give the container an address on the `maas-kvm` network

```sh
sudo nano /etc/netplan/99-maas-kvm-net.yaml
```

Paste the following config, and save

```yaml
network:
  ethernets:
    eth1:
      addresses: [ 10.20.0.2/24 ]
  version: 2
```

10. Apply the new netplan configuration

```sh
sudo netplan apply
```

### Install and initialize MAAS

11. Install the latest MAAS snap, and the test database

```sh 
sudo snap install maas --channel=latest/edge
sudo snap install maas-test-db --channel=latest/edge
```

12. Initialise MAAS with the following command

```sh
sudo maas init region+rack --maas-url="http://10.20.0.2:5240/MAAS" --database-uri maas-test-db:///
```

Take note of the `maas-url` here, you'll need it to log into the UI later.

13. Create your admin user

```sh
sudo maas createadmin
```

### Configure your host machine as a KVM host in MAAS

14. Paste the `maas-url` from step 12 into your browser, and log into MAAS UI. Make sure you import your SSH keys from
    Launchpad or GitHub.
15. Click on "Subnets" in the navigation, and then click on "10.20.0.0/24." Make sure the gateway IP is "10.20.0.1"
16. Go to the VLAN for this subnet (it should show up as "untagged"), and reserve a dynamic range from 10.20.0.100 to
    10.20.0.200.
17. Click "Configure DHCP," check "MAAS provides DHCP," and make sure the IP range you just reserved shows up in the
    form, then submit the form.
18. On your host machine, enter `ip a` and note down the IP address of `lxdbr0`.
19. Click on "LXD" in the navigation, then click "Add LXD host" and fill in the form. You can paste the IP address from
    the previous step into the "LXD address" field. Select "Generate new certificate and key," and click "Next."
20. Run the command shown in the side panel on your host machine to add the newly generated certificate to LXD, then
    click "Check authentication."
21. Select "Add new project" and give it a name—this is where MAAS will deploy all new VMs created with this host.
    Then click "Save LXD host."

And that's a wrap! You should now be able to compose virtual machines on your host using MAAS.

---

## Sample Data Demo Instance

This setup creates a MAAS instance pre-populated with sample data for testing and demonstrations.

### Create demo profile and container

5. Create and edit the `maas-container` profile

> _NOTE: If you have already set up a KVM managing MAAS instance, you can skip this step since KVM uses the same profile
with an additional `maas-kvm` network._

```sh
lxc profile create maas-container
lxc profile edit maas-container
```

Paste the following config, and save

```yaml
name: maas-container
description: MAAS region container
config: { }
devices:
  eth0:
    network: lxdbr0
    type: nic
  root:
    path: /
    pool: default
    type: disk
```

6. Launch an Ubuntu container with the `maas-container` profile

```sh
lxc launch ubuntu:noble maas-demo -p default -p maas-container
```

### Install MAAS

7. Enter the shell for the container, and switch to the `ubuntu` user

```shell
lxc exec maas-demo -- su ubuntu
```

8. Install the latest MAAS snap, and the test database

```sh 
sudo snap install maas --channel=latest/edge
sudo snap install maas-test-db --channel=latest/edge
```

### Set up sample data

To use sample data with MAAS, you'll need to get a database dump. The easiest way is to get a database
dump [from CI](http://maas-ci.internal:8080/view/maas-sampledata-dumper/), or alternatively you can create your
own [dump](https://github.com/maas/maas/blob/master/HACKING.rst#creating-sample-data).

9. Get your database dump from your host machine onto the container

```sh
lxc file push /path/to/your/<dump_filename>.dump maas-demo/tmp/maasdb.dump
```

10. Inside the container, prepare and restore the sample data

```sh
sudo cp /tmp/maasdb.dump /var/snap/maas-test-db/common/maasdb.dump
sudo snap run --shell maas-test-db.psql -c 'db-dump restore /var/snap/maas-test-db/common/maasdb.dump maassampledata'
```

### Initialize MAAS with sample data

11. Initialize MAAS

```sh
sudo maas init region+rack --database-uri maas-test-db:///
```

MAAS will display the default URL. Take note of this URL.

12. Configure MAAS to use the sample database

```sh
sudo sed -i "s/database_name: maasdb/database_name: maassampledata/" /var/snap/maas/current/regiond.conf
```

13. Restart MAAS to apply the changes

```sh
sudo snap restart maas
```

14. Create your admin user

```sh
sudo maas createadmin
```

Your sample data demo MAAS is ready! Open your browser and navigate to the MAAS URL from step 11 to access MAAS
populated with sample data.