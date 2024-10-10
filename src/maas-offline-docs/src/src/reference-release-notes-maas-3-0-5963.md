> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/what-is-new-with-maas-3-0" target = "_blank">Let us know.</a>*

We are happy to announce the release of MAAS 3.0. This release provides new features, along with critical and high-priority [bug fixes](#heading--maas-3-bug-fixes).

MAAS 3.0 can be installed fresh (recommended) with:

```nohighlight
sudo snap install --channel=3.0/stable maas
```

MAAS 3.0 can be installed from packages by adding the `3.0` PPA:

```nohighlight
sudo add-apt-repository ppa:maas/3.0
sudo apt update
sudo apt install maas
```

You can then either install MAAS 3.0 fresh (recommended) with:

```nohighlight
sudo apt-get -y install maas
```

Or, if you prefer to upgrade, you can do so with:

```nohighlight
sudo apt upgrade maas
```

At this point, you may proceed with a normal installation.

## Significant changes

With the advent of MAAS 3.0, we are removing support for RSD pods. Registered pods and their machines will be removed by MAAS upon upgrading to MAAS 3.0.

Note that new features are categorised by the level of release at which they became accessible to users.

## MAAS 3.0 RC1

New features for MAAS 3.0 release candidate 1.

### Consolidation of logs and events

The logs and events tabs have combined and now live under "Logs". In addition to a number of small improvements, navigating and displaying events has been made easier.

![image](https://discourse.maas.io/uploads/default/optimized/2X/4/497fd5d03ece0308648db33cf144f4cfefc6e5ed_2_690x465.png)

#### Downloading logs

A helpful new feature is the ability to download the machine and installation output, and if a machine has failed deployment you can now download a full tar of the curtain logs.

![image](https://discourse.maas.io/uploads/default/optimized/2X/f/fe9df81b810fa3dd502b303b08978d1c60bff933_2_690x465.png)

### Disabling boot methods
 
Individual boot methods may now be disabled. When a boot method is disabled MAAS will configure MAAS controlled isc-dhcpd to not respond to the associated [boot architecture code](https://www.iana.org/assignments/dhcpv6-parameters/dhcpv6-parameters.xhtml#processor-architecture)**^**. External DHCP servers must be configured manually.

To allow different boot methods to be in different states on separate physical networks using the same VLAN ID configuration is done on the subnet in the UI or API. When using the API boot methods to be disabled may be specified using the MAAS internal name or [boot architecture code](https://www.iana.org/assignments/dhcpv6-parameters/dhcpv6-parameters.xhtml#processor-architecture)**^** in octet or hex form. For example the following disabled i386/AMD64 PXE, AMD64 UEFI TFTP, and AMD64 UEFI HTTP

```nohighlight
maas $PROFILE subnet update $SUBNET disabled_boot_architectures="0x00 uefi_amd64_tftp 00:10"
```

#### GRUB

- UEFI AMD64 HTTP(00:10) has been re-enabled.
- UEFI ARM64 HTTP(00:13) has been enabled.
- UEFI ARM64 TFTP(00:0B) and UEFI ARM64 HTTP(00:13) will now provide a shim and GRUB signed with the Microsoft boot loader keys.
- grub.cfg for all UEFI platforms has been updated to replace the deprecated `linuxefi` and `initrdefi` commands with the standard `linux` and `initrd` commands.
- GRUB debug may now be enabled by enabling [rackd debug logging](https://discourse.maas.io/t/running-installed-maas-in-debug-logging-mode/168)**^**.

## MAAS 3.0 Beta 4

New features for MAAS 3.0 Beta 4.

### Improvements to MAAS CLI help UX

The MAAS CLI will now give you help in more places, supporting a more exploration-based interaction. Specifically, we now show `help` for cases where the required arguments are not met.

Say you're trying to find out how to list the details of a machine in MAAS e.g.

 ```nohighlight
$ PROFILE=foo
$ maas login $PROFILE http://$MY_MAAS:5240/MAAS/ $APIKEY
$ maas $PROFILE
usage: maas $PROFILE [-h] COMMAND ...

Issue commands to the MAAS region controller at http://$MY_MAAS:5240/MAAS/api/2.0/.

optional arguments:
  -h, --help            show this help message and exit

drill down:
  COMMAND
    account             Manage the current logged-in user.
    bcache-cache-set    Manage bcache cache set on a machine.
    bcache-cache-sets   Manage bcache cache sets on a machine.
 
✂️--cut for brevity--✂️
    machine             Manage an individual machine.
    machines            Manage the collection of all the machines in the MAAS.
    node                Manage an individual Node.
    nodes               Manage the collection of all the nodes in the MAAS.
✂️--cut for brevity--✂️

too few arguments
$ maas $PROFILE node 
usage: maas $PROFILE node [-h] COMMAND ...

Manage an individual Node.

optional arguments:
  -h, --help        show this help message and exit

drill down:
  COMMAND
    details         Get system details
    power-parameters
                    Get power parameters
    read            Read a node
    delete          Delete a node

The Node is identified by its system_id.

too few arguments

$ maas $PROFILE node read
usage: maas $PROFILE node read [--help] [-d] [-k] system_id [data [data ...]]

Read a node

positional arguments:
  system_id
  data

optional arguments:
  --help, -h      Show this help message and exit.
  -d, --debug     Display more information about API responses.
  -k, --insecure  Disable SSL certificate check

Reads a node with the given system_id.

the following arguments are required: system_id, data
$ maas $PROFILE node read $SYSTEM_ID
{
    "system_id": "$SYSTEM_ID",
    "domain": {
        "authoritative": true,
        "ttl": null,
        "is_default": true,
        "id": 0,
        "name": "maas",
        "resource_record_count": 200,
        "resource_uri": "/MAAS/api/2.0/domains/0/"
✂️--cut for brevity--✂️
```

We can see at each stage `help` which gives us clues as to what the next step is, finally arriving at a complete CLI command.

## MAAS 3.0 Beta 2

New features for MAAS 3.0 Beta 2.

### Registering a machine as a VM host during deployment

When deploying a machine through the API, it’s now possible to specify `register_vmhost=True` to have LXD configured on the machine and registered as a VM host in MAAS (similar to what happens with virsh if `install_kvm=True` is provided).

## MAAS 3.0 Beta 1

New features for MAAS 3.0 Beta 1

### PCI and USB devices are now modelled in MAAS

MAAS 3.0 models all PCI and USB devices detected during commissioning:

- Existing machines will have to be recommissioned to have PCI and USB devices modelled
- PCI and USB devices are shown in the UI and on the API using the node-devices endpoint
- Node devices may be deleted on the API only

On the API using the allocate operation on the machines endpoint a machine may allocated by a device vendor_id, product_id, vendor_name, product_name, or commissioning_driver.

### IBM Z DPM partition support

IBM Z14 GA2 (LinuxOne II) and above mainframe partitions are supported in MAAS 3.0. Note that partitions (LPARS) must pre-configured and use qeth-based network devices (use HyperV sockets and properly-defined storage groups like Hipersockets or OSA adaptors) and properly-defined (FCP) storage groups.. IBM Z DPM Partitions can be added as a chassis, which allows you to add all partitions at once.

### Proxmox support

MAAS 3.0 supports Proxmox as a power driver:

- Only Proxmox VMs are supported
- You may authenticate with Proxmox using a username and password or a username and API token
- If an API token is used, it must be given permission to query, start and stop VMs.
- Proxmox VMs can be added as a chassis; this allows you to add all VMs in Proxmox at once.

Note that proxmox support has also been back-ported to MAAS 2.9

### LXD projects support

MAAS 3.0 supports the use of LXD projects:

- LXD VM hosts registered in MAAS are now tied to a specific LXD project which MAAS uses to manage VMs
- MAAS doesn’t create or manage machines for VMs in other projects
- MAAS creates the specified project when the VM host is registered, if it doesn't exist
- All existing VMs in the specified project are commissioned on registration
- Resource usage is reported at both project and global levels

### PCI and USB device tabs in UI machine details

Tables for detected PCI and USB devices have been added to the machine details page for MAAS 3.0:

<a  href="https://discourse.maas.io/uploads/default/original/2X/8/87f42bafe321d45af94d73216f933a9067f01df2.png" target = "_blank"><img src="https://discourse.maas.io/uploads/default/original/2X/8/87f42bafe321d45af94d73216f933a9067f01df2.png"></a>

These tables include a new skeleton loading state while node devices are being fetched:

![image](https://discourse.maas.io/uploads/default/original/2X/4/4faa1d8cd996a25ee5089ada924b405bc8903aa4.png)

The user is prompted to commission the machine if no devices are detected.

### Workload annotations

Workload annotations have been added to the machine summary page in MAAS 3.0. These allow you to apply `owner_data` to a machine and make it visible while the machine is in allocated or deployed state:

![image](https://discourse.maas.io/uploads/default/original/2X/5/54682ae5f9c7bb449a1ad222679be0156f27d109.png)

This data is cleared once the machine state changes to something other than "allocated" or "deployed."  The machine list can be filtered by these workload annotations. MAAS will warn you on the release page to remind you that workload annotations will be cleared upon releasing the machine.

### Fixed status bar

In MAAS 3.0, a fixed status bar has been added to the bottom of the screen, which will always display the MAAS name and version on the left. The right side of the status bar is intended to show contextual data, depending on the UI panel currently displayed. For now, the only data shown is a “last commissioned” timestamp when the user is on a machine details page:

![image](https://discourse.maas.io/uploads/default/original/2X/3/3a15d7e1d7251f3e928e3054a2aab71f414503bd.png)


## Bug fixes

MAAS 3.0 incorporates a large number of bug fixes, summarised in the sections below. Please feel free to validate these fixes at your convenience and give us feedback if anything doesn't seem to work as presented in the bug request.

One particular bug, [#1916860](https://bugs.launchpad.net/maas/+bug/1916860)**^**, involves failures in the IPMI cipher suite in MAAS 2.9.2 and up, on the Lenovo x3650 M5 (and others). This particular bug is a not a MAAS bug, but a firmware issue with the subject machines. While the MAAS team can't fix this (hence the assignment of "Won't Fix"), the team did provide a easy [workaround](https://bugs.launchpad.net/maas/+bug/1916860/comments/27)**^** which helps circumvent this issue.

### MAAS 3.0 bug fixes

Here are the bugs that were 'Fix Released' for the MAAS 3.0 release:

|Number | Description | Importance |
|:------|:------------|:-----------|
|[#1932136](https://bugs.launchpad.net/bugs/1932136)**^**|interface with a warning is not configured properly| Critical|
|[#1896771](https://bugs.launchpad.net/bugs/1896771)**^**|interfaces that are not connected are detected as 'connected to slow interface'|Medium|

### MAAS 3.0 RC2 bug fixes

Here are the bugs that have been 'Fix Released' in MAAS 3.0 RC2:

| Number | Description | Importance |
|:-------|:------------|:-----------|
|[#1929552](https://bugs.launchpad.net/bugs/1929552)**^**|Deb-based controller fails to run machine-resources|Critical|
|[#1929576](https://bugs.launchpad.net/bugs/1929576)**^**|Machines fail to commission using the 3.0 snap due to possible? DNS issue|Critical|
|[#1930227](https://bugs.launchpad.net/bugs/1930227)**^**|Failure to commission when interfaces has a /32 IP |Critical|  
|[#1930554](https://bugs.launchpad.net/bugs/1930554)**^**|vm-host CLI command is now named vmhosts  |Critical| 
|[#1930587](https://bugs.launchpad.net/bugs/1930587)**^**|Different disks with same LUN detected as multipath  |Critical|  
|[#1931215](https://bugs.launchpad.net/bugs/1931215)**^**|[.0~rc2-10023 testing] two IPs assigned to one interface  |Critical| 
|[#1931838](https://bugs.launchpad.net/bugs/1931838)**^**|Reverse DNS lookup fails for subnets smaller than /24  |Critical| 
|[#1835292](https://bugs.launchpad.net/bugs/1835292)**^**|UI should add button to download curtin-logs.tar on deployment failure MAAS |High| 
|[#1908552](https://bugs.launchpad.net/bugs/1908552)**^**|maas init fails; 'relation "maasserver_routable_pairs" does not exist'  |High|  
|[#1929086](https://bugs.launchpad.net/bugs/1929086)**^**|LXD VM hosts can't be refreshed if VLANs interfaces aren't named $parent.$vid  |High| 
|[#1929643](https://bugs.launchpad.net/bugs/1929643)**^**|MAAS often fails and and returns a Pickled object if request header is set to Accept: */*  |Medium|  
|[#1924820](https://bugs.launchpad.net/bugs/1924820)**^**|Trying to edit a disconnected NIC, then cancelling the edit and connecting the NIC via its drop-down menu, many drop-down menu options then disappear|Undecided| 

### MAAS 3.0 RC1 bug fixes

Here are the bugs that have been 'Fix Released' in MAAS 3.0 RC1:

| Number | Description |Importance|
|:-----|:-----|:-----:|
[#1774529](https://bugs.launchpad.net/bugs/1774529)**^**|Cannot delete some instances of model 'Domain' because they are referenced through a protected foreign key|High|
[#1919001](https://bugs.launchpad.net/bugs/1919001)**^**|Unable to network boot VM on IBM Z DPM Partition|High|
[#1925249](https://bugs.launchpad.net/bugs/1925249)**^**|MAAS detects 0 cores, RAM available for KVM host, reports negative availability on pod compose|High|
[#1927292](https://bugs.launchpad.net/bugs/1927292)**^**|Updating controller has vlan_ids error|High|
[#1927657](https://bugs.launchpad.net/bugs/1927657)**^**|Global kernel command line options not passed with tags|High|
[#1928098](https://bugs.launchpad.net/bugs/1928098)**^**|If a workload annotation has a key with spaces in it, filtering doesn't work|High|
[#1926140](https://bugs.launchpad.net/bugs/1926140)**^**|maas_url not returned to the UI|Medium|
[#1926171](https://bugs.launchpad.net/bugs/1926171)**^**|Failure processing network information when adding a rack|Medium|
[#1927036](https://bugs.launchpad.net/bugs/1927036)**^**|Incorrect value "accept_ra" in interface definition|Medium|
[#1927340](https://bugs.launchpad.net/bugs/1927340)**^**|Deb to snap migration script should support remote Postgres|Medium|
[#1928104](https://bugs.launchpad.net/bugs/1928104)**^**|New workload annotations don't show up without a reload|Medium|
[#1928115](https://bugs.launchpad.net/bugs/1928115)**^**|API still refers to "owner data" rather than "workload annotations"|Medium|
[#1922891](https://bugs.launchpad.net/bugs/1922891)**^**|MAAS configures nodes with incorrect DNS server addresses when using multiple IP addresses|Undecided|
[#1923268](https://bugs.launchpad.net/bugs/1923268)**^**|grubnet default grub.cfg should try /grub/grub.cfg-${net_default_mac} before /grub/grub.cfg|Undecided|
[#1926164](https://bugs.launchpad.net/bugs/1926164)**^**|VLAN page shows odd "Rack controllers" value|Undecided|
[#1926510](https://bugs.launchpad.net/bugs/1926510)**^**|dhcp subnet snippets are NOT inside the pool block|Undecided|
[#1927559](https://bugs.launchpad.net/bugs/1927559)**^**|Default logical volume size too big in UI|Undecided|
[#1928024](https://bugs.launchpad.net/bugs/1928024)**^**|UI states commissioning/testing scripts were never uploaded|Undecided|
[#1928226](https://bugs.launchpad.net/bugs/1928226)**^**|Information "not available" indicates that it''s an error of some sort|Undecided|
[#1928235](https://bugs.launchpad.net/bugs/1928235)**^**|notes field won't update properly: MAAS 3.0 RC]()**^**|Undecided|
[#1928324](https://bugs.launchpad.net/bugs/1928324)**^**|updating a machine zone or resource pool doesn't refresh details|Undecided|

### MAAS 3.0 Beta 5 bug fixes

Here are the bugs that have been `Fix Released` in MAAS 3.0 Beta 5:

| Number | Description |Importance|
|:-----|:-----|:-----:|
|[#1925784](https://bugs.launchpad.net/bugs/1925784)**^**|Processing LXD results failure with loopback|Critical|
|[#1923871](https://bugs.launchpad.net/bugs/1923871)**^**|LXD vmhost project usage includes usage for other projects|High|
|[#1815084](https://bugs.launchpad.net/bugs/1815084)**^**|MAAS web ui should perform Save action when Enter/Return is pressed|Medium|
|[#1923867](https://bugs.launchpad.net/bugs/1923867)**^**|Commissioning fails if NIC gets different PCI address|Medium|

### MAAS 3.0 Beta 4 bug fixes

Here are the bugs that have been `Fix Released` in MAAS 3.0 Beta 4:

| Number | Description |Importance|
|:-----|:-----|:-----:|
|[#1923246](https://bugs.launchpad.net/bugs/1923246)**^**|Unable to compose LXD VM with multiple NICs |High |
|[#1918963](https://bugs.launchpad.net/bugs/1918963)**^**|Controllers page out of sync with nodes |Undecided |
|[#1923685](https://bugs.launchpad.net/bugs/1923685)**^**|Unable to deploy LXD VM host on S390X |Undecided |
|[#1923687](https://bugs.launchpad.net/bugs/1923687)**^**|LXD VM host refresh failure is ignored |Undecided |
|[#1774529](https://bugs.launchpad.net/bugs/1774529)**^**|Cannot delete some instances of model 'Domain' because they are referenced through a protected foreign key |High |
|[#1914762](https://bugs.launchpad.net/bugs/1914762)**^**|test network configuration broken with openvswitch bridge |High |
|[#1919001](https://bugs.launchpad.net/bugs/1919001)**^**|Unable to network boot VM on IBM Z DPM Partition |High |
|[#1917963](https://bugs.launchpad.net/bugs/1917963)**^**|Add chassis lowers the case of added machines |Low |
|[#1915087](https://bugs.launchpad.net/bugs/1915087)**^**|2.9 UI is broken, seems to loop between user intro and machines pages endlessly |High |
|[#1923842](https://bugs.launchpad.net/bugs/1923842)**^**|Can't use action menu on machine details page |High |
|[#1917667](https://bugs.launchpad.net/bugs/1917669)**^**|Commissioning/testing scripts no longer show ETA or progress |Undecided |
|[#1917669](https://bugs.launchpad.net/bugs/1917669)**^**|No way to view previous commissioning or testing script results |Undecided |
|[#1917670](https://bugs.launchpad.net/bugs/1917670)**^**|Storage and interface tests not assoicated with a device |Undecided |
|[#1917671](https://bugs.launchpad.net/bugs/1917671)**^**|Commissioning/testing scripts not updated after starting commissioning or testing |Undecided |
|[#1917794](https://bugs.launchpad.net/bugs/1917794)**^**|Unable to view full history of events in UI |Undecided |
|[#1918964](https://bugs.launchpad.net/bugs/1918964)**^**|UI shows action unavailable after performing action |Undecided |
|[#1918966](https://bugs.launchpad.net/bugs/1918966)**^**|Tabs aren't always underscorred |Undecided |
|[#1918971](https://bugs.launchpad.net/bugs/1918971)**^**|UI does not autofill size on storage tab |Undecided |
|[#1923524](https://bugs.launchpad.net/bugs/1923524)**^**|Unable to delete LXD composed machine on KVM page |Undecided |

### MAAS 3.0 Beta 3 bug fixes

Here are the bugs that have been `Fix Released` in MAAS 3.0 Beta 3:

| Number | Description |Importance|
|:-----|:-----|:-----:|
|[#1922569](https://bugs.launchpad.net/bugs/1922569)**^**| Create KVM fails in MAAS 3.0 Beta with a project error |High|
|[#1923251](https://bugs.launchpad.net/bugs/1923251)**^**| Creating an LXD VM host now requires a project name |High|
|[#1809939](https://bugs.launchpad.net/bugs/1809939)**^**| dhcp snippet create fail when dhcp subnet is relayed |Medium|
|[#1913460](https://bugs.launchpad.net/bugs/1913460)**^**| Add option to pick whether to keep or decompose machines in a VM host |Undecided|
|[#1922787](https://bugs.launchpad.net/bugs/1922787)**^**| make "LXD" the default VM host in MAAS UI (rather than virsh) |Undecided|
|[#1922876](https://bugs.launchpad.net/bugs/1922876)**^**| Deploy KVM hosts with LXD by default |Undecided|
|[#1922972](https://bugs.launchpad.net/bugs/1922972)**^**| MAAS 3.0 Beta2 UI says "machine cannot be deployed" while successfully deploying machine |Undecided|
|[#1923719](https://bugs.launchpad.net/bugs/1923719)**^**| MAAS 3.0 : snap refresh maas from 3.0.0~beta2-9826-g.13cc184d5 |Undecided|

### MAAS 3.0 Beta 2 bug fixes

Here are the bugs that have been `Fix Released` in MAAS 3.0 Beta 2:

| Number | Description |Importance|
|:-----|:-----|:-----:|
|[#1922107](https://bugs.launchpad.net/bugs/1922107)**^**| Hugepages/pinning available for virsh and lack validation |High|
|[#1922433](https://bugs.launchpad.net/bugs/1922433)**^**| Machine resources path set incorrectly in rackd when using snap |High|

### MAAS 3.0 Beta 1 bug fixes

Here are the bugs that have been `Fix Released` in MAAS 3.0 Beta 1:

| Number | Description |Importance|
|:-----|:-----|:-----:|
|[#1896199](https://bugs.launchpad.net/maas/+bug/1896199)**^** |API docs link is not offline|Critical|
|[#1904245](https://bugs.launchpad.net/bugs/1904245)**^**|MAAS Snap fails to build on PPC64 on Launchpad |Critical|
|[#1912727](https://bugs.launchpad.net/bugs/1912727)**^**|KVM Page Fails to load with error "An unexpected error has occurred, please try refreshing your browser window." |Critical|
|[#1915869](https://bugs.launchpad.net/bugs/1915869)**^**| maas snap cli renders SyntaxWarning in the stderr |Critical|
|[#1916093](https://bugs.launchpad.net/bugs/1916093)**^**|Unable to add more than 3 Promox VMs |Critical| 
|[#1883824](https://bugs.launchpad.net/bugs/1883824)**^**|Support LXD projects in power control |High| 
|[#1884276](https://bugs.launchpad.net/bugs/1884276)**^**|Terrible user experience adding existing LXD host |High| 
|[#1902425](https://bugs.launchpad.net/bugs/1902425)**^**|Failed to allocate the required AUTO IP addresses after 2 retries |High| 
|[#1908087](https://bugs.launchpad.net/bugs/1908087)**^**|Reverse DNS for non-maas RFC1918 zones fails inside maas |High| 
|[#1908356](https://bugs.launchpad.net/bugs/1908356)**^**|Owner data websocket methods are not working |High|
|[#1908434](https://bugs.launchpad.net/bugs/1908434)**^**|Can't delete LXD VM in offline state |High| 
|[#1913323](https://bugs.launchpad.net/bugs/1913323)**^**|/MAAS/docs/ leads to 404 page |High| 
|[#1914588](https://bugs.launchpad.net/bugs/1914588)**^**|Enabling debug from snap traceback |High| 
|[#1915021](https://bugs.launchpad.net/bugs/1915021)**^**|Mapping subnet doesn't work from the MAAS snap |High| 
|[#1915022](https://bugs.launchpad.net/bugs/1915022)**^**|The MAAS snap doesn't include nmap |High| 
|[#1915715](https://bugs.launchpad.net/bugs/1915715)**^**|LXD VM additional disks all show 10Gb size |High| 
|[#1915970](https://bugs.launchpad.net/bugs/1915970)**^**|Facebook Wedge BMC detection fails on non-x86 architectures |High| 
|[#1918997](https://bugs.launchpad.net/bugs/1918997)**^**|MAAS does not set snap proxy |High| 
|[#1919000](https://bugs.launchpad.net/bugs/1919000)**^**|Unable to connect MAAS to an LXD VM host |High| 
|[#1887797](https://bugs.launchpad.net/bugs/1887797)**^**|Impossible to delete zombie LXD VM |Medium| 
|[#1894116](https://bugs.launchpad.net/bugs/1894116)**^**|Machines can't be deployed after deselecting all archs in the "Ubuntu extra architectures" package repo |Medium| 
|[#1897946](https://bugs.launchpad.net/bugs/1897946)**^**|hi1620-based ARM Servers are shown as "Unknown model" |Medium| 
|[#1906212](https://bugs.launchpad.net/bugs/1906212)**^**|timeout in testing scripts ignores the days if set to greater than 24 hours |Medium| Hemanth Nakkina 
|[#1911825](https://bugs.launchpad.net/bugs/1911825)**^**|Unable to use FQDN as power_address |Medium| 
|[#1914165](https://bugs.launchpad.net/bugs/1914165)**^**|Proxmox does not allow custom port |Medium| 
|[#1917652](https://bugs.launchpad.net/bugs/1917652)**^**|30-maas-01-bmc-config failing on commissioning Cisco UCSC-C220-M4L |Medium| 
|[#1335175](https://bugs.launchpad.net/bugs/1335175)**^**|maas does not combine kernel_opts when nodes have multiple tags with kernel options |Low| 
|[#1915359](https://bugs.launchpad.net/bugs/1915359)**^**|make sampledata can't find machine-resources |Low| 
|[#1916844](https://bugs.launchpad.net/bugs/1916844)**^**|Removing a machine that is a vm host tells you to remove the "pod" |Low| 
|[#1920019](https://bugs.launchpad.net/bugs/1920019)**^**|maas_remote_syslog_compress is unnecessarily chatty |Low| 
|[#1887558](https://bugs.launchpad.net/bugs/1887558)**^**|Multipath JBOD storage devices are not shown via /dev/mapper but each path as a single device. |Wishlist| 
|[#1901944](https://bugs.launchpad.net/bugs/1901944)**^**|tags field in machine edit page overtakes other fields |Undecided| 
|[#1909985](https://bugs.launchpad.net/bugs/1909985)**^**|Add commission timestamp to machine websocket api |Undecided| 
|[#1913464](https://bugs.launchpad.net/bugs/1913464)**^**|Drop RSD pods UI |Undecided| 
|[#1914590](https://bugs.launchpad.net/bugs/1914590)**^**|Support composing LXD VMs with multiple disks in the UI |Undecided| 
|[#1915970](https://bugs.launchpad.net/bugs/1915970)**^**|Facebook Wedge BMC detection fails on non-x86 architectures |Undecided| 
|[#1916073](https://bugs.launchpad.net/bugs/1916073)**^**|MAAS should install qemu-efi-aarch64 on arm64 KVM pods |Undecided| 
|[#1916317](https://bugs.launchpad.net/bugs/1916317)**^**|UI is using API to request scripts with full content |Undecided| 
|[#1919381](https://bugs.launchpad.net/bugs/1919381)**^**|typo "veryiying" in info message in smartctl-validate |Undecided|
