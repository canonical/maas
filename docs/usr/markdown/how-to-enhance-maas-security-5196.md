
## Cheat sheet

| Topic         | Commands / UI path | Notes |
|---------------|--------------------|-------|
| TLS (3.3+) | `maas config-tls enable key.pem cert.pem --cacert chain.pem --port 5443` | Use same cert across HA; default port 5443 |
| TLS (≤3.2) | Reverse proxy with nginx or apache2 | TLS must be terminated in front of MAAS |
| Check TLS | UI: *Settings* > *Security* | Shows CN, expiry, fingerprint |
| Renew TLS | Re-run `config-tls enable` with new files | Store certs in `/var/snap/maas/common` |
| Ports | `ufw allow 5240`, `ufw allow 5248`, `ufw allow 5241:5247/tcp|udp`, `ufw allow 5250:5270/tcp|udp` | Limit exposure, see [port reference](https://canonical.com/maas/docs/configuration-reference#p-17901-controller-port-settings) |
| HAProxy | `sudo apt install haproxy` → edit `/etc/haproxy/haproxy.cfg` | Use as TLS terminator + load balancer |
| Logs | Snap: `/var/snap/maas/common/log/` <br> Package: `/var/log/maas/` | Watch for anomalies, see [logging ref](https://canonical.com/maas/docs/maas-logging-reference) |
| Users | UI: *Settings* > *Users* <br> CLI: `maas $PROFILE users create ...` | Manage carefully; add SSH/API keys as needed |
| Vault | `sudo maas config-vault configure ...` then `maas config-vault migrate` | Integrates MAAS with HashiCorp Vault for secrets |

Security underpins everything MAAS does: deploying machines, managing networks, and serving API calls. Strong encryption, careful logging, and user access management reduce the chance of compromise.

This guide shows how to:
- Enable and verify TLS (native in 3.3+, proxied in earlier versions).
- Control network ports and use HAProxy.
- Use logs to detect issues.
- Manage users, SSH keys, and API tokens.
- Integrate secrets with HashiCorp Vault.


## Use TLS (3.3 and later)

TLS encryption secures both the MAAS API and UI.

### Configure TLS with `config-tls`
Run `maas config-tls` to enable or disable TLS.

```nohighlight
maas config-tls enable key.pem cert.pem --cacert chain.pem --port 5443
maas config-tls disable
```

- `--port`: defaults to 5443.
- `--cacert`: include full certificate chain when using non-self-signed certs.

### High availability (HA)
All region/rack controllers in HA must share the same certificate. Use Subject Alternative Names (SANs) to cover multiple DNS names or IPs:

```nohighlight
X509v3 Subject Alternative Name:
  DNS:example.com, IP Address:10.211.55.9
```

### Check TLS status
UI path: *Settings* > *Security*.
Look for:
- Common name (CN)
- Expiration date
- Fingerprint
- Warnings if TLS is disabled

### Log in to MAAS CLI with TLS
Use `https://` and port 5443:

```nohighlight
maas login myprofile https://maas.example:5443/MAAS <api_key>
```

Add `--cacerts` if your CA is not globally trusted.

### Renew certificates
Re-run the `enable` command with new files:

```nohighlight
sudo maas config-tls enable new-key.pem new-cert.pem --port 5443
```

Store certs in a snap-accessible path like `/var/snap/maas/common`.

### Automate renewal
- With step-ca or Caddy (ACME protocol).
- With acme.sh or certbot (hooks to re-run `maas config-tls enable`).

See examples in [certbot docs](https://certbot.eff.org).

### PEM file management
Combine cert and key:
```nohighlight
cat mysite.com.crt mysite.com.key > mysite.com.pem
sudo cp mysite.com.pem /etc/ssl/private/
```
Append root and intermediate CA certs if required.


## Use TLS (3.2 and earlier)

Older MAAS releases do not support native TLS. Use a reverse proxy.

### nginx example
```nohighlight
server {
 listen 443 ssl;
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

### apache2 example
```nohighlight
<VirtualHost *:443>
 SSLEngine On
 SSLCertificateFile /etc/apache2/ssl/apache2.crt
 SSLCertificateKeyFile /etc/apache2/ssl/apache2.key

 ProxyPass / http://localhost:5240/
 ProxyPassReverse / http://localhost:5240/
</VirtualHost>
```


## Manage network ports

Limit exposure with a firewall.

Example (UFW):
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

See [port reference](https://canonical.com/maas/docs/configuration-reference#p-17901-controller-port-settings) for a complete list.


## Deploy HAProxy

Use HAProxy for TLS termination, load balancing, and high availability.

1. Install HAProxy:
   ```nohighlight
   sudo apt install haproxy
   ```

2. Update `/etc/haproxy/haproxy.cfg`:
   ```nohighlight
   global
     maxconn 2000
     tune.ssl.default-dh-param 2048

   defaults
     mode http
     option forwardfor
     option http-server-close

   frontend maas
     bind *:443 ssl crt /etc/ssl/private/mysite.com.pem
     reqadd X-Forwarded-Proto:\ https
     default_backend maas

   backend maas
     balance source
     server localhost localhost:5240 check
     server maas-api-1 10.0.0.11:5240 check
     server maas-api-2 10.0.0.12:5240 check
   ```

3. Restart:
   ```nohighlight
   sudo systemctl restart haproxy
   ```


## Use logging

Monitor logs for suspicious activity.

- Snap: `/var/snap/maas/common/log/`
- Package: `/var/log/maas/`

See [MAAS logging reference](https://canonical.com/maas/docs/maas-logging-reference).


## Manage users

Careful user management protects access.

### Add users
UI: *Settings* > *Users* > *Add user*
CLI:
```nohighlight
maas $PROFILE users create username=$USERNAME email=$EMAIL password=$PASSWORD is_superuser=0
```

### Edit users
UI: select user > *Details* > save changes.

### SSH keys
UI: *Settings* > *Users* > select user > *Edit keys*
CLI:
```nohighlight
maas $PROFILE sshkeys create key="$(cat ~/.ssh/id_rsa.pub)"
```

### API keys
UI: *Settings* > *Users* > *API keys*.

### Passwords
Admins can reset any password. 


## Integrate with Vault

Use [HashiCorp Vault](https://developer.hashicorp.com/vault/docs) to centralize secrets.

1. Enable `approle` and KV v2 in Vault.
2. Write a policy allowing MAAS access.
3. Assign a role to each region controller.
4. Generate role ID and wrapped secret.
5. Configure MAAS:
   ```nohighlight
   sudo maas config-vault configure $URL $ROLE_ID $WRAPPED_TOKEN $SECRETS_PATH --mount $MOUNT
   sudo maas config-vault migrate
   ```

For details, see [Vault tutorial](https://learn.hashicorp.com/tutorials/vault/approle-best-practices?in=vault/auth-methods#approle-response-wrapping).


## Safety nets

- Always use the same certs on all controllers in HA.
- Verify TLS status in the UI after any change.
- Run `maas status` to confirm services after firewall/Haproxy changes.
- Test cert renewals with `--dry-run`.


## Next steps
- Learn [how to use logging](https://canonical.com/maas/docs/how-to-use-logging).
- Discover ways to [monitor MAAS](https://canonical.com/maas/docs/how-to-monitor-maas)
- In situations where proven security is needed, [deploy a FIPS-compliant kernel](https://canonical.com/maas/docs/how-to-deploy-a-fips-compliant-kernel)
