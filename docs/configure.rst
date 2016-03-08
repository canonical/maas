Additional Configuration
========================


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

Using the maas command
^^^^^^^^^^^^^^^^^^^^^^

It is also possible to select a series using the maas command. This
can be done on a per node basis with::

 $ maas <profile> machine update <system_id> distro_series="<value>"

Where the string contains one of the valid, available distro series (e.g.
"trusty") or is empty for the default value.


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

  /etc/maas/preseeds/curtin_userdata

The preseed file is used to customize the installation of a machine
based on different options. Users can set early_commands or late_commands
according to what they need, or customize it based on nodes, architecture
and other variables. The preseeds offers a concept that will allow users
to configure it as required. This is based on a node's ::

    node.system_id
    node.hostname
    node.domain
    node.owner
    node.bios_boot_method
    node.osystem
    node.distro_series
    node.architecture
    node.min_hwe_kernel
    node.hwe_kernel
    node.zone
    node.cpu_count
    node.memory

You can configure the preseed to add late_commands. For example,
you can configure the preseed to install a package based on the hostname,
and after the installation has been completed::

    late_commands:
    {{if node.hostname == 'node01'}}
        package_install: ["curtin", "in-target", "--", "apt-get", "-y", "install", "mysql"]
    {{endif}}


Installing Additional Rack Controllers
--------------------------------------

In an environment comprising large numbers of nodes, it is likely that you will
want to organise the nodes on a more distributed basis. The standard install of
the MAAS region controller includes a rack controller, but it is
possible to add additional rack controllers to the configuration, as
shown in the diagram below:

.. image:: media/orientation_architecture-diagram.*

Each rack controller will need to run on a separate Ubuntu server.
Installing and configuring the software is straightforward though::

  $ sudo apt-get install maas-rack-controller

This meta-package will install all the basic requirements of the system.


Configuring the Rack Controller
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Follow the instructions at :doc:`rack-configuration` to configure
additional Rack Controllers.


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
