> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/enhance-maas-security" target = "_blank">Let us know.</a>*

This page offers actionable steps for securing your MAAS instance.

## Firewalls

For a secure MAAS setup, you need to regulate the network ports accessible on your rack controllers. Below is a table outlining the essential TCP ports for MAAS communication:

| Port(s)         | Description                                                                               |
|-----------------|-------------------------------------------------------------------------------------------|
| `5240`          | HTTP traffic with each region controller. In HA environments, port `80` is commonly used. |
| `5241` - `5247` | Allocated for MAAS internal services.                                                    |
| `5248`          | Designated for rack HTTP communication.                                                  |
| `5250` - `5270` | Reserved for region workers (RPC).                                                       |
| `5271` - `5274` | Required for communication between Rack Controller (specifically maas-agent) and Region Controller | 
|`5281` - `5284` | Region Controller Temporal cluster membership gossip communication         |

To further harden your security, consider configuring your [firewall](https://ubuntu.com/server/docs/security-firewall)**^** to allow only the ports MAAS uses. For example, if you're using `ufw`, the commands would look like:

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

Note that the above commands are illustrative; your specific setup and MAAS version may require different settings. Always refer to the relevant firewall documentation for your system.

>**Pro tip**: This example assumes you're using `ufw` for your firewall settings. Always consult your system-specific firewall manual for the most accurate instructions.

## TLS termination

Enhancing both security and availability of your MAAS deployment can be achieved by using a TLS-terminating load balancer. For this purpose, we recommend [HAProxy](https://www.haproxy.com)**^**. This guide outlines how to establish one.

<details><summary>Sidebar: Understanding TLS-terminated load balancing</summary>

Within MAAS, a [load balancer](https://www.nginx.com/resources/glossary/load-balancing/) routes incoming Web UI and API requests across several region controllers. This lessens MAAS workload and reduces user request latency. This is usually part of a high-availability (HA) setup, but MAAS also supports other [HA configurations](/t/how-to-enable-high-availability/5120) for BMC access and DHCP.

A TLS-terminated load balancer carries out encryption and decryption as close to the edge of the network as possible, in this case, right at the load balancer. While "SSL" is an outdated term, we opt for "TLS," or **Transport Layer Security**. TLS aims to ensure both privacy and data integrity between multiple applications, achieved through [symmetric cryptography](https://en.wikipedia.org/wiki/Symmetric-key_algorithm) and [message authentication codes](https://en.wikipedia.org/wiki/Message_authentication_code).

</details>

### TLS configuration (3.3++)

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

### Enabling TLS

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

By default, the HTTPS port is set to 5443, but you can customize this with the --port option. If you're using a non-self-signed certificate, you can specify the full certificate chain using the --cacert option.

If you have HA setup, please note that every MAAS instance will use the same certificate, so you need to create one certificate with multiple domain names or IP addresses; for example:

```nohighlight
X509v3 Subject Alternative Name:
                DNS:example.com, IP Address:10.211.55.9
```

### Disabling TLS

If for some reason you want to disable TLS, you can do it using the following command:

```nohighlight
usage: maas config-tls disable [-h]

optional arguments:
  -h, --help  show this help message and exit
```

After this, MAAS API and UI will be again reachable on port 5240, over plain HTTP.

### TLS via CLI

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

### Certificate renewal

Once a certificate has expired, you can update it by running the same command used for enabling TLS:

```nohighlight
$ ​​sudo maas config-tls enable new-server-key.pem new-server.pem --port 5443
```

If you’re using the snap, the certificate and key must be placed in a directory that’s readable by the CLI, such as `/var/snap/maas/common` (e.g., if you're using the snap version).

### Is TLS enabled?

When TLS is enabled, the following certificate information is displayed in the MAAS UI under *Settings >> Configuration >> Security*: 

- CN 
- Expiration date
- Fingerprint
- Certificate

If TLS is disabled, this section will instead show a warning. We recommend that you enable TLS for secure communication.

### Notifications

When the specified number of days remain until certificate expiration (as defined in the notification reminder), all administrators will see the certificate expiration notification. This notification enumerates the number of days until certificate expiration. It can be dismissed, but once dismissed, it won't appear again.

A certificate expiration check runs every twelve hours. When the certificate has expired, the notification will change to “certificate has expired”.

### Auto-renew certs

MAAS does not auto-renew certificates, but there's no reason why we cannot provide a gratuitous example. Use at your own risk.

### Local cert authority

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

### Using certbot

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

### TLS for MAAS 3.2--

MAAS doesn't support native TLS encryption. If you are not interested in [setting up an HAProxy](https://maas.io/docs/how-to-enable-high-availability#p-9026-api-ha-with-haproxy) which users access directly, the examples below explain how to create this configuration.

Note that MAAS doesn't bind to port 80; instead, MAAS binds to port 5240.

### nginx config

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

### apache2 config

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

## PEM files

Firstly, amalgamate your SSL certificate (`mysite.com.crt`) and key pair (`mysite.com.key`) into a single PEM file:

```nohighlight
cat mysite.com.crt mysite.com.key > mysite.com.pem
sudo cp mysite.com.pem /etc/ssl/private/
```

Depending on your certificate authority, you may also need to include your root and intermediate CA certificates in the same PEM file.

## HAProxy

To deploy HAProxy, run the following:

```nohighlight
sudo apt-get update
sudo apt-get install haproxy
```

Then, modify `/etc/haproxy/haproxy.cfg`. In the `global` section, set the maximum number of concurrent connections:

```nohighlight
maxconn <number of concurrent connections>
```

Additionally, include the following line to configure temporary DHE key sizes:

```nohighlight
tune.ssl.default-dh-param 2048
```

In the `defaults` section under `mode http`, add:

```nohighlight
option forwardfor
option http-server-close
```

Finally, specify the frontend and backend settings to manage connections between HAProxy and MAAS:

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

Optional features like [HAProxy logging](https://www.digitalocean.com/community/tutorials/how-to-implement-ssl-termination-with-haproxy-on-ubuntu-14-04)**^** can also be enabled, depending on your needs.

You can alternatively bypass SSL without HAProxy.

## Logging

Four types of log files can assist in pinpointing security problems:

1. Firewall logs
2. Web server logs
3. MAAS log files
4. System log files

This guide offers insights and references for each category.

## Firewalls

Ubuntu's Uncomplicated Firewall ([UFW](https://wiki.ubuntu.com/UncomplicatedFirewall)) serves as a front-end for [iptables](https://help.ubuntu.com/community/IptablesHowTo). To secure your MAAS setup, regularly review logs located in `/var/log/ufw*`. 

Identifying security red flags in UFW and iptables logs is more of an art than a science. However, here are some key patterns to help:

- Be wary of traffic probing ports not linked to any application service. Such behavior often signifies a port scanner in action.
  
```nohighlight
    blocked incoming tcp connection request from 96.39.208.43:8240 to 128.17.92.85:6002
```
    
- Cross-reference unusual port numbers against databases of [known hacker tools](http://www.relevanttechnologies.com/resources_4.asp).

- Repeated, failed access attempts from the same domain, IP, or subnet suggest malicious intent.

```nohighlight
    blocked incoming tcp connection request from 96.39.208.43:49343 to 64.242.119.18:31337
```
    
- Messages from within your network may indicate a Trojan horse at play.

```nohighlight
    blocked outgoing tcp packet from 192.168.23.100:5240 to 96.38.231.18:443 as FIN:ACK received, but there is no active connection.
```

## Web server

To analyze web server activity, employ a log analysis tool or inspect raw logs stored in paths like `/var/log/httpd/` or `/var/log/apache2`. Things to keep an eye on include:

- Multiple, rapid-fire requests
- Multiple failed login attempts
- Requests for non-existent pages
- Signs of SQL injection and Web shell attempts

## MAAS logs

| Pkg Fmt  | Look for failed logins in...           |
|----------|-----------------------------------------|
| Snap     | `/var/snap/maas/common/log/regiond.log` |
| Packages | `/var/log/maas/regiond.log`             |

For example, a legitimate login request might resemble:

```nohighlight
    2020-03-31 21:17:56 regiond: [info] 10.132.172.1 GET /MAAS/accounts/login/ HTTP/1.1 --> 200 OK
```
	
## PostgreSQL security

PostgreSQL contains secrets, and should be encrypted for maximum protection. You should consider [full disk encryption ](https://help.ubuntu.com/community/Full_Disk_Encryption_Howto_2019)**^**. Also recommended is [TLS encryption between MAAS and PostgreSQL ](https://www.postgresql.org/docs/current/ssl-tcp.html)**^**.

## Other steps

In addition to the items mentioned above, you should be aware of a few other ways to harden MAAS.

## Good passwords

You should pick good passwords and store them securely (e.g. in a KeePassX password database). Perform user administration only via the web UI. Only share the `maas` and `root` user passwords with administrators.

## Permissions

MAAS configuration files should be set to have permission `640`: readable by logins belonging to the `maas` group and writeable only by the `root` user. Currently, the `regiond.conf` file contains the login credentials for the PostgreSQL database used by MAAS to keep track of all machines, networks, and configuration.

| Pkg Fmt  | chmod 640 on files...                | Final Perms  |
|----------|---------------------------------------|--------------|
| Snap     | `/var/snap/maas/current/regiond.conf` | `-rw-r-----` |
|          | `/var/snap/maas/current/rackd.conf`   | `-rw-r-----` |
| Packages | `/etc/maas/rackd.conf/regiond.conf`   | `-rw-r-----` |
|          | `/etc/maas/rackd.conf/rackd.conf`     | `-rw-r-----` | 

## snap security

Snaps are fully confined or 'sandboxed,' offering inherent security for the enclosed application. For more detailed information, see [this snap blog](https://snapcraft.io/blog/where-eagles-snap-a-closer-look)**^**.

## Manage users

Carefully managing users is essential to a strong, proactive security posture.

### Add a user (3.4 UI)

Navigate to *Settings >> Users* and select *Add user*. Fill in the necessary fields and save your changes. To grant the user administrative rights, make sure to check the appropriate box before saving.

### Edit users (3.4 UI)

Alter user credentials by selecting the MAAS username located at the bottom of the left panel. In the *Details* section, you can change the username, full name, or email address. This is also the place to manage passwords, API and SSH keys, and SSL keys.

### Update users (3.3-- UI)

The steps for adding or updating users are similar to the MAAS 3.4 version. Access user preferences by clicking the MAAS username at the top right of the UI.

### Update users (CLI)

To create a new user using the CLI, enter:

```nohighlight
maas $PROFILE users create username=$USERNAME \
    email=$EMAIL_ADDRESS password=$PASSWORD is_superuser=0
```

### Add SSH keys

To include an SSH key, execute:

```nohighlight
ubuntu@maas:~$ maas $PROFILE sshkeys create key="$(cat /home/ubuntu/.ssh/id_rsa.pub)"
```

>Pro tip: The initial login will automatically import your first SSH key.

### Edit SSH+API keys (UI)

You can add or manage SSH keys by navigating to *Settings > Users* and clicking the pencil icon next to the user's name, then following the key import steps. API keys can be generated similarly—just select *API keys* after clicking the pencil icon.

### Change passwords (UI)

To modify your password, navigate to *Settings > Users*, click the pencil icon next to the user's name, and follow the on-screen instructions.

>Pro tip: Administrators have the ability to change the password for any user here.

## Shared secrets

When you add a new rack or region controller, MAAS asks for a shared secret it will use to communicate with the rest of MAAS. This secret is also exposed in the web UI when you click the 'Add rack controller' button on the Controllers page. MAAS automatically generates this secret when your first region controller installed, and stores the secret in a plain text file. This file is automatically protected with the correct permissions, so there is no need for any action on your part.

As a MAAS administrator, it's crucial to avoid storing secrets associated with your MAAS instance in the database. This includes secrets like the OMAPI key and the RPC secret.

## HashiCorp Vault

Beginning with version 3.3, MAAS secrets are stored in [HashiCorp Vault](https://www.hashicorp.com/products/vault). 

Vault employs identity for securing secrets and encryption keys. Its core component is the `kv` secrets engine, which utilizes key-value pairs to store secrets within an encrypted storage managed by Vault. You can explore more about [secrets engines](https://developer.hashicorp.com/vault/docs/secrets) if you're interested.

Vault safeguards the secrets engine using a [barrier view](https://developer.hashicorp.com/vault/docs/secrets#barrier-view), creating a folder with a randomly-generated UUID as the absolute root directory for that engine. This prevents the engine from accessing secrets outside its UUID folder.

> Vault is compatible with MAAS version 3.3 and above. Please upgrade if you're using an older version.

### Manage Vault

To ensure seamless integration between MAAS and Vault, you'll first need to obtain a `role_id` and `wrapped_token` through Vault's CLI. For detailed guidance, check [Hashicorp Vault's tutorial](https://learn.hashicorp.com/tutorials/vault/approle-best-practices?in=vault/auth-methods#approle-response-wrapping)**^**.

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

## Security consulting

If you need help implementing MAAS security, please [contact us](/t/how-to-contact-us/5448). We will be happy to assist you in arranging security consulting appropriate to your needs.