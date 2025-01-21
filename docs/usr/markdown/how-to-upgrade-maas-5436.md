> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/upgrading-maas" target = "_blank">Let us know.</a>*

Upgrade your MAAS setup using this page.

> Note that with versions 3.4.1 and 3.5, [PostgreSQL requirements have changed](/t/postgresql-deprecation-notices/8089).

## Upgrade to 3.5

> **Important note**: Review the new PostgreSQL requirements in the [installation requirements document](/t/reference-installation-requirements/6233) before installing MAAS.

**For a region+rack setup**, run this command:

```nohighlight
sudo snap refresh maas
```

Be sure to input your password. Your snap will update to the 3.5 channel, no MAAS re-initialisation required.

**For separate regions and racks**, update the rack nodes first with the above command, followed by the region nodes.

### Upgrading MAAS 2.9++ to 3.5

Before updating to MAAS 3.5, keep in mind that PostgreSQL 12 support has been phased out. You must [upgrade to PostgreSQL 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) beforehand.

If you're running MAAS versions 2.9 to 3.3, first check the Ubuntu version with `lsb_release -a`. Look for "22.04" as the release and "Jammy" as the codename.

Next, update Ubuntu, if needed. If you're on Ubuntu 20.04 LTS, move to 22.04 LTS using:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

You can safely follow the upgrade prompts, sticking to the default responses. When asked to reboot, restart the machine. When it reboots, double-check the Ubuntu version with `lsb_release -a`. The codename should now be "jammy."

### Upgrading MAAS 2.8-- to 3.5

Upgrading from MAAS 2.8 or lower? Proceed with caution; this is untested, so start by completely backing up your MAAS server.

Once that's done, add the PPA (ignore any errors here):

```nohighlight
sudo apt-add-repository ppa:maas/3.5
```

Perform the upgrade, using this command and sticking to default answers:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

Confirm the upgrade using `lsb_release -a` (look for "22.04" and "Jammy"), and verify the MAAS version as "3.5."

Failed? Restore from your backup and consider a fresh install on separate hardware.

## Upgrade to 3.4

Switching to MAAS 3.4? Here's a quick rundown on how to upgrade your snap installation. Before diving in, note that PostgreSQL 12 support is ending with MAAS 3.4 and won't be available in 3.5. We suggest [upgrading to PostgreSQL 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) first.

**For a region+rack setup**, run this command:

```nohighlight
sudo snap refresh maas
```

Be sure to input your password. Your snap will update to the 3.4 channel, no MAAS re-initialisation required.

**For separate regions and racks**, update the rack nodes first with the above command, followed by the region nodes.

### Upgrading MAAS 2.9++ to 3.4

Before updating to MAAS 3.4, keep in mind that PostgreSQL 12 support is being phased out. We recommend [upgrading to PostgreSQL 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) beforehand.

### MAAS versions 3.3 to 2.9

If you're running MAAS versions 2.9 to 3.3, first check the Ubuntu version with `lsb_release -a`. Look for "22.04" as the release and "Jammy" as the codename.

Next, update Ubuntu, if needed. If you're on Ubuntu 20.04 LTS, move to 22.04 LTS using:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

You can safely follow the upgrade prompts, sticking to the default responses. When asked to reboot, restart the machine. When it reboots, double-check the Ubuntu version with `lsb_release -a`. The codename should now be "jammy."

### Upgrading MAAS 2.8-- to 3.4

Upgrading from MAAS 2.8 or lower? Proceed with caution; this is untested, so start by completely backing up your MAAS server.

Once that's done, add the PPA (ignore any errors here):

```nohighlight
sudo apt-add-repository ppa:maas/3.4
```

Perform the upgrade, using this command and sticking to default answers:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

Confirm the upgrade using `lsb_release -a` (look for "22.04" and "Jammy"), and verify the MAAS version as "3.4."

Failed? Restore from your backup and consider a fresh install on separate hardware.

## Upgrade to 3.3

Note that support for PostgreSQL version 12 is deprecated for MAAS version 3.3, and will be discontinued in MAAS 3.5. We recommend [upgrading to PostgreSQL version 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) before installing MAAS 3.3.

To upgrade from a earlier snap version to the 3.3 snap (using a `region+rack` configuration), enter the following command:

```nohighlight
sudo snap refresh --channel=3.3 maas
```

Be sure to enter your account password. The snap will refresh from the 3.3 channel. You will not need to re-initialise MAAS.

If you are using a multi-node maas deployment with separate regions and racks, you should first run the upgrade command above for rack nodes, then for region nodes.

### Moving to MAAS 3.3 via Snap

First up, PostgreSQL 12 support is sun-setting with MAAS 3.3 and will be fully discontinued in version 3.5. Consider [upgrading to PostgreSQL version 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) before you proceed.

### For a single node with region+rack

Fire off the following command to refresh your snap:

```nohighlight
sudo snap refresh --channel=3.3 maas
```

Input your account password when prompted. The snap will automatically shift to the 3.3 channel, sparing you a MAAS reconfiguration.

### For clustered deployment

If you're operating a multi-node setup, apply the snap refresh first to rack nodes and then to the region nodes.

### Transitioning to MAAS 3.3: The essentials

Heads up, MAAS 3.3 doesn't play well with PostgreSQL 12. Plan on [shifting to PostgreSQL 14](/t/how-to-upgrade-postgresql-v12-to-v14/7203) as 3.5 will drop support entirely.

### If you're on MAAS 2.9 to 3.2

Verify your Ubuntu version by running `lsb_release -a`. Aim for 22.04 — aka "Jammy." If you're not on Jammy, transition from focal with:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

Proceed with caution: Accept default prompts during the upgrade; reboot post-upgrade; and run `lsb_release -a` again, post-reboot, to confirm a successful transition to 22.04.

### For versions 2.8 or lower

Proceed with extreme caution, as this jump is not thoroughly tested. Make a comprehensive backup. Don't skip this.

Once backed up, add the MAAS 3.3 PPA:

```nohighlight
sudo apt-add-repository ppa:maas/3.3
```

Next, initiate the upgrade; defaults are your friend here:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

When done, double-check the upgrade with `lsb_release -a`.

Finally, go to your MAAS UI and confirm version 3.3 at the bottom of the machine list. If all else fails, revert to your backup and consider a fresh 3.3 install on separate hardware.

### Upgrade MAAS 2.9++ to MAAS 3.3

Note that support for PostgreSQL version 12 is deprecated for MAAS version 3.3, and will be discontinued in MAAS 3.5. We recommend [upgrading to PostgreSQL version 14] before installing MAAS 3.3.

If you are running MAAS 3.2 through MAAS 2.9, you can upgrade directly to MAAS 3.3 with the following procedure:

1. Check whether the target system is running Ubuntu 22.04 LTS:

```nohighlight
lsb_release -a
```

The response should look something like this:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu xx.yy
Release:	xx.yy
Codename:	$RELEASE_NAME
```

The required “xx.yy” for MAAS 3.3 is “22.04,” code-named “Jammy”.

2. If you are currently running Ubuntu focal 20.04 LTS, Upgrade to Jammy 22.04 LTS:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

3. Accept the defaults for any questions asked by the upgrade script.

4. Reboot the machine when requested.

5. Check whether the upgrade was successful:

```nohighlight
lsb_release -a
```

A successful upgrade should respond with output similar to the following:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu 22.04(.nn) LTS
Release:	22.04
Codename:	jammy
```

### Upgrade MAAS 2.8-- to MAAS 3.3

If you’re upgrading from MAAS version 2.8 or lower to version 3.3, try the fooling procedure. While the this procedure should work, note that they it's untested. Use at your own risk. 

1. Back up your MAAS server completely with your favourite tools and media.

2. Add the MAAS 3.3 PPA to your repository list; ignore any apparent error messages:

```nohighlight
sudo apt-add-repository ppa:maas/3.3
```

3. Upgrade the release; answer any questions with the default values:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

4. Check whether your upgrade has been successful:

```nohighlight
lsb_release -a
```

If the upgrade was successful, this command should yield output similar to the following:

```nohighlight
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 22.04(.nn) LTS
Release:	22.04
Codename:	jammy
```

5. Check your running MAAS install (by looking at the information on the bottom of the machine list) to make sure you’re running the 3.3 release.

If this didn’t work, you will need to restore from the backup you made in step 1, and consider obtaining separate hardware to install MAAS 3.3.

## Upgrade to 3.2

To upgrade from a earlier snap version to the 3.2 snap (using a `region+rack` configuration):

1. Enter the following command:

```nohighlight
sudo snap refresh --channel=3.2 maas
```

2. Enter your account password.

The snap will refresh from the 3.2 channel; you will not need to re-initialise MAAS.

If you are using a multi-node maas deployment with separate regions and racks, you should first run the upgrade command above for rack nodes, then for region nodes.

### Upgrade MAAS 2.9++ to MAAS 3.2

To upgrade from MAAS 2.9 - 3.1 to MAAS 3.2, follow these steps:

1. Back up your MAAS server completely; the tools and media are left entirely to your discretion.

2. Add the MAAS 3.2 PPA to your repository list with the following command, ignoring any apparent error messages:

```nohighlight
sudo apt-add-repository ppa:maas/3.2
```

3. Run the MAAS upgrade:

```nohighlight
sudo apt update
sudo apt upgrade maas
```

4. Check your running MAAS install (by looking at the information on the bottom of the machine list) to make sure you're running the 3.2 release.

5. If this didn't work, you will need to restore from the backup you made in step 1, and consider obtaining separate hardware to install MAAS 3.2.

### Upgrade MAAS 2.8-- to MAAS 3.2

If you are running MAAS 2.8 or lower, you can't upgrade directly to MAAS 3.2: 

1. Make sure that the target system is running Ubuntu 20.04 LTS or higher:

```nohighlight
lsb_release -a
```

The response should look something like this:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu xx.yy
Release:	xx.yy
Codename:	$RELEASE_NAME
```

The minimum "xx.yy" required for MAAS 3.2 is "20.04," code-named "focal."

2. If you're not running focal, upgrade the release:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

3. Accept the defaults for any questions asked by the upgrade script.

4. Reboot the machine when requested.

5. Check whether the upgrade was successful:

```nohighlight
lsb_release -a
```

A successful upgrade should respond with output similar to the following:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04(.nn) LTS
Release:	20.04
Codename:	focal
```

## Upgrade to 3.1

To upgrade from a earlier snap version to the 3.1 snap (using a `region+rack` configuration):

1. Refresh the snap:

```nohighlight
sudo snap refresh --channel=3.1 maas
```
2. Enter your account password.

The snap will refresh from the 3.1 channel. You will not need to re-initialise MAAS.

If you are using a multi-node maas deployment with separate regions and racks, you should first run the upgrade command above for rack nodes, then for region nodes.

### Upgrade MAAS 2.9++ to MAAS 3.1

You can upgrade from MAAS 2.9 or MAAS 3.0 to MAAS 3.1:

1. Back up your MAAS server completely; the tools and media are left entirely to your discretion. Just be sure that you can definitely restore your previous configuration, should this procedure fail to work correctly.

2. Add the MAAS 3.1 PPA to your repository list with the following command, ignoring any apparent error messages:

```nohighlight
sudo apt-add-repository ppa:maas/3.1
```

3. Run the MAAS upgrade like this:

```nohighlight
sudo apt update
sudo apt upgrade maas
```

4. Check your running MAAS install (by looking at the information on the bottom of the machine list) to make sure you're running the 3.1 release.

5. If this didn't work, you will need to restore from the backup you made in step 1, and consider obtaining separate hardware to install MAAS 3.1.

### Upgrade MAAS 2.8-- to MAAS 3.1

If you are running MAAS 2.8 or lower, you can also upgrade directly to MAAS 3.1, but it requires some extra steps. You must first make sure that the target system is running Ubuntu 20.04 LTS or higher, by executing the following command:

```nohighlight
lsb_release -a
```

The response should look something like this:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu xx.yy
Release:	xx.yy
Codename:	$RELEASE_NAME
```

The minimum "xx.yy" required for MAAS 3.0 is "20.04," code-named "focal."

If you are currently running Ubuntu bionic 18.04 LTS, you can upgrade to focal 20.04 LTS with the following procedure:

1. Upgrade the release:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

2. Accept the defaults for any questions asked by the upgrade script.

3. Reboot the machine when requested.

4. Check whether the upgrade was successful:

```nohighlight
lsb_release -a
```

A successful upgrade should respond with output similar to the following:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04(.nn) LTS
Release:	20.04
Codename:	focal
```

## Upgrade to 3.0

To upgrade from a earlier snap version to the 3.0 snap (using a `region+rack` configuration), do the following:

1. Refresh the snap:

```nohighlight
sudo snap refresh --channel=3.0 maas
```

2. Enter your user password.

The snap will refresh from the 3.0 channel. You will not need to re-initialise MAAS.

If you are using a multi-node maas deployment with separate regions and racks, you should first run the upgrade command above for rack nodes, then for region nodes.

### Upgrade MAAS 2.9 to MAAS 3.0

To upgrade a working MAAS 2.9 instance to MAAS 3.0, follow these steps:

1. Back up your MAAS server completely; the tools and media are left entirely to your discretion.

2. Add the MAAS 3.0 PPA to your repository list:

```nohighlight
sudo apt-add-repository ppa:maas/3.0
```

3. Run the MAAS upgrade:

```nohighlight
sudo apt update
sudo apt upgrade maas
```

4. Check your running MAAS install (by looking at the information on the bottom of the machine list) to make sure you're running the 3.0 release.

5. If this didn't work, you will need to restore from the backup you made in step 1, and consider obtaining separate hardware to install MAAS 3.0.

### Upgrade MAAS 2.8-- to MAAS 3.0

If you are running MAAS 2.8, you can upgrade directly to MAAS 3.0 with the following procedure:

1. Check your release:

```nohighlight
lsb_release -a
```

The response should look something like this:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu xx.yy
Release:	xx.yy
Codename:	$RELEASE_NAME
```

The minimum "xx.yy" required for MAAS 3.0 is "20.04," code-named "focal."

If you are currently running Ubuntu bionic 18.04 LTS, you can upgrade to focal 20.04 LTS with the following procedure:

2. Upgrade the release:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

3. Accept the defaults for any questions asked by the upgrade script.

4. Reboot the machine when requested.

5. Check whether the upgrade was successful:

```nohighlight
lsb_release -a
```

A successful upgrade should respond with output similar to the following:

```nohighlight
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04(.nn) LTS
Release:	20.04
Codename:	focal
```

## Upgrade to 2.9

To upgrade from an earlier snap version to the 2.9 snap (using a `region+rack` configuration), do the following:

1. Refresh the snap:

```nohighlight
sudo snap refresh --channel=3.0/stable maas
```

2. Enter your user password.

The snap will refresh from the 3.0 channel. You will not need to re-initialise MAAS.

If you are using a multi-node maas deployment with separate regions and racks, you should first run the upgrade command above for rack nodes, then for region nodes.

### Upgrade MAAS 2.8-- to MAAS 2.9

MAAS 2.8 is the last supported version for Ubuntu 18.04 LTS. Newer versions of MAAS will not be back-portable, and consequently, to upgrade to MAAS 2.9 and all future versions, you will also need to upgrade the base operating system to Ubuntu 20.04. 

You do these two operations all at once, with the following procedure:

1. Add the 2.9 PPA to your repository path list:

```nohighlight
sudo add-apt-repository ppa:maas/2.9
```

2. Run the release upgrade:

```nohighlight
sudo do-release-upgrade --allow-third-party
```

3. Reboot your machine (requested by the upgrade script).

4. Check that your upgrade was successful:

```nohighlight
lsb_release -a
```

If the upgrade was successful, this command should yield output similar to the following:

```nohighlight
No LSB modules are available.
Distributor ID:	Ubuntu
Description:	Ubuntu 20.04.1 LTS
Release:	20.04
Codename:	focal
```

You have now upgraded to the Ubuntu 20.04 LTS base, and if you check your running MAAS install, you should see that the version has been updated to the latest stable 2.9 release.

## Some upgrade notes

When installing MAAS on Ubuntu, there can be conflicts between the existing NTP client, systemd-timesyncd, and the NTP client/server provided by MAAS, chrony. This can lead to time synchronisation issues, especially if MAAS is configured with different upstream NTP servers than the ones used by systemd-timesyncd. To avoid conflicts, users can manually disable and stop systemd-timesyncd using the following command:

```nohighlight
sudo systemctl disable --now systemd-timesyncd
```

Also note that support for PostgreSQL 12 has been deprecated in MAAS 3.3 and will be discontinued in MAAS 3.5.

## Special situations

This note is especially important for upgrading to MAAS 3.3, but may affect other upgrade paths as well.

If your MAAS environment includes multiple machines with identical IPMI BMC IP addresses and usernames but different passwords, please be aware of a potential migration issue when upgrading your MAAS instance.

**Background:**
In MAAS 3.3, a migration script (`0290_migrate_node_power_parameters`) moves the BMC password from `power_parameters` to a secure store. A unique database constraint (`power_type`, `md5(power_parameters::text)`) that previously allowed for identical BMC IPs and usernames with different passwords now fails because the `power_pass` field is removed during the migration, causing an upgrade failure.

**Steps to prevent upgrade failure:**

1. **Pre-upgrade check:** Before upgrading, ensure that each BMC IP address and username combination is unique. This is essential as the migration script enforces a unique constraint that may not align with your current setup.

2. **Identify affected machines:** Use the MAAS CLI to list all machines and their power parameters. Look for any entries with duplicate BMC IP and username combinations.

3. **Update machine configurations:** For any duplicates found, update the BMC details to have unique combinations. This may involve reconfiguring or decommissioning machines as needed.

4. **Proceed with upgrade:** Once all BMC details are unique, proceed with the upgrade to MAAS 3.3. Monitor the upgrade process for any errors related to power parameters.

**Understanding the unique constraint:**
The unique constraint was designed to prevent duplicate IPMI IP/Username/Password combinations. However, in practice, this constraint might not cover all scenarios, especially where configurations are automatically generated and share many common values.

**Future considerations:**
The development team is aware of this issue and is considering changes to improve the upgrade process, such as adjusting the unique constraint and improving API/UI level checks. Further updates will be provided in subsequent releases.
