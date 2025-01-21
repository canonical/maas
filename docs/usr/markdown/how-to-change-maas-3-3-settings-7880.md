This page explains how to change MAAS settings for MAAS version 3.3 and below.

## General

The following options are found in *Settings* > *Configuration* > *General*.

Managing MAAS site identity is useful when you are running more than one MAAS instance - say,  *Test* and *Production* environments. This section also provides data collection and version notification options. 

- *MAAS name*: The "* MAAS name" is a text box that sets the text which appears at the bottom of every MAAS screen, in front of the version descriptor.

- *Google Analytics*: MAAS uses Google Analytics, Usabilla and Sentry Error Tracking to improve user experience. You can opt in or out of this service by setting or clearing this checkbox.

- *Release notification*: If you select this checkbox, MAAS will notify all users when new releases are available.

## Security

Choosing *Settings* > *Configuration* > *Security* provides instructions for enabling TLS with a certificate and a private key. This is a CLI-operation; use the listed command at the command line, after logging into your MAAS instance.

## Commissioning

The parameters under *Settings* > *Configuration* > *Commissioning* allow you to change the way machines are commissioned:

- *Default commissioning release*: You can choose the default Ubuntu release that will be used for commissioning from a drop-down menu.

- *Default minimum kernel version*: The default minimum kernel version used on all new and commissioned nodes. You can also choose this default from a drop-down menu.

- *IPMI username*: You can set the default IPMI username, which will control IPMI access to machines.

- *K_g BMC key*: Specify this key to encrypt all communication between IPMI clients and the BMC. Leave this blank for no encryption. 

- *IPMI privilege level*: You can choose the privilege level for IPMI access from a set of radio buttons (admin, operator, user).

## Deployment

*Settings* > *Configuration* > *Deployment* lets you configure machine deployment:

- *Default deployment OS*: You can choose the default operating system used for deployment from a drop-down list.

- *Default deployment OS release*: You can also choose the default OS release used for deployment, also from a drop-down.

- *Default hardware sync interval*: You can set the default hardware sync interval, in minutes.

## Kernel parameters

Under *Configuration* > *General* > *Kernel parameters*, you can set global boot that are always passed to the machine kernel.

## Users

*Settings* > *Users* MAAS gives you the ability to manage your users in a tabular format:

- *Add user button*: This button can be used to add a new user.

- *Sortable columns*: some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: Each table row also has an "Actions" column, which allows you to delete or edit the information in that row. Note that the delete and/or edit buttons may be greyed out (unavailable) based on your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular user in a longer list.

## Images

*Settings* > *Images* allows you to specify parameters that control different types of MAAS images.

## Ubuntu images

Under *Settings* > *Images* > *Ubuntu*, you can enable the installation of proprietary drives by selecting the appropriate checkbox.

## Windows images

*Settings* > *Images* > *Windows* allows you to specify the Windows KMS activation host. This is the FQDN or IP address of the host that provides the KMS Windows activation service, which is needed for Windows deployments that use KMS activation.

## VMWare images

If you are using VMWare images, *Settings* > *Images* > *VMware* offers several parameters that you can adjust:

- *VMware vCenter server FQDN or IP address*: the VMware vCenter server FQDN or IP address which is passed to a deployed VMware ESXi host.

- *VMware vCenter username*: the VMware vCenter server username which is passed to a deployed VMware ESXi host.

- *VMware vCenter password*: the VMware vCenter server password which is passed to a deployed VMware ESXi host.

- *VMware vCenter datacenter*: the VMware vCenter datacenter which is passed to a deployed VMware ESXi host.

## License keys

*Settings* > *License keys* gives you the ability to manage your product licenses in a tabular format:

- *Add license key button*: This button can be used to add a new license key.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: These action buttons allow you to delete or edit the information in that row. Note that the delete and/or edit buttons may be greyed out (unavailable) based on your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular license key in a longer list.

## Storage

Under *Settings* > *Storage*, you can set some parameters related to machine disks:

- *Default storage layout*: The default storage layout that is applied to a machine when it is commissioned.

- *Erase before releasing*: Checking this box forces users to always erase disks when releasing machines.

- *Use secure erase*: Check this box to use secure erase by default when erasing disks. This will only be used on devices that support secure erase. Other devices will fall back to full wipe or quick erase depending on the selected options.

- *Use quick erase*: Check this box to use quick erase by default when erasing disks. This box is selected separately to provide a fallback for devices that do not support secure erase, should you have selected secure erase as the default method. Note that this is not a secure erase; it wipes only the beginning and end of each disk.

## Network

*Settings* > *Network* allows you to set several network defaults for MAAS machines.

## HTTP proxy

By choosing *Settings* > *Network* > *Proxy*, you can define the HTTP proxy used by MAAS to download images, and used by provisioned machines for APT and YUM packages. Your choices are (1) no proxy, (2) MAAS built-in proxy, (3) external proxy, or (4) peer proxy. If you choose external or peer proxy, you will be presented with a text box to specify the external proxy URL that the MAAS built-in proxy will use as an upstream cache peer. Note that machines will be configured to use MAAS' built-in proxy to download APT packages when external or peer proxies are specified.

## Upstream DNS

*Settings* > *Network* > *DNS* lets you set DNS parameters for your MAAS. Upstream DNS used to resolve domains not managed by this MAAS (space-separated IP addresses). This only applies when MAAS is running its own DNS server, since this value is used to define forwarding in the DNS server config. You can set the following parameters:

- *Enable DNSSEC validation*: If you wish to enable DNSSEC validation of upstream zones, you can choose the method from this drop-down list. This is only used when MAAS is running its own DNS server. This value is used as the value of 'dnssec_validation' in the DNS server config.

- *List of external networks*: You can also provide a list of external networks to be used for MAAS DNS resolution. MAAS keeps a list of networks that are allowed to use MAAS for DNS resolution. This option allows you to add extra, previously-unknown networks to the trusted ACL where this list of networks is kept. It also supports specifying IPs or ACL names.

## NTP service

Access the NTP service is controlled using *Settings* > *Network* > *NTP*. You can enter the address of NTP servers, specified as IP addresses or hostnames delimited by commas and/or spaces, to be used as time references for MAAS itself, the machines MAAS deploys, and devices that make use of MAAS DHCP services. 

You can also instruct MAAS to *Use external NTP only*, so that all daemons and machines refer directly to the external NTP server (and not to each other). If this is not set, only region controller hosts will be configured to use those external NTP servers; rack controller hosts will in turn refer to the regions' NTP servers, and deployed machines will refer to the racks' NTP servers.

## Syslog configuration

You can use *Settings* > *Network* > *Syslog* to specify a remote syslog server to which machine logs should be forwarded. MAAS will use this remote syslog server for all log messages when enlisting, commissioning, testing, and deploying machines. Conversely, clearing this value will restore the default behaviour of forwarding syslog entries to MAAS.

## Network discovery

*Settings* > *Network* > *Network discovery*, when enabled, will cause MAAS to use passive techniques (such as listening to ARP requests and mDNS advertisements) to observe networks attached to rack controllers. Active subnet mapping will also be available to be enabled on the configured subnets. You can set the *Active subnet mapping interval* by choosing a desired interval from a drop-down. When network discovery is enabled, each rack will scan subnets enabled for active mapping, which helps to ensure that discovery information is accurate and complete.

## Scripts

Under the section *Settings* > *Scripts*, MAAS provides a great deal of flexibility when dealing with commissioning and testing scripts.

## Commissioning scripts

*Settings* > *Scripts* > *Commissioning scripts* gives you the ability to manage machine commissioning scripts in a tabular format:

- *Upload script button*: This button can be used to upload a new commissioning script.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Expandable script contents*: Also note that individual script names are clickable, allowing you to expand that row to see the contents of the script.

- *Actions column*: Each table row has an "Actions" column, which allows you to delete the script in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular commissioning script in a longer list.

## Testing scripts

Similar to *Commissioning scripts*, the choices *Settings* > *Scripts* > *Testing scripts* give you the ability to manage your machines testing scripts in a tabular format:

- *Upload script button*: This button can be used to upload a new test script.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Expandable script contents*: Also note that individual script names are clickable, allowing you to expand that row to see the contents of the script.

- *Actions column*: Each table row has an "Actions" column, which allows you to delete the script in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular test script in a longer list.

## DHCP snippets

*Settings* > *DHCP snippets* lets you manage your DHCP snippets in a table:

- *Add snippet button*: This button can be used to add a new DHCP snippet.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Expandable snippets*: Also note that individual snippets are clickable, allowing you to expand that row to see the contents of that snippet.

- *Actions column*: Each table row has an "Actions" column, which allows you to edit delete the snippet in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular snippet in a longer list.

## Package repos

You can manage your MAAS repositories with the *Settings* > *Package repos* option. Referenced repos are listed in a table:

- *Add PPA button*: This button can be used to add a new PPA to the search path.

- *Add repository button*: This button can be used to add a new repository to the search path.

- *Sortable columns*: Note that some of the column headings are clickable, allowing you to sort those columns. These are "three click" sorts: ascending, descending, and none.

- *Actions column*: Each table row also has an "Actions" column, which allows you to edit or delete the repository information in that row, depending upon your role.

Note that if the table becomes longer than one screen will accommodate, paging buttons will appear at the bottom of the screen. A search bar is also provided to help you locate a particular test script in a longer list.