# Harden a MAAS test controller

In this tutorial, you will build a disposable MAAS controller, turn on security hardening, and work through the issues that MAAS reports until the controller is compliant. Along the way, you will see how MAAS reports problems, how the password policy works, and how a hardened controller responds to web requests.

The tutorial takes about 30 minutes. It does not require FIPS mode or an Ubuntu Pro subscription.

:::{warning}
Use a disposable virtual machine. Do not follow this tutorial on a production MAAS controller.
:::

## What you need

- A computer that can run [Multipass](https://multipass.run), with at least 4 GB of free memory and 20 GB of free disk space.
- An internet connection.

## Create a test machine

Install Multipass, then launch an Ubuntu virtual machine and open a shell in it:

```bash
sudo snap install multipass
multipass launch 24.04 --name maas-hardening --cpus 2 --memory 4G --disk 20G
multipass shell maas-hardening
```

Run every remaining command inside this shell.

Store the machine's IP address in a variable. You will use it several times:

```bash
MAAS_IP=$(hostname -I | awk '{print $1}')
echo $MAAS_IP
```

## Install MAAS

Install a test database and MAAS, then initialize MAAS as a combined region and rack controller:

```bash
sudo snap install maas-test-db
sudo snap install maas --channel=3.8/stable
sudo maas init region+rack \
  --database-uri maas-test-db:/// \
  --maas-url http://$MAAS_IP:5240/MAAS
```

The test database listens on a local Unix socket. Socket connections do not use TLS, so MAAS will not ask you to secure the database connection in this tutorial.

## Turn on hardening

Activate hardening, then restart MAAS so that every service picks up the change:

```bash
sudo maas config-hardening enable
sudo snap restart maas
```

You see:

```text
Hardening enabled (hardening_enabled=on).
```

MAAS is still running. Hardening never stops MAAS from starting. Instead, MAAS checks its prerequisites and reports anything that is missing.

## Meet the password policy

Try to create an administrator with a weak password:

```bash
sudo maas createadmin --username admin --email admin@example.com --password maas
```

The command fails. Its error message lists every rule the password breaks:

```text
Password must be at least 14 characters; Password must contain at least one uppercase letter; Password must contain at least one digit; Password must contain at least one special character (any non-alphanumeric character)
```

Now use a password that meets every rule. When prompted, enter a password of at least 14 characters that includes an uppercase letter, a digit, and a special character:

```bash
sudo maas createadmin --username admin --email admin@example.com
```

The administrator is created. Keep the password; you will need it to log in to the web UI.

## See what MAAS reports

Ask MAAS to check the controller:

```bash
sudo maas config-hardening validate
```

MAAS lists three violations:

```text
VIOLATIONS (3):
  [MISSING_TLS_CERT] TLS certificate is not configured
    Resolution: Run: maas config-tls enable <key> <cert>
    Config key: tls
  [WILDCARD_BIND_NOT_ALLOWED] api_int_bind is not configured; the service would bind to all interfaces, which is not allowed when hardening is active
    Resolution: Run: maas config-hardening set api_int_bind <specific-ip-address>
    Config key: api_int_bind
  [WILDCARD_BIND_NOT_ALLOWED] dns_bind is not configured; the service would bind to all interfaces, which is not allowed when hardening is active
    Resolution: Run: maas config-hardening set dns_bind <specific-ip-address>
    Config key: dns_bind
```

Each violation has a code, a message, and a suggested fix. The same violations appear as error notifications in the web UI. Open `http://<MAAS_IP>:5240/MAAS` in your browser and log in as `admin` to see them. Notice that the notifications have no dismiss button.

You will fix the violations one at a time.

## Serve the API over TLS

First, create a self-signed certificate for the test controller:

```bash
openssl req -x509 -newkey rsa:3072 -sha256 -days 30 -nodes \
  -keyout maas.key -out maas.crt \
  -subj "/CN=$MAAS_IP" -addext "subjectAltName=IP:$MAAS_IP"
```

Copy the files to a location that the MAAS snap can read:

```bash
sudo cp maas.key maas.crt /var/snap/maas/common/
```

Enable TLS on port 5443:

```bash
sudo maas config-tls enable \
  /var/snap/maas/common/maas.key /var/snap/maas/common/maas.crt \
  --port 5443 --yes
```

Run validation again:

```bash
sudo maas config-hardening validate
```

The `MISSING_TLS_CERT` violation is gone. Two remain.

## Choose where services listen

Most MAAS services work out a specific address from the MAAS URL. Two services do not, because they may need to serve several networks:

- `api_int_bind`: the plain HTTP listener that rack controllers use when TLS is on.
- `dns_bind`: the DNS server, which must listen on every subnet where MAAS provides DNS.

This test machine has one network, so use its address for both:

```bash
sudo maas config-hardening set api_int_bind $MAAS_IP
sudo maas config-hardening set dns_bind $MAAS_IP
```

Validate once more:

```bash
sudo maas config-hardening validate
```

You see:

```text
OK: no hardening violations.
```

## Apply the configuration

The services read their settings when they start. Restart MAAS:

```bash
sudo snap restart maas
```

Refresh the web UI at `https://<MAAS_IP>:5443/MAAS`. Your browser warns about the self-signed certificate; accept it for this test. The hardening notifications are gone.

## Look at the hardened web server

List the effective configuration:

```bash
sudo maas config-hardening list
```

Look at the `api_bind` line. You did not set it, but MAAS shows the addresses it derived from the MAAS URL after `effective:`.

Now look at the response headers that the web server sends:

```bash
curl -skI https://$MAAS_IP:5443/MAAS/r/ | grep -iE 'content-security-policy|x-frame-options|strict-transport'
```

You see a `Content-Security-Policy` header, `X-Frame-Options: DENY`, and a `Strict-Transport-Security` header.

Finally, send an `OPTIONS` request:

```bash
curl -sk --http1.1 -X OPTIONS https://$MAAS_IP:5443/MAAS/r/
echo "exit status: $?"
```

The server closes the connection without replying, and `curl` exits with status `52` (empty reply). A hardened controller refuses `OPTIONS` and `TRACE` requests.

## Clean up

Leave the shell and delete the virtual machine:

```bash
exit
multipass delete --purge maas-hardening
```

## What you learned

In this tutorial, you:

- Activated MAAS hardening on a host that is not in FIPS mode.
- Saw that MAAS keeps running and reports missing prerequisites as violations.
- Met the password policy that hardening enforces.
- Fixed each violation and confirmed the result with `maas config-hardening validate`.
- Observed the headers and request filtering of a hardened web server.

## Next steps

- Understand the design in [FIPS mode and security hardening](/explanation/fips.md).
- Harden a production controller with [Activate MAAS hardening](/how-to-guides/activate-maas-hardening.md).
- Look up every setting and code in the [Security hardening reference](/reference/configuration-guides/security-hardening.md).
