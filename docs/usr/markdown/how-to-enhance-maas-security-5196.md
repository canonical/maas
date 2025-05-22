Enhance MAAS security along many different vectors.

## Use TLS termination (MAAS 3.3+)

Learn more about [TLS termination](https://maas.io/docs/ensuring-security-in-maas#p-13983-tls-termination).

### Configure TLS (3.3+)

Manage TLS settings in MAAS with `config-tls`. 

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

### Enable TLS

TLS requires both a private key and a corresponding X509 certificate, both in PEM format:

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

The default HTTPS port is 5443; customize this with the `--port` option. Specify the full certificate change (e.g. when using a non-self-signed certificate) using the `--cacert` option.

### Manage TLS with HA

High availability requires that every MAAS instance use the same certificate.  Create one certificate with multiple domain names or IP addresses, for example:

```nohighlight
X509v3 Subject Alternative Name:
                DNS:example.com, IP Address:10.211.55.9
```

### Disable TLS

When you disable TLS, MAAS API and UI will use HTTP over port 5240:

```nohighlight
usage: maas config-tls disable [-h]

optional arguments:
  -h, --help  show this help message and exit
```

### Check TLS status

Confirm TLS is active at *Settings* > *Configuration* > *Security*: 

- CN 
- Expiration date
- Fingerprint
- Certificate

This section of the UI will warn you if TLS is disabled.

### Login to the MAAS CLI with TLS

Login to the MAAS API with an https URL when using TLS:

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

If credentials are not provided on the command-line, they will be prompted for interactively.

the following arguments are required: profile-name, url
```

Certificates provided via `--cacerts` will be stored in your profile for future CLI commands.

### Renew certificates

Renew a certificate the same way you enable TLS:

```nohighlight
$ ​​sudo maas config-tls enable new-server-key.pem new-server.pem --port 5443
```

Place the certificate and key in an accessible directory, such as `/var/snap/maas/common` if you're using the MAAS snap.

### Set up a local cert authority

You can setup your own Certificate Authority (CA) server that supports the ACME protocol with these components:

- [step-ca from Smallstep](https://smallstep.com/docs/step-ca)
- [Caddy server with ACME support](https://caddyserver.com/docs/caddyfile/directives/acme_server)  (available since version 2.5)

If you have a CA server with ACME protocol support, you can use any ACME client for an automated certificate renewal and use crontab to renew on a desired time interval. For example, [acme.sh](https://GitHub.com/acmesh-official/acme.sh): 

```nohighlight
$> acme.sh --issue -d mymaas.internal --standalone --server https://ca.internal/acme/acme/directory

Your cert is in: /root/.acme.sh/mymaas.internal/mymaas.internal.cer
Your cert key is in: /root/.acme.sh/mymaas.internal/mymaas.internal.key
The intermediate CA cert is in: /root/.acme.sh/mymaas.internal/ca.cer
And the full chain certs is there: /root/.acme.sh/foo/fullchain.cer
```

Once the certificate is issued, you can install it:

```nohighlight
$> sudo acme.sh --installcert -d maas.internal \
   --certpath /var/snap/maas/certs/server.pem \
   --keypath /var/snap/maas/certs/server-key.pem  \
   --capath  /var/snap/maas/certs/cacerts.pem  \
   --reloadcmd  "(echo y) | maas config-tls enable /var/snap/maas/certs/server-key.pem /var/snap/maas/certs/server.pem --port 5443"
```

### Use certbot

[certbot](https://certbot.eff.org) can be used to renew certificates, using a post-renewal hook to update MAAS:


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

When obtaining a new certificate. 

```nohighlight
sudo REQUESTS_CA_BUNDLE=ca.pem certbot certonly --standalone -d maas.internal     --server https://ca.internal/acme/acme/directory
```

Note that hooks are run only on renewal.  You can test the process with a `--dry-run` flag:

```nohighlight
sudo REQUESTS_CA_BUNDLE=ca.pem certbot renew --standalone --server https://ca.internal/acme/acme/directory --dry-run
```

Refer to the [certbot documentation](https://certbot.eff.org/instructions?ws=other&os=ubuntufocal) for more information.

### Manage PEM files

Combine SSL certificate (`mysite.com.crt`) and key pair (`mysite.com.key`) into a single PEM file:

```nohighlight
cat mysite.com.crt mysite.com.key > mysite.com.pem
sudo cp mysite.com.pem /etc/ssl/private/
```

Include your root and intermediate CA certificates in the same PEM file, if required.

## Use TLS termination (3.2-)

MAAS versions 3.2 and below don't support native TLS encryption. If you are not interested in [setting up an HAProxy](https://maas.io/docs/how-to-enable-high-availability#p-9026-api-ha-with-haproxy), you can still enable TLS.

### Configure nginx

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

Note that MAAS binds to port 5240, not 80.

### Configure apache2

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

## Manage network ports

Regulate accessible network ports for stronger MAAS security. Consider configuring your [firewall](https://ubuntu.com/server/docs/security-firewall) to allow only the ports MAAS uses. Using the Ubuntu UncomplicatedFirewall:

```nohighlight
sudo ufw enable
sudo ufw default deny incoming
sudo ufw allow 5240
sudo ufw allow 5248
sudo ufw allow 5241:5247/tcp
sudo ufw allow 5241:5247/udp
sudo ufw allow 5250:5270/tcp
sudo ufw allow 5250:5270/udp
```

Your specifics may vary, so refer to the relevant firewall documentation and the required MAAS controller port settings.

See [MAAS network port reference table](https://maas.io/docs/configuration-reference#p-17901-controller-port-settings) for a complete active port listing.

## Deploy HAProxy

```nohighlight
sudo apt-get update
sudo apt-get install haproxy
```

Modify `/etc/haproxy/haproxy.cfg` to set the maximum number of concurrent connections in the global section:

```nohighlight
maxconn <number of concurrent connections>
```

Also configure temporary DHE key sizes:

```nohighlight
tune.ssl.default-dh-param 2048
```

In `defaults` (under `mode http`) add:

```nohighlight
option forwardfor
option http-server-close
```

Specify frontend and backend settings to manage connections:

```nohighlight
frontend maas
    bind *:443 ssl crt /etc/ssl/private/mysite.com.pem
    reqadd X-Forwarded-Proto:\ https
    retries 3
    option redispatch
    default_backend maas

backend maas
    timeout server 90s
    balance source
    hash-type consistent
    server localhost localhost:5240 check
    server maas-api-1 <ip-address-of-a-region-controller>:5240 check
    server maas-api-2 <ip-address-of-another-region-controller>:5240 check
```

Apply these changes by restarting HAProxy:

```nohighlight
sudo systemctl restart haproxy
```

Enable [HAProxy logging](https://www.digitalocean.com/community/tutorials/how-to-implement-ssl-termination-with-haproxy-on-ubuntu-14-04) if desired.  Alternatively, bypass SSL without HAProxy.

## Use logging

Use MAAS log files to find potential security issues.

See the [MAAS logging reference](https://maas.io/docs/maas-logging-reference) for detailed examples & log file locations.

## Manage users

Manage users carefully to maintain strong, proactive security.

### Add a user

UI**
*Settings* > *Users* > *Add user*> [Fill fields] > *Save*.

Check the appropriate box to grant administrative rights.

CLI**
```nohighlight
    maas $PROFILE users create username=$USERNAME \
    email=$EMAIL_ADDRESS password=$PASSWORD is_superuser=0
```

### Edit users

UI**
*[Select user]* > *Details* > *[Make changes]* > *Save*

### Manage SSH keys

UI**
*Settings* > *Users* > *[User]* > *Pencil* > *[Follow key import steps]*

CLI**
```nohighlight
    ubuntu@maas:~$ maas $PROFILE sshkeys create key="$(cat /home/ubuntu/.ssh/id_rsa.pub)"
```

### Manage API Keys

*Settings* > *Users* > *[User]* > *Pencil* > *API keys*

### Change passwords

*Settings* > *Users* > *[User]* > *Pencil* > [Follow instructions]

> *Note that administrators can change any user's password.  Learn more about [strong passwords](https://maas.io/docs/ensuring-security-in-maas#p-13983-strong-passwords).*

## Manage Vault

Learn more about [MAAS and Hashicorp Vault](https://maas.io/docs/ensuring-security-in-maas#p-13983-hashicorp-vault).

To ensure seamless integration between MAAS and Vault, you'll first need to obtain a `role_id` and `wrapped_token` through Vault's CLI. For detailed guidance, check [Hashicorp Vault's tutorial](https://learn.hashicorp.com/tutorials/vault/approle-best-practices?in=vault/auth-methods#approle-response-wrapping).

Here's an illustrative example on how to set up this integration using the `vault` CLI:

1. **Enable the `approle` engine**

```nohighlight
$ vault auth list
```
If `approle/` isn't mounted, enable it:

```nohighlight
$ vault auth enable approle
```

2. **Confirm or mount the KV v2 engine**

```nohighlight
$ vault secrets enable -path $SECRETS_MOUNT kv-v2
```

3. **Create a suitable policy**

```nohighlight
path "$SECRETS_MOUNT/metadata/$SECRETS_PATH/" {
	capabilities = ["list"]
}

path "$SECRETS_MOUNT/metadata/$SECRETS_PATH/*" {
	capabilities = ["read", "update", "delete", "list"]
}

path "$SECRETS_MOUNT/data/${SECRETS_PATH}/*" {
	capabilities = ["read", "create", "update", "delete"]
}
```
4. **Apply the policy in Vault**

```nohighlight
$ vault policy write $MAAS_POLICY $POLICY_FILE
```

5. **Associate each MAAS region controller with the policy**

```nohighlight
$ vault write auth/approle/role/$ROLE_NAME \
policies=$MAAS_POLICY token_ttl=5m
```
Fetch the role ID:

```nohighlight
$ vault read auth/approle/role/$ROLE_NAME/role-id
```

6. **Generate a secret ID for each role**

```nohighlight
$ vault write -wrap-ttl=5m auth/approle/role/$ROLE_NAME/secret-id
```

Post-setup, you can integrate MAAS with Vault using:

```nohighlight
sudo maas config-vault configure $URL $APPROLE_ID $WRAPPED_TOKEN $SECRETS_PATH --mount $SECRET_MOUNT
```

Complete the integration by migrating the secrets:

```nohighlight
$ sudo maas config-vault migrate
```
For detailed information, it's recommended to refer to the [Vault documentation](https://developer.hashicorp.com/vault/docs) and consider [Vault certification](https://developer.hashicorp.com/vault/tutorials/associate-cert).

