> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/troubleshooting-common-maas-issues" target = "_blank">Let us know.</a>*

## Overlapping subnets can break deployments

Ensure that your subnets don't overlap to avoid deployment failures. Check and delete any outdated or redundant subnets through the Web UI.

## Need to reconfigure server IP address

If you need to modify your MAAS server's IP, simply re-run the setup:

```nohighlight
sudo dpkg-reconfigure maas-region-controller
```

## Network booting IBM Power servers

IBM Power servers with OPAL firmware utilise Petitboot for PXE interactions. For smooth deployment, configure a specific NIC as the network boot device via Petitboot.

## Resolve DNS conflicts between LXD and MAAS

If both MAAS and LXD are managing DNS, disable LXD's DNS and DHCP:

```nohighlight
lxc network set $LXD_BRIDGE_NAME dns.mode=none
lxc network set $LXD_BRIDGE_NAME ipv4.dhcp=false
lxc network set $LXD_BRIDGE_NAME ipv6.dhcp=false
```

## Nodes hang on "Commissioning"

**Timing issues**: Make sure the hardware clocks on your nodes and MAAS server are synchronised.

**Network drivers**: Use Linux-compatible network adaptors if commissioning hangs due to driver issues.

Feel free to contribute additional issues and solutions.

## Command 'packer' not found

When you try to run `packer` or execute a `make` command, you may encounter an error message indicating that `packer` is not installed. The issue can be resolved by [referring to this section](/t/how-to-customise-images/5104).

## Error with `packer`:

```nohighlight
stormrider@neuromancer:~$ packer
Command 'packer' not found...
```

## Error with `make`:

```nohighlight
stormrider@neuromancer:~/mnt/Dropbox/src/git/packer-maas/ubuntu$ make
sudo: packer: command not found...
```

## No rule to make target ...OVMF_VARS.fd

Should you see an error like the one below, you've forgotten to [install a needed dependency](/t/how-to-customise-images/5104).

```nohighlight
make: *** No rule to make target '/usr/share/OVMF/OVMF_VARS.fd'...
```

## Failure to create QEMU driver

Encountering the following error means you're missing a dependency. Refer to [this section](/t/how-to-customise-images/5104) for resolution.

```nohighlight
Failed creating Qemu driver: exec: "qemu-img": executable file not found in $PATH
```

## Timeout changes not taking effect

If you've modified the session timeout settings in the MAAS web interface but don't see the changes, do the following:

1. Make sure you've got administrative access to the MAAS web interface for changing session timeout settings.
2. After altering the session timeout duration, don't forget to save the new settings.
3. Clear your browser's cache and cookies. They might be holding on to old settings. Restart your browser and try again.

## Users logged out before timeout expires

If users are getting logged out before the session timeout you've set, consider these checks:

1. Double-check the unit of time you've set for the session timeout (weeks, days, hours, minutes). A mistake in units can cause unexpected timeouts.
2. Inspect any server settings conflicting with MAAS that may cause premature session timeouts, like window manager logout settings in Ubuntu.
3. If you're using a load balancer or proxy, make sure it's not causing additional timeouts conflicting with MAAS.

## Can't set an infinite session timeout

You can't set an "infinite" session timeout in MAAS. The maximum allowed duration is 14 days. This limit strikes a balance between security and usability.

## Users are suddenly logged out

MAAS will auto-logoff users when the session timeout duration is reached. If this happens more often than desired, consider increasing the timeout value to prevent frequent "idle-time" logouts.

## Can't set different timeouts for user groups

MAAS only supports a global session timeout setting. While you can't customise this by user group, you could deploy separate MAAS instances with different configurations to achieve similar effects.

## Can't extend sessions beyond the timeout

The timeout duration resets every time there's activity from the user. To extend a session, simply refresh the page before the timeout period ends. This will reset the session timer.

## Django errors

Sometimes, you may face the following Django error:

```nohighlight
django.core.exceptions.ValidationError: ['Subarchitecture(<value>) must be generic when setting hwe_kernel.']
```

To solve this, try specifying a different commissioning kernel—perhaps upgrading from Xenial to Focal.

## Forgotten password

If you forget your MAAS admin password but have sudo privileges, you can reset it like so:

```nohighlight
sudo maas changepassword $PROFILE
```

Replace `$PROFILE` with the username.

## Missing Web UI

The default MAAS web UI is at `http://<hostname>:5240/MAAS/`. If it's unreachable:

- Verify Apache is running: `sudo /etc/init.d/apache2 status`.
- Validate the hostname or try `http://127.0.0.1:5240/MAAS/`.

## Backdoor image login

Ephemeral images boot nodes during MAAS activities. If you need emergency access, you can create a temporary backdoor in these images. This lets you log in to check logs and debug issues.

## Extract the cloud image

Download the appropriate image and extract its files:

```nohighlight
wget https://cloud-images.ubuntu.com/xenial/current/xenial-server-cloudimg-amd64-root.tar.gz
mkdir xenial
sudo tar -C xenial -xpSf xenial-server-cloudimg-amd64-root.tar.gz --numeric-owner --xattrs "--xattrs-include=*"
```

## Generate password hash

Create a SHA-512 hashed password:

```nohighlight
python3 -c 'import crypt; print(crypt.crypt("ubuntu", crypt.mksalt(crypt.METHOD_SHA512)))'
```

Modify the `xenial/etc/shadow` file to insert this hash.

## Rebuild squashfs image

Create a new SquashFS file with your changes:

```nohighlight
sudo mksquashfs xenial/ xenial-customized.squashfs -xattrs -comp xz
```

Replace the existing MAAS image with this customised one.

## Migrating snap installs

For snap-based MAAS in 'all' mode, you can migrate to a local PostgreSQL:

```nohighlight
sudo /snap/maas/current/helpers/migrate-vd Snapatabase
```

## Manual DB export

To manually move your MAAS database, run:

```nohighlight
export PGPASS=$(sudo awk -F':\\s+' '$1 == "database_pass" {print $2}' \
    /var/snap/maas/current/regiond.conf)
sudo pg_dump -U maas -h /var/snap/maas/common/postgres/sockets \
    -d maasdb -F t -f maasdb-dump.tar
```

Stop the MAAS snap (`sudo snap stop maas`) and create a new PostgreSQL user and database for MAAS on the destination machine.

This should cover various miscellaneous issues you may encounter while using MAAS. Feel free to contribute with your own experiences.

## Leaked admin API key

If MAAS hardware sync leaks your admin API key, you can:

- Rotate all admin tokens
- Re-deploy machines with hardware sync enabled

Or swap the token manually:

## Manually swap the MAAS admin API token

Query the database to identify machines with hardware sync enabled:

```nohighlight
select system_id 
from maasserver_node 
where enable_hw_sync = true;
```

Rotate API keys on any affected machines. To verify an API key belongs to an admin, perform this database query:

```nohighlight
select u.username, u.email 
from auth_user u
left join piston3_consumer c 
on u.id = c.user_id
where key = 'your-leaked-api-key';
```

To remove the leaked API key, log in to the MAAS UI and delete it. Then reconfigure your MAAS CLI and hardware sync as needed.