> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/setting-up-lxd-for-vms" target = "_blank">Let us know.</a>*

This page explains how to set up the LXD package to provide MAAS with virtual machines.

## Make LXD 5.21 available

Assuming that you want to use LXD [VM hosts](/t/how-to-use-virtual-machines/6500), you need to install the correct version of LXD, which is 5.21. Older versions will not function correctly with MAAS.

## Remove older versions of LXD

If you're on a version of Ubuntu older than 20.04, or you have the Debian version of LXD, start the uninstall process with the following command:

```nohighlight
sudo apt-get purge -y *lxd* *lxc*
```

This command should result in output that looks something like this:

```nohighlight
Reading package lists... Done
Building dependency tree      
Reading state information... Done
Note, selecting 'lxde-core' for glob '*lxd*'
Note, selecting 'python-pylxd-doc' for glob '*lxd*'
Note, selecting 'python3-pylxd' for glob '*lxd*'
Note, selecting 'python-nova-lxd' for glob '*lxd*'
Note, selecting 'lxde-common' for glob '*lxd*'
Note, selecting 'lxde-icon-theme' for glob '*lxd*'
Note, selecting 'lxde-settings-daemon' for glob '*lxd*'
Note, selecting 'lxde' for glob '*lxd*'
Note, selecting 'lxdm' for glob '*lxd*'
Note, selecting 'lxd' for glob '*lxd*'
Note, selecting 'lxd-tools' for glob '*lxd*'
Note, selecting 'python-pylxd' for glob '*lxd*'
Note, selecting 'lxdm-dbg' for glob '*lxd*'
Note, selecting 'lxde-session' for glob '*lxd*'
Note, selecting 'nova-compute-lxd' for glob '*lxd*'
Note, selecting 'openbox-lxde-session' for glob '*lxd*'
Note, selecting 'python-nova.lxd' for glob '*lxd*'
Note, selecting 'lxd-client' for glob '*lxd*'
Note, selecting 'openbox-lxde-session' instead of 'lxde-session'
Note, selecting 'lxctl' for glob '*lxc*'
Note, selecting 'lxc-common' for glob '*lxc*'
Note, selecting 'python3-lxc' for glob '*lxc*'
Note, selecting 'libclxclient-dev' for glob '*lxc*'
Note, selecting 'lxc-templates' for glob '*lxc*'
Note, selecting 'lxc1' for glob '*lxc*'
Note, selecting 'lxc-dev' for glob '*lxc*'
Note, selecting 'lxc' for glob '*lxc*'
Note, selecting 'liblxc1' for glob '*lxc*'
Note, selecting 'lxc-utils' for glob '*lxc*'
Note, selecting 'vagrant-lxc' for glob '*lxc*'
Note, selecting 'libclxclient3' for glob '*lxc*'
Note, selecting 'liblxc-dev' for glob '*lxc*'
Note, selecting 'nova-compute-lxc' for glob '*lxc*'
Note, selecting 'python-lxc' for glob '*lxc*'
Note, selecting 'liblxc-common' for glob '*lxc*'
Note, selecting 'golang-gopkg-lxc-go-lxc.v2-dev' for glob '*lxc*'
Note, selecting 'lxcfs' for glob '*lxc*'
Note, selecting 'liblxc-common' instead of 'lxc-common'
Package 'golang-gopkg-lxc-go-lxc.v2-dev' is not installed, so not removed
Package 'libclxclient-dev' is not installed, so not removed
Package 'libclxclient3' is not installed, so not removed
Package 'lxc-templates' is not installed, so not removed
Package 'lxctl' is not installed, so not removed
Package 'lxde' is not installed, so not removed
Package 'lxde-common' is not installed, so not removed
Package 'lxde-core' is not installed, so not removed
Package 'lxde-icon-theme' is not installed, so not removed
Package 'lxde-settings-daemon' is not installed, so not removed
Package 'lxdm' is not installed, so not removed
Package 'lxdm-dbg' is not installed, so not removed
Package 'openbox-lxde-session' is not installed, so not removed
Package 'python-lxc' is not installed, so not removed
Package 'python3-lxc' is not installed, so not removed
Package 'vagrant-lxc' is not installed, so not removed
Package 'liblxc-dev' is not installed, so not removed
Package 'lxc-dev' is not installed, so not removed
Package 'nova-compute-lxc' is not installed, so not removed
Package 'nova-compute-lxd' is not installed, so not removed
Package 'python-nova-lxd' is not installed, so not removed
Package 'python-pylxd' is not installed, so not removed
Package 'python-pylxd-doc' is not installed, so not removed
Package 'lxc' is not installed, so not removed
Package 'lxc-utils' is not installed, so not removed
Package 'lxc1' is not installed, so not removed
Package 'lxd-tools' is not installed, so not removed
Package 'python-nova.lxd' is not installed, so not removed
Package 'python3-pylxd' is not installed, so not removed
The following packages were automatically installed and are no longer required:
  dns-root-data dnsmasq-base ebtables libuv1 uidmap xdelta3
Use 'sudo apt autoremove' to remove them.
The following packages will be REMOVED:
  liblxc-common* liblxc1* lxcfs* lxd* lxd-client*
0 upgraded, 0 newly installed, 5 to remove and 21 not upgraded.
After this operation, 34.1 MB disk space will be freed.
(Reading database ... 67032 files and directories currently installed.)
Removing lxd (3.0.3-0ubuntu1~18.04.1) ...
Removing lxd dnsmasq configuration
Removing lxcfs (3.0.3-0ubuntu1~18.04.2) ...
Removing lxd-client (3.0.3-0ubuntu1~18.04.1) ...
Removing liblxc-common (3.0.3-0ubuntu1~18.04.1) ...
Removing liblxc1 (3.0.3-0ubuntu1~18.04.1) ...
Processing triggers for man-db (2.8.3-2ubuntu0.1) ...
Processing triggers for libc-bin (2.27-3ubuntu1) ...
(Reading database ... 66786 files and directories currently installed.)
Purging configuration files for liblxc-common (3.0.3-0ubuntu1~18.04.1) ...
Purging configuration files for lxd (3.0.3-0ubuntu1~18.04.1) ...
Purging configuration files for lxcfs (3.0.3-0ubuntu1~18.04.2) ...
Processing triggers for systemd (237-3ubuntu10.40) ...
Processing triggers for ureadahead (0.100.0-21) ...
```

You should also autoremove packages no longer needed by LXD:

```nohighlight
$ sudo apt-get autoremove -y
```

Output from this command should be similar to:

```nohighlight
Reading package lists... Done
Building dependency tree      
Reading state information... Done
The following packages will be REMOVED:
  dns-root-data dnsmasq-base ebtables libuv1 uidmap xdelta3
0 upgraded, 0 newly installed, 6 to remove and 21 not upgraded.
After this operation, 1860 kB disk space will be freed.
(Reading database ... 66769 files and directories currently installed.)
Removing dns-root-data (2018013001) ...
Removing dnsmasq-base (2.79-1) ...
Removing ebtables (2.0.10.4-3.5ubuntu2.18.04.3) ...
Removing libuv1:amd64 (1.18.0-3) ...
Removing uidmap (1:4.5-1ubuntu2) ...
Removing xdelta3 (3.0.11-dfsg-1ubuntu1) ...
Processing triggers for man-db (2.8.3-2ubuntu0.1) ...
Processing triggers for libc-bin (2.27-3ubuntu1) ...
```

Now install LXD from the Snap:

```nohighlight
$ sudo snap install lxd
2020-05-20T22:02:57Z INFO Waiting for restart...
lxd 4.1 from Canonical✓ installed
```

## Refresh LXD

If you are on 20.04 or above LXD should be installed by default, but it's a good idea to make sure it's up to date:

```nohighlight
$ sudo snap refresh
All snaps up to date.
```

## Initialise LXD prior to use

Once LXD is installed it needs to be configured with `lxd init` before first use:

```nohighlight
$ sudo lxd init
```

Your interactive output should look something like the following. Note a few points important points about these questions:

1. `Would you like to use LXD clustering? (yes/no) [default=no]: no` - support for LXD clusters was added in MAAS v3.1.

2. `Name of the storage back-end to use (btrfs, dir, lvm, zfs, ceph) [default=zfs]: dir` - testing has primarily been with dir; other options should work, but less testing has been done, so use at your own risk.

3. `Would you like to connect to a MAAS server? (yes/no) [default=no]: no` - When LXD is connected to MAAS containers or virtual machines created by LXD will be automatically added to MAAS as devices. This feature should work, but has limited testing thus far.

4. `Would you like to configure LXD to use an existing bridge or host interface? (yes/no) [default=no]: yes` - The bridge LXD creates is isolated and not managed by MAAS. If this bridge is used, you would be able to add the LXD VM host and compose virtual machines, but commissioning, deploying, and any other MAAS action which uses the network will fail -- so `yes` is the correct answer here.

5. `Name of the existing bridge or host interface: br0` - br0 is the name of the bridge the user configured (see sections above) which is connected to a MAAS-managed network.

6. `Trust password for new clients:` - This is the password the user will enter when connecting with MAAS.


```nohighlight
Would you like to use LXD clustering? (yes/no) [default=no]: no
Do you want to configure a new storage pool? (yes/no) [default=yes]: yes
Name of the new storage pool [default=default]:  
Name of the storage back-end to use (btrfs, dir, lvm, zfs, ceph) [default=zfs]: dir
Would you like to connect to a MAAS server? (yes/no) [default=no]: no
Would you like to create a new local network bridge? (yes/no) [default=yes]: no
Would you like to configure LXD to use an existing bridge or host interface? (yes/no) [default=no]: yes
Name of the existing bridge or host interface: br0
Would you like LXD to be available over the network? (yes/no) [default=no]: yes
Address to bind LXD to (not including port) [default=all]:
Port to bind LXD to [default=8443]:
Trust password for new clients:
Again:
Would you like stale cached images to be updated automatically? (yes/no) [default=yes]
Would you like a YAML "lxd init" preseed to be printed? (yes/no) [default=no]:
```

After initialising LXD, you will also want to make sure that LXD is not trying to provide DHCP for the new local network bridge. You can check this with the following command:

```nohighlight
lxc network show lxdbr0
```

If you didn't accept the default bridge name (lxdbr0), substitute your name for that new bridge in the command above. This will produce output something like this:

```nohighlight
config:
  dns.mode: managed
  ipv4.address: 10.146.214.1/24
  ipv4.dhcp: "true"
  ipv4.nat: "true"
  ipv6.address: fd42:c560:ee59:bb2::1/64
  ipv6.dhcp: "true"
  ipv6.nat: "true"
description: "
name: lxdbr0
type: bridge
used_by:
- /1.0/profiles/default
managed: true
status: Created
locations:
- none
```

There is a [quick tutorial](https://github.com/lxc/lxd/blob/master/doc/networks.md)**^** on the possible settings here. For simplicity, to turn off LXD-provided DHCP, you need to change three settings, as follows:

```nohighlight
lxc network set lxdbr0 dns.mode=none
lxc network set lxdbr0 ipv4.dhcp=false
lxc network set lxdbr0 ipv6.dhcp=false
```

You can check your work by repeating the `show` command:

```nohighlight
$ lxc network show lxdbr0
config:
  dns.mode: none
  ipv4.address: 10.146.214.1/24
  ipv4.dhcp: "false"
  ipv4.nat: "true"
  ipv6.address: fd42:c560:ee59:bb2::1/64
  ipv6.dhcp: "false"
  ipv6.nat: "true"
description: "
name: lxdbr0
type: bridge
used_by:
- /1.0/profiles/default
managed: true
status: Created
locations:
- none
```

Once that's done, the LXD host is now ready to be added to MAAS as an LXD VM host. Upon adding the VM host, its own commissioning information will be refreshed.

When composing a virtual machine with LXD, MAAS uses either the 'maas' LXD profile, or (if that doesn't exist) the 'default' LXD profile. The profile is used to determine which bridge to use. Users may also add additional LXD options to the profile which are not yet supported in MAAS.