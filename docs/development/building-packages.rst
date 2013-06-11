Building Ubuntu packages of MAAS
================================

Using a virtual machine from a cloud provider seems to be easier and
less hassle than using a local VM or LXC container, but the same
recipe ought to apply.

You need to build on the same OS that the package will be targeted to,
so use a Precise instance to make packages for Precise, for example.

#. Start up an instance, log in, and bring it up to date::

     sudo apt-get update && sudo apt-get upgrade

#. Get the appropriate packaging branch::

     bzr branch lp:~maas-maintainers/maas/packaging{...}

   The `MAAS Maintainers <https://launchpad.net/~maas-maintainers>`_
   own all the `official MAAS branches`_.

#. Move into the new branch directory.

#. Check that all the build dependencies are installed. The
   dependencies are defined in ``debian/control``::

     fgrep -i build-depends -A 10 debian/control

   This will yield, for example::

     Build-Depends: debhelper (>= 8.1.0~),
                    dh-apport,
                    po-debconf,
                    python (>= 2.7),
                    python-distribute,
                    python-django
     Standards-Version: 3.9.3
     ...

   Install these dependencies::

     sudo apt get install \
         debhelper dh-apport po-debconf python \
         python-distribute python-django

#. Edit ``debian/changelog`` so it contains:

   * the right upstream revision number in the version,

   * the series you're building for; if ``UNRELEASED`` appears in the
     first entry, ``s/UNRELEASED/precise/`` (or the series you want),

   * the name and email address that correspond to the PGP key you
     want to use to sign the package; these appear near the end of the
     topmost entry.

#. Build::

     bzr bd -S -- -uc -us

   The latter options tell it not to sign the files. You need to do
   this because the remote machine will not have your GPG key.

#. Sign the build on your local machine::

     debsign -r user@host '~/*.changes'

   where ``user@host`` is an SSH string for accessing the remote
   instance. This will scp the changes and dsc locally, sign them, and
   put them back.

#. On the remote instance you can optionally upload to a PPA::

     dput -fu ppa:maas-maintainers/name-of-ppa *.changes

.. _official MAAS branches: https://code.launchpad.net/~maas-maintainers
