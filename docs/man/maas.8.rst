maas
----


Usage
^^^^^

maas  [-h, --help] createadmin | changepassword | shell


Description
^^^^^^^^^^^

The `maas` command is part of Canonical's Metal As A Service software. It is
derived from and can be used similarly to the `django-admin` command, and must
be run with root privileges.

For the end user, there are only three subcommands of interest.

**createadmin**
  This subcommand is used to create a superuser for the
  MAAS install. The suggested username is "root". This command usually only
  needs to be run when installing MAAS for the first time.

**changepassword**
  This subcommand is used to change the superuser password
  for the MAAS install. You will be prompted to enter a new password, and then
  enter it once again to verify.

**shell**
  This subcommand may be useful for debugging installed systems. It
  will open a new python shell environment with the correct django environment
  for working with the installed MAAS software.


Further Documentation
^^^^^^^^^^^^^^^^^^^^^

For more documentation of MAAS, please see https://maas.ubuntu.com/docs


See Also
^^^^^^^^

`maas-cli`
