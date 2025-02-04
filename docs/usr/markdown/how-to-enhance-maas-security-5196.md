> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/enhancing-maas-security" target = "_blank">Let us know.</a>*

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

You can alternatively [bypass SSL](/t/how-to-enable-high-availability/5120) without HAProxy.

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

- Be wary of traffic probing ports not linked to any application service. Such behaviour often signifies a port scanner in action.
  
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

To analyse web server activity, employ a log analysis tool or inspect raw logs stored in paths like `/var/log/httpd/` or `/var/log/apache2`. Things to keep an eye on include:

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

| Pkg Fmt  | chmod 640 on files...                | Final Perms  | Add'l Info                                          |
|----------|---------------------------------------|--------------|-----------------------------------------------------|
| Snap     | `/var/snap/maas/current/regiond.conf` | `-rw-r-----` | [About snap security](#heading--snaps-and-security) |
|          | `/var/snap/maas/current/rackd.conf`   | `-rw-r-----` |                                                     |
| Packages | `/etc/maas/rackd.conf/regiond.conf`   | `-rw-r-----` |                                                     |
|          | `/etc/maas/rackd.conf/rackd.conf`     | `-rw-r-----` |                                                     |

## snap security

Snaps are fully confined or 'sandboxed,' offering inherent security for the enclosed application. For more detailed information, see [this snap blog](https://snapcraft.io/blog/where-eagles-snap-a-closer-look)**^**.

## Shared secrets

When you add a new rack or region controller, MAAS asks for a shared secret it will use to communicate with the rest of MAAS. This secret is also exposed in the web UI when you click the 'Add rack controller' button on the Controllers page. MAAS automatically generates this secret when your first region controller installed, and stores the secret in a plain text file. This file is automatically protected with the correct permissions, so there is no need for any action on your part.

As a MAAS administrator, it's crucial to avoid storing secrets associated with your MAAS instance in the database. This includes secrets like the OMAPI key and the RPC secret.

## HashiCorp Vault

Beginning with version 3.3, MAAS secrets are stored in [HashiCorp Vault](https://www.hashicorp.com/products/vault). 

Vault employs identity for securing secrets and encryption keys. Its core component is the `kv` secrets engine, which utilises key-value pairs to store secrets within an encrypted storage managed by Vault. You can explore more about [secrets engines](https://developer.hashicorp.com/vault/docs/secrets) if you're interested.

Vault safeguards the secrets engine using a [barrier view](https://developer.hashicorp.com/vault/docs/secrets#barrier-view), creating a folder with a randomly-generated UUID as the absolute root directory for that engine. This prevents the engine from accessing secrets outside its UUID folder.

For detailed information, it's recommended to refer to the [Vault documentation](https://developer.hashicorp.com/vault/docs) and consider [Vault certification](https://developer.hashicorp.com/vault/tutorials/associate-cert).

## Security consulting

If you need help implementing MAAS security, please [contact us](/t/how-to-contact-us/5448). We will be happy to assist you in arranging security consulting appropriate to your needs.