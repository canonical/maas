=========
Changelog
=========


2.0.0 (rc3)
===========

Issues fixed in this release
----------------------------

LP: #1557434    For the MAAS CLI, mimic the error behaviour provided by argparse 1.1 on PyPI when insufficient arguments are given.


2.0.0 (rc2)
===========

LP: #1582070    Pick up wrong grub.cfg if another filesystem exists

LP: #1599223    [2.0] confusing reverse DNS lookups because MAAS creates multiple PTR records

LP: #1600259    [2.0] reverse DNS sometimes assigns FQDN where it should assign IFACE.FQDN

LP: #1599997    [2.0rc1] after upgrade from 2.0b3, Error on request (13) subnet.list: 'NoneType' object is not iterable

LP: #1598461    [2.0rc1] Image import dates are inconsistent

LP: #1598937    [2.0rc1] Following fresh install maas command fails - PermissionError: [Errno 13] Permission denied: '/home/ubuntu/.maascli.db'

LP: #1597787    [1.9.3,2.0] cannot create more than 4 partitions when disk is configured with mbr

LP: #1600267    [1.9,2.0,UX] Can't add aliases when parent interface is set to 'DCHP'

LP: #1600198    [1.9,2.0,UX] Creating a Bcache disk is not prevented when is not created in partition


2.0.0 (rc1)
===========

Issues fixed in this release
----------------------------

LP: #1576357    Determine a method for how to reconnect a deleted rack controller

LP: #1592246    [2.0b7, regression] maas-rack register makes up a new hostname

LP: #1595753    [beta8] HMC power driver regression -- Not able to connect via SSH.

LP: #1592885    [2.0b7] Date and time format should be consistent accross logs

LP: #1597324    [2.0b8] Unable to set default gateway interface

LP: #1515188    [1.9] VMware power management fails when VMs are organized in nested subfolders

LP: #1596046    [2.0] maas 2.0 pxeboot fails on PowerNV


2.0.0 (beta8)
=============

Issues fixed in this release
----------------------------

LP: #1590081    Allow ed25519 and ecdsa ssh keys

LP: #1462078    [2.0b2, UI] Can't add a device and it does not show why

LP: #1573626    [2.0b3] Interfaces on region controllers are not discovered

LP: #1562107    [2.0b4, UI] No feedback when failing to assign static IP address on the Node Details Page

LP: #1583670    [2.0b5] No way to read settings, like proxy, for non-admin users

LP: #1585016    [2.0b5] Commissing with LVM breaks deployments

LP: #1581729    [2.0b5] dns templates still in /etc/maas/templates

LP: #1588907    [2.0b6] django.db.utils.IntegrityError: insert or update on table "piston3_consumer" violates foreign key constraint LP: "piston3_consumer_user_id_4ac0863fa7e05162_fk_auth_user_id

LP: #1581130    [2.0b6] Image status stays out-of-sync after adding custom image

LP: #1590144    [2.0b6] core count not updated during commissioning if MAAS previously stored a higher core count

LP: #1592282    [2.0b7] Adding rack controller instructions could be in the GUI

LP: #1592132    [2.0b7] Enlisting output returns objects

LP: #1592137    [2.0b7, UI] Can't sort IP addresses under a subnet details page

LP: #1593789    [2.0b7] Nodes API doesn't show regions


2.0.0 (beta7)
=============

Issues fixed in this release
----------------------------

LP: #1587896    get_interfaces_definition is not thread-safe

LP: #1590946    Auto detection of running virtual environment during commissioning almost always fails

LP: #1591093    [2.0,1.9] 3rd party HP drivers (archive hostname renamed) - deployment fails

LP: #1590021    [2.0] Cannot create an IP reservation with a hostname

LP: #1591346    [2.0] maas createadmin fails

LP: #1577953    [2.0b4] Rack Controller fail to update commissioning info?

LP: #1579215    [2.0b4] Can attempt to commission enlisted nodes without chosen power type

LP: #1581219    [2.0b4 UI] MAAS WebUI doesn't quickly refresh when deleting machines

LP: #1581723    [2.0b5] request to http://192.168.10.27:5240/MAAS/metadata/status/43he8/latest failed

LP: #1587896    [2.0b5] p.refresh.get_swap_size misconverting units

LP: #1590499    [2.9b6] Can edit fabric and subnet on deployed node

LP: #1591395    [2.0b6] some arm64 systems need ipmi_ssif module in addition to ipmi_si

LP: #1589587    [2.0b6] Attempting to delete a VLAN that cannot be deleted, shows traceback in regiond.log

LP: #1591958    [2.0b6] Commisioning fails on machines without HW virtualization

LP: #1590991    [2.0b6] Cannot allocate a node based on its system_id

LP: #1589562    [2.0b6, UI] When I delete a fabric, it takes me back to the Node listing page

LP: #1589596    [2.0b6, UI] When I delete a space, it takes me back to the Node listing page

LP: #1588298    [2.0b5, UI] No form validation when adding a subnet, space, fabric or vlan

LP: #1589606    [2.0b6, UI] Message "No IP ranges have been reserved for this subnet." doesn't go away after adding IP Range

LP: #1589583    [2.0b6, UI] Can't add a VLAN over the WebUI

LP: #1589560    [2.6b6, UI] Adding a fabric with an optional name ends up with a new fabric with automatically assigned name

LP: #1589595    [2.6b6, UI] Adding a space with an optional name ends up with a new space with automatically assigned name


2.0.0 (beta6)
=============

Issues fixed in this release
----------------------------

LP: #1572646    Spurious failures in test_regionservice

LP: #1582836    use http for stream mirror, not https

LP: #1583715    MAAS version API call should not require authentication

LP: #1572740    Detect and identify NIC SR-IOV capability

LP: #1584211    [1.9,2.0]Commissioning fails when BIOS reports floppy drive, but there is none installed

LP: #1584850    [1.9,2.0] DNS record created against IPv6 address when it is not on the PXE interface

LP: #1586555    [2.0] MaaS 2.0 BMC information not removed when nodes are removed

LP: #1508741    [2.0] IPMI driver does not handle timeouts correctly

LP: #1585759    [2.0] Display RAM amount to the first decimal place in the UI

LP: #1585760    [2.0] Expose the refresh rack controller action over the UI

LP: #1585768    [2.0] Rename maas-nodegrou-worker to MAAS

LP: #1553841    [2.0a1] MAAS should ensure that BMC password is correct before saving

LP: #1571645    [2.0b2] DNS zone serials are not stable

LP: #1570985    [2.0b2] If you deploy a machine in MAAS, and manually install a rack controller in it, it disappears from the machine list"

LP: #1576417    [2.0b3] rack / region controllers are visible to non-admins

LP: #1577972    [2.0b4] external maas-rack-controller logs to syslog instead of maas.log

LP: #1580817    [2.0b4] twisted.internet.error.ConnectionDone: Connection was closed cleanly.

LP: #1581318    [2.0b4 UI/API] No notifications rack controller is disconnected. No power type available

LP: #1580350    [2.0b5] AMT machines using wsman do not netboot

LP: #1581737    [2.0b5] When installing secondary region controller on its on, last image sync is never

LP: #1583685    [2.0b5] Can't force the import of images per Rack Controller

LP: #1585649    [2.0b5] After changing proxy, MAAS cannot install images

LP: #1584936    [2.0b5] MAAS doesn't import default images automatically

LP: #1558635    [2.0b5] Trying to assign an IP address statically to a device results in builtins.AttributeError: 'NoneType' object has no attribute 'link_subnet' (vid, fabric_id)=(2, 0) already exists.

LP: #1583333    [2.0b5] duplicate key on startup: Key

LP: #1588531    [2.0b5] Deployed regions should be able to transistion back to machines

LP: #1581224    [2.0b5] domain details page does not update as the domain contents change

LP: #1583392    [2.0b5] Cannot disable DHCP if you remove the subnet first ("Cannot configure DHCP: At least one dynamic range is required.")

LP: #1588846    [2.0b5] builtins.ValueError: invalid literal for int() with base 10

LP: #1585628    [2.0, UI] Bulk actions-Nodes action doesn’t apply should be red

LP: #1587936    [2.0, UI] Add fabric, VLAN, Space show's badly place form

LP: #1587939    [2.0, UI] 'Commission' a node under the Node Listing Page shows actions not correctly formatted.

LP: #1587998    [2.0, UI] Add domain show's badly place form

LP: #1588000    [2.0, UI] There's no spacing between combo boxes under the Machine Details page


2.0.0 (beta5)
=============

Issues fixed in this release
----------------------------

LP: #1572076    [UI 2.0b1] Impossible to change subnet CIDR or gateway with instant editing

LP: #1568102    [UI 2.0b1] Network details page doesn't have CSS for editting

LP: #1571670    [UI 2.0b2] Can't edit fabric's, vlans, subnets from the WebUI

LP: #1571672    [UI 2.0b2] Can't add/edit/delete IP ranges through UI

LP: #1570990    [UI/Backend 2.0b2] Can't delete a rack controller from the Rack Details Page

LP: #1576267    [UI 2.0b3] interface addresses on rack controller details page not updated automatically

LP: #1577386    [UI 2.0b4] Actions list is unordered

LP: #1580827    [UI 2.0b4] I can 'add special filesystem' when the machine is deployed

LP: #1521618    [1.9] wrong subnet in DHCP answer when multiple networks are present

LP: #1536346    [2.0] include maas resetMachine() API primitive

LP: #1575567    [2.0] Re-commissioning doesn't detect storage changes

LP: #1570002    [2.0] Expose custom network in non ubuntu deployments

LP: #1580260    [2.0a4] Reserved IP ranges should be allowed to be created by standard users

LP: #1542353    [2.0b2] 6 Core system is listed as having a single CPU

LP: #1570995    [2.0b2] Cannot delete a rack controller that was previously a 'machine'

LP: #1576758    [2.0b3] IP Ranges section on the subnet page should be shown even if no ranges

LP: #1372544    [2.0b3] Tag changes depend on rack / cluster connection

LP: #1577953    [2.0b4] Rack Controller fail to update commissioning info?

LP: #1577954    [2.0b4] Rack Controller mark-broken / mark-fixed

LP: #1577970    [2.0b4] Registering external rack controller tracebacks

LP: #1578800    [2.0b4] RackControllerService flooding log with: 'RegionAdvertisingService' object has no attribute 'processId'

LP: #1580405    [2.0b4] set_initial_networking_configuration shouldn't raise ValidationError

LP: #1580280    [2.0b4] Disks less than 4MB in size cause a traceback on the MAAS server

LP: #1577974    [2.0b4] Rack Controller details page shows "never" under last image sync

LP: #1580285    [2.0b4] Machines successfully commission but don't get marked 'Ready'

LP: #1581654    [2.0b4] Region RPC losing connection and raising exception

LP: #1580771    [2.0b4] unregisterConnection() missing 1 required positional argument: 'host'


2.0.0 (beta4)
=============

Issues fixed in this release
----------------------------

LP: #1527634    [2.0] Disk erasing with Xenial results it abnormal poweroff

LP: #1555864    [2.0a1] UI Nodes page shows 'ascii' codec can't decode byte

LP: #1574003    [2.0a4] When power_type changed to manual "power_state" was not set to "unknown"

LP: #1571007    [2.0b2] MAAS Rack Controller doesn't log when it is importing images.

LP: #1575945    [2.0b3] rackd fails to register vlan interfaces with "vlan" naming scheme

LP: #1573492    [2.0b3] Traceback deleting fabric

LP: #1566108    [2.0b3] adding files with paths in the filename confuses maas

LP: #1571621    [2.0b3] MAAS does not add node to DNS Domain

LP: #1573644    [2.0b3] tag only supports 'nodes' and and not 'machines' or 'controller's

LP: #1573264    [2.0b3] enlistment fails: /tmp/sh.UZ7qJT/bin/maas-enlist: archdetect: not found

LP: #1562919    [2.0b3] creating a dnsresource-record at the root of a zone should allow fqdn=

LP: #1573690    [2.0b3] In the domain details pages, sometimes names have links to nodes when they should not

LP: #1576854    [2.0b3] Can't power on/off Rack Controller

LP: #1573660    [2.0b4] ipranges create raises incorrect error for missing type

LP: #1557597    [UI 2.0] fabric and space pages fail to update automatically

LP: #1567150    [UI 2.0b1] Subnet page doesn't show which machine or device owns an IP address

LP: #1571680    [UI 2.0b2] MAAS Controller listing page doesn't indicate whne a rack is downloading images

LP: #1573219    [1.9.1] Deleting user in UI leads to 500

LP: #1556219    [1.9.1] maas enlistment of power8 found ipmi 1.5 should do ipmi 2.0


2.0.0 (beta3)
=============

Issues fixed in this release
----------------------------

LP: #1573219    Deleting user in UI leads to 500

LP: #1553665    Unconfigured interfaces shouldn't add DNS records

LP: #1571563    Can't override built in partitioning

LP: #1566109    adding a device with no mac address gives an internal server error

LP: #1564927    [2.0] Can't start OMAPI protocol: address not available

LP: #1570606    [2.0] subnet.list: list index out of range error when using a /31 subnet

LP: #1570600    [2.0b2] Trying to enabled dhcp on fabric-1 with IPv4 networks, results in maas-dhcpd6 attempted to be enabled

LP: #1570609    [2.0b2] builtins.TypeError: cannot use a bytes pattern on a string-like object

LP: #1571851    [2.0b2] interface_set returns an interface without 'links' even if empty

LP: #1570626    [2.0b2] NameError: name 'LargeFile' is not defined

LP: #1572070    [2.0b2] Cannot link physical device interfaces to tagged vlans, breaking juju 2.0 multi-NIC containers

LP: #1569483    [2.0b2] Can't deploy CentOS

LP: #1571622    [2.0b2] Bad VLAN Validation on UI Node Details page

LP: #1555715    [UI 2.0a1] changing a subnet's space does not cause a refresh in networks/spaces tab in the UI

LP: #1570152    [UI 2.0b1] Can't delete subnet in the UI, no action for it.

LP: #1571002    [UI 2.0b2] When reconfiguring DHCP, I can't unselect Secondary Rack Controller


2.0.0 (beta2)
=============

Issues fixed in this release
----------------------------

LP: #1563409    [2.0a4] 2.0 api is confused about its hash

LP: #1555251    [2.0] Missing region-controller API

LP: #1569102    API 2.0 deploy makes machine lose power information

LP: #1564657    [2.0a4] Bridges no longer discovered by the rack controller

LP: #1557144    [2.0a1] When Xenial is the only one image imported, nodes fail to boot after saving the commissioning image

LP: #1556185    TypeError: 'Machine' object is not iterable

LP: #1562198    [2.0a4] When providng DHCP a smarter default dynamic range is needed

LP: #1568051    ThreadPool context entry failure causes thread pool to break

LP: #1567178    [2.0 beta 1] After CD install, maas-region RPC endpoints is not available

LP: #1566419    Rack controllers should output whether boot resources are synced

LP: #1566920    Cannot change power settings for machine

LP: #1568041    "[2.0beta1] macaddress_set should be removed from the machines and devices API"

LP: #1568045    [2.0beta1] constraint_map should be removed from the machines acquire output

LP: #1567213    Devices results missing interface_set

LP: #1568847    "[2.0 beta1 ] Service 'maas-proxy' failed to start

LP: #1543195    Unable to set mtu on default VLAN

LP: #1566336    MAAS keeps IPs assigned to eth0, even after eth0 is enslaved into a bond

LP: #1546274    Importing custom boot images is broken in MAAS 1.10.

LP: #1566503    "Failed talking to node's BMC: cannot use a string pattern on a bytes-like object"

LP: #1543968    MAAS 1.9+ allows non-unique space names and shows no space id in a subnet

LP: #1543707    MAAS 1.9+ should not allow whitespace characters in space names

LP: #1560495    [UI 2.0a3] Bad table spacing between columns

LP: #1561733    [2.0a3] MAAS no longer detects external DHCP servers

LP: #1566848    [2.0 beta1] Xenial is not the default image

LP: #1563701    [2.0] VLAN interfaces of secondary rack-controller are not reported

LP: #1561991    [2.0a4] Doesn't use modify over the OMAPI

LP: #1566829    DoesNotExist: RegionControllerProcess matching query does not exist.

LP: #1561954    Ubuntu Server install menu needs a 16.04 refresh

LP: #1564971    [2.0a4] duplicate ipranges cuase dhcpd Configuration file errors

LP: #1568207    Remove deprecated node-interface


2.0.0 (beta1)
=============

Major new features
------------------

**Region Controller Redundancy**
  Starting from MAAS 2.0 beta 1, MAAS now provides the ability to scale out or
  provide redundancy for the MAAS Region Controller API server and DNS. This
  will allow administrators to set up multiple MAAS Region Controllers
  (maas-region-api) against a common database, providing redundancy of services.
  With further manual configuration, users will be able to setup MAAS Region
  Controller in High Availability.

Minor new features
------------------

**MAAS Proxy is now managed**
  Starting from MAAS 2.0 beta 1, MAAS now manages the configuration for
  maas-proxy. This allows MAAS to lock down maas-proxy, and only allow traffic
  from networks MAAS know about. For more information see :ref:`MAAS Proxy <proxy>`

**DHCP Snippets WebUI**
  MAAS 2.0 beta 1 introduces the ability to add and remove DHCP snippets via
  the Web UI. This can be found under the ‘Settings’ page. This feature is
  available for administrative only.

Issues fixed in this release
----------------------------

LP: #1557451    [2.0] MAAS api 1.0 version returns null

LP: #1563094    builtins.FileNotFoundError: [Errno 2] No such file or directory: 'bzr'

LP: #1557526    [2.0a2] Link "go to rack controllers page" does not link to controllers page.

LP: #1562106    [2.0a4] Can't assign a 'Static IP' Address

LP: #1562888    [2.0] DHCP Snippets are not validated before committed

LP: #1553841    [2.0a1] MAAS should ensure that BMC password is correct before saving

LP: #1379567    maas-proxy is an open proxy with no ACLs. it should add networks automatically

LP: #1562214    [2.0a4] If external proxy is being used, status from maas-proxy shouldn't be surfaced

LP: #1555392    [2.0a1] python3-maas-client needs to send data as bytes()

LP: #1563807    Systemd units need to reflect updated MAAS names

LP: #1563799    [2.0a4] Permission error for boot-resources/cache

LP: #1563779    [2.0a4] maas-rackd missing presumed lost


2.0.0 (alpha4)
==============

Important annoucements
----------------------

**maas-region-controller-min has been renamed to maas-region-api**
  The `maas-region-controller-min` package has now been renamed to
  `maas-region-api`. This package provides the API services for MAAS
  (maas-regiond) and can be used to scale out the API front-end of
  your MAAS region controller.

Major new features
------------------

**DHCP Snippets Backend & API**
  MAAS 2.0 alpha 4 introduces the ability to define DHCP snippets. This
  feature allows administrators to manage DHCP directly from MAAS’, removing
  the need to manually modify template files. Snippets can be defined as:

   * `Host snippets`, allowing to define configuration for a particular node in MAAS.
   * `Subnet snippets`, allowing to define configuration for a specific subnet in MAAS.
   * `Global snippets`, allowing to define configuration that will affect DHCP (isc-dhcp) as a whole.

  For more information, see :ref:`DHCP Snippets <dhcpsnippets>`.

Minor new features
------------------

**Rack Controller Web UI Improvements**
  MAAS 2.0 alpha 4 adds the UI for Served VLANs and Service Tracking, allowing users
  to see what VLANs are being currently served by a rack controller, and the status
  of the services in those Rack Controllers.

**Rsyslog during enlistment and commissioning**
  MAAS 2.0 alpha 4 now enables rsyslog for the enlistment and commissioning
  environment when using Xenial as the Commissioning image. This allows users
  to see all cloud-init’s syslog information in /var/log/maas/rsyslog/.

Known issues and work arounds
-----------------------------

**DHCP snippets are not validated before committed**
  When DHCP snippets are created, MAAS is not validating the DHCP snippet against
  isc-dhcp config. This means that if users input invalid isc-dhcp configuration,
  this will cause the DHCP config to be generated anyway, yielding maas-dhcp to
  not be working properly or started at all.

  See bug `1562888`_ for more information.

.. _1562888:
  http://launchpad.net/bugs/1562888

Issues fixed in this release
----------------------------

LP: #1561816    Rack controller 'None' disconnected.

LP: #1557616    [2.0a2] UI provides no way to disable DHCP

LP: #1559332    [2.0a3] Server VLAN's UI is showing too many vlans

LP: #1555679    [2.0a1] bridges with same mac as physical interfaces prevent rack interface discovery

LP: #1560233    [2.0a3] maas-regiond not available right after install.

LP: #1559330    [2.0a3] maas-rackd attemps to connect to regiond, constantely, without stop

LP: #1559361    [2.0a3] maas-dhcpd is being restarted constantly while enlisting/commissioning multiple machines

LP: #1559327    [2.0a3] dhcpd is configured incorrectly when two subnets are incorrectly placed in the same VLAN

LP: #1549843    [2.0a1] Failed to update this region's process and endpoints; unleashed:pid=28940 record's may be out of date

LP: #1559398    [2.0a3] Can't commission too many machines at a time

LP: #1556366    [2.0a1] PXE interface incorrectly displayed on the UI


2.0.0 (alpha3)
==============

Important Announcements
-----------------------

**Debian Installer Files are no longer installed**
  Following the full drop of support for the Debian Installer (DI) in
  1.9, MAAS no longer downloads the DI related files from simplestreams
  and on upgrade all DI related files will be removed both from the
  region and all rack controllers.

Major new features
------------------

**Networks WebUI**
  MAAS 2.0.0 alpha 3 is introducing a few new Web UI features that were
  not available in MAAS 1.9 or MAAS 1.10.

   * Add Fabric and Space details pages
     MAAS 2.0.0 now displays more detailed information of the Fabric and
     Space, by introducing the details page for each.

   * Add ability to add/remove (create/delete) new Fabrics, Spaces, Subnets and VLANs
     MAAS 2.0.0 now provides the ability to add new Fabrics, Spaces, Subnets and VLANs.
     This can be done as actions under the Networks listing page.

     The ability to delete such Fabrics, Spaces, Subnets and VLANs is also available,
     however, this is only possible for the non-default components and from the
     component’s details page.

**WebUI for new storage features**
  MAAS 2.0.0 alpha 3 provides the ability to add mount options via the WebUI.
  MAAS 2.0.0 alpha 3 also provides the ability to create new swap partitions
  via the WebUI. As a reminder, previous MAAS releases would automatically
  create a swap file, but starting from MAAS 2.0, users will have the
  ability to create a swap partition instead, if so desired.

Minor new features
------------------

**Ability to change a machine’s domain name from the UI**
  MAAS 2.0.0 alpha 3 introduces the ability to change a machine’s DNS domain
  via the WebUI. It was previously supported on the API only.

**Rack Controller details page now shows served VLANs**
  The Rack Controller details page now shows what VLANs are being served on
  this Rack Controller, and whether it is the primary or secondary Rack
  providing services for such VLAN.

**Added `maas-rack support-dump` command**
  For increased support observability, users can now dump the contents of
  several commonly-needed data structures by executing `sudo maas-rack support-dump`.
  This command will dump networking diagnostics, rack configuration, and image
  information. Information can be restricted to a particular category by using
  the `--networking`, `--config`, or `--images` options.

Known issues and work arounds
-----------------------------

**Rack Controller tries to constantly reconnect**
  In some situations, the MAAS Rack Controller will try to constantly re-connect
  to the region controller after a restart, causing the Rack Controller to be
  unavailable for a period of time.

  At the moment, there's no work around other than to wait for a few minutes
  until the Rack Controller has been fully connected.

  See bug `1559330`_ for more information.

.. _1559330:
  http://launchpad.net/bugs/1559330

Major bugs fixed in this release
--------------------------------

LP: #1555393    python3-maas-client API 2.0 seems to no longer use op but MAASClient.post requires it and incorectly passes it along

LP: #1554566    Fail to commission when Fabric on Machine Interface and Rack Interface dont match

LP: #1553848    TFTP back-end crashes

LP: #1554999    Can't deploy a node (no interfaces on rack controller)


2.0.0 (alpha2)
==============

Important Announcements
-----------------------

**maas-region-admin command has been replaced**
  The MAAS Region command, `maas-region-admin` has now been replaced
  by the `maas-region` command.

**maas-provision command has been replaced**
  The MAAS Rack Controller command, `maas-provision`, has now been
  replaced by the `maas-rack` command.

Major new features
------------------

**Networks listing page**
  A new Networks listing page has been introduced, that allows users
  users to have a better view of MAAS networking concepts under the
  'Networks' tab. It allows users to filter by `Fabric` and `Space`.

**Service Tracking**
  MAAS is now fully tracking the status of the services for the different
  services that MAAS uses, as defined by systemd. These services are:

   * maas-proxy
   * bind
   * maas-dhcpd and maas-dhcpd6
   * tgt

Known issues & work arounds
---------------------------

**Failure to commission when Machine interfaces are not in the same fabric as DHCP**
  Machines fail to commission when its interfaces are in a different fabric from the
  one DHCP is running on.

  For example, if DHCP is enabled on `fabric-2`, and the machine's PXE interface is on
  `fabric-0`, the machine will fail to commission. To work around this, you can update
  the Rack Controller interface connected to `fabric-2`, to be under `fabric-0`, and
  enabling DHCP on the `untagged` VLAN under `fabric-0`.

  See bug `1553617`_ for more information.

.. _1554566:
  https://launchpad.net/bugs/1554566


2.0.0 (alpha1)
==============

Important Announcements
-----------------------

**MAAS 2.0 supported on Ubuntu 16.04 LTS (Xenial)**
  MAAS version 2.0 will be supported on Ubuntu 16.04 LTS. MAAS 2.0 (and
  the transitional 1.10 release) will NOT be supported on Ubuntu 14.04 LTS.
  MAAS versions 1.9 and earlier will continue to be supported on Ubuntu
  14.04 LTS (Trusty) until they reach end-of-life.

  Upgrades are supported for users running Ubuntu 14.04 systems running
  MAAS 1.9 or earlier. Upon upgrading to Ubuntu 16.04, the MAAS
  database and configuration will be seamlessly migrated to the supported
  MAAS version.

  Please see the “Other Notable Changes” section below for more details
  regarding the reasons for this change.

**API 1.0 has been deprecated, introducing API 2.0**
  Starting from MAAS 2.0, the API 1.0 has now been deprecated and a new
  MAAS 2.0 API is being introduced. With the introduction of the new
  API version, various different endpoints have now been deprecated
  and new end-points have been introduced. API users will need to update
  their client tools to reflect the changes of the new API 2.0.

  For more information on API 2.0, refer to :ref:`API documentation <region-controller-api>`.

**Cluster Controllers have now been deprecated. Introducing Rack Controllers**
  Starting from MAAS 2.0, MAAS Cluster Controllers have been deprecated
  alongside with the NodeGroups API. The Cluster Controllers have been
  replaced with Rack Controllers, and the RackController API have now
  been introduced. Thehe new Rack Controllers currently provides feature
  parity with earlier versions of MAAS.

  For more information on Rack Controllers, refer to the `Major new Features`
  section bellow or refer to :ref:`rack-configuration`.

**MAAS Static Range has been deprecated**
  Starting from MAAS 2.0, the MAAS Static Range has now been deprecated,
  and MAAS assumes total control of a subnet. MAAS will auto-assign IP
  addresses to deployed machines that are not within a dynamic or a reserved
  range. Users are now only required to (continue to) specify the dynamic
  range, which continues to be used for auto-enlistment, commissioning,
  and any other systems configured for DHCP.

Major new features
-------------------

**MAAS Rack Controllers**
  Starting for MAAS 2.0, MAAS has introduced Rack Controllers that completely
  replace Cluster Controllers.

  * NodeGroups and NodeGroupInterfaces API endpoints are now deprecated.
    RackControllers API endpoint has been introduced.

  * Clusters tab is no longer available in the WebUI.
    Controllers can now be found under the Nodes tab, where each cluster
    interface can be found. Other cluster interface properties have been
    moved to the Subnet and VLAN details page under the “Networks” tab.

  * Machines no longer belong to Rack Controllers.
    In earlier versions of MAAS, Machines would directly belong to a Cluster
    Controller in order for them to be managed. The Cluster Controller that
    the machine belonged to would not only perform DHCP for that machine,
    but also all the PXE/TFTP booting, and power management.

    As of MAAS 2.0, Machines no longer belong to a Rack Controller. Multiple
    Rack Controllers could potentially manage the machine. This is now
    automatically determined.

  * DHCP now configured per VLAN
    In earlier versions of MAAS, DHCP was directly linked and configured
    per Cluster Controller Interface. As of MAAS 2.0, DHCP is now configured
    and managed per VLAN, allowing the ability for any Rack Controller in a
    VLAN to manage DHCP.

  * Rack Controllers now provide High Availability
    Provided that machines no longer belong to a Rack Controller, and that
    DHCP is managed on the VLAN bases, multiple Rack Controllers can manage
    the same set of machines. Starting from MAAS 2.0, Rack Controllers in the
    same VLAN become candidates to manage DHCP, PXE/TFTP, and power for the
    machines connected to the VLAN.

    As such, Rack Controllers now support high availability. MAAS supports
    the concept of Primary and Secondary Rack Controller. In the event that
    the Primary Rack Controller is unavailable, the Secondary Rack Controller
    can take over the services provided providing High Availability.

**DNS Management**
  MAAS 2.0 extends DNS management and provides the ability to:

  * Ability to create multiple DNS domains.
  * Ability to add multiple records (CNAME, TXT, MX, SRV ) per
    domain. (API only)
  * Ability to select Domain for Machines and Devices. (API only, WebUI
    in progress)
  * Ability to assign (additional) names to IP addresses (API only)
  * For deployed machines, A records continue to be create specifying
    the IP of the PXE interface.
  * Additional PTR records and now created for all the other interfaces in
    the form of: <interface>.<machine fully-qualified-domain-name>
  * Reverse DNS is now generated for only the subnet specified, rather
    than the parent /24 or /16.  By default, RFC2137 glue is provided
    for networks smaller than /24.  This can be disabled or changed
    on a per-subnet basis via the API.

**IP Ranges**
  Previous versions of MAAS used the concepts of a “dynamic range” and
  “static range”, which were properties of each cluster interface. This
  has been redesigned for MAAS 2.0 as follows:

  * Dynamic ranges have been migrated from MAAS 1.10 and earlier as-is.

  * Because static ranges have been removed from MAAS, each static
    range has been migrated to one or more reserved ranges, which
    represent the opposite of the previous static range. (MAAS now
    assumes it has full control of each managed subnet, and is free
    to assign IP addresses as it sees fit, unless told otherwise.)

    For example, if in MAAS 1.10 or earlier you configured a cluster
    interface on 192.168.0.1/24, with a dynamic range of 192.168.0.2
    through 192.168.0.99, and a static range of 192.168.0.100 through
    192.168.0.199, this will be migrated to:

      IP range #1 (dynamic): 192.168.0.2 - 192.168.0.99
      IP range #2 (reserved): 192.168.0.200 - 192.168.0.254

    Since 192.168.0.100 - 192.168.0.199 (the previous static range)
    is not accounted for, MAAS assumes it is free to allocate static
    IP addresses from that range.

  * Scalability is now possible by means of adding a second dynamic
    IP range to a VLAN. (To deal with IP address exhaustion, MAAS
    supports multiple dynamic ranges on one or more subnets within
    a DHCP-enabled VLAN.)

  * Reserved ranges can now be allocated to a particular MAAS user.

  * A comment field has been added, so that users can indicate why
    a particular range of IP addresses is reserved.

**API 2.0 and MAAS CLI Updates**
  MAAS 2.0 introduces a new API version, fully deprecating the
  MAAS 1.0 API. As such, new endpoints and commands have been introduced:

  * RackControllers - This endpoint/command has the following operations
    in addition to the base operations provided by nodes:

      * import-boot-images - Import the boot images on all rack
        controllers
      * describe-power-types - Query all of the rack controllers for
        power information

  * RackController - This endpoint/command has the following operations
    in addition to the base operations provided by nodes

    * import-boot-images - Import boot images on the given rack
      controller
    * refresh - refresh the hardware information for the given rack
      controller

  * Machines - This endpoint/command replaces many of the operations
    previously found in the nodes endpoint/command. The machines
    endpoint/command has the following operations in addition to the
    base operations provided by nodes.

    * power-parameters - Retrieve power parameters for multiple
      machines
    * list-allocated - Fetch machines that were allocated to the
      user/oauth token.
    * allocate - Allocate an available machine for deployment.
    * accept - Accept declared machine into MAAS.
    * accept-all - Accept all declared machines into MAAS.
    * create - Create a new machine.
    * add-chassis - Add special hardware types.
    * release - Release multiple machines.

  * Machine - This endpoint/command replaces many of the operations
    previously found in the node endpoint/command. The machine
    endpoint/command has the following operations in addition to the
    base operations provided by node.

    * power-parameters - Obtain power parameters for the given machine.
    * deploy - Deploy an operating system to a given machine.
    * abort - Abort the machines current operation.
    * get-curtin-config - Return the rendered curtin configuration for
      the machine.
    * power-off - Power off the given machine.
    * set-storage-layout - Change the storage layout of the given
      machine.
    * power-on -Turn on the given machine.
    * release - Release a given machine.
    * clear-default-gateways - Clear any set default gateways on the
      machine.
    * update - Change machine configuration.
    * query-power-state - Query the power state of a machine.
    * commission - Begin commissioning process for a machine

  Other endpoints/commands have changed:

  * All list commands/operations have been converted to read
  * All new and add commands/operations have been converted to create
  * Nodes - The nodes endpoint/command is now a base endpoint/command
    for all other node types(devices, machines, and rack-controllers).
    As such most operations have been moved to the machines
    endpoint/command.The following operations remain as they can be
    used on all node types.

    * is-registered - Returns whether or not the given MAC address is
      registered with this MAAS.
    * set-zone - Assign multiple nodes to a physical zone at once.
    * read - List nodes visible to the user, optionally filtered by
      criteria.

  * Node - The node endpoint/command is now a base endpoint/command for
    all other node types(devices, machines, and rack-controllers). As
    such most operations have been moved to the machine endpoint/command.
    The following operations remain as they can be used on all node types.

    * read - Read information about a specific node
    * details - Obtain various system details.
    * delete  - Delete a specific node.

  * With the migration of nodes to machines the following items previously
    outputted with the list command have been changed or removed from the
    machines read command:

    * status - Will now show all status types
    * substatus, substatus_action, substatus_message, substatus_name -
      Replaced by status, status_action, status_message, status_name.
    * boot_type - Removed, MAAS 2.0 only supports fastpath.
    * pxe_mac - Replaced by boot_interface.
    * hostname - Now only displays the hostname, without the domain, of
      the machine. To get the fully qualified domain name the fqdn and
      domain are now also outputted.

  * And other endpoints/commands have been deprecated:

    * NodeGroups - Replacement operations are found in the
      RackControllers, Machines, and BootResources endpoints/commands.
    * NodeGroupInterfaces - replacement operations are found in the
      RackController, IPRanges, Subnets, and VLANS endpoints/commands.

**Extended Storage Support**
  MAAS 2.0 Storage Model has been extended to support:

  * XFS as a filesystem.
  * Mount Options.
  * Swap partitions. MAAS 1.9 only supported the creation of a swap
    file in the filesystem.
  * tmps/ramfs Support.

  All of these options are currently available over the CLI.

Other notable changes
---------------------

**MAAS 2.0 Requires Python 3.5**
  Starting from MAAS 1.10 transitional release, MAAS has now been
  ported to Python 3. The Python 3 version ported against is 3.5,
  which is default in Ubuntu Xenial.

**MAAS 2.0 now fully supports native Django 1.8 migration system**
  Starting from the MAAS 1.10 transitional release, MAAS has added
  support for Django 1.8. Django 1.8 has dropped support for the
  south migration system in favor of the native Django migration
  system, breaking backwards compatibility. As such, MAAS 2.0 has
  inherited such support and moving forward migrations will be run
  with the native migration system.

  Provided that Django 1.8 breaks backwards compatibility with the
  south migration system, the MAAS team has put significant effort
  in ensuring MAAS continues to support an upgrade path, and as
  such, users from 1.5, 1.7, 1.8, 1.9 and 1.10 will be able to
  upgrade seamlessly to MAAS 2.0.

**Instant DHCP Lease Notifications**
  We no longer scan the leases file every 5 minutes. ISC-DHCP now
  directly notifies MAAS if a lease is committed, released, or expires.

**Host entries in DHCP**
  Host entries are now rendered in the DHCP configuration instead
  of placed in the leases file. This removes any state that used
  to previously exist in the leases file on the cluster controller.
  Now deleting the dhcpd.leases file will not cause an issue with
  MAAS static mappings.

**Modeling BMCs**
  We select one of the available rack controllers to power control
  or query a BMC. The same rack controller that powers the BMC does
  not need to be the rack controller that the machine PXE boots from.

Known Problems & Workarounds
----------------------------

**Rack Controllers will fail to register when bond interfaces are present**
  Registering Rack Controller that have bond interfaces will fail.

  See bug `1553617`_ for more information.

.. _1553617:
  https://launchpad.net/bugs/1553617
