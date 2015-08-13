.. -*- mode: rst -*-

.. _hardware-enablement-kernels:

=================================
Using hardware-enablement kernels
=================================

.. note::

  As of MAAS 1.9 this feature is configured by setting the hwe_kernel variable
  instead of the architecture variable.

MAAS allows you to use hardware enablement kernels when booting nodes
with Ubuntu that require them.

What are hardware-enablement kernels?
-------------------------------------

Brand new hardware gets released all the time. We want that hardware to
work well with Ubuntu and MAAS, even if it was released after the latest
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

MAAS imports hardware-enablement kernels along with its generic boot
images. These hardware-enablement kernels are specified by using min_hwe_kernel
or hwe_kernel variables.

The min_hwe_kernel variable is used to instruct MAAS to ensure the release to
be deployed uses a kernel version at or above the value of min_hwe_kernel. For
example if min_hwe_kernel is set to hwe-t when deploying any release before
Trusty the hwe-t kernel will be used. For any release after Trusty the default
kernel for that release will be used. If hwe-t or newer is not availible for
the specified release MAAS will not allow that release to be deployed and throw
an error.

min_hwe_kernel can be set by running the command::

  $ maas <profile-name> node update <system-id>
    min_hwe_kernel=hwe-<release letter>

It's also possible to set the min_hwe_kernel from the MAAS web UI, by visiting
the Node's page and clicking ``Edit node``. Under the Minimum Kernel field, you
will be able to select any HWE kernels that have been imported onto that node's
cluster controller.

You can also set the hwe_kernel during deployment. MAAS checks that the
specified kernel is avalible for the release specified before deploying the
node. You can set the hwe_kernel when deploying in the web interface or by
using the command::

  $ maas <profile-name> node start <system-id> distro_series=<distro>
  hwe_kernel=hwe-<release letter>
