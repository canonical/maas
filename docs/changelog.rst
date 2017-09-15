=========
Changelog
=========

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
