=========
Changelog
=========


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


1.8.2
=====

See https://launchpad.net/maas/+milestone/1.8.2 for full details.

Bug Fix Update
--------------

#1484696    Regenerate the connection URL on websocket client reconnect, to fix
            CSRF after upgrade to 1.8.1.

#1445942    Validate the osystem and distro_series when using the deploy action,
            which fixes win2012r2 deployment issues.

#1481940    Fix failure in MAAS startup messages by not generating dhcpd config
            files when they are not in use.

#1459865    Fix enlistment to always use the correct kernel parameters.


1.8.1
=====

See https://launchpad.net/maas/+milestone/1.8.1 for full details.

Bug Fix Update
--------------

#1481118    Add --username to maas-region-admin apikey command docs.

#1472707    Add ListBootImagesV2 RPC command. Fallback to using ListBootImages RPC
            when the ListBootImagesV2 is not handled on the cluster.

#1470591    Fix setting the default_distro_series over the API.

#1413388    Fix upgrade issue where it would remove custom DNS config, potentially breaking DNS

#1317705    Commissioning x86_64 node never completes, sitting at grub prompt, pserv py tbs

#1389007    Power monitor service hits amp.TooLong errors with > ~600 nodes to a cluster

#1436279    Websocket server accessed over port 5240

#1469305    If hostname not set, sudo warning make maas throw 500

#1470585    Can't set a list of forwarders (BIND config)

#1469846    UCS chassis enlist Failed to probe and enlist UCS nodes: list index out of range

#1470276    Add cisco snic to 3rd party driver

#1402042    console= parameters need to be added before -- on kernel cmdline

#1465722    [UI] Machine details styling

#1465737    [UI] Actions design styles

#1465740    [UI] Replace close "X" with correct versions

#1465742    [UI] Table design styles

#1470389    [UI] Make table heading hover consistant with nodes/devices tabs

#1470395    [UI] adding between node name and save button inconsistent

#1459710    [UI] "Set zone" label oddly placed on node listing page


1.8.0
=====

Important announcements
-----------------------

**Region Controller now running on twisted.**
 The MAAS Region Controller is now running as a twisted daemon. It is
 no longer dependent on Apache in order to run. The MAAS Region
 controller is now controlled by ``maas-regiond`` upstart job or systemd
 unit. The ``maas-regiond`` daemon is available in port ``5240``.

**Firewall ports for Region and Cluster controller communication**
 The communication between Region and Cluster controller is now limited
 to use the ports between ``5250`` and ``5259``. For all of those users who
 are using a remote cluster (not running on the same machine as the
 MAAS Region Controller), need to ensure that these ports are open in
 the firewall.


Major new features
------------------

**Web UI Re-design**
 MAAS now includes a newly re-designed Web UI. The new Web UI features
 a new design and a lot of usability improvements.  Some of the UI new
 features include:

 * Live Updating

   The new UI now allows users to view the current status of the
   various nodes of MAAS in real-time and without having to manually
   refresh the browser.

 * Bulk Actions

   Quickly select multiple nodes or devices and perform actions. If
   nodes or devices are not in a state where that action can be
   performed MAAS will alert you to the machines allowing you to
   modify your selection before performing the action.

 * Live Searching

   View the matching nodes or devices as you search. Just type and the
   nodes will start to filter, no reloading or waiting for the page to
   load.

 * Better Filtering

   Easily filter through the list of nodes and devices in MAAS to find
   the specific nodes that match your search. Examples:

   * All nodes that are Ready and have at least 2 disks::

      status:Ready disks:2

   * All nodes that are not Ready::

      status:!Ready

   * All nodes that have Failed to complete an action::

      status:Failed

   * All nodes that are deployed but their power is off::

      status:Deployed power:off

 * Node & Storage Tag Management

   Administrators can now add and remove tags for both Machine and
   Storage. This is now possible via the Web UI from the `Node Details`
   page.

 * Add Chassis

   A new `Add Chassis` feature has been added to the UI. This is an
   option of `Add Hardware`.  This not only allows administrators to
   add machines that belong to a single chassis, but also allows
   administrators to add Virtual Machines for both KVM and VMWare
   based products.

**Support for Devices**
 MAAS adds a new concept for a different type of machines, called
 `Devices`. `Devices` are machines that MAAS does not fully manage;
 this means that MAAS can not power manage nor properly control.
 `Devices` are machines in the Network that MAAS can provide network
 services for (DHCP/DNS), or can track for inventory.

 Administrators can assign three different types of IP Address to a
 device:

 * `External`, which can be any IP address on the network.
 * `Static`, which can be selected manually or automatically, and
   belongs to Subnetwork that MAAS can control.
 * `Dynamic`, any IP address that is automatically assigned by MAAS
   via DHCP. MAAS will automatically create a DNS mapping for any of
   the IP addresses belonging to a Device.

**Storage Discovery**
 Storage that is attached to a node in MAAS is now a first class
 citizen. Easily view and filter nodes based on the number of disks
 and the size of each disk attached to a node. Information retrieved
 from a storage device includes its name, model, serial, size,
 block size, and extra information that is applied to a storage device
 as a tag. MAAS will auto tag devices including tags for solid state
 device (ssd), rotary, rpm speed, and connected bus.

**Twisted Daemons**
 The MAAS Region Controller no longer requires an Apache frontend. It
 is still used by default to be backward compatible, but the MAAS
 Region Controller is now a standalone Twisted process (the twisted
 daemon for the Cluster Controller, ``maas-clusterd``, was introduced
 in MAAS 1.7). The MAAS Region Controller is now ``maas-regiond``.

 Starting from MAAS 1.8 the Region Controller and Cluster Controller
 are noq controlled only by two daemons. (``maas-regiond`` and
 ``maas-clusterd`` respectively)

**DB Isolation**
 Previously PostgreSQL was used in the default READ COMMITTED
 transaction  isolation mode. It has now been increased to
 REPEATABLE READ. PostgreSQL thus provides extra support to ensure
 that changes in MAAS are logically consistent, a valuable aid in a
 busy distributed system.

**VMware support**
 VMware products are now supported in MAAS. This allows MAAS to register
 all the Virtual Machines that the VMWare product is running (or a subset
 whose name matches a specified prefix), set them up to PXE boot, and
 configure them for power management.

 This feature requires the ``python-pyvmomi`` package to be installed.
 (This is a suggested package, so be sure to use ``--install-suggests`` on
 your ``apt-get`` command line when installing the MAAS cluster, or install
 it manually.)

 The following VMware products have been tested: vSphere Hypervisor 5.5,
 ESXi 5.5, and Workstation 11. This feature supports both i386 and amd64
 virtual machines.


Minor notable changes
---------------------
**RPC Communication & Ports**
 RPC communication between the Region Controller and the
 Cluster Controller has now been limited to use the ports between 5250
 and 5259, inclusive.

**Discovered virtual machine names are imported into MAAS**
 When using the new `Add Chassis` functionality (or the
 ``probe_and_enlist`` API), virtual machines (VMs) imported into MAAS will
 now use the names defined within the Hypervisor as hostnames in MAAS.
 This feature works with KVM (virsh or PowerKVM) and VMWare VMs.

 The names of the virtual machines will be converted into valid
 hostnames, if possible. For example, if a VM called `Ubuntu 64-bit`
 is imported, it will become `ubuntu-64-bit`.

 Note that only the hostname portion of the name is used. For example,
 if a VM is called `maas1.example.com`, only the “mass1” portion of the
 name will be used as the node name. (The cluster configuration
 determines the remainder of the DNS name.)

**Virtual machine boot order is now set automatically**
 When using the new `Add Chassis` functionality (or the
 `probe_and_enlist` API) to add KVM or VMware virtual machines, MAAS
 will automatically attempt to set each virtual machine’s boot order so
 that the network cards (PXE) are attempted first. (This increases the
 repeatability of VM deployments, because a VM whose boot order is
 incorrectly set may work *once*, but subsequently fail to deploy.)

**Systemd Support**
 MAAS now supports systemd, allowing all of the MAAS daemons to run
 with Systemd, if the Ubuntu system is running systemd by default
 instead Upstart. These daemons include ``maas-regiond``,
 ``maas-clusterd``, ``maas-dhcpd``, ``maas-dhcpd6``, ``maas-proxy``.

**Upstart & Systemd improvements**
 Both Upstart Jobs and Systemd Units now run and supervise various
 instances of the ``maas-regiond`` in order to be able to effectively
 handle all requests.


Known Problems & Workarounds
----------------------------

**Disk space is not reclaimed when MAAS boot images are superseded**
 Whenever new boot images are synced to ``maas-regiond``, new large
 objects in the database are created for them, which may replace older
 versions of the same image (for the specified version/architecture
 combination). Unfortunately, the standard postgresql `autovacuum`
 does not remove large objects that are no longer used; a
 “full vacuum” is required for this. Therefore, a new command has
 been introduced which will run the appropriate postgresql vacuum
 command (See bug `1459876`_)::

	maas-region-admin db_vacuum_lobjects

 This command should be run with care (ideally, during a scheduled
 maintenance period), since it could take a long time (on the order
 of minutes) if there are a large number of superseded images.

.. _1459876:
  https://launchpad.net/bugs/1459876

**MAAS logs to maas.log.1 instead of maas.log**
 The `/var/log/maas/maas.log` is a rsyslog based log file, that gets
 rotated in the form of `maas.log.1`, `maas.log.2.gz`, etc. In one
 situation it has been seen that `maas.log` is empty, and rsyslog
 was sending logs to `maas.log.1` instead. This has been identified
 as an issue in rsyslog rather than maas. See bug `1460678`_.

.. _1460678:
  https://launchpad.net/bugs/1460678


Major bugs fixed in this release
--------------------------------

See https://launchpad.net/maas/+milestone/1.8.0 for full details.

#1185455    Not obvious how to search nodes along a specific axis, or multiple axes

#1277545    Node list sort order not maintained

#1300122    No way to get the version of the MAAS server through the API

#1315072    Finding BMC IP address requires clicking "Edit node" in Web UI

#1329267    CLI does not tell users to issue a "refresh" when the API gets out of date

#1337874    Re-commissioning doesn't detect NIC changes

#1352923    MAAS 1.8 requires arbitrary high-numbered port connections between cluster and region controllers

#1384334    Dnssec failures cause nodes to be unable to resolve external addresses

#1402100    Nodes can be in Ready state without commissioning data, if you mark a node in 'failed commisioning', broken and then fixed.

#1412342    Maas.log only contains cluster logs

#1424080    Deployment Failed -- Failed to get installation results

#1432828    MAAS needs to write power off jobs to to systemd units instead of upstart

#1433622    Maas cluster name should not / can not have trailing '.'

#1433625    'APIErrorsMiddleware' object has no attribute 'RETRY_AFTER_SERVICE_UNAVAILABLE'

#1435767    Retry mechanism fails with oauth-authenticated requests

#1436027    Interfaces does not have entry for eth0

#1437388    exceptions.AttributeError: 'NoneType' object has no attribute 'is_superuser'

#1437426    No view for loading page or notification for connection error

#1438218    django.db.transaction.TransactionManagementError: raised when deploying multiple nodes in the UI

#1438606    Releasing node not transitioned to "Failed releasing"

#1438808    Network and storage tables on node details page mis-aligned in Firefox

#1438842    Cannot add an extra NIC

#1439064    Title of individual commissioning result page is permanently "Loading..."

#1439159    maas packaging in vivid needs to prevent isc-dhcpd and squid3 from running

#1439239    MAAS API node details failures

#1439322    Simultaneous IP address requests with only one succeeding

#1439339    "Choose power type" dropdown broken in FF

#1439359    When upgrading to MAAS 1.7 from MAAS 1.5, MAAS should trigger the image import automatically.

#1439366    MAAS 1.7 should be backwards compatible with 1.5 the preseed naming convention

#1440090    NIC information (networks / PXE interface) get's lost due to re-discovering NIC's during commissioning

#1440763    Rregiond.log Tracebacks when trying to deploy 42 nodes at a time

#1440765    oauth.oauth.OAuthError: Parameter not found: %s' % parameter

#1441002    Maas api "device claim-sticky-ip-address" fails with "500: 'bool' object has not attribute 'uuid'".

#1441021    No IP validation

#1441399    Socket.error: [Errno 92] Protocol not available

#1441610    Machines get stuck in releasing for a long time

#1441652    502 Proxy Error when trying to access MAAS in browser

#1441756    Manager service is not sending limit to region

#1441841    Can't add a device that has IP address that it is within the wider range MAAS manages, but not within Dynamic/Static range MAAS manages

#1441933    Internal Server Error when saving a cluster without Router IP

#1442059    Failed deployment/release timeout

#1442162    Spurious test failure: maasserver.api.tests.test_nodes.TestFilteredNodesListFromRequest.test_node_list_with_ids_orders_by_id

#1443344    MAAS node details page shows BMC password in cleartext

#1443346    utils.fs.atomic_write does not preserve file ownership

#1443709    Error on request (58) node.check_power

#1443917    IntegrityError: duplicate key value violates unique constraint "maasserver_componenterror_component_key", (component)=(clusters) already exists

#1445950    Proxy error when trying to delete a windows image

#1445959    Deploying a different OS from node details page yields in always deploying ubuntu

#1445994    Add Devices button has disappeared

#1445997    Clicking on a device takes be back to node details page

#1446000    MAC is not shown in device list

#1446810    Too Many Open Files in maas.log

#1446840    Internal server error saving the clusters interfaces

#1447009    Combo loader crash when requesting JS assets

#1447208    deferToThread cannot wait for a thread in the same threadpool

#1447736    Node isn't removed from the node listing when it becomes non-visible

#1447739    Node isn't added to the node listing when it becomes visible

#1449011    maas root node start distro_series=precise on a non-allocated node returns wrong error message

#1449729    Nodes fail to commission

#1450091    tgt does not auto-start on Vivid

#1450115    django.db.utils.OperationalError raised when instantiating MAASAndNetworkForm

#1450488    MAAS does not list all the tags

#1451852    Legacy VMware "add chassis" option should be removed

#1451857    Probe-and-enlist for VMware needs to update VM config to use PXE boot

#1453730    Commissioning script contents is shown under other settings

#1453954    500 error reported to juju when starting node - "another action is already in progress for that node"

#1455151    Adding one device on fresh install shows as two devices until page refresh

#1455643    Regression: Node listing extends past the edge of the screen

#1456188    Auto image import stacktraces

#1456538    Package install fails with "invoke-rc.d: unknown initscript, /etc/init.d/maas-regiond-worker not found."

#1456698    Unable to deploy a node that is marked fixed when it is on

#1456892    500 error: UnboundLocalError: local variable 'key_required' referenced before assignment

#1456969    MAAS cli/API: missing option set use-fast-installer / use-debian-installer

#1457203    Usability - Enter key in search field should not reset view and filter

#1457708    Cluster gets disconnected after error: provisioningserver.service_monitor.UnknownServiceError: 'maas-dhcpd' is unknown to upstart.

#1457786    Test suite runs sudo commands

#1458894    Cluster image download gives up and logs an IOError too soon

#1459380    MAAS logs 503 spurious errors when the region service isn't yet online

#1459607    Spurious test: maasserver.api.tests.test_node.TestNodeAPI.test_POST_commission_commissions_node

#1459876    When MAAS Boot Images are Superseded, Disk Space is not Reclaimed

#1460485    MAAS doesn't transparently remove multiple slashes in URLs

#1461181    Too many open files, after upgrade to rc1

#1461256    Filter by node broken in Chromium - angular errors in java script console

#1461977    Unused "Check component compatibility and certification" field should be removed

#1462079    Devices can't add a device with a Static IP address outside of dyanmic/static range

#1462320    eventloop table is out of date

#1462507    BlockDevice API is not under the nodes endpoint


1.7.6
=====

Bug Fix Update
--------------

#1470585    Accept list of forwarders for upstream_dns rather than just one.

#1413388    Fix upgrade issue where it would remove custom DNS config,
            potentially breaking DNS


1.7.5
=====

Bug Fix Update
--------------

#1456969    MAAS cli/API: missing option set use-fast-installer / use-debian-installer

1.7.4
=====

Bug Fix Update
--------------

#1456892    500 error: UnboundLocalError: local variable 'key_required' referenced before assignment

#1387859    When MAAS has too many leases, and lease parsing fails, MAAS fails to auto-map NIC with network

#1329267    Alert a command-line user of `maas` when their local API description is out-of-date.

1.7.3
=====

Bug Fix Update
--------------

#1441933    Internal Server Error when saving a cluster without Router IP

#1441133    MAAS version not exposed over the API

#1437094    Sorting by mac address on webui causes internal server error

#1439359    Automatically set correct boot resources selection and start import after upgrade from MAAS 1.5; Ensures MAAS is usable after upgrade.

#1439366    Backwards compatibility with MAAS 1.5 preseeds and custom preseeds. Ensures that users dont have to manually change preseeds names.

1.7.2
=====

Bug Fix Update
--------------

For full details see https://launchpad.net/maas/+milestone/1.7.2

#1331214    Support AMT Version > 8

#1397567    Fix call to amttool when restarting a node to not fail disk erasing.

#1415538    Do not generate the 'option routers' stanza if router IP is None.

#1403909    Do not deallocate StaticIPAddress before node has powered off.

#1405998    Remove all OOPS reporting.

#1423931    Update the nodes host maps when a sticky ip address is claimed over the API.

#1433697    Look for bootloaders in /usr/lib/EXTLINUX


1.7.1
=====

Minor feature improvements
--------------------------

New CentOS Release support.
  Further to the work done in the 1.7.0 MAAS Release, MAAS now supports
  uploading various versions of CentOS. Previously MAAS would only
  officially support 6.5.

Power Monitoring for Seamicro 15000, Cisco UCS and HP Moonshot Chassis
  Further the work done in the 1.7.0 MAAS release, it now supports power
  query and monitoring for the Seamicro 15000 Chassis, the Cisco UCS
  Chassis Manager and the HP Moonshot Chassis Manager.

Node Listing Page and Node Event Log live refresh
  The Node Listing page and the Node Event Log now have live refresh
  every 10 seconds. This allows MAAS to display the latest node status
  and events without forcing a browser refresh.

IP Address Reservation
  The static IP address reservation API now has an optional "mac"
  parameter. Specifying a MAC address here will link the new static IP
  to that MAC address. A DHCP host map will be created for the MAC
  address. No other IPs may be reserved for that MAC address until the
  current one is released.

Bug fix update
--------------

For full details see https://launchpad.net/maas/+milestone/1.7.1

#1330765    If start_nodes() fails, it doesn't clean up after itself.

#1373261    pserv.yaml rewrite breaks when previous generator URL uses IPv6 address

#1386432    After update to the latest curtin that changes the log to install.log MAAS show's two installation logs

#1386488    If rndc fails, you get an Internal Server Error page

#1386502    No "failed" transition from "new"

#1386914    twisted Unhandled Error when region can't reach upstream boot resource

#1391139    Tagged VLAN on aliased NIC breaks migration 0099

#1391161    Failure: twisted.internet.error.ConnectionDone: Connection was closed cleanly.

#1391411    metadata API signal() is releasing host maps at the end of installation

#1391897    Network names with dots cause internal server error when on node pages

#1394382    maas does not know about VM "paused" state

#1396308    Removing managed interface causes maas to delete nodes

#1397356    Disk Wiping fails if installation is not Ubuntu

#1398405    MAAS UI reports storage size in Gibibytes (base 2) but is labeled GB - Gigabytes (base 10).

#1399331    MAAS leaking sensitive information in ps ax output

#1400849    Check Power State disappears after upgrade to 1.7 bzr 3312

#1401241    custom dd-tgz format images looked for in wrong path, so they don't work

#1401983    Exception: deadlock detected

#1403609    can not enlist chassis with maas admin node-group probe-and-enlist-mscm

#1283106    MAAS allows the same subnet to be defined on two managed interfaces of the same cluster

#1303925    commissioning fails silently if a node can't reach the region controller

#1357073    power state changes are not reflected quickly enough in the UI

#1360280    boot-source-selections api allows adding bogus and duplicated values

#1368400    Can't power off nodes that are in Ready state but on

#1370897    The node power monitoring service does not check nodes in parallel

#1376024    gpg --batch [...]` error caused by race in BootSourceCacheService

#1376716    AMT NUC stuck at boot prompt instead of powering down (no ACPI support in syslinux poweroff)

#1378835    Config does not have a unique index on name

#1379370    Consider removing transaction in claim_static_ip_addresses().

#1379556    Panicky log warning that is irrelevant

#1381444    Misleading error message in log "Unknown power_type 'sm15k'"

#1382166    Message disclosing image import necessary visible while not logged in

#1382237    UnicodeEncodeError when unable to create host maps

#1383231    Error message when trying to reserve the same static IP twice is unhelpful

#1383237    Error message trying to reserve an IP address when no static range is defined is misleading

#1384424    Seamicro Machines do not have Power Status Tracking

#1384428    HP Moonshot Chassis Manager lacks power status monitoring

#1384924    need to provide a better upgrade message for images on the cluster but not on the region

#1386517    DHCP leases are not released at the end of commissioning and possibly enlistment

#1387239    MAAS does not provide an API for reserving a static IP for a given MAC address

#1387414    Race when registering new event type

#1388033    Trying to reserve a static IP when no more IPs are available results in 503 Service Unavailable with no error text

#1389602    Inconsistent behavior in the checks to delete a node

#1389733    node listing does not update the status and power of nodes

#1390144    Node 'releasing' should have a timeout

#1391193    API error documentation

#1391421    Names of custom boot-resources not visible in the web UI

#1391891    Spurious test failure: TestDNSForwardZoneConfig_GetGenerateDirectives.test_returns_single_entry_for_tiny_network

#1393423    PowerKVM / VIrsh import should allow you to specify a prefix to filter VM's to import

#1393953    dd-format images fail to deploy

#1400909    Networks are being autocreated like eth0-eth0 instead of maas-eth0

#1401349    Memory size changes to incorrect size when page is refreshed

#1402237    Node event log queries are slow (over 1 second)

#1402243    Nodes in 'Broken' state are being power queried constantly

#1402736    clicking on zone link from node page - requested URL was not found on this server

#1403043    Wrong top-level tab is selected when viewing a node

#1381609    Misleading log message when a node has a MAC address not attached to a cluster interface

#1386909    Misleading Error: Unable to identify boot image for (ubuntu/amd64/generic/trusty/local): cluster 'maas' does not have matching boot image.

#1388373    Fresh image import of 3 archs displaying multiple rows for armhf and amd64

#1398159    TFTP into MAAS server to get pxelinux.0 causes unhandled error

#1383651    Node.start() and Node.stop() raise MulltipleFailures unnecessarily

#1383668    null" when releasing an IP address is confusing

#1389416    Power querying for UCSM not working

#1399676    UX bug: mac address on the nodes page should be the MAC address it pxe booted from

#1399736    MAAS should display memory sizes in properly labeld base 2 units - MiB, GiB, etc.

#1401643    Documentation has wrong pattern for user provided preseeds

#1401707    Slow web performance (5+ minute response time) on MAAS with many nodes

#1403609    Fix MSCM chassis enlistment.

#1409952    Correctly parse MAC Address for Power8 VM enlistment.

#1409852    Do not fail when trying to perform an IP Address Reservation.

#1413030    OS and Release no longer populate on Add Node page

#1414036    Trying to add an empty network crashes (AddrFormatError)


1.7.0
=====

Important announcements
-----------------------

**Re-import your boot images**
 You must re-import your boot images, see below for details.

**Update Curtin preseed files**
 Two changes were made to Curtin preseed files that need your attention
 if you made any customisations:

 *  The OS name must now appear in the filename.  The new schema is shown
    here, each file pattern is tried in turn until a match is found::

    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}_{node_name}
    {prefix}_{osystem}_{node_arch}_{node_subarch}_{release}
    {prefix}_{osystem}_{node_arch}_{node_subarch}
    {prefix}_{osystem}_{node_arch}
    {prefix}_{osystem}
    {prefix}

 * If you are modifying ``/etc/network/interfaces`` in the preseed, it must be
   moved so it is processed last in ``late_commands`` since MAAS now writes
   to this file itself as part of IPv6 setup.  For example::

    late_commands:
      bonding_02: ["curtin", "in-target", "--", "wget", "-O", "/etc/network/interfaces", "http://[...snip...]"]

   must now look like this::

    late_commands:
      zz_write_ifaces: ["curtin", "in-target", "--", "wget", "-O", "/etc/network/interfaces", "http://[...snip...]"]

   The leading ``zz`` ensures the command sorts to the end of the
   ``late_commands`` list.


Major new features
------------------

**Improved image downloading and reporting.**
  MAAS boot images are now downloaded centrally by the region controller
  and disseminated to all registered cluster controllers.  This change includes
  a new web UI under the `Images` tab that allows the admin to select
  which images to import and shows the progress of the ongoing download.
  This completely replaces any file-based configuration that used to take
  place on cluster controllers.  The cluster page now shows whether it has
  synchronised all the images from the region controller.

  This process is also completely controllable using the API.

.. Note::
  Unfortunately due to a format change in the way images are stored, it
  was not possible to migrate previously downloaded images to the new region
  storage.  The cluster(s) will still be able to use the existing images,
  however the region controller will be unaware of them until an import
  is initiated.  When the import is finished, the cluster(s) will remove
  older image resources.

  This means that the first thing to do after upgrading to 1.7 is go to the
  `Images` tab and re-import the images.

**Increased robustness.**
  A large amount of effort has been given to ensuring that MAAS remains
  robust in the face of adversity.  An updated node state model has been
  implemented that takes into account more of the situations in which a
  node can be found including any failures at each stage.

  When a node is getting deployed, it is now monitored to check that each
  stage is reached in a timely fashion; if it does not then it is marked
  as failed.

  The core power driver was updated to check the state of the power on each
  node and is reported in the web UI and API.  The core driver now also
  handles retries when changing the power state of hardware, removing the
  requirement that each power template handle it individually.

**RPC security.**
  As a step towards mutually verified TLS connections between MAAS's
  components, 1.7 introduces a simple shared-secret mechanism to
  authenticate the region with the clusters and vice-versa. For those
  clusters that run on the same machine as the region controller (which
  will account for most people), everything will continue to work
  without intervention. However, if you're running a cluster on a
  separate machine, you must install the secret:

  1. After upgrading the region controller, view /var/lib/maas/secret
     (it's text) and copy it.

  2. On each cluster, run:

       sudo -u maas maas-provision install-shared-secret

     You'll be prompted for the secret; paste it in and press enter. It
     is a password prompt, so the secret will not be echoed back to you.

  That's it; the upgraded cluster controller will find the secret
  without needing to be told.

**RPC connections.**
  Each cluster maintains a persistent connection to each region
  controller process that's running. The ports on which the region is
  listening are all high-numbered, and they are allocated randomly by
  the OS. In a future release of MAAS we will narrow this down. For now,
  each cluster controller needs unfiltered access to each machine in the
  region on all high-numbered TCP ports.

**Node event log.**
  For every major event on nodes, it is now logged in a node-specific log.
  This includes events such as power changes, deployments and any failures.

**IPv6.**
  It is now possible to deploy Ubuntu nodes that have IPv6 enabled.
  See :doc:`ipv6` for more details.

**Removal of Celery and RabbitMQ.**
  While Celery was found to be very reliable it ultimately did not suit
  the project's requirements as it is a largely fire-and-forget mechanism.
  Additionally it was another moving part that caused some headaches for
  users and admins alike, so the decision was taken to remove it and implement
  a custom communications mechanism between the region controller and cluster
  controllers.  The new mechanism is bidirectional and allowed the complex
  interactions to take place that are required as part of the robustness
  improvements.

  Since a constant connection is maintained, as a side effect the web UI now
  shows whether each cluster is connected or not.

**Support for other OSes.**
  Non-Ubuntu OSes are fully supported now. This includes:
   - Windows
   - Centos
   - SuSE

**Custom Images.**
  MAAS now supports the deployment of Custom Images. Custom images can be
  uploaded via the API. The usage of custom images allows the deployment of
  other Ubuntu Flavors, such as Ubuntu Desktop.

**maas-proxy.**
  MAAS now uses maas-proxy as the default proxy solution instead of
  squid-deb-proxy. On a fresh install, MAAS will use maas-proxy by default.
  On upgrades from previous releases, MAAS will install maas-proxy instead of
  squid-deb-proxy.

Minor notable changes
---------------------

**Better handling of networks.**
  All networks referred to by cluster interfaces are now automatically
  registered on the Network page.  Any node network interfaces are
  automatically linked to the relevant Network.

.. Note::
  Commissioning currently requires an IP address to be available for each
  network interface on a network that MAAS manages; this allows MAAS to
  auto-populate its networks database.  In general you should use a
  well-sized network (/16 recommended if you will be using containers and
  VMs) and dynamic pool. If this feature risks causing IP exhaustion for
  your deployment and you do not need the auto-populate functionality, you
  can disable it by running the following command on your region controller::

    sudo maas <profile> maas set-config name=enable_dhcp_discovery_on_unconfigured_interfaces value=False

**Improved logging.**
  A total overhaul of where logging is produced was undertaken, and now
  all the main events in MAAS are selectively reported to syslog with the
  "maas" prefix from both the region and cluster controllers alike.  If MAAS
  is installed using the standard Ubuntu packaging, its syslog entries are
  redirected to /var/log/maas/maas.log.

  On the clusters, pserv.log is now less chatty and contains only errors.
  On the region controller appservers, maas-django.log contains only appserver
  errors.

**Static IP selection.**
 The API was extended so that specific IPs can be pre-allocated for network
 interfaces on nodes and for user-allocated IPs.

**Pronounceable random hostnames.**
 The old auto-generated 5-letter names were replaced with a pseudo-random
 name that is produced from a dictionary giving names of the form
 'adjective-noun'.


Known Problems & Workarounds
----------------------------

**Upgrade issues**
 There may be upgrade issues for users currently on MAAS 1.5 and 1.6; while we
 have attempted to reproduce and address all the issues reported, some bugs
 remain inconclusive. We recommend a full, tested backup of the MAAS servers
 before attempting the upgrade to 1.7. If you do encounter issues, please file
 these and flag them to the attention of the MAAS team and we will address them
 in point-releases.  See bugs `1381058`_, `1382266`_, `1379890`_, `1379532`_,
 and `1379144`_.

.. _1381058:
  https://launchpad.net/bugs/1381058
.. _1382266:
  https://launchpad.net/bugs/1382266
.. _1379890:
  https://launchpad.net/bugs/1379890
.. _1379532:
  https://launchpad.net/bugs/1379532
.. _1379144:
  https://launchpad.net/bugs/1379144

**Split Region/Cluster set-ups**
 If you site your cluster on a separate host to the region, it needs a
 security key to be manually installed by running
 ``maas-provision install-shared-secret`` on the cluster host.

**Private boot streams**
 If you had private boot image stream information configured in MAAS 1.5 or
 1.6, upgrading to 1.7 will not take that into account and it will need to be
 manually entered on the settings page in the MAAS UI (bug `1379890`_)

.. _1379890:
  https://launchpad.net/bugs/1379890

**Concurrency issues**
 Concurrency issues expose us to races when simultaneous operations are
 triggered. This is the source of many hard to reproduce issues which will
 require us to change the default database isolation level. We intend to address
 this in the first point release of 1.7.

**Destroying a Juju environment**
 When attempting to "juju destroy" an environment, nodes must be in the DEPLOYED
 state; otherwise, the destroy will fail. You should wait for all in-progress
 actions on the MAAS cluster to conclude before issuing the command. (bug
 `1381619`_)

.. _1381619:
  https://launchpad.net/bugs/1381619

**AMT power control**
 A few AMT-related issues remain, with workarounds:

  * Commissioning NUC reboots instead of shutting down (bug `1368685`_).  There
    is `a workaround in the power template`_

  * MAAS (amttool) cannot control AMT version > 8. See `workaround described in
    bug 1331214`_

  * AMT NUC stuck at boot prompt instead of powering down (no ACPI support in
    syslinux poweroff) (bug `1376716`_). See the `ACPI-only workaround`_

.. _1368685:
  https://bugs.launchpad.net/maas/+bug/1368685
.. _a workaround in the power template:
  https://bugs.launchpad.net/maas/+bug/1368685/comments/8
.. _workaround described in bug 1331214:
  https://bugs.launchpad.net/maas/+bug/1331214/comments/18
.. _1376716:
  https://bugs.launchpad.net/maas/+bug/1376716
.. _ACPI-only workaround:
  https://bugs.launchpad.net/maas/+bug/1376716/comments/12


**Disk wiping**
 If you enable disk wiping, juju destroy-environment may fail for you. The
 current workaround is to wait and re-issue the command.  This will be fixed in
 future versions of MAAS & Juju. (bug `1386327`_)

.. _1386327:
  https://bugs.launchpad.net/maas/+bug/1386327

**BIND with DNSSEC**
 If you are using BIND with a forwarder that uses DNSSEC and have not
 configured certificates, you will need to explicitly disable that feature in
 your BIND configuration (1384334)

.. _1384334:
  https://bugs.launchpad.net/maas/+bug/1384334

**Boot source selections on the API**
 Use of API to change image selections can leave DB in a bad state
 (bug `1376812`_).  It can be fixed by issuing direct database updates.

.. _1376812:
  https://bugs.launchpad.net/maas/+bug/1376812

**Disabling DNS**
 Disabling DNS may not work (bug `1383768`_)

.. _1383768:
  https://bugs.launchpad.net/maas/+bug/1383768

**Stale DNS zone files**
 Stale DNS zone files may be left behind if the MAAS domainname is changed
 (bug `1383329`_)

.. _1383329:
  https://bugs.launchpad.net/maas/+bug/1383329



Major bugs fixed in this release
--------------------------------

See https://launchpad.net/maas/+milestone/1.7.0 for full details.

#1081660    If maas-enlist fails to reach a DNS server, the node will be named ";; connection timed out; no servers could be reached"

#1087183    MaaS cloud-init configuration specifies 'manage_etc_hosts: localhost'

#1328351    ConstipationError: When the cluster runs the "import boot images" task it blocks other tasks

#1342117    CLI command to set up node-group-interface fails with /usr/lib/python2.7/dist-packages/maascli/__main__.py: error: u'name'

#1349254    Duplicate FQDN can be configured on MAAS via CLI or API

#1352575    BMC password showing in the apache2 logs

#1355534    UnknownPowerType traceback in appserver log

#1363850    Auto-enlistment not reporting power parameters

#1363900    Dev server errors while trying to write to '/var/lib/maas'

#1363999    Not assigning static IP addresses

#1364481    http 500 error doesn't contain a stack trace

#1364993    500 error when trying to acquire a commissioned node (AddrFormatError: failed to detect a valid IP address from None)

#1365130    django-admin prints spurious messages to stdout, breaking scripts

#1365850    DHCP scan using cluster interface name as network interface?

#1366172    NUC does not boot after power off/power on

#1366212    Large dhcp leases file leads to tftp timeouts

#1366652    Leaking temporary directories

#1368269    internal server error when deleting a node

#1368590    Power actions are not serialized.

#1370534    Recurrent update of the power state of nodes crashes if the connection to the BMC fails.

#1370958    excessive pserv logging

#1372767    Twisted web client does not support IPv6 address

#1372944    Twisted web client fails looking up IPv6 address hostname

#1373031    Cannot register cluster

#1373103    compose_curtin_network_preseed breaks installation of all other operating systems

#1373368    Conflicting power actions being dropped on the floor can result in leaving a node in an inconsistent state

#1373699    Cluster Listing Page lacks feedback about the images each cluster has

#1374102    No retries for AMT power?

#1375980    Nodes failed to transition out of "New" state on bulk commission

#1376023    After performing bulk action on maas nodes, Internal Server Error

#1376888    Nodes can't be deleted if DHCP management is off.

#1377099    Bulk operation leaves nodes in inconsistent state

#1379209    When a node has multiple interfaces on a network MAAS manages, MAAS assigns static IP addresses to all of them

#1379744    Cluster registration is fragile and insecure

#1380932    MAAS does not cope with changes of the dhcp daemons

#1381605    Not all the DNS records are being added when deploying multiple nodes

#1012954    If a power script fails, there is no UI feedback

#1186196    "Starting a node" has different meanings in the UI and in the API.

#1237215    maas and curtin do not indicate failure reasonably

#1273222    MAAS doesn't check return values of power actions

#1288502    archive and proxy settings not honoured for commissioning

#1316919    Checks don't exist to confirm a node will actually boot

#1321885    IPMI detection and automatic setting fail in ubuntu 14.04 maas

#1325610    node marked "Ready" before poweroff complete

#1325638    Add hardware enablement for Universal Management Gateway

#1340188    unallocated node started manually, causes AssertionError for purpose poweroff

#1341118    No feedback when IPMI credentials fail

#1341121    No feedback to user when cluster is not running

#1341581    power state is not represented in api and ui

#1341800    MAAS doesn't support soft power off through the API

#1344177    hostnames can't be changed while a node is acquired

#1347518    Confusing error message when API key is wrong

#1349496    Unable to request a specific static IP on the API

#1349736    MAAS logging is too verbose and not very useful

#1349917    guess_server_address() can return IPAddress or hostname

#1350103    No support for armhf/keystone architecture

#1350856    Can't constrain acquisition of nodes by not having a tag

#1356880    MAAS shouldn't allow changing the hostname of a deployed node

#1357714    Virsh power driver does not seem to work at all

#1358859    Commissioning output xml is hard to understand, would be nice to have yaml as an output option.

#1359169    MAAS should handle invalid consumers gracefully

#1359822    Gateway is missing in network definition

#1363913    Impossible to remove last MAC from network in UI

#1364228    Help text for node hostname is wrong

#1364591    MAAS Archive Mirror does not respect non-default port

#1365616    Non-admin access to cluster controller config

#1365619    DNS should be an optional field in the network definition

#1365776    commissioning results view for a node also shows installation results

#1366812    Old boot resources are not being removed on clusters

#1367455    MAC address for node's IPMI is reversed looked up to yield IP address using case sensitive comparison

#1373580    [SRU] Glen m700 cartridge list as ARM64/generic after enlist

#1373723    Releasing a node without power parameters ends up in not being able to release a node

#1233158    no way to get power parameters in api

#1319854    `maas login` tells you you're logged in successfully when you're not

#1368480    Need API to gather image metadata across all of MAAS

#1281406    Disk/memory space on Node edit page have no units

#1299231    MAAS DHCP/DNS can't manage more than a /16 network

#1357381    maas-region-admin createadmin shows error if not params given

#1376393    powerkvm boot loader installs even when not needed

#1287224    MAAS random generated hostnames are not pronounceable

#1348364    non-maas managed subnets cannot query maas DNS


1.6.1
=====

Bug fix update
--------------

- Auto-link node MACs to Networks (LP: #1341619)
  MAAS will now auto-create a Network from a cluster interface, and
  if an active lease exists for a node's MAC then it will be linked to
  that Network.


1.6.0
=====

Special notice:
  Cluster interfaces now have static IP ranges in order to give nodes stable
  IP addresses.  You need to set the range in each interface to turn on this
  feature.  See below for details.


Major new features
------------------

IP addresses overhaul.
  This release contains a total reworking of IP address allocation.  You can
  now define a separate "static" range in each cluster interface configuration
  that is separate from the DHCP server's dynamic range.  Any node in use by
  a user will receive an IP address from the static range that is guaranteed
  not to change during its allocated lifetime.  Previously, this was at the
  whim of the DHCP server despite MAAS placing host maps in its configuration.

  Currently, dynamic IP addresses will continue to receive DNS entries so as
  to maintain backward compatibility with installations being upgraded from
  1.5.  However, this will be changed in a future release to only give
  DNS entries to static IPs.

  You can also use the API to `reserve IP addresses`_ on a per-user basis.

.. _reserve IP addresses: http://maas.ubuntu.com/docs1.6/api.html#ip-addresses

Support for additional OSes.
  MAAS can now install operating systems other than Ubuntu on nodes.
  Preliminary beta support exists for CentOS and SuSE via the `Curtin`_ "fast"
  installer.  This has not been thoroughly tested yet and has been provided
  in case anyone finds this useful and is willing to help find and report bugs.


Minor notable changes
---------------------

DNS entries
  In 1.5 DNS entries for nodes were a CNAME record.  As of 1.6, they are now
  all "A" records, which allows for reliable reverse look-ups.

  Only nodes that are allocated to a user and started will receive "A" record
  entries.  Unallocated nodes no longer have DNS entries.

Removal of bootresources.yaml
  The bootresources.yaml file, which had to be configured separately on each
  cluster controller, is no longer in use.  Instead, the configuration for
  which images to download is now held by the region controller, and defaults
  to downloading all images for LTS releases.  A `rudimentary API`_ is
  available to manipulate this configuration.

.. _rudimentary API: http://maas.ubuntu.com/docs1.6/api.html#boot-source

Fast installer is now the default
  Prevously, the slower Debian installer was used by default.  Any newly-
  enlisted nodes will now use the newer `fast installer`_.  Existing nodes
  will keep the installer setting that they already have.

.. _fast installer: https://launchpad.net/curtin


Bugs fixed in this release
--------------------------
#1307779    fallback from specific to generic subarch broken

#1310082    d-i with precise+hwe-s stops at "Architecture not supported"

#1314174    Autodetection of the IPMI IP address fails when the 'power_address' of the power parameters is empty.

#1314267    MAAS dhcpd will re-issue leases for nodes

#1317675    Exception powering down a virsh machine

#1322256    Import boot resources failing to verify keyring

#1322336    import_boot_images crashes with KeyError on 'keyring'

#1322606    maas-import-pxe-files fails when run from the command line

#1324237    call_and_check does not report error output

#1328659    import_boot_images task fails on utopic

#1332596    AddrFormatError: failed to detect a valid IP address from None executing upload_dhcp_leases task

#1250370    "sudo maas-import-ephemerals" steps on ~/.gnupg/pubring.gpg

#1250435    CNAME record leaks into juju's private-address, breaks host based access control

#1305758    Import fails while writing maas.meta: No such file or directory

#1308292    Unhelpful error when re-enlisting a previously enlisted node

#1309601    maas-enlist prints "successfully enlisted" even when enlistment fails.

#1309729    Fast path installer is not the default

#1310844    find_ip_via_arp() results in unpredictable, and in some cases, incorrect IP addresses

#1310846    amt template gives up way too easily

#1312863    MAAS fails to detect SuperMicro-based server's power type

#1314536    Copyright date in web UI is 2012

#1315160    no support for different operating systems

#1316627    API needed to allocate and return an extra IP for a container

#1323291    Can't re-commission a commissioning node

#1324268    maas-cli 'nodes list' or 'node read <system_id>' doesn't display the osystem or distro_series node fields

#1325093    install centos using curtin

#1325927    YUI.Array.each not working as expected

#1328656    MAAS sends multiple stop_dhcp_server tasks even though there's no dhcp server running.

#1331139    IP is inconsistently capitalized on the 'edit a cluster interface' page

#1331148    When editing a cluster interface, last 3 fields are unintuitive

#1331165    Please do not hardcode the IP address of Canonical services into MAAS managed DHCP configs

#1338851    Add MAAS arm64/xgene support

#1307693    Enlisting a SeaMicro or Virsh chassis twice will not replace the missing entries

#1311726    No documentation about the supported power types and the related power parameters

#1331982    API documentation for nodegroup op=details missing parameter

#1274085    error when maas can't meet juju constraints is confusing and not helpful

#1330778    MAAS needs support for managing nodes via the Moonshot HP iLO Chassis Manager CLI

#1337683    The API client MAASClient doesn't encode list parameters when doing a GET

#1190986    ERROR Nonce already used

#1342135    Allow domains to be used for NTP server configuration, not just IPs

#1337437    Allow 14.10 Utopic Unicorn as a deployable series

#1350235    Package fails to install when the default route is through an aliased/tagged interface

#1353597    PowerNV: format_bootif should make sure mac address is all lowercase

1.5.3
=====

Bug fix update
--------------

 - Reduce number of celery tasks emitted when updating a cluster controller
   (LP: #1324944)
 - Fix VirshSSH template which was referencing invalid attributes
   (LP: #1324966)
 - Fix a start up problem where a database lock was being taken outside of
   a transaction (LP: #1325759)
 - Reformat badly formatted Architecture error message (LP: #1301465)
 - Final changes to support ppc64el (now known as PowerNV) (LP: #1315154)


1.5.2
=====

Minor feature changes
---------------------

Boot resource download changes.
  Further to the work done in the 1.5 (Ubuntu 14.04) release, MAAS no
  longer stores the configuration for downloading boot resources in
  ``/etc/maas/bootresources.yaml``; this file is now obsolete. The
  sources list is now stored on the region controller and passed to the
  cluster controller when the job to download boot resources is started.
  It is still possible to pass a list of sources to
  ``maas-import-pxe-files`` when running the script manually.


1.5.1
=====

Bug fix update
--------------

For full details see https://launchpad.net/maas/+milestone/1.5.1

#1303915    Powering SM15k RESTAPI v2.0 doesn't force PXE boot
#1307780    no armhf commissioning template
#1310076    lost connectivity to a node when using fastpath-installer with precise+hwe-s
#1310082    d-i with precise+hwe-s stops at "Architecture not supported"
#1311151    MAAS imports Trusty's 'rc' images by default.
#1311433    REGRESSION: AttributeError: 'functools.partial' object has no attribute '__module__'
#1313556    API client blocks when deleting a resource
#1314409    parallel juju deployments race on the same maas
#1316396    When stopping a node from the web UI that was started from the API, distro_series is not cleared
#1298784    Vulnerable to user-interface redressing (e.g. clickjacking)
#1308772    maas has no way to specify alternate IP addresses for AMT template
#1300476    Unable to setup BMC/UCS user on Cisco B200 M3

1.5
===

(released in Ubuntu 14.04)

Major new features
------------------

Advanced Networking.
  MAAS will now support multiple managed network interfaces on a single
  cluster.  It will track networks (including tagged VLANs) to which each node
  is able to connect and provides this information in the API.  API clients may
  also use networking information in acquisition constraints when asking for a
  new node allocation.

  See :ref:`The full Networking documentation <networks>`.

Zones.
  A Zone is an arbitrary grouping of nodes.  MAAS now allows admins to define
  Zones, and place in them any of the region's nodes.  Once defined, API
  clients can use the zone name as acquisition constraints for new node
  allocations.

  See :doc:`physical-zones` for more detail.

Hardware Enablement Kernels.
  MAAS is now able to fetch and use hardware enablement kernels which allow
  kernels for newer Ubuntu releases to be used on older releases.

  See :doc:`hardware-enablement-kernels`

Minor feature changes
---------------------

Maas-Test.
  A new project `maas-test`_ was created to put a piece of hardware through MAAS's
  test suite to see if it's suitable for use in MAAS, and optionally report the results
  to a bug in Launchpad's maas-test project.

.. _maas-test: https://launchpad.net/maas-test/

IPMI improvements.
  Many improvements were made to IPMI handling, including better detection
  during enlistment.  Many IPMI-based systems that previously failed to work
  with MAAS will now work correctly.

Completion of image downloading changes.
  Further to the work done in the 1.4 (Ubuntu 13.10) release, MAAS now uses indexed
  "simplestreams" data published by Canonical to fetch not only the ephemeral
  images, but now also the kernels and ramdisks.  The resource download
  configuration is now in a new file ``/etc/maas/bootresources.yaml`` on
  each cluster controller.  All previous configuration files for image
  downloads are now obsolete.  The new file will be pre-configured based on
  images that are already present on the cluster.

  This change also enables end-users to provide their own simplestreams data
  and thusly their own custom images.

Cluster-driven hardware availability.
  When adding or editing node hardware in the region controller, MAAS will
  contact the relevant cluster controller to validate the node's settings.
  As of release, the only validation made is the architecture and the power
  settings.  Available architectures are based on which images have been
  imported on the cluster.  In the future, this will enable new cluster
  controllers to be added that contain drivers for new hardware without
  restarting the region controller.

Seamicro hardware.
  MAAS now supports the Seamicro 15000 hardware for power control and API-based
  enlistment.

AMT.
  MAAS now supports power control using `Intel AMT`_.

.. _Intel AMT: http://www.intel.com/content/www/us/en/architecture-and-technology/intel-active-management-technology.html

DNS forwarders.
  In MAAS's settings it's now possible to configure an upstream DNS, which will
  be set in the bind daemon's 'forwarders' option.

Foreign DHCP servers.
  MAAS detects and shows you if any other DHCP servers are active on the
  networks that are on the cluster controller.

Commissioning Results.
  A node's commissioning results are now shown in the UI.

Renamed commands.
  ``maas`` is renamed to ``maas-region-admin``.  ``maas-cli`` is now just
  ``maas``.


Bugs fixed in this release
--------------------------
For full details see https://launchpad.net/maas/+milestone/14.04

#1227035 If a template substitution fails, the appserver crashes

#1255479    MaaS Internal Server Error 500 while parsing tags with namespaces in definition upon commissioning

#1269648    OAuth unauthorised errors mask the actual error text

#1270052    Adding an SSH key fails due to a UnicodeDecodeError

#1274024    kernel parameters are not set up in the installed OS's grub cfg

#1274190    periodic_probe_dhcp task raises IOError('No such device')

#1274912    Internal server error when trying to stop a node with no power type

#1274926    A node's nodegroup is autodetected using the request's IP even when the request is a manual

#1278895    When any of the commissioning scripts fails, the error reported contains the list of the scripts that *didn't* fail

#1279107    maas_ipmi_autodetect.py ignores command failures

#1282828    Almost impossible to provide a valid nodegroup ID when enlisting new node on API

#1283114    MAAS' DHCP server is not stopped when the number of managed interfaces is zero

#1285244    Deleting a node sometimes fails with omshell error

#1285607    maas_ipmi_autodetect mistakes empty slot for taken slot

#1287274    On OCPv3 Roadrunner, maas_ipmi_autodetect fails because LAN Channel settings can't be changed

#1287512    OCPv3 roadrunner detects IPMI as 1.5

#1289456    maas IPMI user creation fails on some DRAC systems

#1290622    report_boot_images does not remove images that were deleted from the cluster

#1293676    internal server error when marking nodes as using fast-path installer

#1300587    Cloud-archive selection widget is obsolete

#1301809    Report boot images no directory traceback

#1052339    MAAS only supports one "managed" (DNS/DHCP) interface per cluster controller.

#1058126    maas dbshell stacktraces in package

#1064212    If a machine is booted manually when in status "Declared" or "Ready", TFTP server tracebacks

#1073460    Node-specific kernel and ramdisk is not possible

#1177932    Unable to select which pxe files to download by both series and architecture.

#1181334    i386 required to install amd64

#1184589    When external commands, issued by MAAS, fail, the log output does not give any information about the failure.

#1187851    Newline added to end of files obtained with maas-cli

#1190986    ERROR Nonce already used

#1191735    TFTP server not listening on all interfaces

#1210393    MAAS ipmi fails on OCPv3 Roadrunner

#1228205    piston hijacks any TypeError raised by MAAS

#1234880    HP ilo4 consoles default to autodetect protocol, which doesn't work

#1237197    No scheduled job for images download

#1238284    multiple ip address displayed for a node

#1243917    'maas createsuperuser' errors out if no email address is entered.

#1246531    dhcpd.conf not updated when user hits "Save cluster controller"

#1246625    The power parameters used by the virsh power template are inconsistent.

#1247708    Cluster interface shows up with no interface name

#1248893    maas-cli listing nodes filtered by hostname doesn't work

#1249435    kernel options not showing up in WebUI and not being passed at install time to one node

#1250410    Search box renders incorrectly in Firefox

#1268795    unable to automatically commission Cisco UCS server due to BMC user permissions

#1270131    1 CPU when there are multiple cores on Intel NUC

#1271056    API call for listing nodes filtered by zone

#1273650    Fastpath installer does not pick up package mirror settings from MAAS

#1274017    MAAS new user creation requires E-Mail address, throws wrong error when not provided

#1274465    Network identity shows broadcast address instead of the network's address

#1274499    dhcp lease rollover causes loss of access to management IP

#1275643    When both IPMI 1.5 and 2.0 are available, MAAS should use 2.0

#1279304    Node commissioning results are not displayed in the UI

#1279728    Storage capacity isn't always detected

#1287964    MAAS incorrectly detects / sets-up BMC information on Dell PowerEdge servers

#1292491    pserv traceback when region controller not yet ready

#1293661    cannot use fast path installer to deploy other than trusty

#1294302    fast installer fails to PXE boot on armhf/highbank

#1295035    The UI doesn't display the list of available boot images

#1297814    MAAS does not advertise its capabilities

#1298790    Logout page vulnerable to CSRF

#1271189    support switching image streams in import ephemerals

#1287310    hard to determine valid values for power parameters

#1272014    MAAS prompts user to run `maas createadmin`; instead of `maas createsuperuser`

#1108319    maascli could have a way to tell which cluster controllers don't have the pxe files


1.4
===

(released in Ubuntu 13.10)

Major new features
------------------

LLDP collection.
  MAAS now collects LLDP data on each node during its
  commissioning cycle.  The router to which the node is connected will have
  its MAC address parsed out of the data and made available for using as a
  placement constraint (passing connected_to or not_connected_to to the
  acquire() API call), or you can define tags using expressions such as
  ``//lldp:chassis/lldp:id[@type="mac"]/text() = "20:4e:7f:94:2e:10"``
  which would tag nodes with a router using that MAC address.

New faster installer for nodes.
  MAAS will now make use of the new Curtin_ installer which is much quicker
  than the old Debian Installer process.  Typically an installation now
  takes a couple of minutes instead of upwards of 10 minutes.  To have a node
  use the faster installer, add the ``use-fastpath-installer`` tag to it,
  or click the "Use the fast installer" button on the node page.

.. _Curtin: https://launchpad.net/curtin

More extensible templates for DHCP, power control, PXE and DNS.
  Templates supplied for these activities are now all in their own template
  file that is customisable by the user.  The files now generally live under
  /etc/maas/ rather than embedded in the code tree itself.

Minor feature changes
---------------------

Reworked ephemeral downloading
  While there is no end-user visible change, the ephemeral image download
  process is now driven by a data stream published by Canonical at
  http://maas.ubuntu.com/images/streams. In the future this will allow end
  users to use their own customised images by creating their own stream.
  The configuration for this is now also part of ``pserv.yaml``, obsoleting
  the maas_import_ephemerals configuration file.  The config will be auto-
  migrated on the first run of the ``maas-import-ephemerals`` script.

Improved maas-cli support
  Users can now manage their SSH keys and API credentials via the maas-cli
  tool.

Django 1.5
  MAAS is updated to work with Django 1.5

HP Moonshot Systems support.
  MAAS can now manage HP Moonshot Systems as any other hardware. However,
  in order for MAAS to power manage these systems, it requires the user
  to manually specify the iLO credentials before the enlistment process
  begins. This can be done in the ``maas_moonshot_autodetect.py``
  template under ``/etc/maas/templates/commissioning-user-data/snippets/``.

Bugs fixed in this release
--------------------------
#1039513  maas-import-pxe-files doesn't cryptographically verify what
it downloads

#1158425  maas-import-pxe-files sources path-relative config

#1204507  MAAS rejects empty files

#1208497  netboot flag defaults to 'true' on upgrade, even for allocated
nodes

#1227644  Releasing a node using the API errors with "TypeError:
00:e0:81:dd:d1:0b is not JSON serializable"

#1234853  MAAS returns HTTP/500 when adding a second managed interface
to cluster controller

#971349  With 100% of nodes in 'declared' state, pie chart is white on white

#974035  Node listing does not support bulk operations

#1045725  SAY clauses in PXE configs are being evaluated as they're
encountered, not when the label is branched to

#1054518  distro_series can be None or ""

#1064777  If a node's IP address is known, it's not shown anywhere

#1084807  Users are editing the machine-generated dhcpd.conf

#1155607  Conflict between "DNS zone name" in Cluster controller and
"Default domain for new nodes" in settings

#1172336  MAAS server reference to AvahiBoot wiki page that does not exist

#1185160  no way to see what user has a node allocated

#1202314  Discrepancy between docs and behavior

#1206222  Documentation Feedback and Site suggestions

#1209039  Document that MAAS requires 'portfast' on switch ports connected
to nodes

#1215750  No way of tracing/debugging http traffic content in the appserver.

#1223157  start_commissioning needlessly sets owner on commissioning nodes

#1227081  Error in apache's log "No handlers could be found for logger
"maasserver""

#1233069  maas-import-pxe-files fails when md5 checksums can't be downloaded

#1117415  maas dhcp responses do not have domain-name or domain-search

#1136449  maas-cli get-config and set-config documentation

#1175405  Pie chart says "deployed" which is inconsistent with the node
list's "allocated"

#1233833  Usability: deleting nodes is too easy

#1185897  expose ability to re-commission node in api and cli

#997092  Can't delete allocated node even if owned by self

