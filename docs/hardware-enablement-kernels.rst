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


Booting hardware-enablement kernels
-----------------------------------

MAAS imports hardware-enablement kernels along with its generic boot images,
but as different "sub-architectures" to the default "generic" one.

So, for example, a common server might have architecture and sub-architecture
of ``amd64/generic``, but some newer system chassis which doesn't become
fully functional with the default kernel for Ubuntu 14.04 Trusty Tahr, for
example, may require ``amd64/hwe-t``.

The quickest way to make a node use a hardware-enablement kernel is by using
the MAAS command, like this::

  $ maas <profile-name> node update <system-id>
    architecture=amd64/hwe-t

If you specify an architecture that doesn't exist (e.g.  ``amd64/hwe-zz``),
the ``maas`` command will return an error.

It's also possible to use HWE kernels from the MAAS web UI, by visiting
the Node's page and clicking ``Edit node``. Under the Architecture field,
you will be able to select any HWE kernels that have been imported onto
that node's cluster controller.
