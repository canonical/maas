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
