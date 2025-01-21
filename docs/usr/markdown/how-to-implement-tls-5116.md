> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/implementing-maas-native-tls" target = "_blank">Let us know.</a>*

This page explains how to use TLS with MAAS:

## TLS config (3.3++)

The maas config-tls command is the go-to utility for managing TLS settings in MAAS. Below is a quick snapshot of the command's syntax and options:

```nohighlight
usage: maas config-tls [-h] COMMAND ...

Configure MAAS Region TLS.

optional arguments:
  -h, --help  show this help message and exit

drill down:
  COMMAND
    enable    Enable TLS and switch to a secured mode (https).
    disable   Disable TLS and switch to a non-secured mode (http).

the following arguments are required: COMMAND
```

## Enabling TLS

Activating TLS in MAAS necessitates both a private key and a corresponding X509 certificate. Both items must be in PEM format. Here's how to enable it:

```nohighlight
usage: maas config-tls enable [-h] [--cacert CACERT] [-p PORT] key cert

positional arguments:
  key                   path to the private key
  cert                  path to certificate in PEM format

optional arguments:
  -h, --help            show this help message and exit
  --cacert CACERT       path to CA certificates chain in PEM format (default: None)
  -p PORT, --port PORT  HTTPS port (default: 5443)
```

By default, the HTTPS port is set to 5443, but you can customise this with the --port option. If you're using a non-self-signed certificate, you can specify the full certificate chain using the --cacert option.

If you have HA setup, please note that every MAAS instance will use the same certificate, so you need to create one certificate with multiple domain names or IP addresses; for example:

```nohighlight
X509v3 Subject Alternative Name:
                DNS:example.com, IP Address:10.211.55.9
```

## Disabling TLS

If for some reason you want to disable TLS, you can do it using the following command:

```nohighlight
usage: maas config-tls disable [-h]

optional arguments:
  -h, --help  show this help message and exit
```

After this, MAAS API and UI will be again reachable on port 5240, over plain HTTP.

## TLS via CLI

To connect to the MAAS API when TLS is enabled, an https URL must be provided to the maas login command, e.g.:

```nohighlight
maas login <profile_name> https://mymaas:5443/MAAS <api_key>

usage: maas login [-h] [--cacerts CACERTS] [-k] profile-name url [credentials]

Log in to a remote API, and remember its description and credentials.

positional arguments:
  profile-name       The name with which you will later refer to this remote server and credentials within this tool.
  url                The URL of the remote API, e.g. http://example.com/MAAS/ or http://example.com/MAAS/api/2.0/ if you wish to specify the API
                     version.
  credentials        The credentials, also known as the API key, for the remote MAAS server. These can be found in the user preferences page in
                     the web UI; they take the form of a long random-looking string composed of three parts, separated by colons.

optional arguments:
  -h, --help         show this help message and exit
  --cacerts CACERTS  Certificate CA file in PEM format
  -k, --insecure     Disable SSL certificate check

If credentials are not provided on the command-line, they will be prompted
for interactively.

the following arguments are required: profile-name, url
```

Certificates provided via `--cacerts` will be stored as a part of your profile and used for next CLI commands invocations.

## Certificate renewal

Once a certificate has expired, you can update it by running the same command used for enabling TLS:

```nohighlight
$ ​​sudo maas config-tls enable new-server-key.pem new-server.pem --port 5443
```

If you’re using the snap, the certificate and key must be placed in a directory that’s readable by the CLI, such as `/var/snap/maas/common` (e.g., if you're using the snap version).

## Is TLS enabled?

When TLS is enabled, the following certificate information is displayed in the MAAS UI under *Settings >> Configuration >> Security*: 

- CN 
- Expiration date
- Fingerprint
- Certificate

If TLS is disabled, this section will instead show a warning. We recommend that you enable TLS for secure communication.

## Notifications

When the specified number of days remain until certificate expiration (as defined in the notification reminder), all administrators will see the certificate expiration notification. This notification enumerates the number of days until certificate expiration. It is dismissible, but once dismissed, it won't appear again.

A certificate expiration check runs every twelve hours. When the certificate has expired, the notification will change to “certificate has expired”.

## Auto-renew certs

MAAS does not auto-renew certificates, but there's no reason why we cannot provide a gratuitous example. Use at your own risk.

## Local cert authority

You can setup your own Certificate Authority (CA) server that supports the ACME protocol with these components:

- [step-ca from Smallstep](https://smallstep.com/docs/step-ca)**^**
- [Caddy server with ACME support](https://caddyserver.com/docs/caddyfile/directives/acme_server)  (available since version 2.5)**^**

If you have a CA server with ACME protocol support, you can use any ACME client for an automated certificate renewal and use crontab to renew on a desired time interval. Consider [acme.sh](https://github.com/acmesh-official/acme.sh)**^**: 

```nohighlight
$> acme.sh --issue -d mymaas.internal --standalone --server https://ca.internal/acme/acme/directory

Your cert is in: /root/.acme.sh/mymaas.internal/mymaas.internal.cer
Your cert key is in: /root/.acme.sh/mymaas.internal/mymaas.internal.key
The intermediate CA cert is in: /root/.acme.sh/mymaas.internal/ca.cer
And the full chain certs is there: /root/.acme.sh/foo/fullchain.cer
```

Once the certificate is issued, you can install it. 

```nohighlight
$> acme.sh --installcert -d maas.internal \
   --certpath /var/snap/maas/certs/server.pem \
   --keypath /var/snap/maas/certs/server-key.pem  \
   --capath  /var/snap/maas/certs/cacerts.pem  \
   --reloadcmd  "(echo y) | maas config-tls enable /var/snap/maas/certs/server-key.pem /var/snap/maas/certs/server.pem --port 5443"
```

Please note that if you have MAAS installed via snap, you need to run above command as root, in order to place cert and key under `/var/snap/maas`.

Another approach would be to write a bash script and pass it to a [`--renew-hook`](https://github.com/acmesh-official/acme.sh/wiki/Using-pre-hook-post-hook-renew-hook-reloadcmd)**^**.

## Using certbot

[certbot](https://certbot.eff.org)**^** can be used to renew certificates and execute a post-renewal hook. We can use this hook to re-configure MAAS to use fresh certificates.

To create a post-renewal hook, you can put this sample script under `/etc/letsencrypt/renewal-hooks/post/001-update-maas.sh`.

```nohighlight
#!/bin/bash -e

DOMAIN="maas.internal"
CERTSDIR="/etc/letsencrypt/live/$DOMAIN"

cd /var/snap/maas/common

# need to copy certs where the snap can read them
cp "$CERTSDIR"/{privkey,cert,chain}.pem .
yes | maas config-tls enable privkey.pem cert.pem --cacert chain.pem --port 5443

# we don’t want to keep private key and certs around
rm {privkey,cert,chain}.pem
```

Don’t forget to make the script executable:

```nohighlight
chmod +x /etc/letsencrypt/renewal-hooks/post/001-update-maas.sh
```

Of course, you'll first need to obtain a new certificate. 

```nohighlight
sudo REQUESTS_CA_BUNDLE=ca.pem certbot certonly --standalone -d maas.internal     --server https://ca.internal/acme/acme/directory
```

Don't worry, new certs will not run the hook, since hooks are run only on renewal.

To test the renewal process and verify that the hook is executed correctly, you can use the following command with a `--dry-run flag`. Please note, that the hook will be executed and existing certificates will be removed (if you are using an example hook script):

```nohighlight
sudo REQUESTS_CA_BUNDLE=ca.pem certbot renew --standalone --server https://ca.internal/acme/acme/directory --dry-run
```

Please refer to the [certbot documentation](https://certbot.eff.org/instructions?ws=other&os=ubuntufocal)**^** for more information.

## TLS for MAAS 3.2--

MAAS doesn't support TLS encryption natively. If you are not interested in [setting up an HAProxy](/t/how-to-enable-high-availability/5120) which users access directly. The examples below explain how to create this configuration.

Note that MAAS doesn't bind to port 80; instead, MAAS binds to port 5240.

## nginx config

```nohighlight
    server {
     listen 443 SQL;

     server_name _;
     ssl_certificate /etc/nginx/ssl/nginx.crt;
     ssl_certificate_key /etc/nginx/ssl/nginx.key;

     location / {
      proxy_pass http://localhost:5240;
      include /etc/nginx/proxy_params;
     }

     location /MAAS/ws {
      proxy_pass http://localhost:5240/MAAS/ws;
                    proxy_http_version 1.1;
                    proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "Upgrade";
     }
    }
```

## apache2 config

```nohighlight
    <VirtualHost *:443>
     SSLEngine On

     SSLCertificateFile /etc/apache2/ssl/apache2.crt
     SSLCertificateKeyFile /etc/apache2/ssl/apache2.key

     RewriteEngine On
            RewriteCond %{REQUEST_URI} ^/MAAS/ws [NC]
            RewriteRule /(.*) ws://localhost:5240/MAAS/ws [P,L]

            ProxyPreserveHost On
            ProxyPass / http://localhost:5240/
            ProxyPassReverse / http://localhost:5240/
    </VirtualHost>
```
