Additional Configuration
========================

.. _manual-dhcp:

Manual DHCP configuration
-------------------------

There are some circumstances under which you may not wish the master MAAS 
worker to handle DHCP for the network. In these instances, the existing DHCP
server for the network will need its configuration altered to allow MAAS to
enlist and control nodes automatically.

At the very least the next-server should point to the MAAS controller host
address and the filename should be set to pxelinux.0

The configuration entry may look something like this::

   subnet 192.168.122.0 netmask 255.255.255.0 {
       next-server 192.168.122.136;
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

For individual nodes it is a straightforward task to select the Ubuntu
series to install from the user interface. When either adding a node 
manually, or on the node page when the node has been automatically
discovered but before it is accepted, there is a drop down menu to select 
the version of Ubuntu you wish to install.

.. image:: media/series.*

The menu will always list all the currently available series according
to which images are available.

Using the maas-cli command
^^^^^^^^^^^^^^^^^^^^^^^^^^

It is also possible to select a series using the maas-cli command. This
can be done on a per node basis with::

 $ maas-cli <profile> node update <system_id> distro_series="<value>"

Where the string contains one of the valid, available distro series, or
is empty for the default value.


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
system overall. If your nodes however cannot freely access the internet,
the supplied ntp server is not going to be very useful, and you may
find it better to run an ntp service on the MAAS controller and substitute
`ntp.ubuntu.com` in the last line for something else.

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
maximum size. The swap partition ranges from 64 mb to 3 times the system's
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

For more information on preseed option, you should refer to 
`the official Ubuntu documentation <https://help.ubuntu.com/12.04/installation-guide/i386/preseed-contents.html>`_

.. note::
  Future versions of MAAS are likely to replace this type of automatic 
  installation with a different installer.

