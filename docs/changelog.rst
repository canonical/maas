=========
Changelog
=========

MAAS 2.3.0
==========

Important announcements
-----------------------

**Machine network configuration now deferred to cloud-init.**
 Starting from MAAS 2.3, machine network configuration is now handled by
 cloud-init. In previous MAAS (and curtin) releases, the network configuration
 was performed by curtin during the installation process. In an effort to
 improve robustness, network configuration has now been consolidated in
 cloud-init. MAAS will continue to pass network configuration to curtin, which
 in turn, will delegate the configuration to cloud-init.

**Ephemeral images over HTTP**
 As part of the effort to reduce dependencies and improve reliability, MAAS
 ephemeral (network boot) images are no longer loaded using iSCSI (tgt). By
 default, the ephemeral images are now obtained using HTTP requests to the
 rack controller.

 After upgrading to MAAS 2.3, please ensure you have the latest available
 images. For more information please refer to the section below (New features
 & improvements).

**Advanced network configuration for CentOS & Windows**
 MAAS 2.3 now supports the ability to perform network configuration for CentOS
 and Windows. The network configuration is performed via cloud-init. MAAS
 CentOS images now use the latest available version of cloud-init that
 includes these features.

New features & improvements
---------------------------

**CentOS network configuration**
 MAAS can now perform machine network configuration for CentOS 6 and 7,
 providing networking feature parity with Ubuntu for those operating systems.
 The following can now be configured for MAAS deployed CentOS images:

 * Bonds, VLAN and bridge interfaces.
 * Static network configuration.

 Our thanks to the cloud-init team for improving the network configuration
 support for CentOS.

**Windows network configuration**
 MAAS can now configure NIC teaming (bonding) and VLAN interfaces for Windows
 deployments. This uses the native NetLBFO in Windows 2008+. Contact us for
 more information (https://maas.io/contact-us).

**Improved Hardware Testing**
 MAAS 2.3 introduces a new and improved hardware testing framework that
 significantly improves the granularity and provision of hardware testing
 feedback. These improvements include:

 * An improved testing framework that allows MAAS to run each component
   individually. This allows MAAS to run tests against storage devices for
   example, and capture results individually.
 * The ability to describe custom hardware tests with a YAML definition:
    * This provides MAAS with information about the tests themselves, such
      as script name, description, required packages, and other metadata about
      what information the script will gather. All of which will be used by
      MAAS to render in the UI.
    * Determines whether the test supports a parameter, such as storage,
      allowing the test to be run against individual storage devices.
    * Provides the ability to run tests in parallel by setting this in the
      YAML definition.
 * Capture performance metrics for tests that can provide it.
    * CPU performance tests now offer a new ‘7z’ test, providing metrics.
    * Storage performance tests now include a new ‘fio’ test providing metrics.
    * Storage test ‘badblocks’ has been improved to provide the number of
      badblocks found as a metric.
 * The ability to override a machine that has been marked ‘Failed testing’.
   This allows administrators to acknowledge that a machine is usable despite
   it having failed testing.

 Hardware testing improvements include the following UI changes:

 * Machine Listing page
    * Displays whether a test is pending, running or failed for the machine
      components (CPU, Memory or Storage.)
    * Displays whether a test not related to CPU, Memory or Storage has failed.
    * Displays a warning when the machine has been overridden and has failed
      tests, but is in a ‘Ready’ or ‘Deployed’ state.
 * Machine Details page
    * Summary tab - Provides hardware testing information about the different
      components (CPU, Memory, Storage).
    * Hardware Tests /Commission tab - Provides an improved view of the latest
      test run, its runtime as well as an improved view of previous results. It
      also adds more detailed information about specific tests, such as status,
      exit code, tags, runtime and logs/output (such as stdout and stderr).
    * Storage tab - Displays the status of specific disks, including whether a
      test is OK or failed after running hardware tests.

 For more information please refer to https://docs.ubuntu.com/maas/2.3/en/nodes-hw-testing.

**Network discovery & beaconing**
 In order to confirm network connectivity and aide with the discovery of VLANs,
 fabrics and subnets, MAAS 2.3 introduces network beaconing.

 MAAS now sends out encrypted beacons, facilitating network discovery and
 monitoring. Beacons are sent using IPv4 and IPv6 multicast (and unicast) to
 UDP port 5240. When registering a new controller, MAAS uses the information
 gathered from the beaconing protocol to ensure that newly registered
 interfaces on each controller are associated with existing known networks
 in MAAS. This aids MAAS by providing better information on determining the
 network topology.

 Using network beaconing, MAAS can better correlate which networks are
 connected to its controllers, even if interfaces on those controller are
 not configured with IP addresses. Future uses for beaconing could include
 validation of networks from commissioning nodes, MTU verification, and a
 better user experience for registering new controllers.

**Ephemeral Images over HTTP**
 Historically, MAAS has used ‘tgt’ to provide images over iSCSI for the
 ephemeral environments (e.g commissioning, deployment environment, rescue
 mode, etc). MAAS 2.3 changes the default behaviour by now providing images
 over HTTP.

 These images are now downloaded directly by the initrd. The change means
 that the initrd loaded on PXE will contact the rack controller to download
 the image to load in the ephemeral environment. Support for using 'tgt' is
 being phased out in MAAS 2.3, and will no longer be supported from MAAS 2.4
 onwards.

 For users who would like to continue to use & load their ephemeral images
 via ‘tgt’, they can disable http boot with the following command.

   maas <user> maas set-config name=http_boot value=False

**Upstream Proxy**
 MAAS 2.3 now enables an upstream HTTP proxy to be used while allowing MAAS
 deployed machines to continue to use the caching proxy for the repositories.
 Doing so provides greater flexibility for closed environments, including:

 * Enabling MAAS itself to use a corporate proxy while allowing machines to
   continue to use the MAAS proxy.
 * Allowing machines that don’t have access to a corporate proxy to gain
   network access using the MAAS proxy.

 Adding upstream proxy support also includes an improved configuration on
 the settings page. Please refer to Settings > Proxy for more details.

**UI Improvements**
 * Machines, Devices, Controllers
   MAAS 2.3 introduces an improved design for the machines, devices and
   controllers detail pages that include the following changes.

    * "Summary" tab now only provides information about the specific node
      (machine, device or controller), organised across cards.
    * "Configuration" has been introduced, which includes all editable
      settings for the specific node (machine, device or controllers).
    * "Logs" consolidates the commissioning output and the installation
      log output.

 * Other UI improvements
   Other UI improvements that have been made for MAAS 2.3 include:

    * Added DHCP status column on the ‘Subnet’s tab.
    * Added architecture filters
    * Updated VLAN and Space details page to no longer allow inline editing.
    * Updated VLAN page to include the IP ranges tables.
    * Zones page converted to AngularJS (away from YUI).
    * Added warnings when changing a Subnet’s mode (Unmanaged or Managed).
    * Renamed “Device Discovery” to “Network Discovery”.
    * Discovered devices where MAAS cannot determine the hostname now show
      the hostname as “unknown” and greyed out instead of using the MAC
      address manufacturer as the hostname.

**Rack Controller Deployment**
 MAAS 2.3 can now automatically deploy rack controllers when deploying a
 machine. This is done by providing cloud-init user data, and once a machine
 is deployed, cloud-init will install and configure the rack controller.
 Upon rack controller registration, MAAS will automatically detect the
 machine is now a rack controller and it will be transitioned automatically.
 To deploy a rack controller, users can do so via the API (or CLI), e.g:

   maas <user> machine deploy <system_id> install_rackd=True

 Please note that this features makes use of the MAAS snap to configure the
 rack controller on the deployed machine. Since snap store mirrors are not
 yet available, this will require the machine to have access to the internet
 to be able to install the MAAS snap.

**Controller Versions & Notifications**
 MAAS now surfaces the version of each running controller and notifies the
 users of any version mismatch between the region and rack controllers. This
 helps administrators identify mismatches when upgrading their MAAS on a
 multi-node MAAS cluster, such as within a HA setup.

**Improved DNS Reloading**
 This new release introduces various improvements to the DNS reload
 mechanism. This allows MAAS to be smarter about when to reload DNS after
 changes have been automatically detected or made.

**API Improvements**
 The machines API endpoint now provides more information on the configured
 storage and provides additional output that includes volume_groups, raids,
 cache_sets, and bcaches fields.

**Django 1.11 support**
 MAAS 2.3 now supports the latest Django LTS version, Django 1.11. This
 allows MAAS to work with the newer Django version in Ubuntu Artful, which
 serves as a preparation for the next Ubuntu LTS release.

  * Users running MAAS in Ubuntu Artful will use Django 1.11.
  * Users running MAAS in Ubuntu Xenial will continue to use Django 1.9.

Issues fixed in this release
----------------------------

 For issues fixed in MAAS 2.3, please refer to the following milestones:

 https://launchpad.net/maas/+milestone/2.3.0

 https://launchpad.net/maas/+milestone/2.3.0rc2

 https://launchpad.net/maas/+milestone/2.3.0rc1

 https://launchpad.net/maas/+milestone/2.3.0beta3

 https://launchpad.net/maas/+milestone/2.3.0beta2

 https://launchpad.net/maas/+milestone/2.3.0beta1

 https://launchpad.net/maas/+milestone/2.3.0alpha3

 https://launchpad.net/maas/+milestone/2.3.0alpha2

 https://launchpad.net/maas/+milestone/2.3.0alpha1


MAAS 2.3.0 (rc2)
================

For more information, visit: https://launchpad.net/maas/+milestone/2.3.0rc2

Issues fixed in this release
----------------------------

LP: #1730481    [2.3, HWTv2] When 'other' test fails, node listing incorrectly shows two icons

LP: #1723425    [2.3, HWTv2] Hardware tests do not provide start, current running or estimated run time

LP: #1728304    [2.3, HWTv2] Tests fail but transition to ready with "Unable to map parameters" when disks are missing

LP: #1731075    [2.3, HWTv2] Rogue test results when machine fails to commission for the first time

LP: #1721825    [2.3, HWTv2] Tests are not run in meaningful order

LP: #1731350    [2.3, HWTv2, UI] Aborting commissioning (+ testing) of a machine never commissioned before, leaves 'pending' icons in the UI

LP: #1721743    [2.3b2] Rack and region controller versions still not updated

LP: #1722646    [2.x] 2 out of 3 rack controller interfaces are missing links

LP: #1730474    [2.x] MAAS region startup sequence leads to race conditions

LP: #1662343    [2.1.3] Commissioning doesn't pick up new storage devices

LP: #1730485    [2.2+, HWT] badblocks fails with LVM

LP: #1730799    [2.3] Traceback when viewing controller commissioning scripts

LP: #1731292    [2.3, UI, regression] Hardware testing / commissioning table doesn't fit in a small screen but there's a lot of whitespace

LP: #1730703    [2.3, UI] Rename the section "Settings" of machine details to Configuration


MAAS 2.3.0 (rc1)
================

Issues fixed in this release
----------------------------

For more information, visit: https://launchpad.net/maas/+milestone/2.3.0rc1

LP: #1727576    [2.3, HWTv2] When specific tests timesout there's no log/output

LP: #1728300    [2.3, HWTv2] smartctl interval time checking is too short

LP: #1721887    [2.3, HWTv2] No way to override a machine that Failed Testing

LP: #1728302    [2.3, HWTv2, UI] Overall health status is redundant

LP: #1721827    [2.3, HWTv2] Logging when and why a machine failed testing (due to missing heartbeats/locked/hanged) not available in maas.log

LP: #1722665    [2.3, HWTv2] MAAS stores a limited amount of test results

LP: #1718779    [2.3] 00-maas-06-get-fruid-api-data fails to run on controller

LP: #1729857    [2.3, UI] Whitespace after checkbox on node listing page

LP: #1696122    [2.2] Failed to get virsh pod storage: cryptic message if no pools are defined

LP: #1716328    [2.2] VM creation with pod accepts the same hostname and push out the original VM

LP: #1718044    [2.2] Failed to process node status messages - twisted.internet.defer.QueueOverflow

LP: #1723944    [2.x, UI] Node auto-assigned address is not always shown while in rescue mode

LP: #1718776    [UI] Tooltips missing from the machines listing page

LP: #1724402    no output for failing test

LP: #1724627    00-maas-06-get-fruid-api-data fails relentlessly, causes commissioning to fail

LP: #1727962    Intermittent failure: TestDeviceHandler.test_list_num_queries_is_the_expected_number

LP: #1727360    Make partition size field optional in the API (CLI)

LP: #1418044    Avoid picking the wrong IP for MAAS_URL and DEFAULT_MAAS_URL

LP: #1729902    When commissioning don't show message that user has overridden testing


MAAS 2.3.0 (beta3)
==================

Issues fixed in this release
----------------------------

For more information, visit: https://launchpad.net/maas/+milestone/2.3.0beta3

LP: #1727551    [2.3] Commissioning shows results from script that no longer exists

LP: #1696485    [2.2, HA] MAAS dhcp does not offer up multiple domains to search

LP: #1696661    [2.2, HA] MAAS should offer multiple DNS servers in HA case

LP: #1724235    [2.3, HWTv2] Aborted test should not show as failure

LP: #1721824    [2.3, HWTv2] Overall health status is missing

LP: #1727547    [2.3, HWTv2] Aborting testing goes back into the incorrect state

LP: #1722848    [2.3, HWTv2] Memtester test is not robust

LP: #1727568    [2.3, HWTv2, regression] Hardware Tests tab does not show what tests are running

LP: #1721268    [2.3, UI, HWTv2] Metrics table (e.g. from fio test) is not padded to MAAS' standard

LP: #1721823    [2.3, UI, HWTv2] No way to surface a failed test that's non CPU, Mem, Storage in machine listing page

LP: #1721886    [2.3, UI, HWTv2] Hardware Test tab doesn't auto-update

LP: #1559353    [2.0a3] "Add Hardware > Chassis" cannot find off-subnet chassis BMCs

LP: #1705594    [2.2] rackd errors after fresh install

LP: #1718517    [2.3] Exceptions while processing commissioning output cause timeouts rather than being appropriately surfaced

LP: #1722406    [2.3] API allows "deploying" a machine that's already deployed

LP: #1724677    [2.x] [critical] TFTP back-end failed right after node repeatedly requests same file via tftp

LP: #1726474    [2.x] psycopg2.IntegrityError: update or delete on table "maasserver_node" violates foreign key constraint

LP: #1727073    [2.3] rackd — 12% connected to region controllers.

LP: #1722671    [2.3, pod] Unable to delete a machine or a pod if the pod no longer exists

LP: #1680819    [2.x, UI] Tooltips go off screen

LP: #1725908    [2.x] deleting user with static ip mappings throws 500

LP: #1726865    [snap,2.3beta3] maas init uses the default gateway in the default region URL

LP: #1724181    maas-cli missing dependencies: netifaces, tempita

LP: #1724904    Changing PXE lease in DHCP snippets global sections does not work


MAAS 2.3.0 (beta2)
==================

Issues fixed in this release
----------------------------

For more information, visit: https://launchpad.net/maas/+milestone/2.3.0beta2

LP: #1719015    $TTL in zone definition is not updated

LP: #1711760    [2.3] Workaround issue in 'resolvconf', where resolv.conf is not set in ephemeral envs (commissioning, testing, etc)

LP: #1721548    [2.3] Failure on controller refresh seem to be causing version to not get updated

LP: #1721108    [2.3, UI, HWTv2] Machine details cards - Don't show "see results" when no tests have been run on a machine

LP: #1721111    [2.3, UI, HWTv2] Machine details cards - Storage card doesn't match CPU/Memory one

LP: #1721524    [2.3, UI, HWTv2] When upgrading from older MAAS, Storage HW tests are not mapped to the disks

LP: #1721276    [2.3, UI, HWTv2] Hardware Test tab - Table alignment for the results doesn't align with titles

LP: #1721525    [2.3, UI, HWTv2] Storage card on machine details page missing red bar on top if there are failed tests

LP: #1719361    [2.3, UI, HWTv2] On machine listing page, remove success icons for components that passed the tests

LP: #1721105    [2.3, UI, HWTv2] Remove green success icon from Machine listing page

LP: #1721273    [2.3, UI, HWTv2] Storage section on Hardware Test tab does not describe each disk to match the design

LP: #1719353    [2.3a3, Machine listing] Improve the information presentation of the exact tasks MAAS is running when running hardware testing

LP: #1721113    [2.3, UI] Group physical block devices in the storage card off of their size and type


MAAS 2.3.0 (beta1)
==================

New Features & Improvements
---------------------------

**Hardware Testing**
 MAAS 2.3 beta 1 overhauls and improves the visibility of hardware tests
 results and information. This includes various changes across MAAS:

 * Machine Listing page
  * Surface progress and failures of hardware tests, actively showing when
    a test is pending, running, successful or failed.

 * Machine Details page
  * Summary tab - Provide hardware testing information about the different
    components (CPU, Memory, Storage)
  * Hardware Tests tab - Completely re-design of the Hardware Test tab. It
    now shows a list of test results per component. Adds the ability to view
    more details about the test itself.

**UI Improvements**
 MAAS 2.3 beta 1 introduces a new design for the node summary pages:

 * "Summary tab" now only shows information of the machine, in a complete new
   design.
 * "Settings tab" has been introduced. It now includes the ability to edit
   such node.
 * "Logs tab" now consolidates the commissioning output and the installation
   log output.
 * Add DHCP status column on the ‘Subnet’s tab.
 * Add architecture filters
 * Update VLAN and Space details page to no longer allow inline editing.
 * Update VLAN page to include the IP ranges tables.
 * Convert the Zones page into AngularJS (away from YUI).
 * Add warnings when changing a Subnet’s mode (Unmanaged or Managed).

**Rack Controller Deployment**
 MAAS beta 1 now adds the ability to deploy any machine with the rack
 controller, which is only available via the API.

**API Improvements**
 MAAS 2.3 beta 1 introduces API output for volume_groups, raids, cache_sets, and
 bcaches field to the machines endpoint.

Issues fixed in this release
----------------------------

For more information, visit: https://launchpad.net/maas/+milestone/2.3.0beta1

LP: #1711320    [2.3, UI] Can't 'Save changes' and 'Cancel' on machine/device details page

LP: #1696270    [2.3] Toggling Subnet from Managed to Unmanaged doesn't warn the user that behavior changes

LP: #1717287    maas-enlist doesn't work when provided with serverurl with IPv6 address

LP: #1718209    PXE configuration for dhcpv6 is wrong

LP: #1718270    [2.3] MAAS improperly determines the version of some installs

LP: #1718686    [2.3, master] Machine lists shows green checks on components even when no tests have been run

LP: #1507712    cli: maas logout causes KeyError for other profiles

LP: #1684085    [2.x, Accessibility] Inconsistent save states for fabric/subnet/vlan/space editing

LP: #1718294    [packaging] dpkg-reconfigure for region controller refers to an incorrect network topology assumption


MAAS 2.3.0 (alpha3)
===================

New Features & Improvements
---------------------------

**Hardware Testing (backend only)**
 MAAS has now introduced an improved hardware testing framework. This new
 framework allows for MAAS to test individual components of a single machine,
 as well as providing better feedback to the user for each of those tests.
 This feature has introduced:

  * Ability to define a custom testing script with a YAML definition - Each
    custom test can be defined with a YAML that will provide information
    about the test. This information includes the script name, description,
    required packages, and other metadata about what information the script
    will gather. This information can then be displayed in the UI.

  * Ability to pass parameters - Adds the ability to pass specific parameters
    to the scripts. For example, in upcoming beta releases, users would be
    able to select which disks they want to test if they don't want to test
    all disks.

  * Running test individually - Improves the way how hardware tests are run
    per component. This allows MAAS to run tests against any individual
    component (such a single disk).

  * Added additional performance tests:
    * Added a CPU performance test with 7z.
    * Added a storage performance test with fio.

 Please note that individual results for each of the components is currently
 only available over the API. Upcoming beta release will include various UI
 allow the user to better surface and interface with these new features.

**Rack Controller Deployment in Whitebox Switches (with the MAAS snap)**

 MAAS has now the ability to install and configure a MAAS rack controller
 once a machine has been deployed. As of today, this feature is only available
 when MAAS detects the machine is a whitebox switch. As such, all MAAS
 certified whitebox switches will be deployed with a MAAS rack controller.
 Currently certified switches include the Wedge 100 and the Wedge 40.

 Please note that this features makes use of the MAAS snap to configure the
 rack controller on the deployed machine. Since snap store mirrors are not
 yet available, this will require the machine to have access to the internet
 to be able to install the MAAS snap.

**Improved DNS Reloading**

 This new release introduces various improvements to the DNS reload mechanism.
 This allows MAAS to be smarter about when to reload DNS after changes have
 been automatically detected or made.

**UI - Controller Versions & Notifications**

 MAAS now surfaces the version of each running controller, and notifies the
 users of any version mismatch between the region and rack controllers. This
 helps administrators identify mismatches when upgrading their MAAS on a
 multi-node MAAS cluster, such as a HA setup.

**UI - Zones tab has been migrated to AngularJS**

 The Zones tab and related pages have now been transferred to AngularJS,
 moving away from using YUI. As of today, the only remaining section still
 requiring the use of YUI is some sections inside the settings page. Thanks
 to the Ubuntu Web Team for their contribution!

Issues fixed in this release
----------------------------

Issues fixed in this release are detailed at:

 https://launchpad.net/maas/+milestone/2.3.0alpha3


MAAS 2.3.0 (alpha2)
===================

Important announcements
-----------------------

**Advanced Network for CentOS & Windows**
 The MAAS team is happy to announce that MAAS 2.3 now supports the ability to
 perform network configuration for CentOS and Windows. The network
 configuration is performed via cloud-init. MAAS CentOS images now use the
 latest available version of cloud-init that includes these features.

New Features & Improvements
---------------------------

**CentOS Networking support**
 MAAS can now perform machine network configuration for CentOS, giving CentOS
 networking feature parity with Ubuntu. The following can now be configured for
 MAAS deployed CentOS images:

  * Static network configuration.
  * Bonds, VLAN and bridge interfaces.

 Thanks for the cloud-init team for improving the network configuration support
 for CentOS.

**Support for Windows Network configuration**
 MAAS can now configure NIC teaming (bonding) and VLAN interfaces for Windows
 deployments. This uses the native NetLBFO in Windows 2008+. Contact us for
 more information (https://maas.io/contact-us).

**Network Discovery & Beaconing**
 MAAS now sends out encrypted beacons to facilitate network discovery and
 monitoring. Beacons are sent using IPv4 and IPv6 multicast (and unicast) to
 UDP port 5240. When registering a new controller, MAAS uses the information
 gathered from the beaconing protocol to ensure that newly registered
 interfaces on each controller are associated with existing known networks in
 MAAS.

**UI improvements**
 Minor UI improvements have been made:

  * Renamed “Device Discovery” to “Network Discovery”.
  * Discovered devices where MAAS cannot determine the hostname now show the
    hostname as “unknown” and greyed out instead of using the MAC address
    manufacturer as the hostname.

Issues fixed in this release
----------------------------
Issues fixed in this release are detailed at:

 https://launchpad.net/maas/+milestone/2.3.0alpha1


2.3.0 (alpha1)
==============

Important annoucements
----------------------

**Machine Network configuration now deferred to cloud-init.**
 The machine network configuration is now deferred to cloud-init. In previous
 MAAS (and curtin) releases, the machine network configuration was performed
 by curtin during the installation process. In an effort to consolidate and
 improve robustness, network configuration has now been consolidated in
 cloud-init.

 Since MAAS 2.3 now depends on the latest version of curtin, the network
 configuration is now deferred to cloud-init. As such, while MAAS will
 continue to send the network configuration to curtin for backwards
 compatibility, curtin itself will defer the network configuration to
 cloud-init. Cloud-init will then perform such configuration on first boot
 after the installation process has completed.


New Features & Improvements
---------------------------

**Django 1.11 support**
 MAAS 2.3 now supports the latest Django LTS version, Django 1.11. This
 allows MAAS to work with the newer Django version in Ubuntu Artful, which
 serves as a preparation for the next Ubuntu LTS release.

  * Users running MAAS from the snap in any Ubuntu release will use Django 1.11
  * Users running MAAS in Ubuntu Artful will use Django 1.11.
  * Users running MAAS in Ubuntu Xenial will continue to use Django 1.9.

**Upstream Proxy**
 MAAS 2.3 now supports the ability to use an upstream proxy. Doing so, provides
 greater flexibility for closed environments provided that:

  * It allows MAAS itself to use the corporate proxy at the same time as
    allowing machines to continue to use the MAAS proxy.
  * It allows machines that don’t have access to the corporate proxy, to have
    access to other pieces of the infrastructure via MAAS’ proxy.

 Adding upstream proxy support als includes an improved configuration on the
 settings page. Please refer to Settings > Proxy for more details.

**Fabric deduplication and beaconing**
 MAAS is introducing a beaconing to improve the fabric creation and network
 infrastructure discovery. Beaconing is not yet turned by default in
 MAAS 2.3 Alpha 1, however, improvements to fabric discovery and creation have
 been made as part of this process. As of alpha 1 MAAS will no longer create
 empty fabrics.

**Ephemeral Images over HTTP**
 Historically, MAAS has used ‘tgt’ to provide images over iSCSI for the
 ephemeral environments (e.g commissioning, deployment environment, rescue
 mode, etc). MAAS 2.3 changes that behavior in favor of loading images via
 HTTP. This means that ‘tgt’ will be dropped as a dependency in following
 releases.

 MAAS 2.3 Alpha 1 includes this feature behind a feature flag. While the
 feature is enabled by default, users experiencing issues who would want
 to go back to use 'tgt' can do so by turning of the feature flag:

   maas <user> maas set-config name=http_boot value=False

Issues fixed in this release
----------------------------

Issues fixed in this release are detailed at:

 https://launchpad.net/maas/+milestone/2.3.0alpha1
