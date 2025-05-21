Cloud-init is a powerful part of the MAAS customization suite.  This article walks through specific usage of cloud-init scripts to customize and automate MAAS instances. Cloud-init helps you set up machines automatically; here are some common examples.

## What is cloud-init?

Cloud-init automatically configures machines after bootup. It can create users, install software, and set up networking. When you're using MAAS, cloud-init can ensure that each machine is ready to use when deployed. If you're relatively new to cloud-init, we recommend you consult [the cloud-init documentation](https://cloudinit.readthedocs.io/en/latest/) before trying these examples.

## Basic cloud-init configurations for MAAS

Cloud-init can get very complicated, very fast, so let's start small and build.  Here are some basic templates and examples for you to try with MAAS.

### Creating a user and installing basic packages

Let’s start with something simple: creating a new user and installing some basic software packages.

Here's a basic cloud-init script that does just that:

```yaml
#cloud-config
users:
  - name: maas_user
    ssh_authorized_keys:
      - ssh-rsa AAAAB3Nz... user@domain
    sudo: "ALL=(ALL) NOPASSWD:ALL"
    groups: sudo
    shell: /bin/bash
packages:
  - git
  - htop
```

What this script does:

1. Creates a user named `maas_user`.
2. Adds an SSH key to allow secure remote login.
3. Installs packages like `git` (a version control tool) and `htop` (a system monitor).

How you can test it:

To login, you'll want to use a command of this form:

```nohighlight
ssh -i /.ssh/id_rsa maas_user@10.192.226.195
```

You can then test it further by running `htop` and trying out some `git` commands.

### Creating multiple users and adding sudo privileges

Sometimes you may need to create multiple users with administrative `sudo` access:

```yaml
#cloud-config
users:
  - name: admin_user
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAAB3Nz... admin@domain
    groups: sudo
    shell: /bin/bash

  - name: dev_user
    sudo: ALL=(ALL) NOPASSWD:ALL
    ssh_authorized_keys:
      - ssh-rsa AAAAB3Nz... dev@domain
    groups: sudo
    shell: /bin/bash
```

What this script does:

1. Creates two users: `admin_user` and `dev_user`.
2. Grants both users sudo privileges without requiring a password.

How to test it:

1. Depending on what you ran last on your host, you might need to update the `known_hosts` file like this:

```nohighlight
ssh-keygen -f "/path/to/.ssh/known_hosts" -R "<ip_address>"

2. You'll login as before, with a command like this:

```nohighlight
ssh -i /.ssh/id_rsa maas_user@10.192.226.195
```
3. When logged in, you can try a few commands that require `sudo` to verify that your `cloud-init` was successful.

### Setting up SSH keys for multiple users

You can set up SSH keys for multiple users in one go:

```yaml
#cloud-config
users:
  - default
  - name: user1
    ssh_authorized_keys:
      - ssh-rsa AAAAB3Nz... user1@domain
  - name: user2
    ssh_authorized_keys:
      - ssh-rsa AAAAB3Nz... user2@domain
```

What this script does:

1. Sets up a default user.
2. Creates `user1` and `user2` with their own SSH keys for secure login.

How to use it:

- Copy any of these scripts and paste them into the “User Data” field when deploying a machine in MAAS. The setup will automatically run when the machine starts up, making it ready for use.

## Disk and filesystem management

Sometimes, you need specific disk setups, like creating custom partitions or using RAID. Ideally, you'd use `curtin` for this, but here’s how to do it with `cloud-init`:

## Automating software deployment

You can use `cloud-init` to automatically install and configure software. This is the most common usage with MAAS, and you can effect it like this:

### Installing Docker

```yaml
#cloud-config
packages:
  - docker.io
runcmd:
  - systemctl enable docker
  - systemctl start docker
```

What this script does:

1. Installs Docker on the machine.
2. Enables and starts Docker to make sure it’s running whenever the machine boots up.

### Installing a LAMP stack (Linux, Apache, MySQL, PHP)

A LAMP stack is commonly used for hosting websites and web applications. Here’s how to set it up:

```yaml
#cloud-config
packages:
  - apache2
  - mysql-server
  - php
runcmd:
  - systemctl enable apache2
  - systemctl start apache2
  - systemctl enable mysql
  - systemctl start mysql
```

What this script does:

1. Installs Apache, MySQL, and PHP.
2. Enables and starts Apache and MySQL services.

### Setting up Node.js and Nginx

For modern web applications, you may want Node.js and Nginx:

```yaml
#cloud-config
packages:
  - nginx
  - nodejs
  - npm
runcmd:
  - systemctl enable nginx
  - systemctl start nginx
```

What this script does:

1. Installs Nginx, Node.js, and npm (Node Package Manager).
2. Enables and starts Nginx to serve web applications.

How to use it:

- Use these scripts in MAAS to automatically install and start various software. This is perfect for setting up a new server to run specific applications or services.

## Security configurations

Keeping your servers secure is crucial. Here’s how to use `cloud-init` to help with that:

### Setting up a firewall with UFW

```yaml
#cloud-config
package_update: true
packages:
  - ufw
runcmd:
  - ufw allow ssh
  - ufw enable
```

What this script does:

1. Updates the package list to make sure all software is up to date.
2. Installs UFW (Uncomplicated Firewall).
3. Configures UFW to allow SSH connections and then enables the firewall.

### Enforcing strong password policies

To ensure strong passwords are used on your system, you can enforce password policies:

```yaml
#cloud-config
chpasswd:
  expire: true
  list: |
    user1:u*Y4$$0)@2yUgp
    user2:i$$3%907DfU#
```

What this script does:

1. Sets passwords for `user1` and `user2`.
2. Forces these passwords to expire, requiring users to change them on first login.

### Disabling unused services

For security, it's a good idea to disable services you don't need. Here’s how to do it:

```yaml
#cloud-config
runcmd:
  - systemctl stop bluetooth.service
  - systemctl disable bluetooth.service
```

What this script does:

1. Stops the Bluetooth service.
2. Disables the Bluetooth service to prevent it from starting on boot.

How to use it:

- Paste these scripts into the “User Data” section in MAAS to secure your server immediately after it’s deployed.

## Logging and monitoring setup

To keep track of what’s happening on your servers, you might want to set up logging and monitoring tools.

### Setting up Prometheus node exporter

```yaml
#cloud-config
packages:
  - prometheus-node-exporter
runcmd:
  - systemctl enable prometheus-node-exporter
  - systemctl start prometheus-node-exporter
```

What this script does:

1. Installs Prometheus Node Exporter, a monitoring tool that helps track server metrics like CPU and memory usage.
2. Enables and starts the Prometheus Node Exporter service.

### Installing and configuring ELK Stack

The ELK Stack (Elasticsearch, Logstash, and Kibana) is great for centralized logging:

```yaml
#cloud-config
packages:
  - elasticsearch
  - logstash
  - kibana
runcmd:
  - systemctl enable elasticsearch
  - systemctl start elasticsearch
  - systemctl enable logstash
  - systemctl start logstash
  - systemctl enable kibana
  - systemctl start kibana
```

What this script does:

1. Installs Elasticsearch, Logstash, and Kibana.
2. Enables and starts all three services to collect, store, and visualize logs.

### Setting up Grafana for monitoring dashboards

Grafana is a popular tool for creating visual dashboards for monitoring:

```yaml
#cloud-config
packages:
  - grafana
runcmd:
  - systemctl enable grafana-server
  - systemctl start grafana-server
```

What this script does:

1. Installs Grafana on the server.
2. Enables and starts the Grafana server to provide monitoring dashboards.

How to use it:

- Add these scripts to MAAS to automatically set up logging and monitoring on new servers. It’s a great way to keep an eye on performance and detect any issues early.

## Example templates for common use cases

Here are some ready-to-use templates for common scenarios:

### Web server deployment

```yaml
#cloud-config
packages:
  - apache2
  - php
runcmd:
  - systemctl enable apache2
  - systemctl start apache2
```

### Database server setup

```yaml
#cloud-config
packages:
  - mysql-server
  - mysql-client
runcmd:
  - systemctl enable mysql
  - systemctl start mysql
```

### Load balancer configuration with HAProxy

```yaml
#cloud-config
packages:
  - haproxy
write_files:
  - path: /etc/haproxy/haproxy.cfg
    content: |
      global
        log /dev/log local0
        log /dev/log local1 notice
        chroot /var/lib/haproxy
        stats socket /run/haproxy/admin.sock mode 660 level admin
        stats timeout 30s
        user haproxy
        group haproxy
        daemon
      defaults
        log global
        mode http
        option httplog
        option dontlognull
        timeout connect 5000
        timeout client 50000
        timeout server 50000
runcmd:
  - systemctl enable haproxy
  - systemctl start haproxy
```

How to use them:

- Pick a template based on your needs and copy it into MAAS. These templates help you quickly deploy common server types with minimal manual effort.

## Debugging and error handling

Sometimes, things don’t go as planned. Here’s how to debug cloud-init configurations:

### Checking cloud-init logs

- After deploying a machine, connect to it and check the cloud-init logs located at `/var/log/cloud-init.log` and `/var/log/cloud-init-output.log`. These logs will show you what happened during the cloud-init process and can help you find and fix any issues.

### Using cloud-init to write custom logs

You can use cloud-init to create custom log files for debugging:

```yaml
#cloud-config
runcmd:
  - echo "Starting custom log" >> /var/log/custom-init.log
  - some-command >> /var/log/custom-init.log 2>&1
```

What this script does:

1. Starts a custom log file at `/var/log/custom-init.log`.
2. Logs

 the output of `some-command` to this custom log file for easier debugging.

### Adding retry logic for commands

Sometimes commands may fail temporarily, and adding retry logic can help:

```yaml
#cloud-config
runcmd:
  - for i in {1..5}; do some-command && break || sleep 2; done
```

What this script does:

1. Tries to run `some-command` up to five times.
2. Waits for 2 seconds between each try if the command fails.

How to use it:

- Include these debugging techniques in your cloud-init configurations to help identify and resolve issues during machine deployment.

## Conclusion

By using these cloud-init scripts, you can easily automate and customize your machines in MAAS, making deployments faster and more efficient. Feel free to mix and match the examples to fit your needs, and remember that cloud-init is a powerful tool that can help you manage your servers more effectively. Happy deploying!

