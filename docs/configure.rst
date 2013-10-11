Additional Configuration
========================


.. _manual-dhcp:

Manual DHCP configuration
-------------------------

There are some circumstances under which you may not wish the master
MAAS worker to handle DHCP for the network. In these instances, the
existing DHCP server for the network will need its configuration
altered to allow MAAS to enlist and control nodes automatically.

At the very least the filename should be set to pxelinux.0.

The configuration entry may look something like this::

   subnet 192.168.122.0 netmask 255.255.255.0 {
       filename "pxelinux.0";
       option subnet-mask 255.255.255.0;
       option broadcast-address 192.168.122.255;
       option domain-name-servers 192.168.122.136;
       range dynamic-bootp 192.168.122.5 192.168.122.135;
   }


.. _ssl:

SSL Support
-----------

If you want secure access to your MAAS web UI/API, you need to do a few
things. First, turn on SSL support in Apache::

  $ sudo a2enmod ssl

Ensure that the Apache config file from ``etc/maas/maas-http.conf`` is
included in ``/etc/apache2/conf.d/``, then edit
``/etc/maas/maas_local_settings.py`` and change DEFAULT_MAAS_URL so that it
uses https instead of http.

Now, restart Apache::

  $ sudo service apache2 restart

At this point you will be able to access the MAAS web server using https but
the default SSL certificate is insecure.  Please generate your own and then
edit ``/etc/apache2/conf.d/maas-http.conf`` to set the location of the
certificate.


Choosing a series to install
----------------------------

You may have some specific reason to choose a particular version of Ubuntu
to install on your nodes, perhaps based around package availability,
hardware support or some other reason.
 
It is possible to choose a specific series from those available in a 
number of ways.

From the user interface
^^^^^^^^^^^^^^^^^^^^^^^

The web-based user interface makes it easy to select which Ubuntu series you
wish to install on an individual node. When either adding a node 
manually, or on the node page when the node has been automatically
discovered but before it is accepted, there is a drop down menu to select 
the version of Ubuntu you wish to install.

.. image:: media/series.*

The menu will always list all the currently available series according
to which boot images are available.

Using the maas-cli command
^^^^^^^^^^^^^^^^^^^^^^^^^^

It is also possible to select a series using the maas-cli command. This
can be done on a per node basis with::

 $ maas-cli <profile> node update <system_id> distro_series="<value>"

Where the string contains one of the valid, available distro series (e.g.
"precise") or is empty for the default value.


.. _preseed:

Altering the Preseed file
-------------------------

.. warning::
  Do not try to alter the preseed files if you don't have a good 
  understanding of what you are doing. Altering the installed version 
  of Ubuntu can prevent MAAS from working as intended, and may have
  security and stability consequences. 

When MAAS commissions a node it installs a version of Ubuntu. The 
installation is performed using a 'preseed' file, which is 
effectively a list of answers to the questions you would get were 
you to run the installer manually.
The preseed file used by MAAS is carefully made so that the 
target node can be brought up and do all the jobs expected of it.
However, in exceptional circumstances, you may wish to alter the 
pressed file to work around some issue.
There are actually two preseed files, stored here::

  /usr/share/maas/preseeds/generic
  /usr/share/maas/preseeds/preseed-master

The generic file actually references the preseed-master file, and is 
used to set conditional parameters based on the type of series and 
architecture to install as well as to define the minimum set of install
packages and to tidy up the PXE boot process if that has been used for 
the node. Unless you have a specific need to change where install 
packages come from, you should not need to edit this file.

For the more usual sorts of things you may wish to change, you should 
edit the preseed-master file. For example, depending on your network
you may wish to change the clock settings::

    # Local clock (set to UTC and use ntp)
    d-i     clock-setup/utc boolean true
    d-i     clock-setup/ntp boolean true
    d-i     clock-setup/ntp-server  string ntp.ubuntu.com

Having consistent clocks is very important to the working of your MAAS
system overall. If your nodes however cannot freely access the Internet,
the supplied NTP server is not going to be very useful, and you may
find it better to run an ntp service on the MAAS controller and change
the `ntp.ubuntu.com` in the last line for a more appropriate server.

One thing you may wish to alter in the preseed file is the disk
partitioning. This is a simple recipe that creates a swap partition and 
uses the rest of the disk for one large root filesystem::

	partman-auto/text/atomic_scheme ::

	500 10000 1000000 ext3
		$primary{ }
		$bootable{ }
		method{ format }
		format{ }
		use_filesystem{ }
		filesystem{ ext3 }
		mountpoint{ / } .

	64 512 300% linux-swap
		method{ swap }
		format{ } .


Here the root partition must be at least 500 mb, and has effectively no
maximum size. The swap partition ranges from 64 MB to 3 times the system's
ram.
Adding `$bootable{ }` to make the partition bootable, and $primary{ }
marks it as the primary partition. The other specifiers used are:

*method{ format }*
	Used to make the partition be formatted. For swap partitions,
	change it to "swap". To create a new partition but do not
	format it, change "format" to "keep" (such a partition can be
	used to reserve for future use some disk space).
*format{ }*
	Also needed to make the partition be formatted.
*use_filesystem{ }*
	Specifies that the partition has a filesystem on it.
*filesystem{ ext3 }*
	Specifies the filesystem to put on the partition.
*mountpoint{ / }*
	Where to mount the partition.

For more information on preseed options, you should refer to 
`the official Ubuntu documentation 
<https://help.ubuntu.com/12.04/installation-guide/i386/preseed-contents.html>`_

.. note::
  Future versions of MAAS are likely to replace this type of automatic 
  installation with a different installer.


Installing additional clusters
------------------------------

In an environment comprising large numbers of nodes, it is likely that you will
want to organise the nodes on a more distributed basis. The standard install of
the MAAS region controller includes a cluster controller, but it is 
possible to add additional cluster controllers to the configuration, as 
shown in the diagram below:

.. image:: media/orientation_architecture-diagram.*

Each cluster controller will need to run on a separate Ubuntu server. 
Installing and configuring the software is straightforward though:: 

  $ sudo apt-get install maas-cluster-controller

This meta-package will install all the basic requirements of the system. 
However, you may also wish or need to run DHCP and/or DNS services, in
which case you should also specify these::

  $ sudo apt-get install maas-cluster-controller maas-dhcp maas-dns

Configuring the cluster controller
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once the packages are installed, the cluster controller needs to know
where to look for the region controller. This is achieved using `dpkg` to 
configure the software::

  $ dpkg-reconfigure maas-cluster-controller

.. image:: media/cluster-config.*

The configuration script should then bring up a screen where you can 
enter the IP address of the region controller. Additionally, you will need
to run the ``maas-import-pxe-files`` script to install the distro image files
locally for commissioning::

  $ maas-cli maas node-groups import-boot-images

...and optionally set up the DHCP and DNS for 
the cluster by either:

*Using the web UI*
  Follow the instructions at :doc:`cluster-configuration` to
  use the web UI to set up your cluster controller.

*Using the command line client*
  First :ref:`logging in to the API <api-key>` and then
  :ref:`following this procedure <cli-dhcp>` 


Client-side DNS configuration
-----------------------------

When using a third party tool such as ``juju`` it will need to be able to
resolve the hostnames that the MAAS API returns to it.  In order for this to
happen, *client-side DNS* must be configured to point to MAAS's DNS
server.  Generally speaking, this is a simple case of adding the following
line to the ``/etc/resolv.conf`` file on your client host::

  nameserver <IP OF MAAS DNS HOST>

replacing the <IP OF MAAS DNS HOST> with the actual IP address of the host
running the MAAS DNS server.

However, for hosts using the ``resolvconf`` package, please read its
documentation for more information.
