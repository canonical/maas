=========
Changelog
=========

1.7.0
=====

Major new features
------------------

Improved image downloading and reporting.
  MAAS boot images are now downloaded centrally by the region controller
  and disseminated to all registered cluster controllers.  This change includes
  a new web UI under the `Images` tab that allows the admin to select
  which images to import and shows the progress of the ongoing download.
  This completely replaces any file-based configuration that used to take
  place on cluster controllers.  The cluster page now shows whether it has
  synchronised all the images from the region controller.

  This process is also completely controllable using the API.

Note:
  Unfortunately due to a format change in the way images are stored, it
  was not possible to migrate previously downloaded images to the new region
  storage.  The cluster(s) will still be able to use the existing images,
  however the region controller will be unaware of them until an import
  is initiated.  When the import is finished, the cluster(s) will remove
  older image resources.

  This means that the first thing to do after upgrading to 1.7 is go to the
  `Images` tab and re-import the images.

Increased robustness.
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

RPC security.
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

RPC connections.
  Each cluster maintains a persistent connection to each region
  controller process that's running. The ports on which the region is
  listening are all high-numbered, and they are allocated randomly by
  the OS. In a future release of MAAS we will narrow this down. For now,
  each cluster controller needs unfiltered access to each machine in the
  region on all high-numbered TCP ports.

Node event log.
  For every major event on nodes, it is now logged in a node-specific log.
  This includes events such as power changes, deployments and any failures.

IPv6.
  It is now possible to deploy Ubuntu nodes that have IPv6 enabled.
  See :doc:`ipv6` for more details.

Removal of Celery and RabbitMQ.
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

Support for other OSes.
  Non-Ubuntu OSes are fully supported now. This includes:
   - Windows
   - Centos
   - SuSE

Custom Images.
  MAAS now supports the deployment of Custom Images. Custom images can be
  uploaded via the API. The usage of custom images allows the deployment of
  other Ubuntu Flavors, such as Ubuntu Desktop.

maas-proxy.
  MAAS now uses maas-proxy as the default proxy solution instead of
  squid-deb-proxy. On a fresh install, MAAS will use maas-proxy by default.
  On upgrades from previous releases, MAAS will continue to use squid-deb-proxy
  as the proxy for backwards compatibility.
  If you wish to use maas-proxy, you simply need to install it. Running this will
  install maas-proxy and remove squid-deb-proxy:
  sudo apt-get install maas-proxy

Minor notable changes
---------------------

Better handling of networks.
  All networks referred to by cluster interfaces are now automatically
  registered on the Network page.  Any node network interfaces are
  automatically linked to the relevant Network.

Improved logging.
  A total overhaul of where logging is produced was undertaken, and now
  all the main events in MAAS are selectively reported to syslog with the
  "maas" prefix from both the region and cluster controllers alike.  If MAAS
  is installed using the standard Ubuntu packaging, its syslog entries are
  redirected to /var/log/maas/maas.log.

  On the clusters, pserv.log is now less chatty and contains only errors.
  On the region controller appservers, maas-django.log contains only appserver
  errors.

Static IP selection.
 The API was extended so that specific IPs can be pre-allocated for network
 interfaces on nodes and for user-allocated IPs.

Pronounceable random hostnames.
 The old auto-generated 5-letter names were replaced with a pseudo-random
 name that is produced from a dictionary giving names of the form
 'adjective-noun'.

Bugs fixed in this release
--------------------------
#1081660    If maas-enlist fails to reach a DNS server, the node will be named ";; connection timed out; no servers could be reached"
#1087183    MaaS cloud-init configuration specifies 'manage_etc_hosts: localhost'
#1328351    ConstipationError: When the cluster runs the "import boot images" task it blocks other tasks
#1340208    DoesNotExist: NodeGroupInterface has no nodegroup
#1340896    MAAS upgrade from 1.5.2+bzr2282-0ubuntu0.2 to experiment failed
#1342117    CLI command to set up node-group-interface fails with /usr/lib/python2.7/dist-packages/maascli/__main__.py: error: u'name'
#1342395    power_on: ipmi failed: name 'power_off_mode' is not defined at line 12 column 18 in file /etc/maas/templates/power/ipmi.template
#1347579    Schema migration 0091 is broken (node boot type)
#1349254    Duplicate FQDN can be configured on MAAS via CLI or API
#1352575    BMC password showing in the apache2 logs
#1353598    maas-import-pxe-files logger import error for logger
#1355014    Can't run tests without a net connection
#1355534    UnknownPowerType traceback in appserver log
#1356788    Test failure: “One or more services are registered” etc.
#1359029    Power status monitoring does not scale
#1359517    Periodic DHCP probe breaks: "Don't log exceptions to maaslog"
#1359551    create_Network_from_NodeGroupInterface is missing a catch for IntegrityError
#1360004    UI becomes unresponsive (unaccessible) if RPC to cluster fails
#1360008    Data migration fails with django.db.utils.InternalError: current transaction is aborted, commands ignored until end of transaction block
#1360676    KeyError raised importing boot images
#1361799    absolute_reverse returns incorrect url if base_url is missing ending /
#1362397    django.core.exceptions.ValidationError: {'power_state': [u'Ensure this value has at most 10 characters (it has 18).']}
#1363105    Change in absolute_reverse breaks netbooting on installed MAAS
#1363116    DHCP Probe timer service fails
#1363138    DHCP Probe TimerService fails with 'NoneType' object has no attribute 'encode'
#1363474    exceptions.KeyError: u'subarches' when syncing uploaded image from region to cluster
#1363525    preseed path for generated tgz doesn't match actual path
#1363722    Boot resource upload failed: error: length too large
#1363850    Auto-enlistment not reporting power parameters
#1363900    Dev server errors while trying to write to '/var/lib/maas'
#1363999    Not assigning static IP addresses
#1364062    New download boot resources method doesn't use the configured proxy
#1364481    http 500 error doesn't contain a stack trace
#1364993    500 error when trying to acquire a commissioned node (AddrFormatError: failed to detect a valid IP address from None)
#1365130    django-admin prints spurious messages to stdout, breaking scripts
#1365175    bootloader import code goes directly to archive.ubuntu.com rather than the configured archive
#1365850    DHCP scan using cluster interface name as network interface?
#1366104    [FFe] OperationError when large object greater than 2gb
#1366172    NUC does not boot after power off/power on
#1366212    Large dhcp leases file leads to tftp timeouts
#1366652    Leaking temporary directories
#1366726    CI breakage: Deployed nodes don't get a static IP address
#1368269    internal server error when deleting a node
#1368590    Power actions are not serialized.
#1370534    Recurrent update of the power state of nodes crashes if the connection to the BMC fails.
#1370958    excessive pserv logging
#1371033    A node can get stuck in the 'RELEASING' state if the power change command fails to power down the node.
#1371064    Spurious test failure: maasserver.rpc.tests.test_nodes.TestCreateNode.test_creates_node
#1371236    power parameters for probe-and-enlist mscm no longer saved for enlisted nodes
#1372408    PowerQuery RPC method crashes with exceptions.TypeError: get_power_state() got an unexpected keyword argument 'power_change'
#1372732    ImportError running src/metadataserver/tests/test_fields.py
#1372735    Deprecation warning breaks Node model tests
#1372767    Twisted web client does not support IPv6 address
#1372944    Twisted web client fails looking up IPv6 address hostname
#1373031    Cannot register cluster
#1373103    compose_curtin_network_preseed breaks installation of all other operating systems
#1373207    Can't build package
#1373237    maas-cluster-controller installation breaks: __main__.py: error: unrecognized arguments: -u maas -g maas
#1373265    Where did the “Import boot images” button go?
#1373357    register_event_type fails: already exists
#1373368    Conflicting power actions being dropped on the floor can result in leaving a node in an inconsistent state
#1373477    Circular import between preseed.py and models/node.py
#1373658    request_node_info_by_mac_address errors during enlistment: MACAddress matching query does not exist
#1373699    Cluster Listing Page lacks feedback about the images each cluster has
#1373710    Machines fail to PXE Boot
#1374102    No retries for AMT power?
#1374388    UI checkbox for Node.disable_ipv4 never unchecks
#1374793    Cluster page no longer shows whether the cluster is connected or not.
#1375594    After a fresh install, cluster can't connect to region
#1375664    Node powering on but not deploying
#1375835    Can't create node in the UI with 1.7 beta 4
#1375970    Timeout leads to inconsistency between maas and real world state, can't commission or start nodes
#1375980    Nodes failed to transition out of "New" state on bulk commission
#1376000    oops: 'NoneType' object has no attribute 'encode'
#1376023    After performing bulk action on maas nodes, Internal Server Error
#1376028    maasserver Unable to identify boot image for (ubuntu/amd64/generic/trusty/poweroff): cluster 'maas' does not have matching boot image.
#1376031    WebUI became unresponsive after disconnecting Remote Cluster Controller (powered node off)
#1376303    Can't commission a node: xceptions.AttributeError: 'NoneType' object has no attribute 'addCallback'
#1376304    Timeout errors in RPC commands cause 500 errors
#1376782    Node stuck with: "another action is already in progress for that node."
#1376888    Nodes can't be deleted if DHCP management is off.
#1377099    Bulk operation leaves nodes in inconsistent state
#1377860    Nodes not configured with IPv6 DNS server address
#1379154    "boot-images" link in the "Visit the boot images page to start the import." is a 404
#1379209    When a node has multiple interfaces on a network MAAS manages, MAAS assigns static IP addresses to all of them
#1379568    maas-cluster fails to register if the host has an IPv6 address
#1379591    nodes with two interfaces fail to deploy in maas 1.7 beta5
#1379641    IPv6 netmasks aren't *always* 64 bits, but we only configure 64-bit ones
#1379649    Invalid transition - 'Releasing Failed' to 'Disk Erasing'
#1379744    Cluster registration is fragile and insecure
#1379924    maas 1.7 flooded with OOPSs
#1380927    Default Cluster does not autoconnect after a fresh install
#1380932    MAAS does not cope with changes of the dhcp daemons
#1381605    Not all the DNS records are being added when deploying multiple nodes
#1381714    Nodes release API bypasses disk erase
#1012954    If a power script fails, there is no UI feedback
#1057250    TestGetLongpollContext.test_get_longpoll_context is causing test failures in metadataserver
#1186196    "Starting a node" has different meanings in the UI and in the API.
#1237215    maas and curtin do not indicate failure reasonably
#1273222    MAAS doesn't check return values of power actions
#1288502    archive and proxy settings not honoured for commissioning
#1300554    If the rabbit password changes, clusters are not informed
#1315161    cannot deploy Windows
#1316919    Checks don't exist to confirm a node will actually boot
#1321885    IPMI detection and automatic setting fail in ubuntu 14.04 maas
#1325610    node marked "Ready" before poweroff complete
#1325638    Add hardware enablement for Universal Management Gateway
#1333954    global registry of license keys
#1334963    Nodegroupinterface.clean_ip_ranges() is very slow with large networks
#1337437    [SRU] maas needs utopic support
#1338169    Non-Ubuntu preseed templates are not tested
#1339868    No way to list supported operating systems via RPC
#1339903    No way to validate an OS license key via RPC
#1340188    unallocated node started manually, causes AssertionError for purpose poweroff
#1340305    No way to get the title for a release from OperatingSystem
#1341118    No feedback when IPMI credentials fail
#1341121    No feedback to user when cluster is not running
#1341581    power state is not represented in api and ui
#1341619    NodeGroupInterface is not linked to Network
#1341772    No way to get extra preseed data from OperatingSystem via RPC
#1341800    MAAS doesn't support soft power off through the API
#1343425    deprecate use-fastpath-installer tag and use a property on node instead
#1344177    hostnames can't be changed while a node is acquired
#1347518    Confusing error message when API key is wrong
#1349496    Unable to request a specific static IP on the API
#1349736    MAAS logging is too verbose and not very useful
#1349917    guess_server_address() can return IPAddress or hostname
#1350103    No support for armhf/keystone architecture
#1350856    Can't constrain acquisition of nodes by not having a tag
#1350948    IPMI power template treats soft as an option rather than a command
#1354014    clusters should sync boot images from the region
#1356490    Metadataserver api needs tests for _store_installing_results
#1356780    maaslog items are logged twice
#1356880    MAAS shouldn't allow changing the hostname of a deployed node
#1357071    When a power template fails, the content of the event from the node event log is not readable (it contains the whole template)
#1357685    docs/bootsources.rst:: WARNING: document isn't included in any toctree
#1357714    Virsh power driver does not seem to work at all
#1358177    maas-region-admin requires root privileges [docs]
#1358337    [docs] MAAS documentation suggests to execute 'juju --sync-tools'
#1358829    IPMI power query fails when trying to commit config changes
#1358859    Commissioning output xml is hard to understand, would be nice to have yaml as an output option.
#1359169    MAAS should handle invalid consumers gracefully
#1359822    Gateway is missing in network definition
#1361897    exceptions in PeriodicImageDownloadService will cause it to stop running
#1361941    erlang upgrade makes maas angry
#1361967    NodePowerMonitorService has no tests
#1363913    Impossible to remove last MAC from network in UI
#1364228    Help text for node hostname is wrong
#1364591    MAAS Archive Mirror does not respect non-default port
#1364617    ipmipower returns a zero exit status when password invalid
#1364713    selenium test will not pass with new Firefox
#1365616    Non-admin access to cluster controller config
#1365619    DNS should be an optional field in the network definition
#1365722    NodeStateViolation when commissioning
#1365742    Logged OOPS ... NoSuchEventType: Event type with name=NODE_POWER_ON_FAILED could not be found.
#1365776    commissioning results view for a node also shows installation results
#1366812    Old boot resources are not being removed on clusters
#1367455    MAC address for node's IPMI is reversed looked up to yield IP address using case sensitive comparison
#1368398    Can't mark systems that 'Failed commissioning' as 'Broken'
#1368916    No resources found in Simplestreams repository
#1370860    Node power monitor doesn't cope with power template answers other than "on" or "off"
#1370887    No event is registered on a node for when the power monitor sees a problem
#1371663    Node page Javascript crashes when there is no lshw output to display yet
#1371763    Need to use RPC for validating license key.
#1372974    No "installation complete" event
#1373272    "No boot images are available.…" message doesn't disappear when images are imported
#1373580    [SRU] Glen m700 cartridge list as ARM64/generic after enlist
#1373723    Releasing a node without power parameters ends up in not being able to release a node
#1373727    PXE node event logs provide too much info
#1373900    New install of MAAS can't download boot images
#1374153    Stuck in "power controller problem"
#1374321    Internal server error when attempting to perform an action when the cluster is down
#1375360    Automatic population of managed networks for eth1 and beyond
#1375427    Need to remove references to older import images button
#1375647    'static-ipaddresses' capability in 1.6 not documented.
#1375681    "Importing images . . .​" message on the image page never disappears
#1375953    bootsourcecache is not refreshed when sources change
#1376016    MAAS lacks a setting for the Simple Streams Image repository location
#1376481    Wrong error messages in UI
#1376620    maas-url config question doesn't make clear that localhost won't do
#1376990    Elusive JavaScript lint
#1378366    When there are no images, clusters should show that there
#1378527    Images UI doesn't handle HWE images
#1378643    Periodic test failure for compose_curtin_network_preseed_for
#1378837    "Abort operation" action name is vague and misleading
#1378910    Call the install log 'install log' rather than 'curtin log'
#1379401    Race in EventManager.register_event_and_event_type
#1379816    disable_ipv4 has a default setting on the cluster, but it's not visible
#1380470    Event log says node was allocated but doesn't say to *whom*
#1380805    uprade from 1.5.4 to 1.7 overwrote my cluster name
#1381007    "Acquire and start node" button appears on node page for admins who don't own an allocated but unstarted node
#1381213    mark_fixed should clear the osystem and distro_series fields
#1381747    APIRPCErrorsMiddleware isn't installed
#1381796    license_key is not given in the curtin_userdata preseed for Windows
#1172773    Web UI has no indication of image download status.
#1233158    no way to get power parameters in api
#1319854    `maas login` tells you you're logged in successfully when you're not
#1351451    Impossible to release a BROKEN node via the API.
#1361040    Weird log message: "Power state has changed from unknown to connection timeout."
#1366170    Node Event log doesn't currently display anything apart from power on/off
#1368480    Need API to gather image metadata across all of MAAS
#1370306    commissioning output XML and YAML tabs are not vertical
#1371122    WindowsBootMethod request pxeconfig from API for every file
#1376030    Unable to get RPC connection for cluster 'maas' <-- 'maas' is the DNS zone name
#1378358    Missing images warning should contain a link to images page
#1281406    Disk/memory space on Node edit page have no units
#1299231    MAAS DHCP/DNS can't manage more than a /16 network
#1357381    maas-region-admin createadmin shows error if not params given
#1357686    Caching in get_worker_user() looks like premature optimisation
#1358852    Tons of Linking <mac address> to <cluster interface> spam in log
#1359178    Docs - U1 still listed for uploading data
#1359947    Spelling Errors/Inconsistencies with MAAS Documentation
#1365396    UI: top link to “<name> MAAS” only appears on some pages
#1365591    "Start node" UI button does not allocate node before starting in 1.7
#1365603    No "stop node" button on the page of a node with status "failed deployment"
#1371658    Wasted space in the "Discovery data" section of the node page
#1376393    powerkvm boot loader installs even when not needed
#1376956    commissioning results page with YAML/XML output tabs are not centered on page.
#1287224    MAAS random generated hostnames are not pronounceable
#1348364    non-maas managed subnets cannot query maas DNS
#1381543    Disabling Disk Erasing with node in 'Failed Erasing' state leads to Invalid transition: Failed disk erasing -> Ready.

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
#1332596    AddrFormatError: failed to detect a valid IP address from None execu
ting upload_dhcp_leases task
#1250370    "sudo maas-import-ephemerals" steps on ~/.gnupg/pubring.gpg
#1250435    CNAME record leaks into juju's private-address, breaks host based ac
cess control
#1305758    Import fails while writing maas.meta: No such file or directory
#1308292    Unhelpful error when re-enlisting a previously enlisted node
#1309601    maas-enlist prints "successfully enlisted" even when enlistment fail
s.
#1309729    Fast path installer is not the default
#1310844    find_ip_via_arp() results in unpredictable, and in some cases, incor
rect IP addresses
#1310846    amt template gives up way too easily
#1312863    MAAS fails to detect SuperMicro-based server's power type
#1314536    Copyright date in web UI is 2012
#1315160    no support for different operating systems
#1316627    API needed to allocate and return an extra IP for a container
#1323291    Can't re-commission a commissioning node
#1324268    maas-cli 'nodes list' or 'node read <system_id>' doesn't display the
 osystem or distro_series node fields
#1325093    install centos using curtin
#1325927    YUI.Array.each not working as expected
#1328656    MAAS sends multiple stop_dhcp_server tasks even though there's no dh
cp server running.
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

