> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/what-is-new-with-maas-2-9" target = "_blank">Let us know.</a>*

## MAAS 2.9.2

We have released MAAS 2.9.2, which contains two new features, and some notable [bug fixes](https://launchpad.net/maas/+milestone/2.9.2)**^**. The two new features are:

- Proxmox driver: A driver has been added to MAAS 2.9.2 which interacts with the Proxmox API. Only one URL is needed, though a username and credentials are required. Credentials can be either a password or an API token. Note that if you use a token, you have to configure the permissions for the token. Newly-created Proxmox tokens don't assign any permissions by default, so you must add `power on`, `power off`, and `query power` permissions to the token before using it.

- Power driver Webhook:  A webhook was added to 2.9.2, which allows MAAS to interface with another web service that's running the power commands. This webhook is provided for interacting with objects that MAAS does not support, that is, the MAAS team supports the driver itself, but whatever is interfacing to the driver is not supported. This webhook as three URLs, one each for power on, power off, and power query. Optionally, this webhook also supports a power user and password or token (RFC 6717). This gives you a way to add your own power drivers without waiting for the driver to be added to MAAS. There is a [video tutorial](https://discourse.maas.io/t/maas-show-and-tell-proxmox-and-webhook/3754/3)**^** available on this new feature.

You can also find a [digest](#heading--bug-fixes-2-9-2) of the 2.9.2 bug fixes below.

## MAAS 2.9.1

Building upon MAAS 2.9, we have released 2.9.1, which contains some notable [bug fixes](https://launchpad.net/maas/+milestone/2.9.1)**^**. You can find a [digest](#heading--bug-fixes-2-9-1)**^** of these fixes below.

## MAAS 2.9

Following on from MAAS 2.8, we are happy to announce that MAAS 2.9 is now available.

### Focal Fossa default

Ubuntu 20.04 LTS (Focal Fossa) is now the default commissioning and deployment release for new MAAS installations. Machines deployed with Focal may now be registered as KVM hosts.

### OpenVswitch support

MAAS 2.9 allows you to create an OpenVswitch bridge type when creating a bridge.

### NUMA, SR-IOV, and hugepages

MAAS 2.9 adds extensive optimisation tools for using NUMA with virtual machines. You can now see how many VMs are allocated to each NUMA node, along with the allocations of cores, storage, and memory. You can quickly spot a VM running in multiple NUMA nodes, and optimise accordingly, with instant updates on pinning and allocations. You can also tell which VMs are currently running. Using the CLI, you can also pin nodes to specific cores, and configure hugepages for use by VMs.

Specifically, there are five new features available to support NUMA, SR-IOV, and hugepages:

- You can examine resources on a per-NUMA-node basis.
- You can pin nodes to specific cores (CLI only).
- You can see resources for VM hosts supporting NUMA nodes.
- You can see the alignment between VM host interfaces and NUMA nodes.
- You can configure and use hugepages (configurable in CLI only).

This functionality comes with an enhanced panel in the "KVM" details section:

<a href="https://discourse.maas.io/uploads/default/optimized/1X/57245bbbfe6d28e83c9b7fb30e52caf05714eb00_2_485x500.png" target = "_blank">![](upload://5qDhxTUUitJxRzlVYIhaxShZXS9.png)</a>

See the [VM hosting](/t/about-virtual-machines/6704) page for more details, and be sure to use the menu at the top of that page to select your desired build method and interface, so that you'll see the most relevant instructions.

### Improved performance

MAAS 2.9 includes changes to the machine batch size that the UI loads. Previously the UI loaded machines in batches of 25; it now pulls in 25 for the first call, then 100 at a time in subsequent batches.

You can see the results of the investigation in [this video podcast](https://discourse.maas.io/t/maas-show-and-tell-improving-ui-performance-for-large-maas-installs/3515)**^**.

### Release notifications

MAAS now includes new release notifications for users and administrators. These appear when a new release is available:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/c4f426b9f493a970efcc59c4d948d24fa5f12860.png)

Both regular and administrative users can snooze these notifications for two weeks at a time. Administrative users can opt out of new release notifications completely, preventing notifications for any user of that MAAS.

### IPMI configuration

MAAS now includes UI panels corresponding to the [IPMI power driver upgrades](#heading--ipmi-driver) mentioned earlier:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/433b28f5dd807caef7c7382f9a877607c2ea2dac.png)

This screen can be reached from `Settings | Configuration | Commissioning`.

### "Mark broken" descriptions

When marking a machine broken, a description can now be included:

![image](https://discourse-maas-io-uploads.s3.us-east-1.amazonaws.com/original/1X/69df48044c964d27caf59b60dcf5bf5210894c15.png?)

This description appears in that machine's row on the machine list.

### Curtin 20.2 support

A number of MAAS issues have actually been issues with an older version of Curtin. MAAS now includes Curtin 20.2, which fixes many of these issues, including [MAAS is changing my boot order!](https://discourse.maas.io/t/maas-is-changing-my-boot-order/3491)**^**.

### HTTP boot disabled

MAAS 2.9 disables HTTP boot. There are known issues with HTTP boot in MAAS, as well as known issues for HTTP boot with grub (e.g. https://bugs.launchpad.net/maas/+bug/1899581 **^**)  This shouldn’t affect machine boot, as machines will normally try PXE as a fallback boot method if HTTP boot fails. Be aware, though, that machine boot will fail if the BIOS is configured to boot only over HTTP; those machines need to be reconfigured to use PXE.

### New commissioning parameters

Four new parameters have been added for IPMI BMC configuration. These parameters will pull from the global defaults, eliminating the need to set the corresponding parameter in each instance.

- maas_auto_ipmi_user - The username for the MAAS created IPMI user. Default comes from the global configuration setting.
- maas_auto_ipmi_user_password - The password for the MAAS created IPMI user, by default a random password is generated.
- maas_auto_ipmi_k_g_bmc_key - he IPMI K_g pre-shared encryption key to be set when adding the MAAS IPMI user. Note not all IPMI BMCs support setting the k_g key, if MAAS is unable to set the key commissioning will fail. Default comes from the global configuration setting. If an IPMI K_g key is set but the key is rejected by the BMC MAAS will automatically retry without the K_g key. This works around an edge case where some BMCs will allow you to set an K_g key but don’t allow it to be used.
- maas_auto_ipmi_user_privilege_level - The IPMI user privilege level to use when adding the MAAS IPMI user. Possible options are USER, OPERATOR, or ADMIN. Default comes from the global configuration setting.

Note that MAAS will not capture the BMC MAC address when detecting IPMI BMCs.

### New IPMI options

Two new global IPMI configuration options have been added:

- maas_auto_ipmi_k_g_bmc_key - sets a global default IPMI BMC key.
- maas_auto_ipmi_user_privilege_level - sets a global default IPMI BMC user privilege level.
    
### IPMI config via UI

You may now set the global configuration options `maas_auto_ipmi_user`, `maas_auto_ipmi_k_g_bmc_key`, and `maas_auto_ipmi_user_privilege_level` on the "Settings" page in the UI under "Commissioning."

### New maas.power command

Available in all MAAS 2.9 releases is the new `maas.power` CLI command. This command interfaces directly with the supported MAAS power drivers. This command can be used to control the power on a machine before it has been added to MAAS, for all maas supported power drivers. You can get power status, turn machines on or off, and cycle power. The `maas.power --help` shows usage details, including syntax for naming each power type (consistent with other MAAS CLI commands).

### IPMI BMC improvements

This release adds two improvements to IPMI BMC detection capability:

- The IPMI cipher suite ID will now be automatically detected. MAAS tries to find the most secure cipher suite available. Preference order is 17, 3, 8, 12. If detection fails MAAS will fall back to using freeipmi-tool default, 3, which is what previous versions of MAAS use.
- The IPMI K_g BMC key will now be automatically detected if previously set. 

### RAD

This release features Reader Adaptive Documentation, which allows you to adapt individual pages to your install method (Snap vs. Deb), version (2.7/2.8/2.9), and preferred interface (CLI/UI). 

### Offline documentation

This release will include offline documentation for those users whose MAAS installations reside behind firewalls, unable to access the online documentation.

### BMC improvements

Three substantial improvements to BMC usage have been released:

- IPMI, HP Moonshot, and Facebook Wedge BMC detection and configuration scripts have been migrated to the commissioning script `30-maas-01-bmc-config `.
- BMC detection and configuration are now logged to commissioning results.
- If BMC configuration is skipped a ScriptResult will log this result, and indicate which user chose to skip the configuration step.

#### IPMI power driver upgrades

Three new configuration options have been added to the IPMI power driver:

- K_g - The BMC Key of the IPMI device. Used to encrypt all traffic to and from the device during communication.
- Cipher Suite ID - The cipher suite to use when communicating with the IPMI BMC. Only 3, 8, 12, and 17 are available as only those enable ciphers for authentication, integrity, and confidentiality. Defaults to 3, freeipmi-tools default. See http://fish2.com/ipmi/bp.pdf **^** for more information.
- Privilege Level - The IPMI privilege level to use when communicating with the BMC. Defaults to OPERATOR.

See the [power management page](/t/reference-power-drivers/7882) for details.

### Enlistment improvements

Script flow and capabilities have been improved in three ways:

1. `maas-run-remote-scripts` can now enlist machines.
2. Enlistment `user_data` scripts have been removed.
3.  The metadata endpoints `http://<MAAS>:5240/<latest or 2012-03-01>/` and `http://<MAAS>:5240/<latest or 2012-03-01>/meta-data/` are now available anonymously for use during enlistment.

### Commissioning script upgrades

Seven major improvements were made to commissioning script flow and capabilities:

1. Commissioning scripts can now send BMC configuration data
2. Commissioning scripts can now be used to configure BMC data. 
3. The environment variable BMC_CONFIG_PATH is passed to serially run commissioning scripts. 
4. These scripts may write BMC power credentials to BMC_CONFIG_PATH in a YAML format where each key is the power parameter. 
5. If the commissioning script returns 0, it will be sent to MAAS. 
6. The first script to write BMC_CONFIG_PATH is the only script that may configure the BMC, allowing you to override MAAS's builtin BMC detection.
7. All builtin commissioning scripts have been migrated into the database.

### Commissioning script reordering

Commissioning scripts have been reordered and some are now set to run in parallel. You can now easily set a script to run before the builtin MAAS commissioning scripts. There are nine significant changes:

1. 00-maas-03-install-lldpd -> 20-maas-01-install-lldpd

2. 00-maas-05-dhcp-unconfigured-ifaces -> 20-maas-02-dhcp-unconfigured-ifaces

3. 99-maas-05-kernel-cmdline -> maas -kernel-cmdline

4. 00-maas-00-support-info -> maas-support-info(now runs in parallel)

5. 00-maas-01-lshw -> maas-lshw(now runs in parallel)

6. 00-maas-04-list-modaliases -> maas-list-modaliases(now runs in parallel)

7. 00-maas-06-get-fruid-api-data -> maas-get-fruid-api-data(now runs in parallel)

8. 00-maas-08-serial-ports -> maas-serial-ports(now runs in parallel)

9. 99-maas-01-capture-lldp -> maas-capture-lldp(now runs in parallel)

See the [How to read commissioning logs](how-to-read-commissioning-logs/5248) for more details on these changes.

### Commissioning is faster now

Four improvements have been made to speed up the commissioning process, mostly by running scripts in parallel (see above):


1. Commissioning should now take 60s.
2. Logging has been added to 20-maas-01-install-lldpd  (commissioning log output).
3. Logging added to 20-maas-02-dhcp-unconfigured-ifaces (commissioning log output).
4. `user_data` can now be input directly into the UI.

## Bug fixes

### Bugs fixed in 2.9.2 release

- In the MAAS UI, ARM servers based on the [Hi1620 ARM SoC appear as an "Unknown model"](https://bugs.launchpad.net/maas/+bug/1897946)**^**. A fix was added to [lxd-4.11]( https://discuss.linuxcontainers.org/t/lxd-4-11-has-been-released/10135)**^**, released 2021-02-05.

- Debian package installs of MAAS [reached an "impossible situation"](https://bugs.launchpad.net/maas/+bug/1910910)**^** trying to install the MAAS region controller. This is caused because of an unsupported move from the transitional MAAS PPA to the latest PPA. The workaround is to purge the MAAS packages (and the snap, if installed)**^**, and install clean with the latest PPA enabled, which will install the correct versions.

- CentOS/RHEL 7+ ship with an unsigned version of GRUB [which breaks UEFI secure boot](https://bugs.launchpad.net/curtin/+bug/1895067)**^**. This bug is believed to be fixed in curtin version 21.1, which is now supported by MAAS 2.9.2.

- Debug [could not be properly enabled for MAAS snap version 2.9.1](https://bugs.launchpad.net/maas/+bug/1914588)**^**. This has been remedied.

- The MAAS [Backup doc article](/t/how-to-back-up-maas/5096) [was not clearly written with respect to stopping critical services](https://bugs.launchpad.net/maas/+bug/1892998)**^**. The article has been reworked to make clear in what order steps should be performed so that services are not stopped before appropriate data has been retrieved for backup.

- Deselecting all architectures in the Ubuntu extra architectures repo [blocks all deployments](https://bugs.launchpad.net/maas/+bug/1894116)**^**. The default architectures have been changed to prevent this issue.

- MAAS does not allow [FQDNs to be used in place of IPs](https://bugs.launchpad.net/maas/+bug/1911825)**^** when a BMC extracts the address from the `power_address`. This incorrect behaviour was changed in 2.9.2.

- The Proxmox driver [uses a hard-coded port that cannot be customised](https://bugs.launchpad.net/maas/+bug/1914165)**^**. This port is now customisable in 2.9.2.

### Bugs fixed in 2.9.1 release

- It is now possible to [delete an LXD VM in an offline state](https://bugs.launchpad.net/maas/+bug/1908434)**^**.
- MAAS now handles multiple NUMA nodes even when there are [gaps in the numbering](https://bugs.launchpad.net/maas/+bug/1910473)**^**.
- A [snap install issue](https://bugs.launchpad.net/maas/+bug/1910909)**^** was fixed.
- The way MAAS handles [gateways WRT DHCP](https://bugs.launchpad.net/maas/+bug/1910909)**^** was adjusted.
- A majority of the document [headings have been converted to links](https://bugs.launchpad.net/maas/+bug/1900010)**^** for easy bookmarking.

### Bugs fixed in 2.9 release

- MAAS 2.9 includes a fix for [Bug #1894727: Admin uses cannot change other user's passwords via the UI](https://bugs.launchpad.net/maas/+bug/1894727)**^**.

## Known issues

### RAD LHS menu

There is a known issue with the Reader Adaptive Documentation left-hand-side menu (navigation), in that the menu links cannot currently be adapted to the RAD parameters. This means that selecting a different page in the LHS menu will take you the the RAD for the current recommended version. Every page that is different in RAD, though, should present you with a top menu, so that you can choose the RAD parameters matching your own preferences.

### Erroneous message about "missing migration"

When upgrading to any release above 2.8, using packages, you may receive a warning about missing migration(s) -- specifically something that looks like this:

```nohighlight
Setting up maas-common (2.8.3~rc1-8583-g.9ddc8051f-0ubuntu1~18.04.1) ...
Setting up maas-region-api (2.8.3~rc1-8583-g.9ddc8051f-0ubuntu1~18.04.1) ...
Setting up maas-region-controller (2.8.3~rc1-8583-g.9ddc8051f-0ubuntu1~18.04.1) ...
Operations to perform:
  Apply all migrations: auth, contenttypes, maasserver, metadataserver, piston3, sessions, sites
Running migrations:
  No migrations to apply.
  Your models have changes that are not yet reflected in a migration, and so won't be applied.
  Run 'manage.py makemigrations' to make new migrations, and then re-run 'manage.py migrate' to apply them.
```

This warning message has no effect on the installation or operation of MAAS, so it can be safely ignored.
