> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/maas-settings" target = "_blank">Let us know.</a>*
	
This page explains how to change settings for MAAS versions 3.4 and above. There are separate settings guides for [MAAS 3.3 and below](/t/how-to-change-maas-3-3-settings/7880), and [the MAAS CLI](/t/how-to-change-settings-with-the-cli/7881).
	
*Settings* is available near the bottom of the left navigation panel.

## MAAS name

You can assign a unique name to each MAAS instance, along with one or more Unicode emojis. To do so, navigate to *Settings* > *Configuration* > *General*, use the *MAAS name* and *Unicode emoji* to describe your MAAS instance, and *Save* your changes. This will help differentiate and identify your instance easily, for example:

```nohighlight
US-west-2 🇺🇸 MAAS-prod
my-maas ❗ no-deploys
```

## MAAS theme main colour

In addition to a unique name and emoji (see above), you can differentiate MAAS instances by changing the theme colour. Simply navigate to *Settings* > *Configuration* > *General* and choose the main colour theme for your MAAS instance. This will determine the overall visual appearance of the interface.

## Data analytics

You can enable analytics to shape improvements to the user experience. The analytics used in MAAS include Google Analytics, Usabilla, and Sentry Error Tracking. Navigate to *Settings* > *Configuration* > *General* and check the box entitled *Enable analytics to shape improvements to user experience*. This data is handled with privacy in mind.

## Notifications

You can also enable notifications for new releases. Navigate to *Settings* > *Configuration* > *General* and choose *Enable new release notifications*. This feature applies to all MAAS users, allowing you to receive dismissible notifications regarding the availability of new releases.

## Default Ubuntu release used for commissioning

The default Ubuntu release used for commissioning determines the version of Ubuntu that is installed on newly commissioned machines. By default, the Ubuntu 20.04 LTS "Focal Fossa" release is used. This is the recommended and supported release for commissioning.

If you have synced other release images using *Configuration > Images*, they will appear in the drop-down *Default Ubuntu release used for commissioning*. To change the default commissioning release, navigate to *Settings* > *Configuration* > *Commissioning*, and select your desired *Default Ubuntu release used for commissioning*.

## Default minimum kernel version

The default minimum kernel version is the lowest kernel version allowed on all new and commissioned nodes. Navigate to *Settings* > *Configuration* > *Commissioning* and select your desired *Default minimum kernel version*. By default, there is no minimum kernel version set, meaning any kernel version can be used. 

> While the absence of a minimum kernel version provides flexibility, it's important to ensure compatibility with your specific system requirements.

## Default operating system used for deployment

Default OS refers to the base operating system, e.g., Ubuntu, CentOS, etc. To change it, navigate to *Settings* > *Configuration* > *Deploy* and select your desired *Default OS release used for deployment*. Only the OS images you have synced using *Configuration* > *Images* are available.

## Default OS release used for deployment

Default OS release refers to the specific OS release, e.g, Ubuntu 22.04, CentOS 7, etc. To set this, navigate to *Settings* > *Configuration* > *Deploy* and select your desired *Default operating system used for deployment*. Only OS releases you have synced using *Configuration > Images* will be available.

## Default hardware sync interval (minutes)

The default hardware sync interval refers to the frequency at which hardware information is synchronised between the MAAS server and deployed machines. To change it, navigate to *Settings > Configuration > Deploy* and set your desired *Default hardware sync interval* in minutes.

By default, the hardware sync interval is set to 15 minutes. This means that every 15 minutes, the MAAS server will update and synchronise the hardware information of the deployed machines. You can adjust this interval according to your specific needs and requirements, but it's recommended to maintain a reasonable interval for efficient synchronisation.

## Configuration > Kernel parameters

Global kernel parameters are settings that are consistently passed to the kernel during the boot process for all machines in your MAAS instance. These parameters can be used to configure specific behaviours or enable certain features in the kernel.

Navigate to *Settings* > *Configuration* > *Kernel parameters* and set *Global boot parameters always passed to the kernel*. Ensure that the boot parameters you specify are compatible with the kernel and any specific requirements of your system.

> Changes to the global boot parameters will affect all machines in your MAAS instance during the boot process. Make sure to review and test the parameters thoroughly before applying them to your production environment.

## Security protocols

By default, TLS (Transport Layer Security) is disabled in MAAS. If you want to enable TLS to ensure secure communication, run the following command:

```nohighlight
sudo maas config-tls enable $key $cert --port YYYY
```

This command will enable TLS for the MAAS instance. More information about MAAS native TLS can be found [here](/t/how-to-implement-tls/5116)

## Secret storage

To integrate MAAS with Vault, use the following procedure.

## Obtain the necessary information from Vault

Get the $wrapped_token and $role_id from Vault. Refer to the documentation provided by Hashicorp Vault for more details on retrieving these values.

## Configure Vault on each region controller

To set up Vault on your region controllers, run this command on each one, substituting the variables with appropriate values:

```nohighlight
sudo maas config-vault configure $URL $APPROLE_ID $WRAPPED_TOKEN $SECRETS_PATH --secrets-mount $SECRET_MOUNT
```

This command configures Vault on the region controller using the provided parameters.

## Migrate secrets on one of the region controllers

After configuring Vault on all region controllers, select one of the region controllers. Run the following command on that controller to migrate the secrets:

```nohighlight
sudo maas config-vault migrate
```

For more information on Vault integration with MAAS, refer to the [additional documentation](/t/about-maas-security/6719) provided.

## Session timeout

MAAS allows you to configure the session timeout, which determines the length of time a user session can remain active before requiring re-authentication. First, determine the desired session timeout duration, noting the following:

 - The maximum session length is 14 days or 2 weeks.
 - You can specify the duration in weeks, days, hours, and/or minutes.
 - Access the MAAS web interface and log in with your credentials.

Navigate to *Settings* > *Security* > *Session timeout* and enter your desired duration. Use the appropriate format options (e.g., "2 weeks," "14 days," "336 hours," or "20,160 minutes").

> After changing the session expiration time, MAAS will automatically log out all users. The new session timeout will apply for subsequent logins.

## IPMI settings

MAAS provides options to configure the IPMI (Intelligent Platform Management Interface) settings for your systems. 

## MAAS-generated IPMI username

The MAAS-generated IPMI username is set to "maas" by default. This username is used for IPMI authentication.

## K_g BMC key

The K_g BMC key is used to encrypt all communication between IPMI clients and the BMC (Baseboard Management Controller). If you wish to enable encryption, specify the key in this field. Leave the field blank for no encryption.

## MAAS-generated IPMI user privilege level

MAAS provides three user privilege levels for the MAAS-generated IPMI user:

- Admin: This privilege level grants full access to all IPMI features and controls.
- Operator: This privilege level allows access to most IPMI features but restricts certain critical functions.
- User: This privilege level provides limited access to IPMI features.

Choose the appropriate privilege level for the MAAS-generated IPMI user based on your requirements.

## Configuring IPMI security

Navigate to *Settings* > *Security* > *IPMI settings*. Locate the fields for the MAAS-generated IPMI username, K_g BMC key, and IPMI user privilege level, and enter the desired values, based on the discussion above.

> These settings are specific to the MAAS-generated IPMI user and apply to the IPMI communication for your systems.

## User management

MAAS provides basic functionality to manage users, as described in this section.

## Search

The search feature allows you to find specific users in the MAAS system based on different criteria. You can search by username, real name, email, machines, type, last seen, role, or MAAS keys.

The search results will display a table with relevant information for each user, including their username, real name, email, number of machines, user type, last seen date and time, role, and MAAS keys. Additionally, actions such as editing or deleting users can be performed using the respective buttons under the "Actions" column.

## Add User

Choose *Settings* > *Users* > *Add user*. Fill in the required information for the new user:

- Username: Enter the desired username for the new user.
- Full name: Provide the real name of the user.
- Email address: Enter the email address associated with the user.
- Password: Enter a password for the new user and confirm it.

Be sure to save your changes.

## Editing a user entry

To edit an existing user, navigate to *Settings* > *Users*. 

If you have a large number of users, use the [Search function described above](#heading--Search) to filter the list. Click on the pencil icon at the end of the user's row, and edit information as desired.

## Use proprietary drivers

To enable the installation of proprietary drivers, navigate to *Settings* > *Images* > *Ubuntu* and toggle *Enable the Installation of Proprietary Drivers*. Enabling this option will allow the system to install proprietary drivers, such as HPVSA (High-Performance Virtual Storage Architecture), when necessary or desired.

> The availability and functionality of proprietary drivers may vary depending on your specific system and hardware configuration. It may also be necessary for you to load the needed drivers onto your system.

## Windows KMS host

The Windows KMS (Key Management Service) activation host is used for activating Windows deployments through KMS activation. In order to activate KMS, you'll need the FQDN (Fully Qualified Domain Name) or IP address of the host that provides the KMS Windows activation service.

Navigate to *Settings* > *Images* > *Windows*, and enter the FQDN under *Windows KMS activation host*.

> This configuration is only necessary for Windows deployments that use KMS activation. If you are not using KMS activation or have already configured a different activation method, you can leave this field blank.

## VMware vCenter server configuration

To configure the VMware vCenter server settings in MAAS, first obtain the necessary information:

- VMware vCenter server FQDN or IP address: This is the Fully Qualified Domain Name (FQDN) or IP address of your VMware vCenter server, which will be passed to the deployed VMware ESXi host.
- VMware vCenter username: This is the username for your VMware vCenter server, which will be passed to the deployed VMware ESXi host.
- VMware vCenter password: This is the password for your VMware vCenter server, which will be passed to the deployed VMware ESXi host.
- VMware vCenter data centre: This is the data centre in your VMware vCenter environment, which will be passed to the deployed VMware ESXi host.

Having done so, navigate to *Settings* > *Images* > *VMware* and enter this information into the provided fields.

## License keys

*Settings > License keys* gives you the ability to manage your product licenses in a tabular format:

- *Add license key button*: This button can be used to add a new license key.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: These action buttons allow you to delete or edit the information in that row. Note that the delete and/or edit buttons may be greyed out (unavailable) based on your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular license key in a longer list.

## Default storage layout

The default storage layout determines the layout that is applied to a node when it is commissioned. Navigate to *Settings* > *Storage* and choose your desired *Default Storage Layout*. This layout will be applied during commissioning.

## Erasing disks prior to releasing

You can force users to always erase disks when releasing nodes. Navigate to *Settings* > *Storage* and enable *Erase nodes' disks prior to releasing*. This option ensures that disks are properly wiped before releasing nodes.

## Disk erasure options 

MAAS provides different disk erasure options depending on the capabilities of the devices. Navigate to *Settings* > *Storage*. Choose the desired option based on your requirements:

- *Use secure erase by default when erasing disks*: This option will be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.
- *Use quick erase by default when erasing disks*: This option performs a non-secure erase by wiping only the beginning and end of each disk.
Save the changes to apply the configuration.

## HTTP proxy configuration

MAAS allows you to configure an HTTP proxy for image downloads and for provisioned machines to access APT and YUM packages. To configure this proxy, navigate to *Settings* > *Network* > *Proxy*. Choose the appropriate option based on your requirements:

- Don't use a proxy: Select this option if you do not want to use an HTTP proxy for MAAS image downloads or for APT/YUM package access by provisioned machines.

- MAAS built-in: Select this option if you want to use the built-in HTTP proxy provided by MAAS. This is the default option and requires no additional configuration.

- External: Enter the URL of the external proxy that MAAS will use to download images, and the machines will use to download APT packages for provisioned machines. Be sure to provide the complete URL of the external proxy server, including the protocol (e.g., http:// or https://), the hostname or IP address, and the port number.

- Peer: Enter the URL of an external proxy that will serve as an upstream cache peer for the MAAS built-in proxy. Machines provisioned by MAAS will be configured to use the MAAS built-in proxy to download APT packages, and this external proxy will be used as a peer for caching. By configuring an upstream cache peer, MAAS can leverage caching functionality to improve APT package download performance for provisioned machines. Be sure to provide the complete URL of the external proxy server, including the protocol (e.g., http:// or https://), the hostname or IP address, and the port number.

## Upstream DNS configuration

MAAS allows you to configure the upstream DNS settings for resolving domains not managed by MAAS. Navigate to *Settings* > *Network* > *DNS*. Enter the IP addresses of the upstream DNS servers in *Upstream DNS*. Separate multiple IP addresses with a space. For example, you can enter 8.8.8.8 to use Google's public DNS server.

This upstream DNS configuration is only used when MAAS is running its own DNS server. The provided IP addresses will be used as the value of 'forwarders' in the DNS server configuration.

## DNS delegation

MAAS allows for efficient DNS management, including the delegation of DNS zones. Delegation is typically used to direct traffic from a parent domain to a child domain, managed by different DNS servers. Below is a guide to configure DNS delegation in MAAS.

## Delegate a zone to MAAS

1. **External DNS Configuration:** In your external DNS server, create NS records for the subdomain that point to the MAAS region controller. For example, for the subdomain `dc1.mycompany.com`, create an NS record in your global DNS that delegates to MAAS.

2. **MAAS DNS Configuration:** Within MAAS, create an authoritative domain for `dc1.mycompany.com`. MAAS will then handle DNS requests for this subdomain.

## Delegate a zone from MAAS to another DNS server

1. **Create the Domain:** In MAAS, create a domain you wish to delegate, say `dc1.mycompany.com`, but set it as non-authoritative.

2. **Configure the NS Records:** In the MAAS domain, create NS records pointing to the DNS servers that will be authoritative for the subdomain.

3. **A/AAAA Records:** Ensure you have A or AAAA records for each DNS server to which you're delegating within the MAAS domain.

Remember that proper DNS delegation requires pointing NS records to the hostname of the authoritative DNS servers (A/AAAA records), not directly to IP addresses -- although using IP addresses can work in most cases.

## Enable DNSSEC validation of upstream zones
 
MAAS provides the option to enable DNSSEC (Domain Name System Security Extensions) validation for upstream zones. Navigate to *Settings* > *Network* > *DNS* and set *Enable DNSSEC validation of upstream zones* based on your requirements:

- Automatic (use default root key): Select this option to enable DNSSEC validation using the default root key. This is the recommended option as it simplifies the configuration and maintenance of DNSSEC.

- Yes (manually configured root key): Select this option if you have a specific root key that you want to use for DNSSEC validation. This allows you to manually configure and manage the root key used for validation.

- No (Disable DNSSEC; useful when upstream DNS is misconfigured): Select this option to disable DNSSEC validation. This option is useful when the upstream DNS is misconfigured or does not support DNSSEC properly.Automatic (use default root key): Select this option to enable DNSSEC validation using the default root key.

DNSSEC validation is only used when MAAS is running its own DNS server. The selected option will be used as the value of 'dnssec_validation' in the DNS server configuration.

## List of external networks allowed to use MAAS for DNS resolution

MAAS maintains a list of networks that are allowed to use MAAS for DNS resolution. You can add extra networks to this trusted ACL list, specifically networks that were not previously known. To add extra networks, navigate to *Settings* > *Network* > *DNS*. Enter the IP addresses or ACL (Access Control List) names into *List of external networks (not previously known) that will be allowed to use MAAS for DNS resolution*.

## NTP server configuration

MAAS allows you to configure NTP (Network Time Protocol) servers to be used as time references for MAAS itself, the machines deployed by MAAS, and devices utilising MAAS DHCP services. Navigate to *Settings* > *Network* > *NTP*, and enter the IP/hostname of external NTP servers into *Addresses of NTP servers*. The configured NTP servers will be used as time references for MAAS itself, the machines deployed by MAAS, and devices utilising MAAS DHCP services.

## Use external NTP servers only

MAAS provides the option to configure the use of external NTP servers exclusively. Navigate to *Settings* > *Network* > *NTP*, and enable *Use external NTP servers only*.

Enabling this option ensures that all relevant MAAS components, including region controller hosts, rack controller hosts, and deployed machines, will refer directly to the configured external NTP servers for time synchronisation. Disabling this option will result in a different hierarchy of NTP server references.

## Remote syslog server configuration

MAAS allows you to configure a remote syslog server to which log messages from enlisted, commissioned, tested, and deployed machines will be sent. Navigate to *Settings* > *Network* > *Syslog* and enter the syslog sever address into *Remote syslog server to forward machine logs*.

Once configured, MAAS will automatically set the remote syslog server on enlisted, commissioned, tested, and deployed machines to forward all log messages to the specified server. If you wish to restore the default behaviour of forwarding syslog to MAAS instead of a remote server, simply clear the configured value in this field. MAAS will revert to its default behaviour.

## Network discovery configuration

MAAS allows you to configure network discovery, which enables MAAS to observe networks attached to rack controllers using passive techniques such as listening to ARP requests and DNS advertisements. Navigate to *Settings* > *Network* > *Network discovery* and enable *Network discovery*.

## Active subnet mapping interval

MAAS provides the option to enable active subnet mapping, which involves scanning subnets at regular intervals to ensure accurate and complete discovery information. Enabling active subnet mapping helps ensure that the discovery information gathered by MAAS is up-to-date and accurate. Navigate to *Settings* > *Network* > *Network discovery* and set your desired *Active subnet mapping interval*.