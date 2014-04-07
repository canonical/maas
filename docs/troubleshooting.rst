********************
MAAS Troubleshooting
********************

Some parts of MAAS may still be a little confusing, and sometimes you might be
trying to do things that are just plain impossible. This section covers some of
the most commonly encountered problems and tries its best to make them gone.

.. contents:: Contents
 :depth: 1
 :local:


Nodes hang on "Commissioning"
=============================


Possible Cause: Timing issues
-----------------------------

Various parts of MAAS rely on OAuth to negotiate a connection to nodes. If the
current time reported by the hardware clock on your node differs significantly
from that on the MAAS server, the connection will not be made.

**SOLUTION:** Check that the hardware clocks are consistent, and if necessary,
adjust them. This can usually be done from within the system BIOS, without
needing to install an OS


Possible Cause: Network drivers
-------------------------------

Sometimes the hardware can boot from PXE, but fail to load correct drivers when
booting the received image. This is sometimes the case when no open source
drivers are available for the network hardware.

**SOLUTION:** The best fix for this problem is to install a Linux-friendly
network adaptor. It *is* theoretically possible to modify the boot image to
include proprietary drivers, but it is not a straightforward task.


Nodes fail to PXE boot
======================


Possible Cause: Using an incorrectly configured VM
--------------------------------------------------

Some Virtual Machine setups include emulation of network hardware that does not
support PXE booting, and in most setups, you will need to explicitly set up the
VM to boot via PXE.

**SOLUTION**: Consult the VM docs for details of PXE booting.


Possible Cause: DHCP conflict
-----------------------------

If you are using MAAS in a setup with an existing DHCP, *DO NOT SET UP THE MAAS
DHCP SERVER* as this will cause no end of confusion to the rest of your network
and most likely won't discover any nodes either.

**SOLUTION**: You will need to either:

* Configure your existing DHCP server to point to the MAAS server.

  or

* Enlist nodes using Avahi, which is the preferred option. For a quick guide to
  this, please see :ref:`enlist-via-boot-media`.


Can't log in to node
====================

Sometimes you may wish to login directly to a node on your system. If
you have set up Juju and MAAS, the attached nodes will automatically
receive existing ssh keys and sets up ssh on the node to authenticate
via key, so you can just login with no password from the server.
There is also an option in the MAAS web interface to add new ssh keys
to the nodes (via Preferences in the drop down menu which appears when
clicking your username in the top-right of the page).


Forgot MAAS superuser password
==============================

As long as you have sudo privileges, this is not a disaster. You can
use the ``maas`` command to change the password for the MAAS superuser
on the MAAS server:

    ``sudo maas changepassword root``


Need to reconfigure server IP address
=====================================

If you made a mistake during setup or you just need to reconfigure your MAAS
server, you can simply run the setup again:

    ``sudo dpkg-reconfigure maas-region-controller``


Can't find MAAS webpage
=======================

The default webpage is located at ``http://<hostname>/MAAS/``. If you can't
access it, there are a few things to try:

  #. Check that the webserver is running - By default the web interface uses
     Apache, which runs under the service name *apache2*. To check it, on the
     MAAS server box you can run ``sudo /etc/init.d/apache2 status``.
  #. Check that the hostname is correct - It may seem obvious, but check that
     the hostname is being resolved properly. Try running a browser (even a text
     mode one like lynx) on the same box as the MAAS server and navigating to
     the page. If that doesn't work, try ``http://127.0.0.1/MAAS/``, which will 
     always point at the local server.
  #. If you are still getting "404 - Page not found" errors, check that the MAAS
     web interface has been installed in the right place. There should be a file
     present called /usr/share/maas/maas/urls.py

Debugging ephemeral image
=========================

Backdoor (add a login) to ephemeral images
------------------------------------------

If you cannot login to an instance, you might have to "backdoor it" in order
to see what is going wrong. Scott Moser wrote a simple utility that injects a
user and password into an image. Here's how to add a 'backdoor' user with a
password to your images::

 bzr branch lp:~maas-maintainers/maas/backdoor-image

 imgs=$(echo var/lib/maas/ephemeral/*/*/*/*/*.img)
 for img in $imgs; do
     [ -f "$img.dist" ] || cp -a --sparse=always $img $img.dist
 done

 for img in $imgs; do
     sudo ./backdoor-image -v --user=backdoor --password-auth --password=ubuntu
 done

Inside the ephemeral image
--------------------------

Important files for debugging (Someone is likely to ask you for these
things to help debug)::

 /var/log/cloud-init.log
 /var/log/boot.log
 /var/log/cloud-init-output.log

After enlistment or commissioning, the user-data from maas instructs the system
to power off. To stop that from happening, you can just create a file in /tmp::

 touch /tmp/block-poweroff

MAAS credentials
----------------

MAAS credentials can be found in 2 places:

#. from the cmdline you'll see a ``url=`` or ``cloud-config-url=``
   parameter. You can get the cloud-config from that url, which will have
   credentials::

    $ sed -n 's,.*url=\([^ ]*\).*,\1,p' /proc/cmdline
    http://10.55.60.194/MAAS/metadata/latest/enlist-preseed/?op=get_enlist_preseed

#. from ``/etc/cloud/cloud.cfg.d/91_kernel_cmdline_url``. The file was pulled
   from ``url=`` parameter by cloud-init::

    $ sudo cat /etc/cloud/cloud.cfg.d/91_kernel_cmdline

MAAS datasource
---------------

The cloud-init datasource for MAAS can be invoked as a 'main' for debugging
purposes. To do so, you need to know the url for the MAAS datasource and a
config file that contains credentials::

 cfg=$(echo /etc/cloud/cloud.cfg.d/*_cmdline_url.cfg)
 echo $cfg /etc/cloud/cloud.cfg.d/91_kernel_cmdline_url.cfg

Now get the metadata_url from there::

 url=$(sudo awk '$1 == "metadata_url:" { print $2 }' $cfg)
 echo $url http://10.55.60.194/MAAS/metadata/enlist

Invoke the client /usr/share/pyshared/cloudinit/sources/DataSourceMAAS.py
The client has --help Usage also, but here is an example of how to use it::

 $ maasds="/usr/share/pyshared/cloudinit/sources/DataSourceMAAS.py"
 $ sudo python $maasds --config=$cfg get $url
 == http://10.55.60.194/MAAS/metadata/enlist ==
 2012-03-01
 latest
 $ sudo python $maasds --config=$cfg get $url/latest/meta-data/local-hostname
 maas-enlisting-node
