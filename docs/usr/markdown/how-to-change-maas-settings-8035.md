> *Errors or typos? Topics missing? Hard to read? <a href="https://docs.google.com/forms/d/e/1FAIpQLScIt3ffetkaKW3gDv6FDk7CfUTNYP_HGmqQotSTtj2htKkVBw/viewform?usp=pp_url&entry.1739714854=https://maas.io/docs/maas-settings" target = "_blank">Let us know.</a>*

How you change MAAS settings depends on the MAAS version and interface you've chosen:

- [MAAS 3.4 UI](/t/how-to-change-maas-3-4-settings/6347)
- [MAAS 3.3 and below UI](/t/how-to-change-maas-3-3-settings/7880)
- [MAAS CLI](/t/how-to-change-settings-with-the-cli/7881)

## MAAS 3.4 UI
This page explains how to change settings for MAAS versions 3.4 and above. There are separate settings guides for [MAAS 3.3 and below](/t/how-to-change-maas-3-3-settings/7880), and [the MAAS CLI](/t/how-to-change-settings-with-the-cli/7881).
	
*Settings* is available near the bottom of the left navigation panel.

### MAAS name

You can assign a unique name to each MAAS instance, along with one or more Unicode emojis. To do so, navigate to *Settings* > *Configuration* > *General*, use the *MAAS name* and *Unicode emoji* to describe your MAAS instance, and *Save* your changes. This will help differentiate and identify your instance easily, for example:

```nohighlight
US-west-2 🇺🇸 MAAS-prod
my-maas ❗ no-deploys
```

### MAAS theme main colour

In addition to a unique name and emoji (see above), you can differentiate MAAS instances by changing the theme colour. Simply navigate to *Settings* > *Configuration* > *General* and choose the main colour theme for your MAAS instance. This will determine the overall visual appearance of the interface.

### Data analytics

You can enable analytics to shape improvements to the user experience. The analytics used in MAAS include Google Analytics, Usabilla, and Sentry Error Tracking. Navigate to *Settings* > *Configuration* > *General* and check the box entitled *Enable analytics to shape improvements to user experience*. This data is handled with privacy in mind.

### Notifications

You can also enable notifications for new releases. Navigate to *Settings* > *Configuration* > *General* and choose *Enable new release notifications*. This feature applies to all MAAS users, allowing you to receive dismissible notifications regarding the availability of new releases.

### Default Ubuntu release used for commissioning

The default Ubuntu release used for commissioning determines the version of Ubuntu that is installed on newly commissioned machines. By default, the Ubuntu 20.04 LTS "Focal Fossa" release is used. This is the recommended and supported release for commissioning.

If you have synced other release images using *Configuration > Images*, they will appear in the drop-down *Default Ubuntu release used for commissioning*. To change the default commissioning release, navigate to *Settings* > *Configuration* > *Commissioning*, and select your desired *Default Ubuntu release used for commissioning*.

### Default minimum kernel version

The default minimum kernel version is the lowest kernel version allowed on all new and commissioned nodes. Navigate to *Settings* > *Configuration* > *Commissioning* and select your desired *Default minimum kernel version*. By default, there is no minimum kernel version set, meaning any kernel version can be used. 

> While the absence of a minimum kernel version provides flexibility, it's important to ensure compatibility with your specific system requirements.

### Default operating system used for deployment

Default OS refers to the base operating system, e.g., Ubuntu, CentOS, etc. To change it, navigate to *Settings* > *Configuration* > *Deploy* and select your desired *Default OS release used for deployment*. Only the OS images you have synced using *Configuration* > *Images* are available.

### Default OS release used for deployment

Default OS release refers to the specific OS release, e.g, Ubuntu 22.04, CentOS 7, etc. To set this, navigate to *Settings* > *Configuration* > *Deploy* and select your desired *Default operating system used for deployment*. Only OS releases you have synced using *Configuration > Images* will be available.

### Default hardware sync interval (minutes)

The default hardware sync interval refers to the frequency at which hardware information is synchronised between the MAAS server and deployed machines. To change it, navigate to *Settings > Configuration > Deploy* and set your desired *Default hardware sync interval* in minutes.

By default, the hardware sync interval is set to 15 minutes. This means that every 15 minutes, the MAAS server will update and synchronise the hardware information of the deployed machines. You can adjust this interval according to your specific needs and requirements, but it's recommended to maintain a reasonable interval for efficient synchronisation.

### Configuration > Kernel parameters

Global kernel parameters are settings that are consistently passed to the kernel during the boot process for all machines in your MAAS instance. These parameters can be used to configure specific behaviours or enable certain features in the kernel.

Navigate to *Settings* > *Configuration* > *Kernel parameters* and set *Global boot parameters always passed to the kernel*. Ensure that the boot parameters you specify are compatible with the kernel and any specific requirements of your system.

> Changes to the global boot parameters will affect all machines in your MAAS instance during the boot process. Make sure to review and test the parameters thoroughly before applying them to your production environment.

### Security protocols

By default, TLS (Transport Layer Security) is disabled in MAAS. If you want to enable TLS to ensure secure communication, run the following command:

```nohighlight
sudo maas config-tls enable $key $cert --port YYYY
```

This command will enable TLS for the MAAS instance. More information about MAAS native TLS can be found [here](/t/how-to-implement-tls/5116)

### Secret storage

To integrate MAAS with Vault, use the following procedure.

### Obtain the necessary information from Vault

Get the $wrapped_token and $role_id from Vault. Refer to the documentation provided by Hashicorp Vault for more details on retrieving these values.

### Configure Vault on each region controller

To set up Vault on your region controllers, run this command on each one, substituting the variables with appropriate values:

```nohighlight
sudo maas config-vault configure $URL $APPROLE_ID $WRAPPED_TOKEN $SECRETS_PATH --secrets-mount $SECRET_MOUNT
```

This command configures Vault on the region controller using the provided parameters.

### Migrate secrets on one of the region controllers

After configuring Vault on all region controllers, select one of the region controllers. Run the following command on that controller to migrate the secrets:

```nohighlight
sudo maas config-vault migrate
```

For more information on Vault integration with MAAS, refer to the [additional documentation](/t/about-maas-security/6719) provided.

### Session timeout

MAAS allows you to configure the session timeout, which determines the length of time a user session can remain active before requiring re-authentication. First, determine the desired session timeout duration, noting the following:

 - The maximum session length is 14 days or 2 weeks.
 - You can specify the duration in weeks, days, hours, and/or minutes.
 - Access the MAAS web interface and log in with your credentials.

Navigate to *Settings* > *Security* > *Session timeout* and enter your desired duration. Use the appropriate format options (e.g., "2 weeks," "14 days," "336 hours," or "20,160 minutes").

> After changing the session expiration time, MAAS will automatically log out all users. The new session timeout will apply for subsequent logins.

### IPMI settings

MAAS provides options to configure the IPMI (Intelligent Platform Management Interface) settings for your systems. 

### MAAS-generated IPMI username

The MAAS-generated IPMI username is set to "maas" by default. This username is used for IPMI authentication.

### K_g BMC key

The K_g BMC key is used to encrypt all communication between IPMI clients and the BMC (Baseboard Management Controller). If you wish to enable encryption, specify the key in this field. Leave the field blank for no encryption.

### MAAS-generated IPMI user privilege level

MAAS provides three user privilege levels for the MAAS-generated IPMI user:

- Admin: This privilege level grants full access to all IPMI features and controls.
- Operator: This privilege level allows access to most IPMI features but restricts certain critical functions.
- User: This privilege level provides limited access to IPMI features.

Choose the appropriate privilege level for the MAAS-generated IPMI user based on your requirements.

### Configuring IPMI security

Navigate to *Settings* > *Security* > *IPMI settings*. Locate the fields for the MAAS-generated IPMI username, K_g BMC key, and IPMI user privilege level, and enter the desired values, based on the discussion above.

> These settings are specific to the MAAS-generated IPMI user and apply to the IPMI communication for your systems.

### User management

MAAS provides basic functionality to manage users, as described in this section.

### Search

The search feature allows you to find specific users in the MAAS system based on different criteria. You can search by username, real name, email, machines, type, last seen, role, or MAAS keys.

The search results will display a table with relevant information for each user, including their username, real name, email, number of machines, user type, last seen date and time, role, and MAAS keys. Additionally, actions such as editing or deleting users can be performed using the respective buttons under the "Actions" column.

### Add User

Choose *Settings* > *Users* > *Add user*. Fill in the required information for the new user:

- Username: Enter the desired username for the new user.
- Full name: Provide the real name of the user.
- Email address: Enter the email address associated with the user.
- Password: Enter a password for the new user and confirm it.

Be sure to save your changes.

### Editing a user entry

To edit an existing user, navigate to *Settings* > *Users*. 

If you have a large number of users, use the [Search function described above](#heading--Search) to filter the list. Click on the pencil icon at the end of the user's row, and edit information as desired.

### Use proprietary drivers

To enable the installation of proprietary drivers, navigate to *Settings* > *Images* > *Ubuntu* and toggle *Enable the Installation of Proprietary Drivers*. Enabling this option will allow the system to install proprietary drivers, such as HPVSA (High-Performance Virtual Storage Architecture), when necessary or desired.

> The availability and functionality of proprietary drivers may vary depending on your specific system and hardware configuration. It may also be necessary for you to load the needed drivers onto your system.

### Windows KMS host

The Windows KMS (Key Management Service) activation host is used for activating Windows deployments through KMS activation. In order to activate KMS, you'll need the FQDN (Fully Qualified Domain Name) or IP address of the host that provides the KMS Windows activation service.

Navigate to *Settings* > *Images* > *Windows*, and enter the FQDN under *Windows KMS activation host*.

> This configuration is only necessary for Windows deployments that use KMS activation. If you are not using KMS activation or have already configured a different activation method, you can leave this field blank.

### VMware vCenter server configuration

To configure the VMware vCenter server settings in MAAS, first obtain the necessary information:

- VMware vCenter server FQDN or IP address: This is the Fully Qualified Domain Name (FQDN) or IP address of your VMware vCenter server, which will be passed to the deployed VMware ESXi host.
- VMware vCenter username: This is the username for your VMware vCenter server, which will be passed to the deployed VMware ESXi host.
- VMware vCenter password: This is the password for your VMware vCenter server, which will be passed to the deployed VMware ESXi host.
- VMware vCenter data centre: This is the data centre in your VMware vCenter environment, which will be passed to the deployed VMware ESXi host.

Having done so, navigate to *Settings* > *Images* > *VMware* and enter this information into the provided fields.

### License keys

*Settings > License keys* gives you the ability to manage your product licenses in a tabular format:

- *Add license key button*: This button can be used to add a new license key.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: These action buttons allow you to delete or edit the information in that row. Note that the delete and/or edit buttons may be greyed out (unavailable) based on your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular license key in a longer list.

### Default storage layout

The default storage layout determines the layout that is applied to a node when it is commissioned. Navigate to *Settings* > *Storage* and choose your desired *Default Storage Layout*. This layout will be applied during commissioning.

### Erasing disks prior to releasing

You can force users to always erase disks when releasing nodes. Navigate to *Settings* > *Storage* and enable *Erase nodes' disks prior to releasing*. This option ensures that disks are properly wiped before releasing nodes.

### Disk erasure options 

MAAS provides different disk erasure options depending on the capabilities of the devices. Navigate to *Settings* > *Storage*. Choose the desired option based on your requirements:

- *Use secure erase by default when erasing disks*: This option will be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.
- *Use quick erase by default when erasing disks*: This option performs a non-secure erase by wiping only the beginning and end of each disk.
Save the changes to apply the configuration.

### HTTP proxy configuration

MAAS allows you to configure an HTTP proxy for image downloads and for provisioned machines to access APT and YUM packages. To configure this proxy, navigate to *Settings* > *Network* > *Proxy*. Choose the appropriate option based on your requirements:

- Don't use a proxy: Select this option if you do not want to use an HTTP proxy for MAAS image downloads or for APT/YUM package access by provisioned machines.

- MAAS built-in: Select this option if you want to use the built-in HTTP proxy provided by MAAS. This is the default option and requires no additional configuration.

- External: Enter the URL of the external proxy that MAAS will use to download images, and the machines will use to download APT packages for provisioned machines. Be sure to provide the complete URL of the external proxy server, including the protocol (e.g., http:// or https://), the hostname or IP address, and the port number.

- Peer: Enter the URL of an external proxy that will serve as an upstream cache peer for the MAAS built-in proxy. Machines provisioned by MAAS will be configured to use the MAAS built-in proxy to download APT packages, and this external proxy will be used as a peer for caching. By configuring an upstream cache peer, MAAS can leverage caching functionality to improve APT package download performance for provisioned machines. Be sure to provide the complete URL of the external proxy server, including the protocol (e.g., http:// or https://), the hostname or IP address, and the port number.

### Upstream DNS configuration

MAAS allows you to configure the upstream DNS settings for resolving domains not managed by MAAS. Navigate to *Settings* > *Network* > *DNS*. Enter the IP addresses of the upstream DNS servers in *Upstream DNS*. Separate multiple IP addresses with a space. For example, you can enter 8.8.8.8 to use Google's public DNS server.

This upstream DNS configuration is only used when MAAS is running its own DNS server. The provided IP addresses will be used as the value of 'forwarders' in the DNS server configuration.

### DNS delegation

MAAS allows for efficient DNS management, including the delegation of DNS zones. Delegation is typically used to direct traffic from a parent domain to a child domain, managed by different DNS servers. Below is a guide to configure DNS delegation in MAAS.

### Delegate a zone to MAAS

1. **External DNS Configuration:** In your external DNS server, create NS records for the subdomain that point to the MAAS region controller. For example, for the subdomain `dc1.mycompany.com`, create an NS record in your global DNS that delegates to MAAS.

2. **MAAS DNS Configuration:** Within MAAS, create an authoritative domain for `dc1.mycompany.com`. MAAS will then handle DNS requests for this subdomain.

### Delegate a zone from MAAS to another DNS server

1. **Create the Domain:** In MAAS, create a domain you wish to delegate, say `dc1.mycompany.com`, but set it as non-authoritative.

2. **Configure the NS Records:** In the MAAS domain, create NS records pointing to the DNS servers that will be authoritative for the subdomain.

3. **A/AAAA Records:** Ensure you have A or AAAA records for each DNS server to which you're delegating within the MAAS domain.

Remember that proper DNS delegation requires pointing NS records to the hostname of the authoritative DNS servers (A/AAAA records), not directly to IP addresses -- although using IP addresses can work in most cases.

### Enable DNSSEC validation of upstream zones
 
MAAS provides the option to enable DNSSEC (Domain Name System Security Extensions) validation for upstream zones. Navigate to *Settings* > *Network* > *DNS* and set *Enable DNSSEC validation of upstream zones* based on your requirements:

- Automatic (use default root key): Select this option to enable DNSSEC validation using the default root key. This is the recommended option as it simplifies the configuration and maintenance of DNSSEC.

- Yes (manually configured root key): Select this option if you have a specific root key that you want to use for DNSSEC validation. This allows you to manually configure and manage the root key used for validation.

- No (Disable DNSSEC; useful when upstream DNS is misconfigured): Select this option to disable DNSSEC validation. This option is useful when the upstream DNS is misconfigured or does not support DNSSEC properly.Automatic (use default root key): Select this option to enable DNSSEC validation using the default root key.

DNSSEC validation is only used when MAAS is running its own DNS server. The selected option will be used as the value of 'dnssec_validation' in the DNS server configuration.

### List of external networks allowed to use MAAS for DNS resolution

MAAS maintains a list of networks that are allowed to use MAAS for DNS resolution. You can add extra networks to this trusted ACL list, specifically networks that were not previously known. To add extra networks, navigate to *Settings* > *Network* > *DNS*. Enter the IP addresses or ACL (Access Control List) names into *List of external networks (not previously known) that will be allowed to use MAAS for DNS resolution*.

### NTP server configuration

MAAS allows you to configure NTP (Network Time Protocol) servers to be used as time references for MAAS itself, the machines deployed by MAAS, and devices utilising MAAS DHCP services. Navigate to *Settings* > *Network* > *NTP*, and enter the IP/hostname of external NTP servers into *Addresses of NTP servers*. The configured NTP servers will be used as time references for MAAS itself, the machines deployed by MAAS, and devices utilising MAAS DHCP services.

### Use external NTP servers only

MAAS provides the option to configure the use of external NTP servers exclusively. Navigate to *Settings* > *Network* > *NTP*, and enable *Use external NTP servers only*.

Enabling this option ensures that all relevant MAAS components, including region controller hosts, rack controller hosts, and deployed machines, will refer directly to the configured external NTP servers for time synchronisation. Disabling this option will result in a different hierarchy of NTP server references.

### Remote syslog server configuration

MAAS allows you to configure a remote syslog server to which log messages from enlisted, commissioned, tested, and deployed machines will be sent. Navigate to *Settings* > *Network* > *Syslog* and enter the syslog sever address into *Remote syslog server to forward machine logs*.

Once configured, MAAS will automatically set the remote syslog server on enlisted, commissioned, tested, and deployed machines to forward all log messages to the specified server. If you wish to restore the default behaviour of forwarding syslog to MAAS instead of a remote server, simply clear the configured value in this field. MAAS will revert to its default behaviour.

### Network discovery configuration

MAAS allows you to configure network discovery, which enables MAAS to observe networks attached to rack controllers using passive techniques such as listening to ARP requests and DNS advertisements. Navigate to *Settings* > *Network* > *Network discovery* and enable *Network discovery*.

### Active subnet mapping interval

MAAS provides the option to enable active subnet mapping, which involves scanning subnets at regular intervals to ensure accurate and complete discovery information. Enabling active subnet mapping helps ensure that the discovery information gathered by MAAS is up-to-date and accurate. Navigate to *Settings* > *Network* > *Network discovery* and set your desired *Active subnet mapping interval*.

## MAAS 3.3 (and below) UI

This page explains how to change MAAS settings for MAAS version 3.3 and below.

### General

The following options are found in *Settings* > *Configuration* > *General*.

Managing MAAS site identity is useful when you are running more than one MAAS instance - say,  *Test* and *Production* environments. This section also provides data collection and version notification options. 

- *MAAS name*: The "* MAAS name" is a text box that sets the text which appears at the bottom of every MAAS screen, in front of the version descriptor.

- *Google Analytics*: MAAS uses Google Analytics, Usabilla and Sentry Error Tracking to improve user experience. You can opt in or out of this service by setting or clearing this checkbox.

- *Release notification*: If you select this checkbox, MAAS will notify all users when new releases are available.

### Security

Choosing *Settings* > *Configuration* > *Security* provides instructions for enabling TLS with a certificate and a private key. This is a CLI-operation; use the listed command at the command line, after logging into your MAAS instance.

### Commissioning

The parameters under *Settings* > *Configuration* > *Commissioning* allow you to change the way machines are commissioned:

- *Default commissioning release*: You can choose the default Ubuntu release that will be used for commissioning from a drop-down menu.

- *Default minimum kernel version*: The default minimum kernel version used on all new and commissioned nodes. You can also choose this default from a drop-down menu.

- *IPMI username*: You can set the default IPMI username, which will control IPMI access to machines.

- *K_g BMC key*: Specify this key to encrypt all communication between IPMI clients and the BMC. Leave this blank for no encryption. 

- *IPMI privilege level*: You can choose the privilege level for IPMI access from a set of radio buttons (admin, operator, user).

### Deployment

*Settings* > *Configuration* > *Deployment* lets you configure machine deployment:

- *Default deployment OS*: You can choose the default operating system used for deployment from a drop-down list.

- *Default deployment OS release*: You can also choose the default OS release used for deployment, also from a drop-down.

- *Default hardware sync interval*: You can set the default hardware sync interval, in minutes.

### Kernel parameters

Under *Configuration* > *General* > *Kernel parameters*, you can set global boot that are always passed to the machine kernel.

### Users

*Settings* > *Users* MAAS gives you the ability to manage your users in a tabular format:

- *Add user button*: This button can be used to add a new user.

- *Sortable columns*: some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: Each table row also has an "Actions" column, which allows you to delete or edit the information in that row. Note that the delete and/or edit buttons may be greyed out (unavailable) based on your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular user in a longer list.

### Images

*Settings* > *Images* allows you to specify parameters that control different types of MAAS images.

### Ubuntu images

Under *Settings* > *Images* > *Ubuntu*, you can enable the installation of proprietary drives by selecting the appropriate checkbox.

### Windows images

*Settings* > *Images* > *Windows* allows you to specify the Windows KMS activation host. This is the FQDN or IP address of the host that provides the KMS Windows activation service, which is needed for Windows deployments that use KMS activation.

### VMWare images

If you are using VMWare images, *Settings* > *Images* > *VMware* offers several parameters that you can adjust:

- *VMware vCenter server FQDN or IP address*: the VMware vCenter server FQDN or IP address which is passed to a deployed VMware ESXi host.

- *VMware vCenter username*: the VMware vCenter server username which is passed to a deployed VMware ESXi host.

- *VMware vCenter password*: the VMware vCenter server password which is passed to a deployed VMware ESXi host.

- *VMware vCenter datacenter*: the VMware vCenter datacenter which is passed to a deployed VMware ESXi host.

### License keys

*Settings* > *License keys* gives you the ability to manage your product licenses in a tabular format:

- *Add license key button*: This button can be used to add a new license key.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: These action buttons allow you to delete or edit the information in that row. Note that the delete and/or edit buttons may be greyed out (unavailable) based on your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular license key in a longer list.

### Storage

Under *Settings* > *Storage*, you can set some parameters related to machine disks:

- *Default storage layout*: The default storage layout that is applied to a machine when it is commissioned.

- *Erase before releasing*: Checking this box forces users to always erase disks when releasing machines.

- *Use secure erase*: Check this box to use secure erase by default when erasing disks. This will only be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.

- *Use quick erase*: Check this box to use quick erase by default when erasing disks. This box is selected separately to provide a fallback for devices that do not support secure erase, should you have selected secure erase as the default method. Note that this is not a secure erase; it wipes only the beginning and end of each disk.

### Network

*Settings* > *Network* allows you to set several network defaults for MAAS machines.

### HTTP proxy

By choosing *Settings* > *Network* > *Proxy*, you can define the HTTP proxy used by MAAS to download images, and used by provisioned machines for APT and YUM packages. Your choices are (1) no proxy, (2) MAAS built-in proxy, (3) external proxy, or (4) peer proxy. If you choose external or peer proxy, you will be presented with a text box to specify the external proxy URL that the MAAS built-in proxy will use as an upstream cache peer. Note that machines will be configured to use MAAS' built-in proxy to download APT packages when external or peer proxies are specified.

### Upstream DNS

*Settings* > *Network* > *DNS* lets you set DNS parameters for your MAAS. Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses). This only applies when MAAS is running its own DNS server, since this value is used to define forwarding in the DNS server config. You can set the following parameters:

- *Enable DNSSEC validation*: If you wish to enable DNSSEC validation of upstream zones, you can choose the method from this drop-down list. This is only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config.

- *List of external networks*: You can also provide a list of external networks to be used for MAAS DNS resolution. MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows you to add extra, previously-unknown networks to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names.

### NTP service

Access the NTP service is controlled using *Settings* > *Network* > *NTP*. You can enter the address of NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS DHCP services. 

You can also instruct MAAS to *Use external NTP only*, so that all daemons and machines refer directly to the external NTP server (and not to each other). If this is not set, only region controller hosts will be configured to use those external NTP servers; rack controller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers.

### Syslog configuration

You can use *Settings* > *Network* > *Syslog* to specify a remote syslog server to which machine logs should be forwarded. MAAS will use this remote syslog server for all log messages when enlisting, commissioning, testing, and deploying machines. Conversely, clearing this value will restore the default behaviour of forwarding syslog entries to MAAS.

### Network discovery

*Settings* > *Network* > *Network discovery*, when enabled, will cause MAAS to use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets. You can set the *Active subnet mapping interval* by choosing a desired interval from a drop-down. When network discovery is enabled, each rack will scan subnets enabled for active mapping, which helps to ensure that discovery information is accurate and complete.

### Scripts

Under the section *Settings* > *Scripts*, MAAS provides a great deal of flexibility when dealing with commissioning and testing scripts.

### Commissioning scripts

*Settings* > *Scripts* > *Commissioning scripts* gives you the ability to manage machine commissioning scripts in a tabular format:

- *Upload script button*: This button can be used to upload a new commissioning script.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Expandable script contents*: Also note that individual script names are clickable, allowing you to expand that row to see the contents of the script.

- *Actions column*: Each table row has an "Actions" column, which allows you to delete the script in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular commissioning script in a longer list.

### Testing scripts

Similar to *Commissioning scripts*, the choices *Settings* > *Scripts* > *Testing scripts* give you the ability to manage your machines testing scripts in a tabular format:

- *Upload script button*: This button can be used to upload a new test script.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Expandable script contents*: Also note that individual script names are clickable, allowing you to expand that row to see the contents of the script.

- *Actions column*: Each table row has an "Actions" column, which allows you to delete the script in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular test script in a longer list.

### DHCP snippets

*Settings* > *DHCP snippets* lets you manage your DHCP snippets in a table:

- *Add snippet button*: This button can be used to add a new DHCP snippet.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Expandable snippets*: Also note that individual snippets are clickable, allowing you to expand that row to see the contents of that snippet.

- *Actions column*: Each table row has an "Actions" column, which allows you to edit delete the snippet in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular snippet in a longer list.

### Package repos

You can manage your MAAS repositories with the *Settings* > *Package repos* option. Referenced repos are listed in a table:

- *Add PPA button*: This button can be used to add a new PPA to the search path.

- *Add repository button*: This button can be used to add a new repository to the search path.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: Each table row also has an "Actions" column, which allows you to edit or delete the repository information in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular test script in a longer list.
## MAAS CLI

This page explains how to change MAAS configuration options with the MAAS CLI.

Assuming you have successfully logged into the MAAS CLI, you can access configuration values using the `maas $PROFILE maas set-config` command. This command is used to set MAAS configuration values.  This command accepts keyword arguments. You must pass each argument as a key-value pair, with an equals sign between the key and the value, like this:

```nohighlight
maas $PROFILE maas set-config key1=value1 key2=value key3=value3 ...
```

These keyword arguments must come after any positional arguments required by a specific command. The following configuration keywords are currently available:

- *active_discovery_interval*: Active subnet mapping interval. When enabled, each rack will scan subnets enabled for active mapping. This helps ensure discovery information is accurate and complete.
- *boot_images_auto_import*: Automatically import/refresh the boot images every 60 minutes.
- *boot_images_no_proxy*: Set no_proxy with the image repository address when MAAS is behind (or set with) a proxy. By default, when MAAS is behind (and set with) a proxy, it is used to download images from the image repository. In some situations (e.g. when using a local image repository) it doesn't make sense for MAAS to use the proxy to download images because it can access them directly. Setting this option allows MAAS to access the (local) image repository directly by setting the no_proxy variable for the MAAS env with the address of the image repository.
- *commissioning_distro_series*: Default Ubuntu release used for commissioning.
- *completed_intro*: Marks if the initial intro has been completed.
- *curtin_verbose*: Run the fast-path installer with higher verbosity. This provides more detail in the installation logs.
- *default_distro_series*: Default OS release used for deployment.
- *default_dns_ttl*: Default Time-To-Live for the DNS.        If no TTL value is specified at a more specific point this is how long DNS responses are valid, in seconds.
- *default_min_hwe_kernel*: Default Minimum Kernel Version.        The default minimum kernel version used on all new and commissioned nodes.
- *default_osystem*: Default operating system used for deployment.
- *default_storage_layout*: Default storage layout.        Storage layout that is applied to a node when it is commissioned.       Available choices are*: 'bcache' (Bcache layout), 'blank' (No storage (blank) layout), 'custom' (Custom layout (from commissioning storage config)), 'flat' (Flat layout), 'lvm' (LVM layout), 'vmfs6' (VMFS6 layout), 'vmfs7' (VMFS7 layout).
- *disk_erase_with_quick_erase*: Use quick erase by default when erasing disks..        This is not a secure erase; it wipes only the beginning and end of each disk.
- *disk_erase_with_secure_erase*: Use secure erase by default when erasing disks.        Will only be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.
- *dns_trusted_acl*: List of external networks (not previously known), that will be allowed to use MAAS for DNS resolution..        MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows to add extra networks (not previously known) to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names.
- *dnssec_validation*: Enable DNSSEC validation of upstream zones.        Only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config.
- *enable_analytics*: Enable Google Analytics in MAAS UI to shape improvements in user experience.
- *enable_disk_erasing_on_release*: Erase node disks prior to releasing.        Forces users to always erase disks when releasing.
- *enable_http_proxy*: Enable the use of an APT or YUM and HTTP/HTTPS proxy.        Provision nodes to use the built-in HTTP proxy (or user specified proxy) for APT or YUM. MAAS also uses the proxy for downloading boot images.
- *enable_third_party_drivers*: Enable the installation of proprietary drivers (i.e. HPVSA).
- *enlist_commissioning*: Whether to run commissioning during enlistment..        Enables running all built-in commissioning scripts during enlistment.
- *force_v1_network_yaml*: Always use the legacy v1 YAML (rather than Netplan format, also known as v2 YAML) when composing the network configuration for a machine..
- *hardware_sync_interval*: Hardware Sync Interval.        The interval to send hardware info to MAAS from hardware sync enabled machines, in systemd time span syntax.
- *http_proxy*: Proxy for APT or YUM and HTTP/HTTPS.        This will be passed onto provisioned nodes to use as a proxy for APT or YUM traffic. MAAS also uses the proxy for downloading boot images. If no URL is provided, the built-in MAAS proxy will be used.
- *kernel_opts*: Boot parameters to pass to the kernel by default.
- *maas_auto_ipmi_cipher_suite_id*: MAAS IPMI Default Cipher Suite ID.        The default IPMI cipher suite ID to use when connecting to the BMC via ipmitools        Available choices are*: '' (freeipmi-tools default), '12' (12 - HMAC-MD5::MD5-128::AES-CBC-128), '17' (17 - HMAC-SHA256::HMAC_SHA256_128::AES-CBC-128), '3' (3 - HMAC-SHA1::HMAC-SHA1-96::AES-CBC-128), '8' (8 - HMAC-MD5::HMAC-MD5-128::AES-CBC-128).
- *maas_auto_ipmi_k_g_bmc_key*: The IPMI K_g key to set during BMC configuration..        This IPMI K_g BMC key is used to encrypt all IPMI traffic to a BMC. Once set, all clients will REQUIRE this key upon being commissioned. Any current machines that were previously commissioned will not require this key until they are recommissioned.
- *maas_auto_ipmi_user*: MAAS IPMI user..        The name of the IPMI user that MAAS automatically creates during enlistment/commissioning.
- *maas_auto_ipmi_user_privilege_level*: MAAS IPMI privilege level.        The default IPMI privilege level to use when creating the MAAS user and talking IPMI BMCs        Available choices are*: 'ADMIN' (Administrator), 'OPERATOR' (Operator), 'USER' (User).
- *maas_auto_ipmi_workaround_flags*: IPMI Workaround Flags.        The default workaround flag (-W options) to use for ipmipower commands        Available choices are*: '' (None), 'authcap' (Authcap), 'endianseq' (Endianseq), 'forcepermsg' (Forcepermsg), 'idzero' (Idzero), 'integritycheckvalue' (Integritycheckvalue), 'intel20' (Intel20), 'ipmiping' (Ipmiping), 'nochecksumcheck' (Nochecksumcheck), 'opensesspriv' (Opensesspriv), 'sun20' (Sun20), 'supermicro20' (Supermicro20), 'unexpectedauth' (Unexpectedauth).
- *maas_internal_domain*: Domain name used by MAAS for internal mapping of MAAS provided services..        This domain should not collide with an upstream domain provided by the set upstream DNS.
- *maas_name*: MAAS name.
- *maas_proxy_port*: Port to bind the MAAS built-in proxy (default*: 8000).        Defines the port used to bind the built-in proxy. The default port is 8000.
- *maas_syslog_port*: Port to bind the MAAS built-in syslog (default*: 5247).        Defines the port used to bind the built-in syslog. The default port is 5247.
- *max_node_commissioning_results*: The maximum number of commissioning results runs which are stored.
- *max_node_installation_results*: The maximum number of installation result runs which are stored.
- *max_node_testing_results*: The maximum number of testing results runs which are stored.
- *network_discovery*: .        When enabled, MAAS will use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets.
- *node_timeout*: Time, in minutes, until the node times out during commissioning, testing, deploying, or entering rescue mode..        Commissioning, testing, deploying, and entering rescue mode all set a timeout when beginning. If MAAS does not hear from the node within the specified number of minutes the node is powered off and set into a failed status.
- *ntp_external_only*: Use external NTP servers only.        Configure all region controller hosts, rack controller hosts, and subsequently deployed machines to refer directly to the configured external NTP servers. Otherwise only region controller hosts will be configured to use those external NTP servers, rack controller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers.
- *ntp_servers*: Addresses of NTP servers.        NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS DHCP services.
- *prefer_v4_proxy*: Sets IPv4 DNS resolution before IPv6.        If prefer_v4_proxy is set, the proxy will be set to prefer IPv4 DNS resolution before it attempts to perform IPv6 DNS resolution.
- *prometheus_enabled*: Enable sending stats to a prometheus gateway..        Allows MAAS to send statistics to Prometheus. This requires the 'prometheus_push_gateway' to be set.
- *prometheus_push_gateway*: Address or hostname of the Prometheus push gateway..        Defines the address or hostname of the Prometheus push gateway where MAAS will send data to.
- *prometheus_push_interval*: Interval of how often to send data to Prometheus (default*: to 60 minutes)..        The internal of how often MAAS will send stats to Prometheus in minutes.
- *promtail_enabled*: Enable streaming logs to Promtail..        Whether to stream logs to Promtail
- *promtail_port*: TCP port of the Promtail Push API..        Defines the TCP port of the Promtail push API where MAAS will stream logs to.
- *release_notifications*: Enable or disable notifications for new MAAS releases..
- *remote_syslog*: Remote syslog server to forward machine logs.        A remote syslog server that MAAS will set on enlisting, commissioning, testing, and deploying machines to send all log messages. Clearing this value will restore the default behaviour of forwarding syslog to MAAS.
- *subnet_ip_exhaustion_threshold_count*: If the number of free IP addresses on a subnet becomes less than or equal to this threshold, an IP exhaustion warning will appear for that subnet.
- *tls_cert_expiration_notification_enabled*: Notify when the certificate is due to expire.        Enable/Disable notification about certificate expiration.
- *tls_cert_expiration_notification_interval*: Certificate expiration reminder (days).        Configure notification when certificate is due to expire in (days).
- *upstream_dns*: Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses).        Only used when MAAS is running its own DNS server. This value is used as the value of 'forwarders' in the DNS server config.
- *use_peer_proxy*: Use the built-in proxy with an external proxy as a peer.        If enable_http_proxy is set, the built-in proxy will be configured to use http_proxy as a peer proxy. The deployed machines will be configured to use the built-in proxy.
- *use_rack_proxy*: Use DNS and HTTP metadata proxy on the rack controllers when a machine is booted..        All DNS and HTTP metadata traffic will flow through the rack controller that a machine is booting from. This isolated region controllers from machines.
- *vcenter_datacenter*: VMware vCenter datacenter.        VMware vCenter datacenter which is passed to a deployed VMware ESXi host.
- *vcenter_password*: VMware vCenter password.        VMware vCenter server password which is passed to a deployed VMware ESXi host.
- *vcenter_server*: VMware vCenter server FQDN or IP address.        VMware vCenter server FQDN or IP address which is passed to a deployed VMware ESXi host.
- *vcenter_username*: VMware vCenter username.        VMware vCenter server username which is passed to a deployed VMware ESXi host.
- *windows_kms_host*: Windows KMS activation host.        FQDN or IP address of the host that provides the KMS Windows activation service. (Only needed for Windows deployments using KMS activation.)
