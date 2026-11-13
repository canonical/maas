# Harden a rack controller

This guide shows you how to activate security hardening on a MAAS rack controller and configure its bind addresses.

A rack controller reads its hardening setting from its own `rackd.conf` file, not from the MAAS database. Activating hardening on the region controllers does not activate it on rack controllers. A rack controller in FIPS mode activates hardening automatically.

## Before you begin

You need:

- `sudo` access to the rack controller.
- The IP addresses on which the rack controller should serve TFTP, DNS, and RPC. TFTP and DNS need an address on every subnet that the rack controller serves.

How you change the configuration depends on the snap mode:

| Snap mode | How to change rack settings |
|---|---|
| `rack` | `sudo maas config-hardening` with rack subcommands |
| `region+rack` | Edit `/var/snap/maas/current/rackd.conf` |

To check the mode, run `cat /var/snap/maas/common/snap_mode`.

## Rack-only controller

1. Activate hardening. Skip this step on a FIPS host:

   ```bash
   sudo maas config-hardening set hardening_enabled on
   ```

2. Set the bind keys that have no automatic default:

   ```bash
   sudo maas config-hardening set rpc_bind <rack-ip>
   sudo maas config-hardening set tftp_bind <subnet-1-ip>,<subnet-2-ip>
   sudo maas config-hardening set dns_bind <subnet-1-ip>,<subnet-2-ip>
   ```

   `rpc_bind` takes a single address. `tftp_bind` and `dns_bind` take a comma-separated list.

3. Optional: pin the services that otherwise derive an address from the MAAS URL:

   ```bash
   sudo maas config-hardening set api_bind <rack-ip>
   sudo maas config-hardening set syslog_bind <rack-ip>
   sudo maas config-hardening set http_proxy_bind <rack-ip>
   ```

4. Validate the configuration:

   ```bash
   sudo maas config-hardening validate
   ```

   A compliant rack controller prints `OK: no hardening violations.`

5. Restart MAAS to apply the changes:

   ```bash
   sudo snap restart maas
   ```

## Region and rack on the same host

On a `region+rack` host, `maas config-hardening` manages the region side only. Edit the rack side directly.

1. Open `/var/snap/maas/current/rackd.conf` with a text editor as root.

2. Add or update these keys:

   ```yaml
   hardening_enabled: "on"
   rpc_bind: 10.0.0.5
   tftp_bind:
     - 10.0.0.5
     - 10.0.1.5
   dns_bind:
     - 10.0.0.5
     - 10.0.1.5
   ```

   Quote `"on"`. Unquoted, YAML reads it as a Boolean.

3. Restart MAAS:

   ```bash
   sudo snap restart maas
   ```

The region validation command does not check `rackd.conf`.

## Point MAAS Agent at Temporal

MAAS Agent on the rack controller connects to Temporal on the region controllers. By default, it uses the host from the MAAS URL. If the region controllers bind Temporal to a different address, for example because you pinned `temporal_bind`, set `temporal_server` so that MAAS Agent can reach it.

1. Open `/var/snap/maas/current/rackd.conf` with a text editor as root.

2. Add or update the key:

   ```yaml
   temporal_server: 10.0.0.5
   ```

   Use the address or host name that the region controllers bind Temporal to.

3. Restart MAAS:

   ```bash
   sudo snap restart maas
   ```

Apply this setting on every rack controller, whether it runs in `rack` or `region+rack` mode. `maas config-hardening` does not manage this key.

## Check the rack controller regularly

Rack controllers do not post notifications to the region. Problems on a rack controller do not appear in the web UI. Include rack validation in your regular compliance checks:

```bash
sudo maas config-hardening validate
```

The command exits with status `1` when it finds a violation, so you can use it in scripts and monitoring.

## Related topics

- [Rack command and parameters](/reference/configuration-guides/security-hardening.md#rack-command)
- [Region and rack controllers](/explanation/fips.md#region-and-rack-controllers)
- [Activate MAAS hardening](/how-to-guides/activate-maas-hardening.md)
