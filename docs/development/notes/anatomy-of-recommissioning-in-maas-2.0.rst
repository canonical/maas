.. -*- mode: rst -*-

****************************************
Anatomy of a recommissioning in MAAS 2.0
****************************************


**2016-04-30, mpontillo**

You may be asking yourself, "what exactly happens during commissioning"
in MAAS?

Well, maybe you're not. ;-) But as part of a recent bug I triaged, I
wanted to find out for myself. So I analyzed a packet capture during a
recent recommission. I (painstakingly) looked at almost every TCP
stream, to see what status messages cloud-init was posting, and when.

See the timeline later. Also note that you can use a capture filter of
"syslog" to see the syslog of the commissioning node, even if the syslog
packets are being discarded by the server!


Notes on capturing the preseed
------------------------------

If you want to see the preseed and you have a packet capture, the
easiest way I found is to use *File > Export Objects > HTTP...* in
Wireshark. You can export them all if you want, but there will be a lot
of data. The very first one is the preseed; once exported, it will have
a filename like ``%3fop=get_preseed``. See an example below, based on
what it was in the packet trace I looked at. If you dig deeper, you can
also see things like the downloaded ``.deb`` files, the commissioning
scripts tarball, the output of each commissioning script, and each JSON
request/reply.

Similarly, if you need to do some triage based on the files that were
TFTP'd, there is also *File > Export Objects > TFTP*.

.. code-block:: yaml

  #cloud-config
  apt_proxy: http://192.168.100.10:8000/
  datasource:
    MAAS: {consumer_key: 7uCdQBcxmKWMrpaJ8W, metadata_url: 'http://192.168.100.10/MAAS/metadata/',
      token_key: nYLwP4pYm5q2aqvCzU, token_secret: GppvznAv6cueKnFKV6tKGqxdraNEzkjJ}
  power_state: {condition: test ! -e /tmp/block-poweroff, delay: now, mode: poweroff,
    timeout: 3600}
  reporting:
    maas: {consumer_key: 7uCdQBcxmKWMrpaJ8W, endpoint: 'http://192.168.100.10/MAAS/metadata/status/4y3h7r',
      token_key: nYLwP4pYm5q2aqvCzU, token_secret: GppvznAv6cueKnFKV6tKGqxdraNEzkjJ,
      type: webhook}
  rsyslog:
    remotes: {maas: '192.168.100.10:514'}
  system_info:
    package_mirrors:
    - arches: [i386, amd64]
      failsafe: {primary: 'http://archive.ubuntu.com/ubuntu', security: 'http://security.ubuntu.com/ubuntu'}
      search:
        primary: ['http://archive.ubuntu.com/ubuntu']
        security: ['http://archive.ubuntu.com/ubuntu']
    - arches: [default]
      failsafe: {primary: 'http://ports.ubuntu.com/ubuntu-ports', security: 'http://ports.ubuntu.com/ubuntu-ports'}
      search:
        primary: ['http://ports.ubuntu.com/ubuntu-ports']
        security: ['http://ports.ubuntu.com/ubuntu-ports']


Timeline
--------


(0) PXE BIOS loads
==================

Current time: 9.2s

(This was on a ``qemu-kvm`` virtual machine.)

- Sends a *DHCP Discover* packet from ``0.0.0.0`` to
  ``255.255.255.255``.

  - Sends option 60 (vendor class identifier):
    ``PXEClient:Arch:00000:UNDI:002001``

  - Sends numerous options related to netboot, including 66 (tftp server
    name), 67 (bootfile name), 129 through 135 (PXE), 175 (Etherboot)
    and 203 (?).

- Sends ICMPv6 router solicitation packets to the ``ff02::2`` multicast
  address (which corresponds to multicast MAC ``33:33:00:00:00:02``) to
  check for an IPv6 router.


(1) MAAS DHCP offers an IP address
==================================

Current time: 10.2s

- The offer is made from the dynamic range for the subnet the node
  booted from.

- The *DHCP Offer* packet has a 30 second lease time, specifies a boot
  filename of ``pxelinux.0``, and a ``next-server`` IP address of the
  MAAS rack.


(2) PXE BIOS sends a DHCP ACK
=============================

Current time: 12.1s


(3) PXE BIOS announces itself to the world
==========================================

First with an ARP for the ``next-server``, and then it begins TFTP
requests:

- First for ``pxelinux.0``.

- Next, various combinations of ``ldlinux.c32``,
  ``/boot/isolinux/ldlinux.c32``, ``/isolinux/ldlinux.c32``, (et cetera)
  until it finds ``/syslinux/ldlinux.c32``.

- Next, ``pxelinux.cfg/<uuid>`` (fails), then
  ``pxelinux.cfg/01-<mac-address>`` (succeeds)

  The configuration file ultimately contains::

    DEFAULT execute
    LABEL execute
    SAY Booting under MAAS direction...
    SAY nomodeset iscsi_target_name=iqn.2004-05.com.ubuntu:maas:ephemeral-ubuntu-amd64-generic-xenial-release iscsi_target_ip=<rack-ip> iscsi_target_port=3260 iscsi_initiator=<node-hostname> ip=::::<node-hostname>:BOOTIF ro root=/dev/disk/by-path/ip-<rack-ip>:3260-iscsi-iqn.2004-05.com.ubuntu:maas:ephemeral-ubuntu-amd64-generic-xenial-release-lun-1 overlayroot=tmpfs cloud-config-url=http://<region-ip>/MAAS/metadata/latest/by-id/<node-system-id>/?op=get_preseed log_host=<maas-ip> log_port=514
    KERNEL ubuntu/amd64/generic/xenial/release/boot-kernel

    INITRD ubuntu/amd64/generic/xenial/release/boot-initrd

    APPEND nomodeset iscsi_target_name=iqn.2004-05.com.ubuntu:maas:ephemeral-ubuntu-amd64-generic-xenial-release iscsi_target_ip=<rack-ip> iscsi_target_port=3260 iscsi_initiator=<node-hostname> ip=::::<node-hostname>:BOOTIF ro root=/dev/disk/by-path/ip-<rack-ip>:3260-iscsi-iqn.2004-05.com.ubuntu:maas:ephemeral-ubuntu-amd64-generic-xenial-release-lun-1 overlayroot=tmpfs cloud-config-url=http://<region-ip>/MAAS/metadata/latest/by-id/<node-system-id>/?op=get_preseed log_host=<maas-ip> log_port=514

    IPAPPEND 2

- Next, TFTP requests ``ubuntu/amd64/generic/xenial/release/boot-kernel``
  (takes ~1 second)

- Next, TFTP requests
  ``ubuntu/amd64/generic/xenial/release/boot-initrd`` (takes ~3 seconds)

Start time: 21.1s
End time: 25.2s


(4) The commissioning node boots the kernel and loads the initrd
================================================================

Current time: 31.5s

This is evidenced by a new *DHCP Discover* request (followed by an
offer, request, and ack) this time without any of the netboot options.

The node also sends a multicast listener report to ``ff02::16``,
followed by a neighbor solicitation for its link-local address (this is
for IPv6 duplicate address detection purposes; 1 second later when
duplicate address detection completes, it sends a router soliciation
message from the address it originally probed with the neighbor
soliciation).


(5) An iSCSI session begins for the ephemeral image
===================================================

This will persist during the remainder of the commissioning, so it's
best to filter out with a display filter if you're viewing the
commissioning in Wireshark (``not tcp.port = 3260``).


(6) A DNS query (A/AAAA) is issued for ntp.ubuntu.com
=====================================================

Current time: 35.4s


(7) The node ARPs for the router
================================

Current time: 35.7s

So that it can try to reach ntp.ubuntu.com, probably!


(8) The node tries to look up an A record for "ubuntu"
======================================================

Current time: 35.7s

Not sure why (because that's its hostname?) DNS returns "no such name".


(9) cloud-init requests its metadata
====================================

::

  GET /MAAS/metadata/latest/by-id/<system-id>/?op=get_preseed HTTP/1.1
  Host: <region-ip>
  User-Agent: Cloud-Init/0.7.7
  Accept: */*
  Connection: keep-alive
  Accept-Encoding: gzip, deflate


(10) cloud-init posts its first status, and searches for a data source
======================================================================

Example::

  POST /MAAS/metadata/status/<system-id> HTTP/1.1
  Host: <region-ip>
  User-Agent: python-requests/2.9.1
  Authorization: OAuth oauth_nonce="62097414331357635371461972194", oauth_timestamp="1461972194", oauth_version="1.0", oauth_signature_method="PLAINTEXT", oauth_consumer_key="7uCdQBcxmKWMrpaJ8W", oauth_token="nYLwP4pYm5q2aqvCzU", oauth_signature="%26GppvznAv6cueKnFKV6tKGqxdraNEzkjJ"
  Accept: */*
  Content-Length: 171
  Connection: keep-alive
  Accept-Encoding: gzip, deflate

cloud-init continues to post status throughout the process, such as::

  {"description": "attempting to read from cache [trust]", "name": "init-network/check-cache", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no cache found", "name": "init-network/check-cache"}

  {"description": "searching for network data from DataSourceNoCloudNet", "name": "init-network/search-NoCloudNet", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no network data found from DataSourceNoCloudNet", "name": "init-network/search-NoCloudNet"}

  {"description": "searching for network data from DataSourceConfigDriveNet", "name": "init-network/search-ConfigDriveNet", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no network data found from DataSourceConfigDriveNet", "name": "init-network/search-ConfigDriveNet"}

  {"description": "searching for network data from DataSourceOpenNebulaNet", "name": "init-network/search-OpenNebulaNet", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}
  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no network data found from DataSourceOpenNebulaNet", "name": "init-network/search-OpenNebulaNet"}

  {"description": "searching for network data from DataSourceAzureNet", "name": "init-network/search-AzureNet", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no network data found from DataSourceAzureNet", "name": "init-network/search-AzureNet"}

  {"description": "searching for network data from DataSourceAltCloud", "name": "init-network/search-AltCloud", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no network data found from DataSourceAltCloud", "name": "init-network/search-AltCloud"}

  {"description": "searching for network data from DataSourceOVFNet", "name": "init-network/search-OVFNet", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "no network data found from DataSourceOVFNet", "name": "init-network/search-OVFNet"}

  {"description": "searching for network data from DataSourceMAAS", "name": "init-network/search-MAAS", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

Aha! It seems to have found the MAAS data source.


(11) cloud-init requests metadata from MAAS
===========================================

Current time: 39.5s

Sends a GET request::

  GET /MAAS/metadata//2012-03-01/meta-data/instance-id HTTP/1.1

(along with its OAuth *Authorization* header.)

Followed by the following requests::

  GET /MAAS/metadata//2012-03-01/meta-data/local-hostname HTTP/1.1
  GET /MAAS/metadata//2012-03-01/meta-data/instance-id HTTP/1.1
  GET /MAAS/metadata//2012-03-01/meta-data/public-keys HTTP/1.1
  GET /MAAS/metadata//2012-03-01/user-data HTTP/1.1

(The result of this request is a binary blob — presumably the
commissioning scripts.)

Continued::

  POST /MAAS/metadata/status/4y3h7r HTTP/1.1
  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "found network data from DataSourceMAAS", "name": "init-network/search-MAAS"}


(12) cloud-init begins consuming the user-data
==============================================

Current time: 39.8s

It posts more status::

  {"description": "reading and applying user-data", "name": "init-network/consume-user-data", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "reading and applying user-data", "name": "init-network/consume-user-data"}

  {"description": "reading and applying vendor-data", "name": "init-network/consume-vendor-data", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "reading and applying vendor-data", "name": "init-network/consume-vendor-data"}

  {"description": "running config-migrator with frequency always", "name": "init-network/config-migrator", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-migrator ran successfully", "name": "init-network/config-migrator"}

  {"description": "running config-ubuntu-init-switch with frequency once-per-instance", "name": "init-network/config-ubuntu-init-switch", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-ubuntu-init-switch ran successfully", "name": "init-network/config-ubuntu-init-switch"}

  {"description": "running config-seed_random with frequency once-per-instance", "name": "init-network/config-seed_random", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-seed_random with frequency once-per-instance", "name": "init-network/config-seed_random", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-bootcmd with frequency always", "name": "init-network/config-bootcmd", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-bootcmd ran successfully", "name": "init-network/config-bootcmd"}

  {"description": "running config-write-files with frequency once-per-instance", "name": "init-network/config-write-files", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-write-files ran successfully", "name": "init-network/config-write-files"}

  {"description": "running config-growpart with frequency always", "name": "init-network/config-growpart", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-growpart ran successfully", "name": "init-network/config-growpart"}

  {"description": "running config-resizefs with frequency always", "name": "init-network/config-resizefs", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-resizefs ran successfully", "name": "init-network/config-resizefs"}

  {"description": "running config-set_hostname with frequency once-per-instance", "name": "init-network/config-set_hostname", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-set_hostname with frequency once-per-instance", "name": "init-network/config-set_hostname", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-update_hostname with frequency always", "name": "init-network/config-update_hostname", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-update_hostname ran successfully", "name": "init-network/config-update_hostname"}

  {"description": "running config-update_etc_hosts with frequency always", "name": "init-network/config-update_etc_hosts", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-update_etc_hosts with frequency always", "name": "init-network/config-update_etc_hosts", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-ca-certs with frequency once-per-instance", "name": "init-network/config-ca-certs", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-ca-certs with frequency once-per-instance", "name": "init-network/config-ca-certs", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-rsyslog with frequency once-per-instance", "name": "init-network/config-rsyslog", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"description": "running config-rsyslog with frequency once-per-instance", "name": "init-network/config-rsyslog", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

(I suppose this means from about ~42 seconds onward in the capture,
we'll see rsyslog entries, too.)

::

  {"description": "running config-users-groups with frequency once-per-instance", "name": "init-network/config-users-groups", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-users-groups ran successfully", "name": "init-network/config-users-groups"}

  {"description": "running config-ssh with frequency once-per-instance", "name": "init-network/config-ssh", "event_type": "start", "timestamp": 1461972194.3447218, "origin": "cloudinit"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "config-ssh ran successfully", "name": "init-network/config-ssh"}

  {"origin": "cloudinit", "event_type": "finish", "result": "SUCCESS", "timestamp": 1461972194.3447218, "description": "searching for network datasources", "name": "init-network"}

[stream 61 seems to be an iSCSI conversation]

::

  {"event_type": "start", "description": "running config-emit_upstart with frequency always", "origin": "cloudinit", "name": "modules-config/config-emit_upstart", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-emit_upstart", "description": "config-emit_upstart ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-disk_setup with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-disk_setup", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-disk_setup", "description": "config-disk_setup ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-mounts with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-mounts", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-mounts", "description": "config-mounts ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-ssh-import-id with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-ssh-import-id", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-ssh-import-id", "description": "config-ssh-import-id ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-locale with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-locale", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-locale", "description": "config-locale ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-set-passwords with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-set-passwords", "timestamp": 1461972199.9740574}

  {"event_type": "start", "description": "running config-set-passwords with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-set-passwords", "timestamp": 1461972199.9740574}

  {"event_type": "start", "description": "running config-snappy with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-snappy", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-snappy", "description": "config-snappy ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-grub-dpkg with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-grub-dpkg", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-grub-dpkg", "description": "config-grub-dpkg ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-apt-pipelining with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-apt-pipelining", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-apt-pipelining", "description": "config-apt-pipelining ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-apt-configure with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-apt-configure", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-apt-configure", "description": "config-apt-configure ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-package-update-upgrade-install with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-package-update-upgrade-install", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-package-update-upgrade-install", "description": "config-package-update-upgrade-install ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-fan with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-fan", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-fan", "description": "config-fan ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-landscape with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-landscape", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-landscape", "description": "config-landscape ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-timezone with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-timezone", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-timezone", "description": "config-timezone ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-lxd with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-lxd", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-lxd", "description": "config-lxd ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-puppet with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-puppet", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-puppet", "description": "config-puppet ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-chef with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-chef", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-chef", "description": "config-chef ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-salt-minion with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-salt-minion", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-salt-minion", "description": "config-salt-minion ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-mcollective with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-mcollective", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-mcollective", "description": "config-mcollective ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-disable-ec2-metadata with frequency always", "origin": "cloudinit", "name": "modules-config/config-disable-ec2-metadata", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-disable-ec2-metadata", "description": "config-disable-ec2-metadata ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-runcmd with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-runcmd", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-runcmd", "description": "config-runcmd ran successfully", "origin": "cloudinit"}

  {"event_type": "start", "description": "running config-byobu with frequency once-per-instance", "origin": "cloudinit", "name": "modules-config/config-byobu", "timestamp": 1461972199.9740574}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config/config-byobu", "description": "config-byobu ran successfully", "origin": "cloudinit"}

  {"result": "SUCCESS", "event_type": "finish", "timestamp": 1461972199.9740574, "name": "modules-config", "description": "running modules for config", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-rightscale_userdata with frequency once-per-instance", "name": "modules-final/config-rightscale_userdata", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-rightscale_userdata ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-rightscale_userdata", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-scripts-vendor with frequency once-per-instance", "name": "modules-final/config-scripts-vendor", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-scripts-vendor ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-scripts-vendor", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-scripts-per-once with frequency once", "name": "modules-final/config-scripts-per-once", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-scripts-per-once ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-scripts-per-once", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-scripts-per-boot with frequency always", "name": "modules-final/config-scripts-per-boot", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-scripts-per-boot ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-scripts-per-boot", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-scripts-per-instance with frequency once-per-instance", "name": "modules-final/config-scripts-per-instance", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-scripts-per-instance ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-scripts-per-instance", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-scripts-user with frequency once-per-instance", "name": "modules-final/config-scripts-user", "origin": "cloudinit", "event_type": "start"}

[stream 120 is http://archive.ubuntu.com//ubuntu/dists/xenial/InRelease]

[stream 121 is a duplicate request which returns Not Modified]

[stream 122 through stream 125 is updates, backport, security]

Jumping around a bit, finally when the filter is set to ``tcp.stream eq
171``, some commissioning output is posted::

  POST /MAAS/metadata//2012-03-01/ HTTP/1.1
  Accept-Encoding: identity
  Connection: close
  Host: ...
  User-Agent: Python-urllib/3.5
  Authorization: OAuth ...

  --IgeOqQzkofxNCLEJhNqXEZVCsEXdZgS
  Content-Disposition: form-data; name="op"

  signal
  --IgeOqQzkofxNCLEJhNqXEZVCsEXdZgS
  Content-Disposition: form-data; name="script_result"

  0
  --IgeOqQzkofxNCLEJhNqXEZVCsEXdZgS
  Content-Disposition: form-data; name="status"

  WORKING
  --IgeOqQzkofxNCLEJhNqXEZVCsEXdZgS
  Content-Disposition: form-data; name="error"

  finished 00-maas-03-install-lldpd [3/9]: 0
  --IgeOqQzkofxNCLEJhNqXEZVCsEXdZgS
  Content-Disposition: form-data; name="00-maas-03-install-lldpd.out"; filename="00-maas-03-install-lldpd.out"
  Content-Type: application/octet-stream

  Reading package lists...
  Building dependency tree...
  Reading state information...
  The following additional packages will be installed:
    libjansson4
  Suggested packages:
    snmpd
  The following NEW packages will be installed:
    libjansson4 lldpd
  0 upgraded, 2 newly installed, 0 to remove and 17 not upgraded.
  Need to get 171 kB of archives.
  After this operation, 577 kB of additional disk space will be used.
  Get:1 http://archive.ubuntu.com//ubuntu xenial/main amd64 libjansson4 amd64 2.7-3 [26.9 kB]
  Get:2 http://archive.ubuntu.com//ubuntu xenial/universe amd64 lldpd amd64 0.7.19-1 [145 kB]
  Fetched 171 kB in 0s (0 B/s)
  Selecting previously unselected package libjansson4:amd64.
  (Reading database ...
  (Reading database ... 5%
  (Reading database ... 10%
  (Reading database ... 15%
  (Reading database ... 20%
  (Reading database ... 25%
  (Reading database ... 30%
  (Reading database ... 35%
  (Reading database ... 40%
  (Reading database ... 45%
  (Reading database ... 50%
  (Reading database ... 55%
  (Reading database ... 60%
  (Reading database ... 65%
  (Reading database ... 70%
  (Reading database ... 75%
  (Reading database ... 80%
  (Reading database ... 85%
  (Reading database ... 90%
  (Reading database ... 95%
  (Reading database ... 100%
  (Reading database ... 25719 files and directories currently installed.)
  Preparing to unpack .../libjansson4_2.7-3_amd64.deb ...
  Unpacking libjansson4:amd64 (2.7-3) ...
  Selecting previously unselected package lldpd.
  Preparing to unpack .../lldpd_0.7.19-1_amd64.deb ...
  Unpacking lldpd (0.7.19-1) ...
  Processing triggers for libc-bin (2.23-0ubuntu3) ...
  Processing triggers for man-db (2.7.5-1) ...
  Processing triggers for ureadahead (0.100.0-19) ...
  Processing triggers for systemd (229-4ubuntu4) ...
  Setting up libjansson4:amd64 (2.7-3) ...
  Setting up lldpd (0.7.19-1) ...
  Processing triggers for libc-bin (2.23-0ubuntu3) ...
  Processing triggers for ureadahead (0.100.0-19) ...
  Processing triggers for systemd (229-4ubuntu4) ...

  --IgeOqQzkofxNCLEJhNqXEZVCsEXdZgS--
  HTTP/1.1 200 OK
  Date: Fri, 29 Apr 2016 23:23:40 GMT
  Server: TwistedWeb/16.0.0
  Content-Type: text/plain
  X-Maas-Api-Hash: 330962629c417d2f60a5e18c279ca1db7b710cf3
  X-Frame-Options: SAMEORIGIN
  Vary: Authorization,Cookie,Accept-Encoding
  Connection: close
  Transfer-Encoding: chunked

  2
  OK
  0

This behavior continues until all the scripts are finished.

Finally, in stream 191, the scripts finish::

  {"timestamp": 1461972207.09086, "description": "config-scripts-user ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-scripts-user", "origin": "cloudinit"}

and cloud-init continues with other things::

  {"timestamp": 1461972207.09086, "description": "running config-ssh-authkey-fingerprints with frequency once-per-instance", "name": "modules-final/config-ssh-authkey-fingerprints", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-ssh-authkey-fingerprints ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-ssh-authkey-fingerprints", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-keys-to-console with frequency once-per-instance", "name": "modules-final/config-keys-to-console", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-keys-to-console ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-keys-to-console", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-phone-home with frequency once-per-instance", "name": "modules-final/config-phone-home", "origin": "cloudinit", "event_type": "start"}

By now MAAS has revoked the ``oauth_token`` and returns *Authorization
Error: Invalid access token: nYLwP4pYm5q2aqvCzU* but cloud-init keeps
posting::

  {"timestamp": 1461972207.09086, "description": "config-phone-home ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-phone-home", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-final-message with frequency always", "name": "modules-final/config-final-message", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-final-message ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-final-message", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running config-power-state-change with frequency once-per-instance", "name": "modules-final/config-power-state-change", "origin": "cloudinit", "event_type": "start"}

  {"timestamp": 1461972207.09086, "description": "config-power-state-change ran successfully", "event_type": "finish", "result": "SUCCESS", "name": "modules-final/config-power-state-change", "origin": "cloudinit"}

  {"timestamp": 1461972207.09086, "description": "running modules for final", "event_type": "finish", "result": "SUCCESS", "name": "modules-final", "origin": "cloudinit"}


(13) Finished
=============

Total time: 130s
