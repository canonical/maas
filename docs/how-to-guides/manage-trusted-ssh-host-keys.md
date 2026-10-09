# Manage trusted SSH host keys

This guide shows you how to add, list, and remove trusted SSH host keys. On a host in FIPS mode, MAAS connects over SSH only to power devices whose host key is in the trusted list. This applies to SSH-based power drivers such as `hmc`, `mscm`, and `wedge`.

On a host that is not in FIPS mode, MAAS accepts unknown host keys, and you do not need this guide.

You can manage trusted host keys on their page in the web UI. This guide uses the MAAS v3 API, which suits scripting and bulk changes. The steps for collecting and verifying a device key apply to both methods.

## Before you begin

You need:

- A MAAS user with permission to edit global entities, such as an administrator.
- `curl` and `jq` on your workstation.
- The power address of each machine, exactly as it is configured in MAAS. MAAS matches trusted keys against this value.
- The CA certificate for the MAAS API, if it is not trusted by your workstation. The examples use `ca.pem`.

## Get an API token

The trusted host key endpoints are part of the MAAS v3 API. Log in and store the access token:

```bash
read -rsp "MAAS password: " MAAS_PASSWORD; echo
TOKEN=$(curl -s --cacert ca.pem -X POST "https://<maas-host>:5443/MAAS/a/v3/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=<your-username>" \
  --data-urlencode "password=${MAAS_PASSWORD}" | jq -r '.access_token')
```

Tokens are short-lived. If a request returns `401 Unauthorized`, log in again.

## Collect the device host key

From a trusted network location, read the host key of the power device:

```bash
ssh-keyscan -t rsa,ecdsa <power-address>
```

Each output line has three fields: the host, the key type, and the Base64-encoded key. For example:

```text
10.0.0.20 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBB...
```

In FIPS mode, MAAS negotiates only RSA and ECDSA P-256 host keys. Use an `ssh-rsa` key of at least 2048 bits, or an `ecdsa-sha2-nistp256` key.

Verify the fingerprint with the device administrator or the device console before you trust the key:

```bash
ssh-keyscan -t ecdsa <power-address> 2>/dev/null | ssh-keygen -lf -
```

## Add a trusted host key

Send the host, key type, and key to MAAS:

```bash
curl -s --cacert ca.pem -X POST "https://<maas-host>:5443/MAAS/a/v3/ssh-host-keys" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "10.0.0.20",
    "key_type": "ecdsa-sha2-nistp256",
    "public_key": "AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBB...",
    "label": "Rack 4 HMC"
  }'
```

The `host` value must match the machine's power address exactly. If the power address is a host name, use the same host name here.

On a FIPS host, MAAS rejects a key that does not meet the [FIPS key rules](/reference/configuration-guides/fips-mode.md#public-ssh-keys).

## List trusted host keys

```bash
curl -s --cacert ca.pem "https://<maas-host>:5443/MAAS/a/v3/ssh-host-keys" \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | {id, host, key_type, label}'
```

## Replace a trusted host key

When a device's host key changes, for example after a firmware update, replace the stored key:

1. Get the current ETag of the entry:

   ```bash
   ETAG=$(curl -s --cacert ca.pem -D - -o /dev/null \
     "https://<maas-host>:5443/MAAS/a/v3/ssh-host-keys/<id>" \
     -H "Authorization: Bearer $TOKEN" | awk -F': ' 'tolower($1)=="etag" {print $2}' | tr -d '\r')
   ```

2. Send the new key:

   ```bash
   curl -s --cacert ca.pem -X PUT "https://<maas-host>:5443/MAAS/a/v3/ssh-host-keys/<id>" \
     -H "Authorization: Bearer $TOKEN" \
     -H "If-Match: $ETAG" \
     -H "Content-Type: application/json" \
     -d '{
       "host": "10.0.0.20",
       "key_type": "ecdsa-sha2-nistp256",
       "public_key": "<new-base64-key>",
       "label": "Rack 4 HMC"
     }'
   ```

## Remove a trusted host key

```bash
curl -s --cacert ca.pem -X DELETE "https://<maas-host>:5443/MAAS/a/v3/ssh-host-keys/<id>" \
  -H "Authorization: Bearer $TOKEN"
```

## Troubleshoot a rejected connection

If power actions fail for a machine with an SSH-based driver, search the controller logs for `fips_crypto_error`:

```bash
journalctl -t maas-rackd -t maas-agent | grep fips_crypto_error
```

| `operation` | Cause | Action |
|---|---|---|
| `ssh_host_key_verify` | The device key is not in the trusted list, or the `host` value does not match the power address. | Add the key, or correct the `host` value. |
| `ssh_negotiation` | The device does not offer a FIPS-approved cipher or MAC. | Update the device firmware or SSH configuration. See [Session algorithms](/reference/configuration-guides/fips-mode.md#session-algorithms). |

## Related topics

- [FIPS mode reference](/reference/configuration-guides/fips-mode.md#ssh)
- [Enable FIPS mode on a MAAS controller](/how-to-guides/enable-fips-mode-on-a-controller.md)
