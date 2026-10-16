# Resolve hardening violations

This guide shows you how to find and fix each type of hardening violation that MAAS reports. For a summary of every code, see [Violation codes](/reference/configuration-guides/security-hardening.md#violation-codes).

## Find the violations

MAAS reports violations in three places:

- **Web UI**: error notifications for administrators. Bind address notifications start with the system ID of the affected controller.
- **Command line**: run validation on the controller:

  ```bash
  sudo maas config-hardening validate
  ```

- **Logs**: `hardening_violation` entries in the region controller log:

  ```bash
  journalctl -t maas-regiond | grep hardening_violation
  ```

Each violation shows a code, a message, a suggested resolution, and the configuration key involved. Find the code in the sections below.

## Add a TLS certificate

Codes: `MISSING_TLS_CERT`, `MISSING_TLS_KEY`

The public API is not served over TLS. Enable TLS with a certificate and its private key:

```bash
sudo maas config-tls enable /var/snap/maas/common/maas.key /var/snap/maas/common/maas.crt --port 5443
```

Add `--cacert <path>` if the certificate was issued by an intermediate or private CA.

## Replace a mismatched or invalid TLS certificate

Codes: `TLS_CERT_KEY_MISMATCH`, `TLS_CERT_PARSE_ERROR`

The stored certificate and key do not match, or one of them is not valid PEM.

1. Confirm that the key matches the certificate. The two commands must print the same value:

   ```bash
   openssl x509 -in maas.crt -noout -pubkey | openssl sha256
   openssl pkey -in maas.key -pubout | openssl sha256
   ```

2. Enable TLS again with the matching pair:

   ```bash
   sudo maas config-tls enable /var/snap/maas/common/maas.key /var/snap/maas/common/maas.crt --port 5443
   ```

## Replace a weak TLS certificate

Code: `WEAK_TLS_CERT_KEY`

This code appears only on a host in FIPS mode. The certificate uses a key or signature algorithm that FIPS does not allow.

1. Inspect the certificate:

   ```bash
   openssl x509 -in maas.crt -noout -text | grep -E 'Signature Algorithm|Public-Key|Public Key Algorithm'
   ```

   A compliant certificate uses an RSA key of at least 2048 bits or an ECDSA key, and a SHA-256 or stronger signature, such as `sha256WithRSAEncryption`.

2. Create a new key and certificate signing request:

   ```bash
   openssl req -new -newkey rsa:3072 -sha256 -nodes \
     -keyout /var/snap/maas/common/maas.key \
     -out maas.csr \
     -subj "/CN=<maas-host>" \
     -addext "subjectAltName=DNS:<maas-host>"
   ```

3. Have your certificate authority sign the request with SHA-256 or stronger.

4. Enable TLS with the new certificate:

   ```bash
   sudo maas config-tls enable /var/snap/maas/common/maas.key /var/snap/maas/common/maas.crt --port 5443
   ```

## Replace weak or invalid DH parameters

Codes: `WEAK_DH_PARAMS`, `DH_PARAMS_PARSE_ERROR`

The file set in `api_tls_dhparam` is under 2048 bits or is not a valid DH parameters file. Generate a new file and point MAAS at it:

```bash
sudo openssl dhparam -out /var/snap/maas/common/dhparam.pem 2048
sudo maas config-hardening set api_tls_dhparam /var/snap/maas/common/dhparam.pem
```

Alternatively, remove the setting. DH parameters are optional:

```bash
sudo maas config-hardening set api_tls_dhparam ""
```

## Fix a bind address

Codes: `WILDCARD_BIND_NOT_ALLOWED`, `INVALID_BIND_ADDRESS`

A service is set to listen on all interfaces, is unset with no automatic default, or has a value that is not an IP address. The `Config key:` line names the key.

Set the key to one or more specific IP addresses:

```bash
sudo maas config-hardening set <key> <ip-address>[,<ip-address>...]
```

Choose addresses as follows:

- `dns_bind`: an address on every subnet where MAAS provides DNS.
- `api_int_bind`: the address that rack controllers use to reach this region controller.
- Any other key: the interface that should serve the service. Alternatively, leave a derivable key empty so that MAAS derives an address from the MAAS URL:

  ```bash
  sudo maas config-hardening set <key> ""
  ```

To see which keys MAAS can derive, see [Bind addresses](/reference/configuration-guides/security-hardening.md#bind-addresses).

For a rack controller, see [Harden a rack controller](/how-to-guides/harden-a-rack-controller.md).

## Secure the database connection

Code: `INSECURE_DB_SSLMODE`

MAAS connects to PostgreSQL over TCP without verifying the server certificate.

1. Make sure the PostgreSQL server has TLS enabled.

2. Copy the CA certificate that signed the server certificate to the controller, then configure MAAS:

   ```bash
   sudo maas config-hardening set database_sslrootcert /var/snap/maas/common/db-ca.pem
   sudo maas config-hardening set database_sslmode verify-full
   ```

3. If the server requires client certificates, also set `database_sslcert` and `database_sslkey`. Otherwise, you do not need them.

### Database migrations fail with a certificate error

`verify-ca` and `verify-full` both require the PostgreSQL server certificate to carry a Subject Alternative Name (SAN) that matches `database_host`. With a certificate that has no SANs, `maas init` or a snap refresh fails during the database migration step:

```text
x509: certificate relies on legacy Common Name field, use SANs instead
```

1. Inspect the certificate:

   ```bash
   openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"
   ```

2. If the output is empty, reissue the certificate with a SAN for every name and address that MAAS uses in `database_host`.

If the error instead reports an unknown authority, MAAS could not verify your certificate chain. Install the CA certificate in the controller's system trust store:

```bash
sudo cp /var/snap/maas/common/db-ca.pem /usr/local/share/ca-certificates/db-ca.crt
sudo update-ca-certificates
```

See [PostgreSQL server certificate requirements](/reference/configuration-guides/security-hardening.md#postgresql-server-certificate-requirements).

## Resolve a FIPS mismatch

Code: `FIPS_CONFIG_STATUS_MISMATCH`

Another region controller has started in FIPS mode, but this host is not in FIPS mode. MAAS holds every controller to the same requirement, and you cannot clear the flag.

Enable FIPS mode on this host. See [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md).

## Confirm the fix

1. Restart MAAS on the controller:

   ```bash
   sudo snap restart maas
   ```

2. Run validation again:

   ```bash
   sudo maas config-hardening validate
   ```

   The output is `OK: no hardening violations.` when every issue is fixed.

The corresponding notifications disappear from the web UI after the restart.
