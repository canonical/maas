=========
Changelog
=========

1.5.2
=====

Bug fix update
--------------

- Remove workaround for fixed Django bug 1311433 (LP: #1311433)
- Ensure that validation errors are returned when adding a node over
  the API and its cluster controller is not contactable. (LP: #1305061)
- Hardware enablement support for PowerKVM
- Shorten the time taken for a cluster to initially connect to the region
  via RPC to around 2 seconds (LP: #1317682)
- Faster DHCP leases parser (LP: #1305102)
- Documentation fixed explaining how to enable an ephemeral backdoor
  (LP: #1321696)
- Use probe-and-enlist-hardware to enlist all virtual machine inside
  a libvirt machine, allow password qemu+ssh connections.
  (LP: #1315155, LP: #1315157)
- Rename ppc64el boot loader to PowerKVM (LP: #1315154)


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

#1269648    OAuth unauthorized errors mask the actual error text

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

#1238284    mutiple ip address displayed for a node

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

#1274499    dhcp lease rollover causes loss of access to managment IP

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

