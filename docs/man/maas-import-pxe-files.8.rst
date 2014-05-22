maas-import-pxe-files
---------------------

USAGE
^^^^^

maas-import-pxe-files [-h, --help]

DESCRIPTION
^^^^^^^^^^^

This is a helper script for MAAS (Metal As A Service). It downloads operating
system images, prepares them for use by MAAS nodes, and makes them available
for nodes to boot over the network through TFTP, iSCSI, and SMB as
appropriate.

The imports are normally performed automatically once a week, and can also
be triggered from the user interface or API (see below).  The script is an
alternative way of doing this, but the UI/API/scheduled way is preferred.
There are several differences between the script and these other ways of
running the imports.  See :ref:`script_vs_ui` below.

Images that are already in place are kept unchanged, unless the
version in the upstream archive has since been updated.  Only new data is
downloaded, so running this script frequently should not be more costly
than running it only rarely.


.. _script_vs_ui:

Script vs UI/API
^^^^^^^^^^^^^^^^

We recommend triggering manual imports through the UI or API over the
``maas-import-pxe-files`` script.  However there may be circumstances where
you might prefer the command-line script, in which case there are several
differences you need to be aware of:

* The command-line script must run on a cluster controller.  All other ways
  of running the imports are triggered on the region controller, and this can
  be done remotely.
* Running the command-line script on a cluster controller imports images only
  on that cluster controller.
* The command-line script must run as ``root``.  When MAAS itself performs
  imports, it runs them under the ``maas`` user.  Files will be written with
  ``root`` ownership, which may introduce permissions problems for the regular
  MAAS-triggered imports.
* If you run the command-line script using ``sudo``, be aware that it will
  modify state under ``$HOME/.gnupg``.  Since ``sudo`` does not change
  ``$HOME`` by default, this may result in ``root`` becoming the owner of some
  GPG files in your home directory.
* The command-line script completes once the imports are done, but at that
  point the region controller may not have been notified of newly available
  boot images yet.  There may be a wait of up to 5 minutes.  When MAAS itself
  triggers the imports, this notification is triggered immediately when the
  imports finish.


Importing from the UI
^^^^^^^^^^^^^^^^^^^^^

To trigger imports from the browser user interface, log in to your MAAS as an
administrator using a web browser, click the "Clusters" tab at the top of the
page to go to the Clusters page, and click "Import boot images."  This will
start imports on all cluster controllers simultaneously.

The same thing can also be done through the region-controller API, or through
the command-line interface.  The API and command-line interface also support
importing images for one particular cluster.


Configuration
^^^^^^^^^^^^^

Downloaded images are stored in ``/var/lib/maas/boot-resources``.  In order to
know what to download, you must pass the script a list of image "sources," in
the form of a YAML-encoded list.

Each "source" defines a Simplestreams repository location (``url``) from
which images can be downloaded; a ``keyring`` for validating index and image
signatures from that location; and a series of filters (``selections``)
specifying which images should be downloaded from that source.

Each "selection" can contain any of the following constraints:

* ``release``: Operating system release, e.g. ``trusty`` for Ubuntu 14.04.
* ``arches``: List of CPU architectures, e.g. ``amd64``, ``armhf``, ``i386``,
  etc.
* ``subarches``: List of "sub-architectures" for more specific system
  architecture requirements.  Typically ``generic``, but may be e.g. ``hwe-p``
  for hardware which on Ubuntu 12.04 Precise Pangolin still requires special
  hardware-enablement kernels.
* ``labels``: List of release labels, such as ``release`` or ``beta1``.  For
  normal use, specify ``release``.

For any of these filter items, an asterisk (``*``) denotes "match any value."
To match all available architectures, for example, specify an architecture
value of ``"*"`` in the ``arches`` list.

Here's an example of an import source description::

    - url "http://maas.ubuntu.com/images/ephemeral-v2/releases/"
      keyring: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
      selections:
        - release: "precise"
          arches: ["i386", "amd64"]
          subarches: ["generic"]
          labels: ["release"]
        - release: "trusty"
          arches: ["*"]
          subarches: ["generic"]
          labels: ["release"]

This uses one source, but imports multiple kinds of images from that source:
Ubuntu 12.04 ("precise") release images for the i386 and amd64 architectures,
plus Ubuntu 14.04 ("trusty") images for all supported architectures.


Further Documentation
^^^^^^^^^^^^^^^^^^^^^

Full MAAS documentation is at https://maas.ubuntu.com/docs

Imports through the browser interface are described at
http://maas.ubuntu.com/docs/install.html#import-the-boot-images


See Also
^^^^^^^^

`maas-region-admin`, `maas`
