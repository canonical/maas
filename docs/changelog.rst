=========
Changelog
=========

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

  * Users running MAAS from the snap in any Ubuntu release will use Django 1.11.
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
