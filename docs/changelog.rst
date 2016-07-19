=========
Changelog
=========

1.9.5
=====

LP: #1603590    [1.9] MAAS does not allow link-local address for default gateway on ipv6 subnet.

1.9.4
=====

LP: #1584850    [1.9] DNS record added for non-boot interface IP when no address of that family exists on the boot interface

LP: #1583715    [1.9] Ensure that restricted resources also perform meaningful authentication of clients.

LP: #1584211    [1.9] Exclude RAM, floppy, and loopback devices from lsblk during commissioning.

LP: #1585400    [1.9] Change detect_missing_packages in moonshot power driver to look for `ipmitool` instead of `ipmipower`

LP: #1581318    [1.9] Append version to templateUrl in maas.js angular code.

LP: #1591093    [2.0,1.9] 3rd party HP drivers (archive hostname renamed) - deployment fails

LP: #1597460    [1.9] MAAS 1.9 should only download filetypes from a SimpleStream is can process

LP: #1567249    [1.9] If rack and region have different versions, the error is uninformative and confusing.

LP: #1582070    Update the UEFI ARM64 local boot config to chainload the locally installed EFI binary.

LP: #1597787    Send size with the extended partition for MBR partition tables.


1.9.3
=====

See https://launchpad.net/maas/+milestone/1.9.3 for full details.

Bug Fix Update
--------------

LP: #1521618    [1.9] wrong subnet in DHCP answer when multiple networks are present

LP: #1536604    [1.9] IntegrityError while uploading leases - when there are reserved IP's on the dynamic range

LP: #1580712    [1.9] dhcp update error: str object has no attribute mac

LP: #1575567    [1.9] Re-commissioning doesn't detect storage changes

LP: #1576194    [1.9] Enlistment via DHCP fails because DNS has bogus PTR record


1.9.2
=====

See https://launchpad.net/maas/+milestone/1.9.2 for full details.

Bug Fix Update
--------------

LP: #1573219    Deleting user in UI leads to 500

LP: #1508741    IPMI driver does not handle timeouts correctly

LP: #1572070    MAAS 2.0 cannot link physical device interfaces to tagged vlans, breaking juju 2.0 multi-NIC containers

LP: #1573046    14.04 images not available for commissioning as distrio-info --lts now reports xenial

LP: #1571563    Can't override built in partitioning

LP: #1552923    API allows attaching physical, bond interface to VLAN with a known tag (Inconsistent with UI)

LP: #1566336    MAAS keeps IPs assigned to eth0, even after eth0 is enslaved into a bond

LP: #1543195    unable to set mtu on default VLAN

LP: #1560693    Migration 0188 dist-upgrade update failure

LP: #1554747    CPU Utilization of postgresql thread reaches 100% for deleting a node from MaaS

LP: #1499934    Power state could not be queried (vmware)

LP: #1543707    MAAS 1.9+ should not allow whitespace characters in space names

LP: #1543968    MAAS 1.9.0 allows non-unique space names

LP: #1567213    devices results missing interface_set

LP: #1568051    ThreadPool context entry failure causes thread pool to break

LP: #1212205    get_file_by_name does not check owner

LP: #1298772    MAAS API vulnerable to CSRF attack

LP: #1379826    uuid.uuid1() is not suitable as an unguessable identifier/token

LP: #1573264    Enlistment fails: archdetect not found.

LP: #1556219    Discover correct IPMI driver in Power8.


1.9.1
=====

See https://launchpad.net/maas/+milestone/1.9.1 for full details.

Bug Fix Update
--------------

LP: #1523779    Fix grub-install error on deploying power8 machines.

LP: #1526542    Skip block devices with duplicate serial numbers to fix multipath issue.

LP: #1532262    Fix failure to power query requests for SM15K servers.

LP: #1484696    Fix bug in apache2 maas config where it will reuse websocket connections to work around a bug in apache2 itself.


1.9.0
=====

Important announcements
-----------------------

**New Networking Concepts and API's: Fabrics, Spaces and Subnets**
 With the introduction of new MAAS networking concepts, new API's are also
 been introduced. These are:

  * fabrics
  * spaces
  * subnets
  * vlans
  * fan-networks

 MAAS 1.9.0 will continue to provide backwards compatibility with the old
 network API for reading purposes, but moving forward, users are required to
 use the new API to manipulate fabrics, spaces and subnets.

**Advanced Network and Storage Configuration only available for Ubuntu deployments**
 Users can now perform advanced network and storage configurations for nodes
 before deployment. The advanced configuration is only available for Ubuntu
 deployments. All other deployments using third party OS', including CentOS,
 RHEL, Windows and Custom Images, won't result in such configuration.

**Re-commissioning required for upgraded MAAS**
 Now that storage partitioning and advanced configuration is supported natively,
 VM nodes in MAAS need to be re-commissioned.

  * If upgrading from MAAS 1.8, only VM nodes with VirtIO storage devices need
    to be re-commissioned.

  * If upgrading from MAAS 1.7, all nodes will need to be re-commissioned in
    order for MAAS to correctly capture the storage and networking devices.

 This does not affect nodes that are currently deployed.

**Default Storage Partitioning Layout - Flat**
 With the introduction of custom storage, MAAS has also introduced the concept
 of partitioning layouts. Partitioning layouts allow the user to quickly
 auto-configure the disk partitioning scheme after first commissioning or
 re-commissioning (if selected to do so). The partitioning layouts are set
 globally on the `Settings` page.

 The current default Partitioning layout is 'Flat', maintaining backwards
 compatibility with previous MAAS releases. This means MAAS will take the
 first disk it finds in the system and use it as the root and boot disk.

**Deployment with configured /etc/network/interfaces**
 Starting with MAAS 1.9, all node deployments will result in writing
 `/etc/network/interfaces` statically, by default. This increases MAAS'
 robustness and reliability as users no longer have to depend on DHCP for
 IP address allocation solely.

 MAAS will continue to provide IP addresses via DHCP, even though interfaces
 in `/etc/network/interfaces` may have been configured statically.

Major new features
------------------

**Storage Partitioning and Advanced Configuration**
 MAAS now supports Storage Partitioning and Advanced Configuration natively.
 This allows MAAS to deploy machines with different Storage Layouts, as
 well as different complex partitioning configurations. Storage support
 includes:

 * LVM
 * Bcache
 * Software RAID levels 0, 1, 5, 6, 10.
 * Advanced partitioning

 Storace configuration is available both via the WebUI and API. For more
 information refer to :ref:`storage`.

**Advanced Networking (Fabrics, Spaces, Subnetworks) and Node Network Configuration**
 MAAS now supports Advanced Network configuration, allowing users to not
 only perform advanced node network configuration, but also allowing users
 to declare and map their infrastructure in the form of Fabrics, VLANs,
 Spaces and Subnets.

 **Fabrics, Spaces, Subnets and Fan networks**
  MAAS now supports the concept of Fabrics, Spaces, Subnets and FANS,
  which introduce a whole new way of declaring and mapping your network
  and infrastructure in MAAS.

  The MAAS WebUI allows users to view all the declared Fabrics, Spaces,
  VLANs inside fabrics and Subnets inside Spaces. The WebUI does not yet
  support the ability to create new of these, but the API does.

  These new concepts replace the old `Network` concepts from MAAS'
  earlier versions. For more information, see :ref:`networking`.

  For more information about the API, see :ref:`api`.

 **Advanced Node Networking Configuration**
  MAAS can now perform the Node's networking configuration. Doing so,
  results in `/etc/network/interfaces` being written. Advanced
  configuration includes:

   * Assign subnets, fabrics, and IP to interfaces.
   * Create VLAN interfaces.
   * Create bond interfaces.
   * Change interface names.

  MAAS also allows configuration of node interfaces in different modes:

   * Auto Assign - Node interface will be configured statically
     and MAAS will auto assign an IP address.
   * DHCP - The node interface will be configured to DHCP.
   * Static - The user will be able to specify what IP address the
     interface will obtain, while MAAS will configure it statically.
   * Unconfigured - MAAS will leave the interface with LINK UP.

**Curtin & cloud-init status updates**
 Starting from MAAS 1.9.0, curtin and cloud-init will now send messages
 to MAAS providing information regarding various of the actions being
 taken. This information will be displayed in MAAS in the `Node Event Log`.

 Note that this information is only available when using MAAS 1.9.0 and
 the latest version fo curtin. For cloud-init messages this information
 is only available when deploying Wily+.

**Fabric and subnet creation**
 MAAS now auto-creates multiple fabrics per physical interface connected
 to the Cluster Controller, and will correctly create subnetworks under
 each fabric, as well as VLAN's, if any of the Cluster Controller
 interface is a VLAN interface.

**HWE Kernels**
 MAAS now has a different approach to deploying Hardware Enablement
 Kernels. Start from MAAS 1.9, the HWE kernels are no longer coupled
 to subarchitectures of a machine. For each Ubuntu release, users
 will be able to select any of the available HWE kernels for such
 release, as well as set the minimum kernel the machine will be
 deployed with by default.

 For more information, see :ref:`hardware-enablement-kernels`.

**CentOS images can be imported automatically**
 CentOS Image (CentOS 6 and 7) can now be imported automatically from the
 MAAS Images page. These images are currently part of the daily streams.

 In order to test this images, you need to use the daily image stream.
 This can be changed in the `Settings` page under `Boot Images` to
 `http://maas.ubuntu.com/images/ephemeral-v2/daily/`. Once changed, images
 can be imported from the MAAS Images page. The CentOS image will be
 published in the Releases stream shortly.


Minor notable changes
---------------------

**Minimal Config Files for Daemons**
 Starting from MAAS 1.9, minimal configuration files have been introduced
 for both, the MAAS Region Controller and the MAAS Cluster Controller daemons.

 *  The Region Controller (`maas-regiond`) has now dropped the usage of
    `/etc/maas/maas_local_settings.py` in favor of `/etc/maas/regiond.conf`.
    Available configuration options are now `database_host`, `database_name`,
    `database_user`, `database_pass`, `maas_url`. MAAS will attempt to migrate
    any configuration on upgrade, otherwise it will use sane defaults.

 *  The Cluster Controller (`maas-clusterd`) has now dropped the usage of
    `/etc/maas/pserv.yaml` and `/etc/maas/maas_cluster.conf` in favor of
    `/etc/maas/clusterd.conf`. Available configuration options are now `maas_url`
    and `cluster_uuid` only. MAAS will attempt to migrate any configuration
    on upgrade, otherwise it will use sane defaults.

**Commissioning Actions**
 MAAS now supports commissioning actions. These allow the user to specify
 how commissioning should behave in certain escenarios. The commissioning
 actions available are:

  * Enable SSH during commissioning & Keep machine ON after commissioning
  * Keep network configuration after commissioning
  * Keep storage configuration after commissioning

**Warn users about missing power control tools**
 MAAS now warns users about the missing power control tools. Each MAAS
 power driver use a set of power tools that may or may not be installed
 by default. If these power tools are missing from the system, MAAS will
 warn users.

**Python Power Drivers**
 Starting from MAAS 1.9, MAAS is moving away from using shell scripts
 templates for Power Drivers. These are being migrated to MAAS'
 internal control as power drivers. Currently supported are APC, MSCM,
 MSFT OCS, SM15k, UCSM, Virsh, VMWare and IPMI.

 Remaining Power Drivers include AMT, Fence CDU's, Moonshot.

Known Problems & Workarounds
----------------------------

**Garbage in the UI after upgrade**
 When upgrading from any earlier release (1.5, 1.7, 1.8), the user may see
 garbage in the UI. This is because the local cache is dirty and won't be
 refreshed automatically. MAAS 1.9.0 introduced a mechanism to refresh the
 cache automatically, but this will only take into effect upgrading from
 1.9.0 to any later release.

 To work around this issue, the only thing required is to refresh the
 browsers cache, by hitting F5.

 See bug `1515380`_ for more information.

.. _1515380:
  https://launchpad.net/bugs/1515380


Major bugs fixed in this release
--------------------------------

See https://launchpad.net/maas/+milestone/1.9.0 for details.


1.9.0 (RC4)
============

Major bugs fixed in this release
--------------------------------

LP: #1523674    Virsh is reporting ppc64le, not ppc64el.

LP: #1524091    Don't require DHCP to be on if it should be off.

LP: #1523988    No required packages for HMC as it uses pure python paramiko ssh client.

LP: #1524007    Don't hold the cluster configuration lock while reloading boot images.

LP: #1524924    Fix commissioning to correctly identify secondary subnets, VLAN's and fabrics.


1.9.0 (RC3)
=============

Major bugs fixed in this release
--------------------------------

LP: #1522898    "node-interface" API should just be "interface" - to allow devices to use it

LP: #1519527    Juju 1.25.1 proposed: lxc units all have the same IP address after upgrade from 1.7/1.8.

LP: #1522294    MAAS fails to parse some DHCP leases.

LP: #1519090    DHCP interface automatically obtains an IP even when the subnet is unmanaged.

LP: #1519077    MAAS assigns IP addresses on unmanaged subnets without consideration for some addresses known to be in use.

LP: #1519396    MTU field is not exposed over the API for VLAN.

LP: #1521833    Updating subnet name removes dns_server.

LP: #1519919    CC looks for NICs with kernel module loaded and fall back doesn't check persistent device names.

LP: #1522225    Migration 0181 can fail on upgrade if disks across nodes have duplicate serial numbers.

LP: #1519247    Migration 0146 can fail on upgrade when migrating unmanaged subnets.

LP: #1519397    [UI] Once a cache_set is created the UI fails with ERROR.

LP: #1519918    [UI] "failed to detect a valid IP address" when trying to view node details.


1.9.0 (RC2)
=============

Major bugs fixed in this release
--------------------------------

LP: #1513085    Partitioning should align for performance.

LP: #1516815    MAAS creates DNS record against Alias (eth0:1) if alias belongs to the PXE Interface.

LP: #1515769    Failed to power on SM15k.

LP: #1516722    Fix migration that might affect upgrade from 1.7.

LP: #1516065    Failed to power control IPMI BMC that does not support setting the boot order.

LP: #1517097    Constraints for acquiring interfaces argument should 'AND' key-value pairs for the same label.

LP: #1517687    [UI] Cannot create a partition using the whole disk.

LP: #1513258    [UI] CSS Broken for Bond Network Device.

LP: #1516173    [UI] Prevent being able to unmount/remove filesystems while node is on.

LP: #1510457    [UI] No error message if there is no boot and/or root disk configured for a node.


1.9.0 (RC1)
=============

Major bugs fixed in this release
--------------------------------

LP: #1515498    MAAS uses wrong IP for DNS record (creates against the bond).

LP: #1515671    Local archive ignored for deployment. Works for commissioning and enlistment.

LP: #1513485    Fix handling of multiple StaticIPAddress rows with empty IP addresses.

LP: #1513485    Lease parser failure - doesn't update IP on the PXE NIC.

LP: #1514486    Cannot claim sticky IP address for device with parent.

LP: #1514883    Cluster downloads boot-images from managed network (pxe) instead of network used to connect to Region.

LP: #1510917    Updating/modifying/assigning vlans, spaces, fabrics, subnets doesn't allow specifying names and lock to ID's.

LP: #1513095    MAAS should prevent deploying nodes with PXE interface 'unconfigured'.

LP: #1508056    MTU should be a set on the VLAN, and able to override on the interface.

LP: #1439476    Internal Server Error when creating/editing cluster interface.

LP: #1510224    Non-interactive way to change password.

LP: #1513111    When a bond is created all IP address associated with the bond members should be removed.

LP: #1487135    MAAS does not provide a dump of the config it passes to curtin for networking and storage.

LP: #1512959    MAAS should not offer EXT3, rather VFAT, EXT2, EXT4.

LP: #1505031    Network constraints for juju.

LP: #1509535    Creating a partition or a Volume Group on the whole disk leaves free space.

LP: #1511493    Should not allow partitions to be created on bcache device.

LP: #1503475    Storage section should only be editable when Ready or Allocated.

LP: #1512832    maasserver.api.tests.test_fannetworks.TestFanNetworksAPI.test_read fails randomly.

LP: #1508754    Creating a logical volume on a partition that is too small almost works, resulting in strange error messages.

LP: #1503925    [UI] Keep selected nodes selected after action.

LP: #1515380    [UI] Refresh UI cache after an upgrade to avoid seeing garbage.

LP: #1510106    [UI] Boot disk is not lighted nor can be changed.

LP: #1510118    [UI] Can't remove / delete a partition with a filesystem under 'Available disks and partitions'.

LP: #1510153    [UI] Creating a partition should allow to select filesystem and mountpoint.

LP: #1510468    [UI] When selecting a device, ensure padding between buttons is 20px.

LP: #1510455    [UI] Misaligned mount point column on used disks table.

LP: #1510469    [UI] Align the individual storage actions with the name field, rather than the tickbox.

LP: #1503479    [UI] can't add physical interface.

LP: #1503474    [UI] Containers (lxc, kvm) data missing on node details.

LP: #1513271    [UI] Unable to unmount a filesystem in the UI.

LP: #1503536    [UI] Animation missing on show members and select node.

LP: #1510482    [UI] Add tooltips to icons.

LP: #1510486    [UI] Add tooltips to inactive buttons.


1.9.0 (beta2)
=============

Major bugs fixed in this release
--------------------------------

LP: #1511257    New capabilities for subnets, vlan, spaces and fabrics.

LP: #1509077    Upgrade left a PXE NIC"s on nodes without a subnet associated
                causing deploy issues.

LP: #1512109    DNS record doesn't get created against the PXE interface

LP: #1510334    bcache cache_mode setting not configured on servers

LP: #1510210    Administrators unable to delete users using the API

LP: #1509536    Can create a VolumeGroup (vg0) without having created a partition
                on the boot disk

LP: #1501400    set-boot-disk yields in a machine not being able to deploy

LP: #1504956    Deploying Other OS' (CentOS, Windows) should not configure custom storage

LP: #1509164    Add RAID 10 support

LP: #1511437    MAAS should download grub from grub-efi-amd64-signed package instead
                of the archive path

LP: #1510120    Fails to deploy with UEFI

LP: #1507586    previous owner of node can use oauth creds to retrieve current
                owner's user-data

LP: #1507630    IP range validation for too small ranges

LP: #1511610    TestReleaseAutoIPs.test__calls_update_host_maps_for_next_ip_managed_subnet
                can fail randomly

LP: #1511071    No way to disable maas-proxy

LP: #1505034    [UI] HWE naming needs to be clearer

LP: #1509476    [UI] Angular $digest loop issue on node details page

LP: #1509473    [UI] New nodes interfaces doesn't show which interface is the PXE interface

LP: #1510471    [UI] When partitioning, there should be 20px padding between the sizing fields

LP: #1510467    [UI] On the available table, add model and serial to the name column

LP: #1510466    [UI] On the available table, change “available space” to “size” for consistency

LP: #1510472    [UI] when formatting/mounting, the button says “Format & Mount”
                this should just be “Mount”

LP: #1503533    [UI] Tickbox on create bond networking

LP: #1510447    [UI] On the file system table, change name to “File system” (lower case S)

LP: #1510474    [UI] When creating bcache and raid, remove the empty column between the
                config fields and

LP: #1510488    [UI] On the available table, make sure all buttons are lowercase

LP: #1511174    [UI] Subnets filter doesn't show network, it shows name instead

LP: #1509417    [UI] can't edit / add storage tags

LP: #1510891    [UI] Hover state for networking doesn't work

LP: #1510458    [UI] change "edit tag" link to icon storage

LP: #1510629    [UI] Can no longer see the IP address PXE interface gets on commissioning


1.9.0 (beta1)
=============

Major New Features
------------------

**Storage Configuration: LVM and RAID UI**
 Starting from MAAS 1.9.0 (beta1), MAAS now exposes custom
 storage configuration in the WebUI for the following:

  * LVM: Ability to easily create LVM.
  * RAID: Ability to create RAID 0, 1, 5, 6.

Minor notable changes
---------------------

**Fabric and subnet creation**
 Starting from MAAS 1.9.0 (beta1), MAAS now auto-creates multiple fabrics
 per physical interface connected to the Cluster Controller, and will
 correctly create subnetworks under each fabric, as well as VLAN's if any
 VLAN interface on the Cluster Controller is preset.

Known Problems & Workarounds
----------------------------

**CentOS fails to deploy with LVM Storage layout**
 CentOS fails to deploy when deploying with an LVM storage layout.
 Provided that LVM is the default storage layout, every CentOS deployment
 will fail, unless this layout is changed to 'Flat' storage.

 To work around the problem, the default storage layout can be changed from
 `LVM` to `Flat` in MAAS' Networks page, under `Storage Layout` section.

 See bug `1499558`_ for more information.

.. _1499558:
  https://launchpad.net/bugs/1499558

**Fail to deploy (boot) with UEFI**
 MAAS will successfully instal in a UEFI system, however, after deployment
 it won't boot onto the local disk. See bug `1510120`_ for more information.

.. _1510120:
  https://launchpad.net/bugs/1510120


1.9.0 (alpha5)
==============

Major New Features
------------------

**Storage Configuration: Partitioning and Bcache UI**
 Starting from MAAS 1.9.0 (alpha5), MAAS now exposes storage custom
 storage configuration in the WebUI for the following:

  * Partitioning: Ability to create and delete partitions.
  * Bcache: Ability to create cache sets and bcache devices, allowing
    multiple bcache devices to use the same cache set.

Minor notable changes
---------------------

**Warn users about missing power control tools**
 MAAS now warns users about the missing power control tools. Each MAAS
 power driver use a set of power tools that may or may not be installed
 by default. If these power tools are missing from the system, MAAS will
 warn users.

Known Problems & Workarounds
----------------------------

**CentOS fails to deploy with LVM Storage layout**
 CentOS fails to deploy when deploying with an LVM storage layout.
 Provided that LVM is the default storage layout, every CentOS deployment
 will fail, unless this layout is changed to 'Flat' storage.

 To work around the problem, the default storage layout can be changed from
 `LVM` to `Flat` in MAAS' Networks page, under `Storage Layout` section.

 See bug `1499558`_ for more information.

.. _1499558:
  https://launchpad.net/bugs/1499558


**Juju 1.24.6 bootstrap failure - Changing MAAS configured /etc/network/interfaces**
 Juju 1.24.6 (or less), assumes that it can manage the MAAS deployed node's
 network configuration. Juju changes /etc/network/interfaces and disables
 bringing up eth0 on boot, to create a bridge to support LXC. However,
 provided that MAAS / curtin now writes the node's network configuration,
 Juju is unable to successfully finish the creation of the bridge, but in
 the process, it disables auto bring up of eth0.

 Starting from Juju 1.24.7+, Juju has grown support to correctly manage a
 /etc/network/interfaces that has been created after deployment with MAAS 1.9.0.

 See bug `1494476`_ for more information.

.. _1494476:
  https://launchpad.net/bugs/1494476


1.9.0 (alpha4)
==============

Minor notable changes
---------------------

 * Various UI cosmetic fixes and improvements.
 * Do not create MBR larger than 2TiB for LVM.
 * Various concurrency fixes and improvements to robustness.

Known Problems & Workarounds
----------------------------

**CentOS fails to deploy with LVM Storage layout**
 CentOS fails to deploy when deploying with an LVM storage layout.
 Provided that LVM is the default storage layout, every CentOS deployment
 will fail, unless this layout is changed to 'Flat' storage.

 To work around the problem, the default storage layout can be changed from
 `LVM` to `Flat` in MAAS' Networks page, under `Storage Layout` section.

 See bug `1499558`_ for more information.

.. _1499558:
  https://launchpad.net/bugs/1499558

**Juju 1.24+ bootstrap failure - Changing MAAS configured /etc/network/interfaces**
 Juju 1.24+, by default, assumes that it can manage the MAAS deployed node's
 network configuration. Juju changes /etc/network/interfaces and disables
 bringing up eth0 on boot, to create a bridge to support LXC. However,
 provided that MAAS / curtin now write the node's network configuration,
 Juju is unable to successfully finish the creation of the bridge, but in
 the process, it disables auto bring up of eth0.

 The machine will deploy successfully, however, after a reboot eth0 will
 never be brought back up due to the changes made by Juju. This will prevent
 Juju from SSH'ing into the machine and finishing the boostrap.

 To prevent this from happening, `disable-network-management: true` needs
 to be used. Note that this will prevent the deployment of LXC containers
 as they have to DHCP.

 See bug `1494476`_ for more information.

.. _1494476:
  https://launchpad.net/bugs/1494476


1.9.0 (alpha3)
==============


Major New Features
------------------

**Advanced Node Network Configuration UI**
 Starting from MAAS 1.9.0 (alpha3), MAAS can now do the Node's Network
 configuration. Doing such configuration will result in having
 `/etc/network/interfaces` writen.

 Advanced configuration UI includes:

  * Create VLAN interfaces.
  * Create bond interfaces.
  * Create Alias interfaces.
  * Change interface names.

**Subnetworks page UI**
 Starting from MAAS 1.9.0 (alpha3), MAAS can now show the new Subnets
 tab in the UI. This allow users to view:

  * Fabrics
  * Spaces
  * VLANs in fabrics.
  * Subnets in Spaces.

Known Problems & Workarounds
----------------------------

**CentOS fails to deploy with LVM Storage layout**
 CentOS fails to deploy when deploying with an LVM storage layout.
 Provided that LVM is the default storage layout, every CentOS deployment
 will fail, unless this layout is changed to 'Flat' storage.

 To work around the problem, the default storage layout can be changed from
 `LVM` to `Flat` in MAAS' Networks page, under `Storage Layout` section.

 See bug `1499558`_ for more information.

.. _1499558:
  https://launchpad.net/bugs/1499558

**Juju 1.24+ bootstrap failure - Changing MAAS configured /etc/network/interfaces**
 Juju 1.24+, by default, assumes that it can manage the MAAS deployed node's
 network configuration. Juju changes /etc/network/interfaces and disables
 bringing up eth0 on boot, to create a bridge to support LXC. However,
 provided that MAAS / curtin now write the node's network configuration,
 Juju is unable to successfully finish the creation of the bridge, but in
 the process, it disables auto bring up of eth0.

 The machine will deploy successfully, however, after a reboot eth0 will
 never be brought back up due to the changes made by Juju. This will prevent
 Juju from SSH'ing into the machine and finishing the boostrap.

 To prevent this from happening, `disable-network-management: true` needs
 to be used. Note that this will prevent the deployment of LXC containers
 as they have to DHCP.

 See bug `1494476`_ for more information.

.. _1494476:
  https://launchpad.net/bugs/1494476


1.9.0 (alpha2)
==============

Important announcements
-----------------------

**Installation by default configures /etc/network/interfaces**
 Starting from MAAS 1.9.0 (alpha2), all Ubuntu deployments will result
 with static network configurations. Users will be able to interact
 with the  API to further configure interfaces.

**Introduction to Fabrics, Spaces and Subnets introduces new Network API**
 With the introduction of the concepts of Fabrics, Spaces and Subnets starting
 from MAAS 1.9.0 (alpha2), MAAS also introduces new API's for:

  * fabrics
  * spaces
  * subnets
  * vlans
  * fan-networks

 MAAS 1.9.0 will continue to provide backwards compatibility with the old
 network API for reading purposes, but moving forward, users are required to
 use the new API to manipulate fabrics, spaces and subnets.

Major New Features
------------------

**Advanced Node Network Configuration**
 Starting from MAAS 1.9.0 (alpha2), MAAS can now do the Node's Network
 configuration. Doing such configuration will result in having
 `/etc/network/interfaces` writen.

 Advanced configuration includes:

  * Assign subnets, fabrics, and IP to interfaces.
  * Create VLAN interfaces.
  * Create bond interfaces.
  * Change interface names.

**Fabrics, Spaces, Subnets and Fan networks**
 Starting from MAAS 1.9.0 (alpha2), MAAS now supports the concept of
 Fabrics, Spaces, Subnets and FANS.

 These new concepts replaces the old `Network` concepts from MAAS'
 earlier versions. For more information, see :ref:`networking`.

 For more information about the API, see :ref:`api`.

**Curtin & cloud-init status updates**
 Starting from MAAS 1.9.0 (alpha2), curtin and cloud-init will now send
 messages to MAAS providing information regarding various of the actions
 taken. This information will be displayed in MAAS in the `Node Event Log`.

 Note that this information is only available when using MAAS 1.9.0 and
 the latest version fo curtin. For cloud-init messages this information
 is only available when deploying Wily.

Minor notable changes
---------------------

**Commissioning Actions**
 MAAS now supports commissioning actions. These allow the user to specify
 how commissioning should behave in certain escenarios. The commissioning
 actions available are:

  * Enable SSH during commissioning
  * Keep machine ON after commissioning
  * Keep network configuration after commissioning
  * Keep storage configuration after commissioning

**CentOS images can be imported automatically**
 CentOS Image (CentOS 6 and 7) can now be imported automatically from the
 MAAS Images page. These images are currently part of the daily streams.

 In order to test this images, you need to use the daily image stream.
 This can be changed in the `Settings` page under `Boot Images` to
 `http://maas.ubuntu.com/images/ephemeral-v2/daily/`. Once changed, images
 can be imported from the MAAS Images page.

Known Problems & Workarounds
----------------------------

**CentOS fails to deploy with LVM Storage layout**
 CentOS fails to deploy when deploying with an LVM storage layout.
 Provided that LVM is the default storage layout, every CentOS deployment
 will fail, unless this layout is changed to 'Flat' storage.

 To work around the problem, the default storage layout can be changed from
 `LVM` to `Flat` in MAAS' Networks page, under `Storage Layout` section.

 See bug `1499558`_ for more information.

.. _1499558:
  https://launchpad.net/bugs/1499558


**Juju 1.24+ bootstrap failure - Changing MAAS configured /etc/network/interfaces**
 Juju 1.24+, by default, assumes that it can manage the MAAS deployed node's
 network configuration. Juju changes /etc/network/interfaces and disables
 bringing up eth0 on boot, to create a bridge to support LXC. However,
 provided that MAAS / curtin now write the node's network configuration,
 Juju is unable to successfully finish the creation of the bridge, but in
 the process, it disables auto bring up of eth0.

 The machine will deploy successfully, however, after a reboot eth0 will
 never be brought back up due to the changes made by Juju. This will prevent
 Juju from SSH'ing into the machine and finishing the boostrap.

 To prevent this from happening, `disable-network-management: true` needs
 to be used. Note that this will prevent the deployment of LXC containers
 as they have to DHCP.

 See bug `1494476`_ for more information.

.. _1494476:
  https://launchpad.net/bugs/1494476


1.9.0 (alpha1)
==============

Important announcements
-----------------------

**LVM is now the default partitioning layout**
 Starting from MAAS 1.9, all of the deployments will result on having
 LVM configure for each of the machines. A Flat partitioning layout is not
 longer used by default. (This, however, can be changed in the MAAS Settings
 Page).

**Re-commissioning required from VM's with VirtIO devices**
 Starting from MAAS 1.9, storage partitioning and advance configuration is
 supported natively (see below). In order for MAAS to correctly map
 VirtIO devices in VM's, these VM nodes need to be re-commissioned.

 If not re-comissioned, MAAS will prevent the deployment until done so.
 Previously deployed nodes won't be affected, but will also have to be
 re-commissioned if released.

Major new features
------------------

**Storage Partitioning and Advanced Configuration**
 MAAS now natively supports Storage Partitioning and Advanced Configuration.
 This allows MAAS to deploy machines with different Storage Layouts, as
 well as different complext partitioning configurations. Storage support
 includes:

 * LVM
 * Bcache
 * Software Raid
 * Advanced partitioning

 For more information refer to :ref:`storage`.

Minor notable changes
---------------------

**Minimal Config Files for Daemons**
 Starting from MAAS 1.9, minimal configuration files have been introduced
 for both, the MAAS Region Controller and the MAAS Cluster Controller daemons.

 *  The Region Controller (`maas-regiond`) has now dropped the usage of
    `/etc/maas/maas_local_settings.py` in favor of `/etc/maas/regiond.conf`.
    Available configuration options are now `database_host`, `database_name`,
    `database_user`, `database_pass`, `maas_url`. MAAS will attempt to migrate
    any configuration on upgrade, otherwise it will use sane defaults.

 *  The Cluster Controller (`maas-clusterd`) has now dropped the usage of
    `/etc/maas/pserv.yaml` and `/etc/maas/maas_cluster.conf` in favor of
    `/etc/maas/clusterd.conf`. Available configuration options are now `maas_url`
    and `cluster_uuid` only. MAAS will attempt to migrate any configuration
    on upgrade, otherwise it will use sane defaults.

**HWE Kernels**
 MAAS now has a different approach to deploying Hardware Enablement
 Kernels. Start from MAAS 1.9, the HWE kernels are no longer coupled
 to subarchitectures of a machine. For each Ubuntu release, users
 will be able to select any of the available HWE kernels for such
 release, as well as set the minimum kernel the machine will be
 deployed with by default.

 For more information, see :ref:`hardware-enablement-kernels`.

**Python Power Drivers**
 Starting from MAAS 1.9, MAAS is moving away from using shell scripts
 templates for Power Drivers. These are being migrated to MAAS'
 internal control as power drivers. Currently supported are APC, MSCM,
 MSFT OCS, SM15k, UCSM, Virsh, VMWare and IPMI.

 Remaining Power Drivers include AMT, Fence CDU's, Moonshot.

Known Problems & Workarounds
----------------------------

**Fail to deploy Trusty due to missing bcache-tools**
 In order to correctly perform storage partitioning in Trusty+, the
 new version of curtin used by MAAS requires bcache-tools to be
 installed. However, these tools are not available in Trusty, hence
 causing MAAS/curtin deployment failures when installing Trusty. An
 SRU in Ubuntu Trusty for these tools is already in progress.

 To work around the problem, a curtin custom configuration to install
 bcache-tools can be used in `/etc/maas/preseeds/curtin_userdata`::

  {{if node.get_distro_series() in ['trusty']}}
  early_commands:
    add_repo: ["add-apt-repository", "-y", "ppa:maas-maintainers/experimental"]
  {{endif}}

 See bug `1449099`_ for more information.

.. _1449099:
  https://bugs.launchpad.net/bugs/1449099

**Fail to deploy LVM in Trusty**
 MAAS fail to deploy Ubuntu Trusty with a LVM Storage layout, as
 curtin will fail to perform the partitioning. See bug `1488632`_
 for more information.

.. _1488632:
  https://bugs.launchpad.net/bugs/1488632
