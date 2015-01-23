=========
Changelog
=========

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
  https://launchpad.net/bugs/_1381619

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
#1314174    Autodetection of the IPMI IP address fails when the 'power_address'
of the power parameters is empty.
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
#1309601    maas-enlist prints "successfully enlisted" even when enlistment fail
s.
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
#1331139    IP is inconsistently capitalized on the 'edit a cluster interface' p
age
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

