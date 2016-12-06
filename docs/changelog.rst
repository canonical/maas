=========
Changelog
=========

2.1.3
=====

Bugs fixed in this release
--------------------------


LP: #1582323    Select MAAS datasource specifically to ensure commissioning doesn't fail when competing cloud metadata resides on disk

LP: #1646163    [2.1] Icon need to be improved

LP: #1646162    [2.1] Sticky header has been removed

LP: #1646160    [2.1] Device discovery UI does not have a loading state

LP: #1628126    [2.1, FUJ] Column layout shouldn't resize until screen is smaller than 1440

LP: #1628058    [2.1, FUJ] The form spacing is not compatible to the designs

LP: #1628054    [2.1, FUJ] Section complete/incomplete icon

LP: #1639182    [2.1] log format differs for Yakkety

LP: #1637401    Re-adding virsh chassis to discover new nodes powers down existing nodes


2.1.2
=====

Bugs fixed in this release
--------------------------

LP: #1516065    Fix IPMI chassis config session timeout issue when configuring the boot device.  Only error on PowerAuthErrors when configuring the IPMI chassis boot order.

LP: #1642996    2.x preseeds with {{escape.shell}} fail if not upgraded at 2.1.1

LP: #1643057    juju2 with maas 2.1.1 LXD containers get wrong ip addresses

LP: #1640300    Be defensive in the postgresql listener when a system notification is received for a none existent handler or missing listener channel.

LP: #1613862    Re-allow configuration of the port where to connect to postgresql.

LP: #1638575    Add two capabilities: bridging-interface-ubuntu and bridging-automatic-ubuntu.


2.1.1
=====

Bugs fixed in this release
--------------------------

LP: #1554636    maas serving old image to nodes

LP: #1593991    [2.0b7, API/CLI] allows you to add machines with power_type and no power_parameters

LP: #1602482    [2.0rc2] Incorrect DNS records

LP: #1620478    [2.1, UI] Broken validation on VLAN MTU

LP: #1630636    [2.1 ipv6] YAML error when maas_url has an IPv6 IP

LP: #1630679    [2.1b1] Can't use custom image repository

LP: #1633717    [2.1] DHCP probe needs to be smarter about interface selection to avoid log spam

LP: #1636858    [2.1.1, trunk, bzr5510] Can't enlist machines

LP: #1636861    [2.1.1, trunk, bzr5510] UI error when adding a chassis

LP: #1636992    [2.1] Deleting all boot sources and creating a new boot source, does not update the cache

LP: #1598175    [2.0] If the machine is deployed, I cannot update NIC's nor storage

LP: #1603563    [2.0 RC2] Multiple failures to release nodes

LP: #1606508    [2.1] Failover peers must be IPv4 for use with ISC dhcpd

LP: #1632853    [2.1] Observed neighbours should be avoided when assigning IP addresses

LP: #1633401    [2.1] In device discovery in Settings, remove the header of the first dropdown field (Host discovery and network observation)

LP: #1633452    [2.1] In settings, rename the option Disabled (suppress active scanning) in the Active discovery interval field to Never (disabled).

LP: #1633462    [2.1] In settings in the device discovery section reduce the text of the explanation of the fields.

LP: #1633822    [2.1] Device discovery ignores reverse DNS

LP: #1636250    [2.1] machines allocate API returns a random machine if incorrect - parameters are used

LP: #1636873    [2.1.0] Creating a bond doesn't work and no feedback is provided if fabric in interfaces is 'disconnected'

LP: #1636874    [2.1, Yakkety] Plus '+' button is not visible when you hover over an interface in machine details

LP: #1637009    [2.0,2.1] Node acquisition constraints API documentation needs to be updated to match reality

LP: #1637182    Help and documentation 'list of unicodes' inconsistent

LP: #1637192    [2.0,2.1] Allocate using subnets or not_subnets with space fails

LP: #1637246    MaaS should use configured names for VLAN interfaces

LP: #1638284    [2.1.1pre] Debug logging shown by default in regiond.conf

LP: #1638288    [2.1.1 pre] A lot of repeated logging

LP: #1638589    [2.1] commissioning doesn't find the second address family on the boot interface

LP: #1600328    [2.0rc1, API/CLI] When adding a new machine and no rack controller can connect to the BMC, no error message is displayed.

LP: #1633378    [Device Discovery] Rename the section Header in the Settings page

LP: #1633600    [2.1.1] Docs do not mention the need to mirror bootloaders

LP: #1636251    resolv.conf search path doesn't match the domain for the host


2.1.0
=====

Important announcements
-----------------------

**New MAAS dashboard, now including discovered devices!**
 In MAAS 2.1, administrators will be redirected to the new MAAS dashboard
 after they log in to the Web UI. On the dashboard, administrators are guided
 through where to go to quickly get MAAS up and running. In addition,
 administrators can view hosts that have been discovered on the network, and
 quickly convert them to a device in MAAS.

**Image streams have been upgraded to v3. (Important: update your mirrors!)**
 In order to support the new kernels, MAAS has moved to a new format for image
 streams. Previous releases used stream in “v2” format. Starting from MAAS 2.1,
 the “v3” format image stream will be used.

 Users upgrading from earlier versions of MAAS who are using the default images
 URL will be automatically migrated to the new “v3” URL.

 For users with custom mirrors, MAAS will not migrate the image URL
 automatically. Users must ensure their image mirrors contain the “v3” stream,
 which is available at http://images.maas.io/ephemeral-v3/. Old images
 downloaded from the “v2” stream will continue to work until the mirror is
 updated, but the MAAS team only supports MAAS 2.1 users using the “v3” stream.
 Please note that bootloaders are now included in the mirror; be sure to mirror
 them in addition to the images.

**New hardware enablement kernel naming convention**
 Starting from MAAS 2.1 and Ubuntu 16.04 "Xenial", MAAS is adhering to a new
 naming convention for hardware enablement kernels. On Xenial and above, MAAS
 will not support HWE kernels with the old naming convention, but it will
 support HWE kernel channel. For example, given Ubuntu 16.04 "Xenial" and
 Yakkety, currently available kernels in MAAS are:

  * ga-<version>
    The GA, or general availability kernel is the kernel which the Ubuntu
    release shipped with. For example ‘ga-16.04’ is the default 4.4 kernel
    which shipped on Ubuntu 16.04 "Xenial". The ga kernel contains all bug and
    security fixes provided by the Ubuntu archives. Deployments which use the
    ga kernel will stay at the same kernel version through upgrades until the
    entire release is upgraded with ‘do-release-upgrade.’

  * hwe-<version>
    The latest Hardware Enablement Kernel currently available in a given
    Ubuntu release. As new Hardware Enable Kernels are released with new Ubuntu
    releases the hwe-<version> kernel will be upgraded up until the next LTS.
    For example hwe-16.04 is currently the 16.04 GA kernel. Once 16.10 is
    released the hwe-16.04 kernel will be upgraded to the 16.10 GA kernel. The
    kernel will continue to be upgraded up until and including the 18.04 GA
    kernel.

**Commissioning-user-data and pxe/uefi templates no longer available**
 In the past, MAAS stored commissioning-user-data and pxe/uefi templates in
 /etc/maas/templates. As of MAAS 2.1, these templates are no longer available
 under /etc/maas.

Major new features
------------------

**First user configuration journey (UI)**
 MAAS now provides the ability for administrators to perform some initial
 configuration immediately after they log-in into the MAAS UI for the first
 time. The configuration includes:

  * Ability to change the name of your MAAS
  * Ability to configure options that affect connectivity:
    * Option to select an Upstream DNS Server (Optional)
    * Option to input different Ubuntu Mirrors (Required)
    * Option to input an external proxy (Optional)
  * Ability to select additional images to download
  * Ability to import SSH keys from Launchpad or Github

**Device discovery**
 MAAS will now automatically listen to the network and report any discovered
 devices. Devices are identified when the MAAS rack observes them
 communicating on an attached IPv4 subnet. Discovered devices that do not
 correspond to machines and devices already known to MAAS are shown on the
 dashboard. If a device advertises a hostname using mDNS (such as with avahi
 or Bonjour), MAAS will also present the discovered hostname in the dashboard.
 Using the dashboard, a discovery can quickly be added to MAAS as a device or
 as a network interface to a machine or device.

**Active subnet mapping**
 The device discovery feature was designed to operate passively by default.
 While MAAS will not send any traffic on attached networks for discovery
 purposes unless instructed to, there are two ways to instruct MAAS to map
 your networks:

  * On-demand: administrators can choose to map their subnet using an action
    on the subnet details page. This action will scan the subnet just once, so
    that observed devices on that subnet may quickly be seen in the dashboard.
    This feature is useful after initially installing MAAS, to quickly populate
    the list of discoveries with active devices on the network.

  * Periodically (recommended): by enabling active discovery on a per-subnet
    basis, subnets will be scanned at a user-specified interval. (default is
    every three hours) This allows MAAS to maintain current information about
    which IP addresses are in use on each subnet.

 Before actively mapping any networks, it is recommended that the ‘nmap’
 package be installed on each MAAS rack controller. Doing so results in faster
 scans that require less network traffic. (If ‘nmap’ is not installed, MAAS
 will resort to scanning using the ‘ping’ utility.)

**Offline deployment and customizable APT repositories**
 MAAS 2.1 improves its offline deployment capabilities by adding support for
 Ubuntu derived repositories, PPAs, and custom APT repositories. This enables
 MAAS to configure deployed machines with the correct APT repositories and
 keyrings, without being dependent on Internet connectivity.

  * Ubuntu Derived Repositories (from an Ubuntu Mirror)
    MAAS 2.0 and earlier versions only allowed users to change the Ubuntu
    archive to use. This was limited to defining the location of an official
    Ubuntu mirror.

    Derived repositories are based on an Ubuntu mirror, but have had packages
    added or removed, which requires signing the repository with an unofficial
    GPG key. MAAS now allow users to provide GPG key fingerprints to support
    this type of repository. These fingerprints are required in order for
    the derived repository to be trusted, and will be added to the APT keyring
    on each machine.

  * PPAs
    PPAs can now be specified, which will be added to the APT sources on
    deployed machines. Users may define a GPG key fingerprint in order for
    the machine to trust the PPA, for cases where the deployed machine cannot
    access the Ubuntu key server.

  * Custom repositories
    Custom repositories can be specified to add additional packages to deployed
    machines. For custom repositories, the distribution and component can be
    customized as appropriate. For example, users would be able to add the
    Google Chrome repository, which is as follows:

    deb http://dl.google.com/linux/chrome/deb/ stable main

    In this case, the distribution is “stable”, and the component is “main”.
    (Multiple components may also be specified.)

**MAAS time sync, NTP services and configuration**
 MAAS now provides managed NTP services (with ntpd) for all region and rack
 controllers. This allows MAAS to both keep its own controllers synchronized,
 and keep deployed machines synchronized well.

  * Region controllers synchronize time externally
    The MAAS region controller configures the NTP service (ntpd) to keep its
    time synchronized from one or more external sources. By default, the MAAS
    region controller uses ntp.ubuntu.com. This can be customized on the
    settings page.

  * Rack controllers synchronize time from the region controller
    The rack controllers also configure the NTP service (ntpd). Unlike the
    region controllers, rack controllers synchronize their time from region
    controllers, rather than accessing an external time source.

    Rack controllers also configure DHCP with the correct NTP information, so
    that any machine on the network that obtains a DHCP lease from MAAS will
    benefit from the enhanced NTP support.

  * Controllers and Machines can synchronize time for external time sources only.
    MAAS 2.1 also provides the ability to directly use external time sources
    without using the Rack Controller as a source of time for machines. This
    means that administrators who already have their own NTP infrastructure,
    and they don’t want MAAS to provide NTP services, they can tell all
    machines and controllers to sync their time from the external time source.
    This can be done by selecting the "External Only" option on the Settings
    page.

**Advanced networking: static routes**
 MAAS 2.1 introduces the ability to define static routes. This allows
 administrators to configure reachability to a subnet from a source subnet.
 Administrators can define routes on a per-subnet basis to use a particular
 gateway, using a configured destination and metric.

**Machine networking: bridge configuration**
 MAAS now supports the creation of bridge interfaces. This support is limited
 to the ability to create a bridge against a single interface, such as for the
 purpose of eventually deploying virtual machines or containers on the machine.

 Automatic bridge creation on all configured interfaces can also be performed
 at allocation time using the API.

**Rescue mode**
 MAAS 2.1 supports a new state in the machine lifecycle: rescue mode. Rescue
 mode allows users to boot a Deployed or a Broken using an ephemeral image.
 (That is, Ubuntu is running in memory on the machine.) This allows
 administrators to SSH to the machine for maintenance purposes, similar to
 running Ubuntu from a USB stick.

**Enhanced images user interface**
 The MAAS images page has been completely redesigned. Improvements include:

  * Supports selecting the image source (maas.io or custom repository).
  * Now shows the image releases and architectures available in a repository before the import starts.
  * Now displays detailed status throughout the image import process.
  * The Boot Images section in the settings page has been removed.

Minor new features
------------------

**Disk erasing improvements and secure erase**
 In 1.7 (and later) MAAS introduced the ability to erase disks on machine
 release. This support was limited to erasing the whole disk and could only
 be enabled (or disabled) globally.

 Starting from MAAS 2.1, it now supports the ability to request disk erasure
 on a per-machine basis, at the time the machine is released. In addition, new
 options for the disk erase mode have been added:

  * Secure erase - If this option is enabled, MAAS will attempt to erase via
    secure erase (if the storage device support it), otherwise, it will perform
    a full erase or a quick erase (depending on the options provided).

  * Quick erase - If this option is enabled, MAAS will only erase the beginning
    and the end of each storage device.

**Machine networking: - SR-IOV auto-tagging, tags UI**
 MAAS now allows the definition of tags per network interface via the WebUI.
 Additionally, MAAS also attempts to auto-detect and tag SR-IOV NIC cards.

**Support for low latency kernels**
 Starting from Ubuntu 16.04 “Xenial” and later, “low latency” kernels available
 on i386 and amd64 for both GA and HWE kernels. The currently available
 lowlatency kernels are:

  * hwe-x-lowlatency - For using the Xenial Lowlatency kernel on Trusty
  * ga-16.04-lowlatency - For using the GA lowlatency kernel on Xenial
  * hwe-16.04-lowlatency - For using the HWE lowlatency kernel on Xenial.

**Bootloaders are now provided in the image stream**
 Previously, bootloaders where downloaded on the rack controller from the
 Ubuntu archives for each architecture MAAS had images for. Starting from MAAS
 2.1, bootloaders are downloaded with the images. All rack controllers retrieve
 all supported bootloaders from the region controller. MAAS no longer directly
 interacts with the Ubuntu archives.

 In the case that bootloaders are missing from the stream, MAAS will attempt
 to locate previous downloads of the bootloader as well as package installs of
 the bootloader. Users with image mirrors must ensure image their mirrors
 include the bootloaders in order to be running the latest supported versions.

**SSH keys can be imported from Launchpad or GitHub**
 All users will now have the ability to import their SSH public keys from the
 UI. Users who log-in to MAAS for the first time will be prompted to import
 their SSH keys, if desired. Alternatively, users can import keys later on
 their user profile page, or continue to upload keys manually.

Other notable changes
---------------------

**Better error surfacing for DHCP snippets and package repositories**
 Both the DHCP Snippets section and the Package Repositories section have been
 improved in order to show errors in a more user-friendly way.

**Vanilla framework: HTML and CSS updates, smoother look and feel**
 The HTML templates and CSS frameworks in MAAS have been completely rebuilt
 with the Vanilla CSS framework. Icons and interactions in MAAS have greatly
 improved; users will notice smoother, more intuitive interactions with the UI.

 The MAAS team would like to thank the Canonical design and web teams for their
 contributions in this area.

Issues fixed in this release
----------------------------

A full list of issues fixed in this release is available in the Launchpad 2.1.0
Milestone page

  https://launchpad.net/maas/+milestone/2.1.0


2.1.0 (RC1)
===========

Issues fixed in this release
----------------------------

LP: #1569365    TestPartition.test_get_partition_number_returns_starting_at_2_for_ppc64el fails spuriously

LP: #1598470    "Deployed" and "Deploying" are too similar

LP: #1536354    Users' maas api keys do not have a name

LP: #1631358    [2.1] Incorrect logging message - showing SERVICE_STATE.ON

LP: #1631420    [2.1 UI] Images page "Queued for download" is confusing when selections are not saved

LP: #1631024    [2.1b1] Dashboard column widths for discovered items are wonky

LP: #1631022    [2.1b1] 'Registering existing rack controller'

LP: #1629604    [2.1] Command 'interface link-subnet' does not work

LP: #1628114    [FUJ] SSH input field not indicated for invalid username & the error is incomprehensible

LP: #1629475    [2.1 ipv6] DHCP generation should not fail when address-family conflicts are present

LP: #1603466    [2.0rc2] Commissioning node with gateway_link_v4 set fails.

LP: #1608555    [2.1, 2.0 UI] Error when using dhcp range with pre-existing dynamic reservation

LP: #1632815    [2.1b2] Node failed to be released, because of the following error: 'NoneType' object has no attribute 'addErrback'

LP: #1632395    [2.1, Yakkety, UI] UI error when adding a chassis

LP: #1631079    [2.0, 2.1 UI] Other reserved IP ranges disappear when one of them is deleted on Subnet details page.

LP: #1630667    [2.1b1] MAAS fails to deploy systems with 3+ TB disks

LP: #1630633    [2.1 Yakkety UI] Unable to select nodes

LP: #1629061    [2.0, 2.1] Release and list IPs reserved by another user

LP: #1605476    [2.0rc2] Changing DNSSEC validation does not trigger configuration file update


2.1.0 (beta2)
=============

Issues fixed in this release
----------------------------

LP: #1630394    [2.1] Bootloaders not downloaded on initial import

LP: #1611949    cryptic error when PXE-boot requires an image not yet imported

LP: #1625676    [2.0, 2.1, UI] MAAS webui allows boot disk to be changed on an already deployed node

LP: #1630591    Rename "Networks" tab to "Subnets"

LP: #1628761    [2.1] netaddr assumes MAC OUI is ascii

LP: #1619262    [2.1, 2.0] Can't input dynamic range on "Enable DHCP" after I deleted the dynamic range

LP: #1630636    [2.1 ipv6] YAML error when maas_url has an IPv6 IP

LP: #1612203    Machine unable to pxe with no-such-image while non-related images are being imported

LP: #1628645    External DHCP detection is broken for a variety of reasons

LP: #1627362    [2.1] expected string or bytes-like object

LP: #1614659    [2.1] When trying to release a node, it gets stuck in releasing if there is no rack controller to power control

LP: #1445941    WebUI needs a filter for deployed OS


2.1.0 (beta1)
=============

Important Announcements
-----------------------

**New Hardware Enablement Kernels naming convention**
 Starting from MAAS 2.1 and Ubuntu Xenial, MAAS is adhering to a new naming
 convention for hardware enablement kernels. On Xenial and above, MAAS will
 not support HWE kernels with the old naming convention, but it will support
 HWE kernel channel. For Ubuntu Xenial and Yakkety, currently available
 kernels in MAAS now are:

 * ga-<version>
   The GA, or general availability kernel is the kernel which the Ubuntu
   release shipped with. For example ‘ga-16.04’ is the default 4.4 kernel
   which shipped on Ubuntu Xenial. The ga kernel contains all bug and security
   fixes provided by the Ubuntu archives. Deployments which use the ga
   kernel will stay at the same kernel version through upgrades until the
   entire release is upgraded with ‘do-release-upgrade.’

 * hwe-<version>
   The latest Hardware Enablement Kernel currently available in a given
   Ubuntu release. As new Hardware Enable Kernels are released with new
   Ubuntu releases the hwe-<version> kernel will be upgraded up until the
   next LTS. For example hwe-16.04 is currently the 16.04 GA kernel. Once
   16.10 is released the hwe-16.04 kernel will be upgraded to the 16.10 GA
   kernel. The kernel will continue to be upgraded up until and including
   the 18.04 GA kernel.

**New Simplestreams Version - Update your images & your Image repositories**
 In order to support the new kernels, MAAS has updated the version of the
 MAAS Image streams. Previously MAAS has been using the Streams Version 2,
 and as of MAAS 2.1 it will use the MAAS Streams Version 3.

 All users who upgrade from an earlier version of MAAS who have been using
 the default image mirror, will be automatically migrated to the new version
 of streams.

 For all those users running a custom mirror, MAAS won’t make the migration
 automatically. Users are requested to update their image mirror to match the
 latest images. This image mirror is now available at
 http://images.maas.io/ephemeral-v3/.

Major new features
------------------

**Support for Low Latency kernels.**
 Starting from MAAS 2.1 Beta 1 and Ubuntu Xenial, MAAS will be making available
 the ability to install low latency kernels. Low latency kernels are available
 on i386 and amd64 for both GA and HWE kernels. The currently available
 lowlatency kernels are

  * hwe-x-lowlatency - For using the Xenial Lowlatency kernel on Trusty
  * ga-16.04-lowlatency - For using the GA lowlatency kernel on Xenial
  * hwe-16.04-lowlatency - For using the HWE lowlatency kernel on Xenial.

**Bootloaders are now provided in the SimpleStream.**
 Previously bootloaders where downloaded on the Rack Controller from the Ubuntu
 archives for each architecture MAAS had images for. Starting with MAAS 2.1
 Beta 1 bootloaders are downloaded with the images from the SimpleStream. All
 Rack Controllers retrieve all supported bootloaders from the Region Controller.
 MAAS no longer directly interacts with the Ubuntu archives.

 In the case that bootloaders are missing from the SimpleStream MAAS will
 attempt to locate previous downloads of the bootloader as well as package
 installs of the bootloader.

Minor new features
------------------

**Active Device Discovery - Map your subnet**
 To complete MAAS’ Active Discovery, starting from beta 1 MAAS 2.1 now allows
 the user to ‘Map a subnet’, both automatically at regular intervals, or
 manually:

  * Manually
    Administrators can now Map a subnet manually from the Subnet Details page
    under the ‘Take Action’ option. This will allow administrators to map
    their subnet. By default, this will use ping but if nmap is installed,
    it will automatically use nmap.

  * Automatically
    Administrators can now chose to Map their subnets Automatically at regular
    intervals. This allows administrators to have MAAS always probe on the
    network to find new devices. By default, the automatic mechanism is enabled,
    but no subnet is enabled by default.

 To automatically map each subnet, please refer to the ‘Active Discovery’
 section on the subnet details page.

Bugs fixed in this release
--------------------------

LP: #1392763    When changing sync-url via the UI, it's not obvious if syncing starts on its own or not
LP: #1508975    maas deletes products/images locally that do not exist remotely
LP: #1481285    1.8 Boot images tick boxes should be orange
LP: #1629402    [2.1] please cleanup log format for new interface monitoring state
LP: #1629011    Missing punctuation in disk erasing options
LP: #1629008    Missing preposition sentence disk erasing options
LP: #1629004    Typo: "futher"
LP: #1628052    [2.1, FUJ] Help text in input fields is missing 'e.g'
LP: #1459888    Too much spacing between checkboxes/releases in the 'Images'
LP: #1627039    [2.1] Discovery object and view doesn't set a flag when the device is the DHCP server
LP: #1627038    [2.1] SSH key import should use the specified HTTP proxy if one exists
LP: #1625714    DHCP services on rack controllers only publishes external NTP servers
LP: #1625711    Peer selection for NTP servers on region controllers is broken
LP: #1593388    Changing a boot source URL while images are being download doesn't interrupt current downloads to use the new URL
LP: #1623878    [2.1] mDNS label contains disallowed characters
LP: #1394792    MAAS could do a better job of reporting image download status
LP: #1623110    [2.1] Networks page doesn't load fully on yakkety
LP: #1629896    [2.1] Deployment defaulting to hwe-16.04 instead of ga-16.04
LP: #1629491    [2.1] After upgrade to latest trunk (pre-beta1) and after updating images, machines fail to pxe boot due to missing hwe-x kernel
LP: #1629142    2.1 DHCP reported as enabled but not running
LP: #1629045    [2.1] When failing to download images, MAAS leaves old files in the fs
LP: #1629022    [2.1, UI] Broken 'images page' link
LP: #1629019    [2.1 ipv6] log_host needs to be ipv6 when booting ipv6-only
LP: #1628298    [2.1 UI] SSH keys not listed on user page and no button to add keys
LP: #1628213    [2.1 yakkety UI] First user journey doesn't display and can't be skipped
LP: #1627363    [2.1] 'NoneType' object has no attribute 'external_dhcp'
LP: #1627019    [2.1, rev5385] NTP services on region/rack keep showing as ON/OFF constantly
LP: #1623634    [2.1, UX] Trying to cancel an image import from the new Images page results on it not being cancelled on the backend.
LP: #1589640    [2.0b6] MAAS should validate a boot source path actually provides images

Known issues and workarounds
Trusty images not available on fresh installs
The MAAS Images V3 streams do not yet have Ubuntu Trusty available. These are currently being built to be made available.

User’s upgrading from a previous version of MAAS that had originally imported Trusty images will continue to be able to deploy Trusty. Once the images are made available, MAAS will automatically update (if so configured).

LP: #1627362 - expected string or bytes-like object
In some situations after an upgrade, accessing the dashboard might yield error above. This is a difficult to easily reproduce issue. If you come across it please contact a MAAS developer immediately.

https://bugs.launchpad.net/maas/+bug/1627362


2.1.0 (alpha4)
==============

Important Announcements
-----------------------

**MAAS Landing page - Let’s see what’s on your network!**
 As of MAAS 2.1 alpha 4, administrative users have a new landing page. Once
 administrators log in they will be redirected to the MAAS dashboard.

 This dashboard is where administrators will have some basic information
 and the ability to see the observed and discovered devices.

Major new features
------------------

**Device discovery UI**
 MAAS 2.1 alpha 4 introduces the MAAS Device Discovery UI. As part of the
 dashboard, administrative users will be able to see all the observed and
 discovered devices.

 MAAS will also allow administrator to properly register those discoveries
 as MAAS known devices, and be able to select the IP address allocation for
 them, if MAAS is to manage them.

**Active Device Discovery - map your network (API only)**
 As of MAAS 2.1 alpha 2, networks attached to rack controllers are observed
 for device discovery purposes. MAAS listens to ARP requests and replies to
 determine which IPv4 addresses are in-use on attached networks, and will
 resolve their hostnames if possible (when advertised using the mDNS
 protocol).

 As of MAAS 2.1 alpha 4, MAAS now has the ability to actively probe subnets.
 This allows MAAS to keep its knowledge of which devices are on the network
 up-to-date, and discover “quiet” devices that MAAS would not be able to
 observe passively. If ‘nmap’ is installed, MAAS will prefer to use it for
 scanning (since the scan is faster and will transmit fewer packets). If
 ‘nmap’ is not installed, MAAS will fall back to using parallel ‘ping’ requests.

 Scanning is available using the API at the following URL:

    POST /MAAS/api/2.0/discovery/?op=scan

 To scan using the command-line interface, you can use the following syntax:

    maas <profile> discoveries scan [cidr=<cidr> [cidr=<cidr>....] [force=true] [always_use_ping=true] [slow=true] [threads=<num-concurrent-scanning-threads>]

 If you want to scan particular subnets, specify one or more using the cidr
 option. For example, ‘cidr=192.168.0.0/24’ would scan for neighbours on
 192.168.0.0/24 on any rack controller configured with an address in that
 network. The cidr option can be specified multiple times, such as
 ‘cidr=192.168.0.0/24 cidr=192.168.1.0/24’.

 If you want to scan all networks attached to all rack controllers, you must
 specify the “force=true” option. (This is not allowed by default, since some
 network operators do not allow active neighbour scanning.)

 If your organization has a policy against using ‘nmap’, you will want to use
 the ‘always_use_ping’ option, in case ‘nmap’ has been installed on a rack
 controller by mistake.

 If quickly scanning your network using ‘nmap’ may raise alerts with an
 intrusion detection system, you can use the ‘slow=true’ argument to slow
 down scanning. This option has no effect when using ‘ping’, since scanning
 using ‘ping’ is already slower. If using ‘ping’, scans can be slowed down or
 sped up, if desired, by using the threads option, such as by specifying
 “threads=2”. Using the threads option has less impact on nmap threads, which
 use a single thread to scan an entire network.

Minor new features
------------------

**First User Journey - Import your SSH keys from Launchpad or Github**
 The ability to import SSH keys from Launchpad or Github was introduced in
 MAAS alpha 3. As of alpha 4, you can do so via the Front-end.

 All users will now have the ability to import their SSH keys from the UI.
 All users who log-in to MAAS for the first time will be prompted to import
 their SSH keys, if they so desire. Alternatively, users can do so via their
 user profile page.

Other notable changes
---------------------

**NTP Improvements - MAAS NTP vs External**
 MAAS now provides the ability to decide between using solely an external NTP
 server or a MAAS run NTP server. MAAS run NTP services is the preferred
 configuration, but, in order to maintain backwards compatibility,
 administrators can chose to use external NTP organizations. This will only
 be suitable for scenarios where administrators have restricted communication
 between their machines and the MAAS rack controllers.

Bugs fixed in this release
--------------------------

#1625668    [2.1] When trying to add SSH keys for a GH user that doesn't exist, there's no feedback
#1626748    [2.1] maas admin discoveries scan API output shows rack controller ids instead of names
#1626722    [2.1] DHPv6 addresses do not have netmasks: do not create /128 subnets for them
#1625812    [2.1] Error message is not user friendly
#1625689    [2.1] default gateway cannot be set to fe80::/64 via web ui
#1626727    [2.1] You can define distribution or component for 'ubuntu archive' or 'ubuntu extra architectures'
#1625671    [2.1] Need better error message when trying to add SSH keys for LP/GH user that doesn't exist
#1623994    [2.1] DHCP configuration breaks when NTP servers are unresolvable.
#1626669    [2.1] Can't logout, create users and do other actions
#1625674    [2.1] No feedback when there are no keys to import from LP/GH

Known issues and workarounds
----------------------------

**LP: #1623634: Unable to cancel the image import.**
 When downloading images, MAAS will fail to cancel the import of all or
 any of the images being imported. MAAS will first download all the images
 before the user is able to remove them.

 See bug `1617596`_ for more information.

.. _1617596:
  http://launchpad.net/bugs/1617596

**LP: 1624693: Rack failed to run/register on fresh install**
 The MAAS Rack Controller is unable to register after a fresh install due to
 being unable to parse network interfaces. After manual restart of maas-rackd,
 the rack was successfully registered.

 See bug `1624693`_ for more information.

.. _1624693:
  http://launchpad.net/bugs/1624693


2.1.0 (alpha 3)
===============

Major new features
------------------

**First User Configuration Journey (UI)**
 Starting from alpha 3, MAAS now provides the ability for administrators to
 perform some initial configuration when they log-in into the UI for the
 first time. The configuration includes:

  * Ability to change the name of your MAAS.
  * Ability to configure options that affect connectivity:
  * Option to select an Upstream DNS Server (Optional)
  * Option to input different Ubuntu Mirrors (Required).
  * Option to input an external proxy (Optional)
  * Ability to select additional images to download.

**MAAS time sync, NTP services and configuration**
 Starting from alpha 3, MAAS now provides managed NTP services (with ntpd) in
 both the Region and Rack controller. This allows MAAS to not only keep its
 own controllers time synced, but the deployed machines as well.

 * Region Controller time syncs from external source
   The Region Controller configures the NTP service (ntpd) to keep its time
   sync from one or various external sources. By default, the MAAS region
   controller syncs its time from ntp.ubuntu.com. The default can be changed
   by one or multiple external NTP servers from the Settings page, under the
   Network Configuration section.

 * Rack Controller time syncs from the Region Controller
   The Rack Controllers also configure the NTP service (ntpd). Unlike the
   Region Controllers, the Rack Controllers sync their time from the Region
   Controller(s) instead of accessing directly to the external time source.

   Additionally, the Rack Controllers also configure DHCP with the correct
   NTP information, so that any machine on the network that DHCP’s from MAAS
   can benefit of the NTP configuration.

 * Machines configured to sync time from external NTP (transitional).
   MAAS also configures deployed machines with NTP configuration. This is done
   by cloud-init via MAAS vendor data.

   During the transition period, MAAS will configure machines to use the
   external time source (configured under the Settings page). Note that this
   is transitional, as in future releases the machines will default to the
   Rack Controller for NTP.

**MAAS Images page re-written in AngularJS**
 Continuing the transition from YUI to AngularJS, the MAAS Images page has now
 been completely redesigned and reimplemented in AngularJS. Improvements to
 the Image page include:

 * Ability to select the image source (maas.io or custom repository).
   Show the releases and architectures available in the custom repository
   before the import starts.

 * Ability to view the status of the image in the import process.
   Show percentage based progress on the image import.

 Additionally, the ‘Boot Images’ section in the Settings page has been removed.

**Minor new features**

 * (Backend) Ability to import SSH keys from Launchpad and Github
   MAAS now provides the ability to import SSH keys for a user from Launchpad
   and Github. This is currently supported via the API or via the user
   creation process. Users can import their SSH keys when creating their user
   for Launchpad or Github:

    maas createadmin --ssh-import lp:<user-id>
    maas createadmin --ssh-import gh:<user-id>

   Or via the API based CLI with:

    maas <maas username> sshkeys import protocol=lp auth_id=<user-id>
    maas <maas username> sshkeys import protocol=gh auth_id=<user-id>

 * MAAS now provides cloud-init vendor data for NTP
   As of MAAS 2.1 alpha 3, MAAS now provide cloud-init vendor data. Vendor
   data allows cloud-init to do some initial configurations on the system
   before user data is being run. As of 2.1, MAAS will provide NTP
   configuration which is delivered via vendor data. Note that this is
   dependent on the latest version of cloud-init (0.7.8-1-g3705bb5-0ubuntu1).
   This is currently available in Yakkety and is in progress to be available
   in Xenial.

 * Add ability to enable or disable network discovery
   MAAS now provides the ability to disable the discovery of networks and
   devices. By default, discovery is enabled. This setting can be changed
   under the Settings page, or via the MAAS CLI and API using the
   “network_discovery” configuration key. (Accepted values are “enabled” and
   “disabled”.) When discovery is disabled, mDNS records and ARP requests will
   no longer be stored in MAAS, and the listening processes on each rack
   controller will be shut down.

Other notable changes
---------------------

**HTML template updates**
 In MAAS 2.1 alpha 3, the HTML templates and SCSS framework has been
 completely rebuilt and using the current Vanilla CSS framework as its base.
 This includes all design patterns and utility classes which would be expected
 of a powerful frontend GUI framework.

 HTML and CSS templates have been completely redesigned to use the new
 “Vanilla” styles. This brings a refreshed look of icons and interactions that
 benefit the UI. While users may not see much difference, it has been
 completely re-implemented in the backend.

 Thank you the design and web teams for their contribution to MAAS.

Known issues and workarounds
----------------------------

**Unable to cancel the image import.**
 When downloading images, MAAS will fail to cancel the import of all or any of
 the images being imported. MAAS will first download all the images before the
 user is able to remove them.

 See bug `1623634`_ for more information.

.. _1623634:
  http://launchpad.net/bugs/1623634

**Unable to enable DHCP if NTP server is unresolvable.**
 If the NTP server(s) are unresolvable, DHCP will fail to enable. This is
 because DHCP doesn’t accept DNS names for DHCP’s NTP configuration, and as
 such, MAAS tries to resolve the domain before it is able to set it in the
 configuration.

 See bug `1623994`_ for more information.

.. _1623994:
  http://launchpad.net/bugs/1623994

**Rack failed to run/register on fresh install**
 The MAAS Rack Controller is unable to register after a fresh install due to
 being unable to parse network interfaces. After manual restart of maas-rackd,
 the rack was successfully registered.

 See bug `1624693`_ for more information.

.. _1624693:
  http://launchpad.net/bugs/1624693


2.1.0 (alpha2)
==============

Important Announcements
-----------------------

**commissioning-user-data and pxe/uefi templates no longer available**
 In the past, MAAS stored commissioning-user-data and pxe/uefi templates
 in `/etc/maas/templates`. As of MAAS 2.1.0 Alpha 2, these templates are
 no longer available under /etc/maas.

Major New Features
------------------

**(Backend) Device Discovery**
 As of MAAS 2.1.0 Alpha 2, MAAS will automatically listen to the network
 and report any observed devices.

  * New discovery API can be used to get information about what MAAS has
    discovered. This API can be used from the command line interface as
    follows:

    * maas <profile> discoveries read - Lists all MAC, IP bindings
      (discoveries) that MAAS has seen, and attempts to correlate those
      discoveries with hostnames advertised by mDNS.
    * maas <profile> discoveries by-unknown-mac - Lists all discoveries,
      but filters out discoveries where the MAC belongs to an interface
      known to MAAS.
    * maas <profile> discoveries by-unknown-ip - Lists all discoveries,
      but filters out discoveries where the IP address is known to MAAS
      (such as reserved by a user, or assigned to a node).
    * maas <profile> discoveries by-unknown-ip-and-mac - Lists all discoveries,
      but applies the filters for both unknown MACs and unknown IP addresses.

  * Note that the discovery API is currently read-only. It brings together
    data from several different sources, including observed network neighbours,
    resolved mDNS hostnames, and controller interface information.
  * New maas-rack commands have been added, which are called internally by
    MAAS in order to gather information about observed devices on the network.
    MAAS administrators should not normally need to use these commands
    (although they could be helpful for supportability).

    * maas-rack observe-mdns [--verbose]
    * sudo maas-rack observe-arp <interface> [--verbose]

  * Note: this feature intentionally does not place any network devices into
    “promiscuous mode”, or actively probe. MAAS controllers listen to ARP
    traffic they would have received anyway. Therefore, if a MAAS admin wants
    to keep MAAS’s knowledge of the network up-to-date, a command such as one
    of the following could be run periodically (such as from a script invoked
    by a crontab); MAAS will listen to any ARP replies and update its knowledge
    of the network:

     * To actively probe one or more subnet CIDRs on an interface:
       sudo nmap -e <interface> -sn -n -oX - -PR <cidr> [cidr2] [...]

     * To actively probe for a single IP address from a particular interface
       (regardless of whether or not the IP address is routable on-link on that
       interface):
       ping -r -I <interface> <ip-address> -c 3 -w 1 -i 0.2 -D -O

  * MAAS now depends on the avahi-utils and tcpdump packages in order to provide
    this functionality. (Before MAAS 2.1.0 is released, the MAAS team will consider
    making these optional dependencies, in case MAAS administrators do not want
    to run the avahi daemon, or require that tcpdump not be installed.)

Important Bugs Fixed in this Release
------------------------------------

**Bug #1617596: [2.1] Rack(relay) Controller is rejected after upgrade to 2.1**
 Fixes a regression regarding registering rack controllers which have bonds
 interfaces which are not currently bonding any interfaces.

 See bug `1617596`_ for more information.

.. _1617596:
  http://launchpad.net/bugs/1617596

**Bug #1615618: [2.1] 'SERVICE_STATE' object has no attribute 'getStatusInfo'**
 Fixes a regression in the service tracking mechanism, where it would fail to
 successfully track the status of some services.

 See bug `1615618`_ for more information.

.. _1615618:
  http://launchpad.net/bugs/1615618


Other Notable Changes
---------------------

**WebUI - Better error surfacing for DHCP snippets and Package Repositories**
 Both the DHCP Snippets Section and the Package Repositories section have now
 been improvement and will surface better errors.

Ongoing Work
------------

 * First User Journery - WebUI
 * Device Discovery - WebUI
 * Improved IPv6 Support
 * MAAS Services - NTP
 * MAAS Image Consolidation
 * Support for HWE Rolling Kernels

Known Issues and Workarounds
----------------------------

**Configuring APT key’s in ephemeral environment (overlayfs) fails.**
 A regression preventing cloud-init from configuring APT's key in a
 ephemeral environment, prevents MAAS from enlisting, commissioning and
 deploying `only` when using Derived Repositories or Custom Mirrors that
 require a new key.

 See bug `1618572`_ for more information.

.. _1618572:
  http://launchpad.net/bugs/1618572
