.. -*- mode: rst -*-

.. _hardware-enablement-kernels:

=================================
Using hardware-enablement kernels
=================================

.. note::

  This feature is available in MAAS versions 1.5 and above.

MAAS allows you to use hardware enablement kernels when booting nodes
that require them.

What are hardware-enablement kernels?
-------------------------------------

Brand new hardware gets released all the time. We want that hardware to
work well wih Ubuntu and MAAS, even if it was released after the latest
release of MAAS or Ubuntu. Hardware Enablement (HWE) is all about keeping
pace with the new hardware.

Ubuntu's solution to this is to offer newer kernels for older releases.
There are at least two kernels on offer for Ubuntu releases: the
"generic" kernel -- i.e. the kernel released with the current series --
and the Hardware Enablement kernel, which is the most recent kernel
release.

There are separate HWE kernels for each release of Ubuntu, referred to
as ``hwe-<release letter>``. So, the 14.04 / Trusty Tahr HWE kernel is
called ``hwe-t``, the 12.10 / Quantal Quetzal HWE kernel is called
``hwe-q`` and so on. This allows you to use newer kernels with older
releases, for example running Precise with a Saucy (hwe-s) kernel.

For more information see the `LTS Enablement Stack`_ page on the Ubuntu
wiki.

.. _LTS Enablement Stack:
   https://wiki.ubuntu.com/Kernel/LTSEnablementStack

Importing hardware-enablement kernels
-------------------------------------

Hardware-enablement kernels need to be imported to a cluster controller
before that cluster's nodes can use them.

In order to import HWE kernels to a cluster controller you need to edit
the controller's ``/etc/maas/bootresources.yaml`` file, and update the
subarches that you want to import, like this::

  boot:
    storage: "/var/lib/maas/boot-resources/"

    sources:
      - path: "http://maas.ubuntu.com/images/ephemeral-v2/releases/"
        keyring: "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"
        selections:
          - release: "precise"
            arches: ["i386", "amd64"]
            subarches: ["generic", "hwe-q", "hwe-r", "hwe-s", "hwe-t"]
            labels: ["release"]

Once you've updated ``bootresources.yaml``, you can tell the cluster to
re-import its boot images using the ``maas`` command (You will need to
:ref:`be logged in to the API first <api-key>`)::

 $ maas <profile-name> node-group import-boot-images \
   <cluster-controller-uuid>

You can also tell the cluster controller to re-import its boot images by
clicking the ``Import boot images`` button in the ``Clusters`` page of
the MAAS web UI.

Using hardware-enablement kernels in MAAS
-----------------------------------------

A MAAS administrator can choose to use HWE kernels on a per-node basis
in MAAS.

The quickest way to do this is using the MAAS command, like this::

  $ maas <profile-name> node update <system-id>
    architecture=amd64/hwe-t

If you specify an architecture that doesn't exist (e.g.
``amd64/hwe-z``), the ``maas`` command will return an error.


It's also possible to use HWE kernels from the MAAS web UI, by visiting
the Node's page and clicking ``Edit node``. Under the Architecture field,
you will be able to select any HWE kernels that have been imported onto
that node's cluster controller.
