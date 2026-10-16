# Activate MAAS hardening

This guide shows you how to activate security hardening on MAAS region controllers, configure the prerequisites it checks, and confirm that the controllers are compliant.

On a host in FIPS mode, hardening is already active. Skip to [Configure the hardening prerequisites](#configure-the-hardening-prerequisites).

For rack controllers, see [Harden a rack controller](/how-to-guides/harden-a-rack-controller.md).

## Before you begin

You need:

- MAAS 3.7.4 or later, installed as a snap.
- `sudo` access to every region controller.
- A TLS certificate and private key for the MAAS API, in PEM format. The certificate must cover the MAAS URL. For high availability, it must cover every region controller.
- If PostgreSQL runs on a different host: the CA certificate that signed the PostgreSQL server certificate, and TLS enabled on the PostgreSQL server.
- The IP addresses on which each region controller should serve DNS and internal HTTP.

Place certificate and key files in `/var/snap/maas/common/`, where the MAAS snap can read them.

## Activate hardening

1. Turn hardening on. This setting is stored in the MAAS database and applies to every region controller:

   ```bash
   sudo maas config-hardening enable
   ```

   The command prints `Hardening enabled (hardening_enabled=on).`

2. Restart MAAS on each region controller:

   ```bash
   sudo snap restart maas
   ```

MAAS now validates its prerequisites on each start. Any missing prerequisite appears as an error notification for administrators.

## Configure the hardening prerequisites

To see what is missing on a controller, run:

```bash
sudo maas config-hardening validate
```

Complete the following sections as needed. Where you run each one depends on where MAAS stores the setting:

| Section | Run it |
|---|---|
| Serve the API over TLS | Once for the deployment. MAAS stores the certificate and key in its database. |
| Set bind addresses | On every region controller. Each controller keeps its own values. |
| Verify the PostgreSQL server certificate | On every region controller. |
| Set Diffie-Hellman parameters | On every region controller. |

To check where a single setting is stored, run `sudo maas config-hardening get <key>`. The output is `<key> [<store>] = <value>`, where the store is `config` for a setting shared through the database, or `conf` for one that belongs to the controller you are logged in to.

### Serve the API over TLS

Enable TLS with your certificate and key:

```bash
sudo maas config-tls enable \
  /var/snap/maas/common/maas.key \
  /var/snap/maas/common/maas.crt \
  --cacert /var/snap/maas/common/ca.pem \
  --port 5443
```

Omit `--cacert` if the certificate is self-signed. After TLS is enabled, the web UI and API are available only over HTTPS. For more TLS options, see [Use TLS termination](/how-to-guides/enhance-maas-security.md#use-tls-termination-maas-33).

On a FIPS host, the certificate must use an RSA key of at least 2048 bits or an ECDSA key, and be signed with SHA-256 or stronger.

### Set bind addresses

Under hardening, no MAAS service may listen on all interfaces. Most services derive a specific address from the MAAS URL automatically. Two do not, and you must set them:

```bash
sudo maas config-hardening set api_int_bind <region-ip>
sudo maas config-hardening set dns_bind <dns-ip-1>,<dns-ip-2>
```

- `api_int_bind` is the internal HTTP listener that rack controllers use when TLS is enabled.
- `dns_bind` must include an address on every subnet where MAAS provides DNS. You can mix IPv4 and IPv6 addresses.

To pin any other service to a specific interface, set its key explicitly. For example:

```bash
sudo maas config-hardening set api_bind 10.0.0.5,fd00::5
```

If you pin `temporal_bind` to an address other than the MAAS URL host, also set `temporal_server` on each rack controller. See [Point MAAS Agent at Temporal](/how-to-guides/harden-a-rack-controller.md#point-maas-agent-at-temporal).

For the full list of keys and their defaults, see [Bind addresses](/reference/configuration-guides/security-hardening.md#bind-addresses).

### Verify the PostgreSQL server certificate

Skip this section if MAAS connects to PostgreSQL through a local Unix socket. TLS does not apply to socket connections.

1. Confirm that the PostgreSQL server certificate carries a Subject Alternative Name (SAN) for every host name or IP address that MAAS uses to reach the database:

   ```bash
   openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"
   ```

   Expected output:

   ```text
   X509v3 Subject Alternative Name:
       DNS:db.example.com, IP Address:10.0.0.9
   ```

   Empty output means the certificate has no SANs. Reissue it with SANs before you continue. MAAS rejects a certificate that relies on its Common Name field, under both `verify-ca` and `verify-full`. See [PostgreSQL server certificate requirements](/reference/configuration-guides/security-hardening.md#postgresql-server-certificate-requirements).

2. Copy the CA certificate that signed the PostgreSQL server certificate to the controller, then point MAAS at it:

   ```bash
   sudo maas config-hardening set database_sslrootcert /var/snap/maas/common/db-ca.pem
   ```

3. Require certificate verification:

   ```bash
   sudo maas config-hardening set database_sslmode verify-full
   ```

   `verify-full` checks the certificate chain and the host name. `verify-ca` checks the chain only. Both modes require SANs.

4. If the certificate was issued by a private CA and you do not use client certificates, also install the CA certificate in the controller's system trust store:

   ```bash
   sudo cp /var/snap/maas/common/db-ca.pem /usr/local/share/ca-certificates/db-ca.crt
   sudo update-ca-certificates
   ```

   Without this, MAAS cannot verify a private certificate chain when no client certificate is configured.

5. If the PostgreSQL server requires client certificate authentication, also set the client certificate and key:

   ```bash
   sudo maas config-hardening set database_sslcert /var/snap/maas/common/db-client.pem
   sudo maas config-hardening set database_sslkey /var/snap/maas/common/db-client.key
   ```

### Set Diffie-Hellman parameters (optional)

MAAS does not require a Diffie-Hellman (DH) parameters file. If you provide one, it must be at least 2048 bits.

```bash
sudo openssl dhparam -out /var/snap/maas/common/dhparam.pem 2048
sudo maas config-hardening set api_tls_dhparam /var/snap/maas/common/dhparam.pem
```

### Apply the changes

Restart MAAS on each region controller you changed:

```bash
sudo snap restart maas
```

## Verify the configuration

1. Run validation on each region controller:

   ```bash
   sudo maas config-hardening validate
   ```

   A compliant controller prints:

   ```text
   OK: no hardening violations.
   ```

   If violations remain, see [Resolve hardening violations](/how-to-guides/resolve-hardening-violations.md).

2. Review the effective settings:

   ```bash
   sudo maas config-hardening list
   ```

   For a bind key that you left unset, the line ends with the address that MAAS derived, for example `(effective: 10.0.0.5)`.

3. Confirm that the web server returns hardening headers:

   ```bash
   curl -sI --cacert /var/snap/maas/common/ca.pem https://<maas-host>:5443/MAAS/r/ \
     | grep -iE 'content-security-policy|x-frame-options'
   ```

4. In the web UI, confirm that no hardening error notifications remain.

## Deactivate hardening

You can deactivate hardening only on hosts that are not in FIPS mode.

```bash
sudo maas config-hardening disable
sudo snap restart maas
```

To return to the default behavior, where hardening follows the host FIPS state, set the value to `auto`:

```bash
sudo maas config-hardening set hardening_enabled auto
sudo snap restart maas
```

## Related topics

- [FIPS mode and security hardening](/explanation/fips.md)
- [Security hardening reference](/reference/configuration-guides/security-hardening.md)
- [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md)
