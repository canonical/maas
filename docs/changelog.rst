=========
Changelog
=========

2.2.3
=====

Bugs fixed in this release
--------------------------

LP: #1707971    MAAS becomes unstable after rack controller restart

LP: #1710278    [2.3a1] named stuck on reload, DNS broken

LP: #1710308    [2.2] MAAS should confirm the success of DNS reloads by checking the zone serial

LP: #1715634    'tags machines' takes 30+ seconds to respond with list of 9 nodes

LP: #1706196    Maas creates a pod machine even when a machine tag is set as a constraint

LP: #1708052    Curtin fails to install on a disk previosly installed with RAID

LP: #1710681    [2.2, 2.3] Cannot delete an Ubuntu image, "Update Selection" is disabled

LP: #1711700    [2.x] MAAS should avoid updating DNS if nothing changed

LP: #1507712    cli: maas logout causes KeyError for other profiles

LP: #1704444    [2.2] MAAS API returns 500 internal server error instead of raising actual error

LP: #1676992    Force Postgresql restart on maas-region-controller installation.

LP: #1717287    maas-enlist not supporting IPv6 addresses in server_url.

LP: #1718209    Fix IPv6 DHCP PXE configuration.


2.2.2
=====

Bugs fixed in this release
--------------------------

LP: #1706196    Exclude pod machine composition during allocation if tags are supplied.

LP: #1700802    Add missing networking constraint names.

LP: #1702690    Set the machine's min_hwe_kernel to the setting's default_min_hwe_kernel when commissioning.

LP: #1651165	Update the disk when editing the disk in the UI and not only the filesystem. This saves a new disk name if that was changed. Code for any filesystem updates is still in tact via the machine websocket handler update_disk method.

LP: #1686678    Allows the domain of controllers to be changed in the UI.

LP: #1703713    Fix missing link on domain details page.

LP: #1609496    Increase & add 'wait_time' for IPMI to work around issues with older & broken BMC's.

LP: #1701056    Show correct information for a device details page as a normal user

LP: #1701052    Do not show the controllers tab as a normal user

LP: #1703845    Set the re-check interval for rack to region RPC connections to the lowest value when a RPC connection is closed or lost.

LP: #1703403    Lower the maximum number of connections per worker to 9 connections is allowed as 1 is reserved.

LP: #1704489    Duplicate communication is occurring to the same rack controller

LP: #1705254    RegionService can raise unexpected exceptions for an empty connection list

LP: #1705508    Set the no_proxy environment variable to 127.0.0.1,localhost.

LP: #1705792    Emulate a terminal when logging script output

LP: #1701694    Allow uploading images with the format osystem/release.


2.2.1
=====

Bugs fixed in this release
--------------------------

LP: #1690781    Make virsh-based pods more robust when empty XML is returned.

LP: #1695083    Improve NTP IP address selection for MAAS DHCP clients.

LP: #1652298    Device Discovery, Node Listing and Events page performance improvements.

LP: #1694759    RSD Pod refresh shows ComposedNodeState is "Failed"

LP: #1694767    RSD composition not setting local disk tags

LP: #1678339    [2.2] Can't assign a static IP to a physical interface due to incorrect validation

LP: #1693644    Enlistment does not validate min_hwe_kernel\

LP: #1699286    [2.2, trunk] test__renders_ntp_servers_as_comma_separated_list fails randomly

LP: #1650396    Interface configuration cannot be modified unless the node is Ready or Broken.

LP: #1695229    Badblocks: Value too large for defined data type invalid end block

LP: #1682374    [2.2, UI, mobile] The navigation doesn't work on mobile

LP: #1669744    [2.x, UI] [Device discovery] Enable/Disable toggle is hidden

LP: #1680795    [2.x, UI] [Device discovery] Move the tooltipinbetween the label and the toggle


2.2.0
=====

Important announcements
-----------------------

**Migrating MAAS L3 to L2 spaces**
 MAAS 2.2 has changed the definition of spaces from a Layer 3 concept to a
 Layer 2 concept.

 The spaces definition in MAAS (first introduced in MAAS 1.9) is “a set of
 subnets that can mutually communicate”. The assumption is that these spaces
 can route to each other, and have appropriate firewall rules for their
 purposes. (For example, a dmz space might contain subnets with internet
 access, and a storage space might contain subnets that can access the same
 storage networks.) Juju uses the current definition in order to ensure that
 deployed applications have access to networks appropriate for the services
 they provide.

 The current definition of spaces as a L3 concept is problematic, in that
 sometimes Juju wants to deploy applications that themselves create a Layer 3
 subnet. Therefore, it was decided that the concept of spaces will be pushed
 down a layer (to apply to VLANs in MAAS).

 With spaces as a Layer 2 concept, it is is now “a set of VLANs whose subnets
 can mutually communicate”.

 As such, starting from MAAS 2.2b1:

  * VLANs will gain a ‘space’ reference, and subnets will have their spaces
    migrated to the VLANs they are on. On upgrades, if two subnets on the same
    VLAN are in different spaces, the most recently created space will be used
    for both.

  * Spaces will become optional. Fresh installs will not have a default space
    (e.g. space-0). On upgrades, if only the default space (space-0) exists,
    it will be removed.

 The following API changes will occur in MAAS 2.2:

  * Editing a subnet's space will no longer be possible (breaks backwards
    compatibility). Spaces must now be edited each VLAN. For backward
    compatibility, the subnets endpoint will present the underlying VLAN’s space.

 Recommended actions for MAAS administrators prior to upgrading to MAAS 2.2:

  * Ensure that no two subnets in the same VLAN are in different spaces, so that
    the upgrade path migrates the expected space to the VLAN. Ensure that each
    VLAN with an assigned space will contain subnets which can mutually
    communicate with other subnets whose VLAN is in the same space. This will
    allow backward compatibility with Juju charms which use the Layer 3 definition
    of spaces.

 NOTE: Please note that not breakage is expected, provided that most people are not
 using spaces. For those who we know are, they are using them in a compatible way.
 If you experience some type of issue, please contact us.

Major new features
------------------

**DHCP Relay support**
 The ability to model the usage of DHCP relays in your networking configuration has
 been added to MAAS. The allows an administrator to identify which VLANs will be
 relayed through another VLAN running a MAAS DHCP server. This will configure the
 MAAS DHCP server running on the primary and/or secondary rack controller to include
 the shared network statement for that VLAN. Note: MAAS does not run a DHCP relay
 service, it is up to the administrator to configure the DHCP relay service on the
 VLAN and point it at the primary and/or secondary rack controller running the MAAS DHCP.

**Unmanaged subnets**
 In MAAS 2.0, the concept of a “static range” (a specific range of addresses in which
 MAAS was allowed to freely allocate addresses from) was removed from MAAS, in favor
 of the idea that MAAS managing entire subnets. As such, the only way to tell MAAS to
 not allocate certain sections of a subnet is to add a reserved IP range.

 Starting from MAAS 2.2b1, however, MAAS enhances this functionality by introducing a
 new concept, called unamanged subnets. Setting a Subnet in MAAS as unmanaged, allows
 administrators to prevent MAAS from using that subnet for automatic IP assignment.
 In other words, it is a way to tell MAAS that it knows about a subnet but that it
 shouldn’t use it.

Other notable changes
---------------------

**MAAS is now responsive**
 For all of those users that use (or would like to use) MAAS WebUI from their Phone
 or Tablet, will now have a better user experience, provided that starting from
 2.2b1, MAAS is now responsive.

 Phone or Table users will see a new slick design for those devices. Thanks for
 the Ubuntu Web team for putting the effort into making MAAS look great in smaller
 devices.

Known issues and workarounds
----------------------------

**Cannot add a device from the dashboard**
 Please see LP #1659959 for more information.

 https://bugs.launchpad.net/maas/+bug/1659959
