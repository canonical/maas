Local Mirroring of Boot Images
==============================

Boot images are delivered to MAAS via the simplestreams protocol.  It is
useful in some situations, such as testing, to mirror the images locally
so that you don't need to repeatedly pull them down over a slower Internet
link.

First, install the required packages on the host where you wish to store
the mirrored images::

  $ sudo apt-get install simplestreams ubuntu-cloudimage-keyring apache2

Now you can pull the images over using the mirroring tools for simplestreams.
This example gets the daily trusty (14.04) and precise (12.04) images for the
amd64/generic and amd64/hwe-t architectures::

  $ sudo sstream-mirror --keyring=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg http://maas.ubuntu.com/images/ephemeral-v2/daily/ /var/www/html/maas/images/ephemeral-v2/daily 'arch=amd64' 'subarch~(generic|hwe-t)' 'release~(trusty|precise)' --max=1

This may take a while as hundreds of megabytes will be downloaded.

The images will be written to the local disk and you can verify their
presence by browsing to
``http://<server>/maas/images/ephemeral-v2/daily/streams/v1/index.sjson``
(replace ``<server>`` with your own server's name).

It is a good idea to configure a ``cron`` job to repeat this import on a
regular basis to keep your mirror up-to-date.


Configuring MAAS to use the local mirror
----------------------------------------

You can do this using the API or the web UI.  To do this via the API you
can use the ``maas`` (see :doc:`maas-cli`) command, logged in as the admin
user::

  $ maas <profile> boot-sources create url=http://<server>keyring_filename=/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg

And then initiate the download with::

  $ maas <profile> boot-resources import

See :doc:`bootsources` for more detail.

In the web UI, browse to the Settings tab as the admin user and scroll down
to the "Boot Images" section.  There you will find input boxes for the
Sync URL and the keyring path, which should be set as the values in the API
example above.

The import is initiated by browsing to the Images tab and following the
instructions on that page.
