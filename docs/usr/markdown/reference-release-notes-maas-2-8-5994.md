> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/what-is-new-with-maas-2-8" target = "_blank">Let us know.</a>*

## Release history
### MAAS 2.8.4 released

MAAS 2.8.4 has been released, replacing the `2.8/stable` channel in snap and the [ppa:maas/2.8](https://launchpad.net/~maas/+archive/ubuntu/2.8) . You can update your 2.8 release to 2.8.4 with the command:

```nohighlight
    snap refresh --channel=2.8/stable
```

or by using the aforementioned PPA. 2.8.4 has a single [bug fix - LP:1917372 ](https://bugs.launchpad.net/maas/+bug/1917372) in it. No other changes have been made to MAAS with this release.

### MAAS 2.8.3 released

MAAS 2.8.3 has been released, replacing the `2.8/stable` channel in snap and the [ppa:maas/2.8](https://launchpad.net/~maas/+archive/ubuntu/2.8). You can update your 2.8 release to 2.8.3 with the command:

```nohighlight
    snap refresh --channel=2.8/stable
```

or by using the aforementioned PPA. The focus for this release has been [bug-fixing](https://bugs.launchpad.net/maas/+milestone/2.8.3rc1) and [more bug-fixing](https://bugs.launchpad.net/maas/+milestone/2.8.3). No other changes have been made to MAAS with this release.

Here's a summary of the bugs that were fixed in 2.8.3:

- [DNS Servers not set as expected](https://bugs.launchpad.net/maas/+bug/1881133): MAAS was using the region controller IP in dhcpd.conf when other DNS servers are present, effectively bypassing the rack controller proxy to machines. The code was updated to use the region controller IP for DNS only if no other DNS servers are found.

- [not able to import new image after MAAS upgrade](https://bugs.launchpad.net/maas/+bug/1890468): After upgrading from MAAS 2.6.2 to snap-MAAS 2.8.1, it is impossible to import a new image. This was fixed in MAAS 2.8.3.

- [an unlogged chown permission error leaves a temporary file behind](https://bugs.launchpad.net/maas/+bug/1883748): Fixed in MAAS 2.8.3.

- [smartctl-validate fails to detect that NVME device is SMART-capable](https://bugs.launchpad.net/maas/+bug/1904329): MAAS 2.8.2 fails to realize that WD Black gaming NVMEs are smart devices, hence MAAS doesn't display attributes. This is fixed in 2.8.3.

- [cannot use release API on stuck observed IPs](https://bugs.launchpad.net/maas/+bug/1898122): The CLI/API provide commands for forcing the release of an IP, but MAAS 2.8.2 was not allowing these commands to run successfully. This was fixed. There is also a workaround for those who cannot upgrade to 2.8.3 right away:

```nohighlight
    $ sudo -u postgres psql $MAAS_DB -c "UPDATE maasserver_staticipaddress SET alloc_type=5 WHERE ip = '$IP_ADDRESS' AND alloc_type=6;"
    $ maas $PROFILE ipaddresses release ip='$IP_ADDRESS' force=true
```
- [MAAS is unable to handle duplicate UUIDs](https://bugs.launchpad.net/maas/+bug/1893690): The firmware for Dell servers (and possibly others) has a bug whereby they use the service number for the UUID, which is not guaranteed to be unique. This caused MAAS commissioning to fail. The code was modified in 2.8.3 to detect and remove duplicate UUIDs, allowing MAAS to fall back to the MAC address. There is also a database workaround for those who cannot upgrade to 2.8.3 right away:

```nohighlight
     $ sudo -u postgres psql $MAAS_DB -c "UPDATE maasserver_node SET hardware_uuid=NULL where hardware_uuid='$DUPLICATE_UUID'";
```
- [Ubuntu 20.04 pxe installation fails...](https://bugs.launchpad.net/curtin/+bug/1876258):
When trying to PXE install Ubuntu 20.04, the installation fails with "no such file or directory, /dev/disk/by-id exception." This was an issue with block devices being created without serial numbers, bug fixed in curtin and released with 2.8.3.

- [Failed to allocate the required AUTO IP addresses after 2 retries](https://bugs.launchpad.net/maas/+bug/1902425): MAAS incorrectly perceives that there are no available IP addresses, when in fact, there are plenty still available. This is fixed in 2.8.3.

- [maas 2.9 rc1 machines create error (backport)](https://bugs.launchpad.net/maas/+bug/1904398): Adding `commission=true` to a CLI machine creation command produces an error. This was fixed in 2.9 and backported to 2.8.3.

- [Lists of LXD nodes are represented in an incompatible data structure](https://bugs.launchpad.net/maas/+bug/1910473): Fixed in 2.8.3.

- Deselecting all architectures in the Ubuntu extra architectures repo [blocks all deployments (backport)](https://bugs.launchpad.net/maas/+bug/1894116). The default architectures have been changed to prevent this issue. This was fixed in 2.9 and backported to 2.8.3.

- [Can't commission without a test (backport)](https://bugs.launchpad.net/maas/+bug/1884278): MAAS 2.8 does not allow machines to be commissioned with zero tests selected; this occurs only for multiple machines, and only when commissioning from the UI. This was fixed in 2.9 and backported to 2.8.3.

Note that there is a workaround for those not ready to upgrade to 2.8.3, specifically, using the CLI to commission machines without testing them:

```nohighlight
    maas $PROFILE machine commission $SYSTEM_ID testing_scripts=none
```

- [UI should not autoselect noauto commissioning scripts (backport)](https://bugs.launchpad.net/maas/+bug/1884827): Previously, users gained the ability to upload commissioning scripts which do not automatically run, but the UI ignores the "noauto" tag and runs the script anyway. This was fixed in 2.9 and backported to 2.8.3.

- [ipmi-config command not found in snap (backport)](https://bugs.launchpad.net/maas/+bug/1891331): The `ipmi-config` cannot be found in a MAAS snap, due to path confusion in the wrapper script. This was fixed in 2.9 and backported to 2.8.3.

- [Admin users cannot change other user's passwords via UI (backport)](https://bugs.launchpad.net/maas/+bug/1894727): An administrator is unable to change users passwords via the UI. This was fixed in 2.9 and backported to 2.8.3.

- [all rack addresses in vlan are included in list of nameservers sent to deployed server (backport)](https://bugs.launchpad.net/maas/+bug/1896684): From the Bug Description: "MAAS forces all rack addresses for all subnets in a single vlan to any system deployed into any of those subnets. If the deployed systems are isolated, with no gateway configured, they may end up with broken DNS due to having nameservers configured which are not reachable."
This was fixed in 2.9 and backported to 2.8.3.

### MAAS 2.8.2 released

On 1 September 2020, MAAS 2.8.2 was released, replacing the `2.8/stable` channel in snap and the [ppa:maas/2.8](https://launchpad.net/~maas/+archive/ubuntu/2.8). You can update your 2.8 release to 2.8.2 with the command:

```nohighlight
snap refresh --channel=2.8/stable
```

or by using the aforementioned PPA. The focus for this release has been [bug fixing](https://launchpad.net/maas/+milestone/2.8.2rc1) -- there were no changes to MAAS since RC1.

Thanks to everyone who reported the issues with previous 2.7 releases and helped us with the logs.

### MAAS 2.8 released

Following on from MAAS 2.7, we are happy to announce that MAAS 2.8 is now available. This release features some critical bug fixes, along with some exciting new features.

## Features
### FAQ:

- [What are the new features and fixes for 2.8?](#heading--2-8-release-notes)
- [What known issues should I be aware of?](#heading--2-8-known-issues)
- [How do I install MAAS 2.8 as a snap?](/t/how-to-install-maas/5128)
- [How do I upgrade my MAAS 2.7 snap to a MAAS 2.8 snap?](/t/how-to-upgrade-maas/5436)
- [How do I install MAAS 2.8 from packages?](/t/how-to-install-maas/5128)
- [What bugs were fixed in this release?](#heading--bug-fixes)

### LXD support (Beta)

MAAS 2.8 adds the beta capability to use LXD-based VM hosts and virtual machines (VMs), in addition to the [libvirt](https://ubuntu.com/server/docs/virtualization-libvirt)-based VM hosts/VMs already available. These new LXD VM hosts use the same underlying technology as libvirt (QEMU). Unlike libvirt KVMs, though, LXD VMs can be managed without requiring SSH access to the VM host. LXD are remotely accessed via secure HTTP transport, which provides better security for LXD-based VMs. In addition, LXD has a better API, and is part of a much larger constellation of enterprise software, offering a wider range of future features and use cases.

### UI improvements

Within MAAS 2.8, we have made a number of performance improvements to everything related to the machine listing. Some of the most visible changes involve the way that long lists are presented within categories (see the example below), but there are a number of other changes that make the list easier and more efficient to use.

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/b4ec4124225f052fb8646f754c22d287fffcc850.jpeg) 

Among those other changes are persisting UI state for grouping, new grouping options, bookmark-able URLs with filter and search parameters, and many other performance improvements. If you're interested in more details, see this [blog post](https://ubuntu.com/blog/building-a-cross-framework-ui-with-single-spa-in-maas-2-8).

### External PostgreSQL support

In order to make MAAS more scalable, we have separated the MAAS database from the MAAS snap, so that the DB can be situated separately. MAAS 2.8 now allows the MAAS DB to be located outside the snap on localhost, or on a separate, external or remote server. We complement this capability with extensive instructions for setting up and managing this configuration. To support those who are testing MAAS, we've also provided a test DB configuration that embeds the database in a separate snap that can easily be connected to MAAS.

## Bug fixes

We've also fixed number of bugs (see the [list in Launchpad](https://bugs.launchpad.net/bugs/+bugs?field.milestone%3Alist=89978&field.milestone%3Alist=90576&field.milestone%3Alist=90599&field.milestone%3Alist=90640&field.milestone%3Alist=90645&field.milestone%3Alist=90722&field.milestone%3Alist=91005&field.milestone%3Alist=91123&field.milestone%3Alist=91124&field.milestone%3Alist=91180&field.status%3Alist=FIXRELEASED)). Notable among these are the following:

- [MAAS event table](https://bugs.launchpad.net/maas/+bug/1860619): Power events are now being logged differently to reduce log sizes and improve performance.

- [Unprivileged users controlling services](https://bugs.launchpad.net/maas/+bug/1864201): Unprivileged users can no longer start, stop, or restart services via HTTP channels.

- [Adding KVMs to snap-installed MAAS](https://bugs.launchpad.net/maas/+bug/1852405): SSH key usage has been updated so that KVMs can now be added to snap-installed MAAS without difficulty.

- [Trouble editing physical interfaces in GUI](https://bugs.launchpad.net/maas/+bug/1864241): It is now possible to edit physical interface parameters, when appropriate, from the web UI.

- [Subnet pages slow to load](https://bugs.launchpad.net/maas/+bug/1873430): Subnet pages now load more quickly and efficiently.

- [Trouble loading multiple MAC addresses](https://bugs.launchpad.net/maas/+bug/1865122): You can now reliably load multiple MAC addresses using the web UI.

- [Disabling DNS on regiond subnet breaks DNS](https://bugs.launchpad.net/maas/+bug/1871584): This problem has been resolved.

## Known issues

- **Browser caching issue:** There is a known issue with browser caching on some MAAS pages. If you initially encounter a page which does not appear to be correctly formatted, please manually clear your browser cache (**not Ctrl-F5**) and it should restore the page to normal. You manually clear your browser cache, for example, in the "History" section of the menu on a Chrome browser.

- **Extra power types when adding chassis:** ([see bug report](https://bugs.launchpad.net/maas/+bug/1883743)) When adding a chassis, the "Power type" drop-down will show power types not supported by a chassis. Selecting one of the non-supported power types will result in the UI blocking the action. Here is a list of power types supported for chassis creation:
  * `mscm` - Moonshot Chassis Manager
  * `msftocs` - Microsoft OCS Chassis Manager
  * `powerkvm` - Virtual Machines on Power KVM, managed by Virsh
  * `recs_box` - Christmann RECS|Box servers
  * `sm15k` - SeaMicro 1500 Chassis
  * `ucsm` - Cisco UCS Manager
  * `virsh` - virtual machines managed by Virsh
  * `vmware` - virtual machines managed by VMware

- **MAAS keys count in user list is bogus:** ([see bug report](https://bugs.launchpad.net/maas/+bug/1884112)) The count of keys shown in the User list in the UI is wrong.

- **Leftover lock files may be present under some conditions:** Even if you purge an old MAAS Debian package, it can leave lock files in `/run/lock/maas*`. This can cause issues if you later reinstall MAAS, and the previous MAAS user UID has been reassigned. At that point, MAAS can't remove those files and create new ones. If this occurs, it is easily fixed by removing those files manually before reinstalling.

