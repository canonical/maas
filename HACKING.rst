.. -*- mode: rst -*-

************
Hacking MAAS
************


Coding style
============

MAAS follows the `Launchpad Python Style Guide`_, except where it gets
Launchpad specific, and where it talks about `method naming`_. MAAS
instead adopts `PEP-8`_ naming in all cases, so method names should
usually use the ``lowercase_with_underscores`` form.

.. _Launchpad Python Style Guide:
  https://dev.launchpad.net/PythonStyleGuide

.. _method naming:
  https://dev.launchpad.net/PythonStyleGuide#Naming

.. _PEP-8:
  http://www.python.org/dev/peps/pep-0008/


Prerequisites
=============

Container
^^^^^^^^^

There's a configure-lxd-profile script in utilities, that will set
up a LXD profile that is configured properly.


Dependencies
^^^^^^^^^^^^

You can grab MAAS's code manually from Launchpad but Git_ makes it
easy to fetch the last version of the code. First of all, install
Git::

    $ sudo apt install git

.. _Git: https://git-scm.com/

Then go into the directory where you want the code to reside and run::

    $ git clone https://git.launchpad.net/maas && cd maas

MAAS depends on Postgres, isc-dhcp, bind9, and many other packages. To install
everything that's needed for running and developing MAAS, run::

    $ make install-dependencies

Careful: this will ``apt-get install`` many packages on your system,
via ``sudo``. It may prompt you for your password.

This will install ``bind9``. As a result you will have an extra daemon
running. If you are a developer and don't intend to run BIND locally,
you can disable the daemon by inserting ``exit 1`` at the top of
``/etc/default/bind9``. The package still needs to be installed for
tests though.

Python development dependencies are pulled automatically from `PyPI`_ in a
virtualenv located under ``.ve``.

.. _PyPI:
  http://pypi.python.org/


Git Workflow
^^^^^^^^^^^^

You will want to adjust your git repository of lp:maas some before you start
making changes to the code. This includes setting up your own copy of
the repository and making your changes in branches.

First you will want to rename the origin remote to upstream and create a new
origin in your namespace.

::

    $ git remote rename origin upstream
    $ git remote add origin git+ssh://{launchpad-id}@git.launchpad.net/~{launchpad-id}/maas

Now you can make a branch and start making changes.

::

    $ git checkout -b new-branch

Once you have made the changes you want, you should commit and push the branch
to your origin.

::

    $ git commit -m "My change" -a
    $ git push origin new-branch

Now you can view that branch on Launchpad and propose it to the maas
repository.

Once the branch has been merged and your done with it you can update your
git repository to remove the branch.

::

    $ git fetch upstream
    $ git checkout master
    $ git merge upstream/master
    $ git branch -d new-branch


Running tests
=============

To run the whole suite::

    $ make test

To run tests at a lower level of granularity::

    $ ./bin/test.region src/maasserver/tests/test_api.py
    $ ./bin/test.region src/maasserver/tests/test_api.py:AnonymousEnlistmentAPITest

The test runner is `nose`_, so you can pass in options like
``--with-coverage`` and ``--nocapture`` (short option: ``-s``). The
latter is essential when using ``pdb`` so that stdout is not
adulterated.

.. _nose: http://readthedocs.org/docs/nose/en/latest/

.. Note::

   When running ``make test`` through ssh from a machine with locales
   that are not set up on the machine that runs the tests, some tests
   will fail with a ``MismatchError`` and an "unsupported locale
   setting" message. Running ``locale-gen`` for the missing locales or
   changing your locales on your workstation to ones present on the
   server will solve the issue.


Emitting subunit
^^^^^^^^^^^^^^^^

Pass the ``--with-subunit`` flag to any of the test runners (e.g.
``bin/test.rack``) to produce a `subunit`_ stream of test results. This
may be useful for parallelising test runs, or to allow later analysis of
a test run. The optional ``--subunit-fd`` flag can be used to direct the
results to a different file descriptor, to ensure a clean stream.

.. _subunit: https://launchpad.net/subunit/


Production MAAS server debugging
================================

When MAAS is installed from packaging it can help to enable debugging features
to triage issues.

Log all API and UI exceptions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default MAAS only logs HTTP 500 - INTERNAL_SERVER_ERROR into the
regiond.log. To enable logging of all exceptions even exceptions where MAAS
will return the correct HTTP status code.::

  $ sudo sed -i 's/DEBUG = False/DEBUG = True/g' \
  >   /usr/lib/python3/dist-packages/maasserver/djangosettings/settings.py
  $ sudo service maas-regiond restart

Run regiond in foreground
^^^^^^^^^^^^^^^^^^^^^^^^^

It can help when debugging to run regiond a foreground process so you can
interact with the regiond by placing a breakpoint in the code. Once you have
placed a breakpoint into the code you want to inspect you can start the regiond
process in the foreground.::

  $ sudo service maas-regiond stop
  $ sudo -u maas -H \
  >   DJANGO_SETTINGS_MODULE=maasserver.djangosettings.settings \
  >   twistd3 --nodaemon --pidfile= maas-regiond


.. Note::

   By default a MAAS installation runs 4 regiond processes at the same time.
   This will change it to only run 1 process in the foreground. This should
   only be used for debugging. Once finished the breakpoint should be removed
   and maas-regiond service should be started.

Run rackd in foreground
^^^^^^^^^^^^^^^^^^^^^^^^^

It can help when debugging to run rackd a foreground process so you can
interact with the rackd by placing a breakpoint in the code. Once you have
placed a breakpoint into the code you want to inspect you can start the rackd
process in the foreground.::

   $ sudo service maas-rackd stop
   $ sudo -u maas -H /usr/bin/authbind --deep /usr/bin/twistd3 --nodaemon --pidfile= maas-rackd


Development MAAS server setup
=============================

Access to the database is configured in
``src/maasserver/djangosettings/development.py``.

The ``Makefile`` or the test suite sets up a development database
cluster inside your branch. It lives in the ``db`` directory, which
gets created on demand. You'll want to shut it down before deleting a
branch; see below.

First, set up the project. This fetches all the required dependencies
and sets up some useful commands in ``bin/``::

    $ make

Create the database cluster and initialise the development database::

    $ make syncdb

Optionally, if all you want to do is to take a look around the UI and
API, without interacting with real machines or VMs, populate your
database with the sample data::

    $ make sampledata

You can login as a simple user using the test account (username: 'test',
password: 'test') or the admin account (username: 'admin', password: 'test').

If you want to interact with real machines or VMs, it's better to use
the snap. Instead of building a real snap, though, you can use
'snapcraft prime' to create the prime directory. That has all the
contents of the snap, but it's in a plain directory insted of in a
squashfs image. Using a directory is better for testing, since you can
change the files in there and not rebuild the snap.

There's a ``sync-dev-snap`` make target to automate this:

::

    $ make sync-dev-snap

The ``sync-dev-snap`` target creates a clean copy of your working tree (so
that you don't have to run 'make clean' before building the snap) in
build/dev-snap and creates the snap directory in build/dev-snap/prime.

You can now install the snap:

::

    $ sudo snap try build/dev-snap/prime

Note that 'snap try' is used instead of 'snap install'. The maas snap
should now be installed:

::

    $ snap list
    Name          Version                 Rev   Tracking  Publisher   Notes
    core          16-2.41                 7713  stable    canonical✓  core
    core18        20191001                1192  stable    canonical✓  base
    maas          2.7.0-8077-g.7e249fbe4  x1    -         -           try
    maas-cli      0.6.5                   13    stable    canonical✓  -
    snapd         2.41                    4605  stable    canonical✓  snapd

Next you need to initialize the snap, just like you would normally do:

    $ sudo maas init

And now you're ready to make changes to the code. After you've change
some source files and want to test them out, run the ``sync-dev-snap``
target again:

::

    $ make sync-dev-snap

You should now see that you files were synced to the prime directory. Restart
the supervisor service to use the synced code:

::

    $ sudo service snap.maas.supervisor restart

VMs or even real machines can now PXE boot off your development snap.
But of course, you need to set up the networking first. If you want to
do some simple testing, the easiest is to create a networking in
virt-manager that has NAT, but doesn't provide DHCP. If the name of
the bridge that got created is `virbr1`, you can expose it to your
container as eth1 using the following config:

::

    eth1:
      name: eth1
      nictype: bridged
      parent: virbr1
      type: nic

Of course, you also need to configure that eth1 interface. Since MAAS is
the one providing DHCP, you need to give it a static address on the
network you created. For example::

    auto eth1
    iface eth1 inet static
      address 192.168.100.2
      netmask 255.255.255.0

Note that your LXD host will have the .1 address and will act as a
gateway for your VMs.

To shut down the database cluster and clean up all other generated files in
your branch::

    $ make clean


Downloading PXE boot resources
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To use PXE booting, each cluster controller needs to download several
files relating to PXE booting. This process is automated, but it does
not start by default.

First create a superuser and start all MAAS services::

    $ bin/maas-region createadmin
    $ make run

Substitute your own email.  The command will prompt for a choice of password.

Next, get the superuser's API key on the `account preferences`_ page in the
web UI, and use it to log into MAAS at the command-line::

    $ bin/maas login dev http://localhost:5240/MAAS/

.. _`account preferences`: http://localhost:5240/MAAS/account/prefs/

Start downloading PXE boot resources::

    $  bin/maas dev node-groups import-boot-images

This sends jobs to each cluster controller, asking each to download
the boot resources they require. This may download dozens or hundreds
of megabytes, so it may take a while. To save bandwidth, set an HTTP
proxy beforehand::

    $ bin/maas dev maas set-config name=http_proxy value=http://...


Running the built-in TFTP server
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You will need to run the built-in TFTP server on the real TFTP port (69) if
you want to boot some real hardware. By default, it's set to start up on
port 5244 for testing purposes. To make it run on port 69, set the
MAAS_TFTP_PORT environment variable before running make run/start::

    export MAAS_TFTP_PORT=69


Then you need install and configure the authbind, so that your user can
bind to port 69::

    * Install the ``authbind``package:

      $ sudo apt install authbind

    * Create a file ``/etc/authbind/byport/69`` that is *executable* by the
      user running MAAS.

      $ sudo touch /etc/authbind/byport/69
      $ sudo chown $USER /etc/authbind/byport/69
      $ sudo chmod u+x /etc/authbind/byport/69

Now when starting up the MAAS development webserver, "make run" and "make
start" will detect authbind's presence and use it automatically.


Running the BIND daemon for real
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There's a BIND daemon that is started up as part of the development service
but it runs on port 5246 by default. If you want to make it run as a real
DNS server on the box then set the MAAS_BIND_PORT environment variable
before running make run/start::

    export MAAS_BIND_PORT=53

Then as for TFTP above, create an authbind authorisation::

    $ sudo touch /etc/authbind/byport/53
    $ sudo chown $USER /etc/authbind/byport/53
    $ sudo chmod u+x /etc/authbind/byport/53

and run as normal.


Running the cluster worker
^^^^^^^^^^^^^^^^^^^^^^^^^^

The cluster also needs authbind as it needs to bind a socket on UDP port
68 for DHCP probing::

    $ sudo touch /etc/authbind/byport/68
    $ sudo chown $USER /etc/authbind/byport/68
    $ sudo chmod u+x /etc/authbind/byport/68

If you omit this, nothing else will break, but you will get an error in
the cluster log because it can't bind to the port.


Configuring DHCP
^^^^^^^^^^^^^^^^

MAAS requires a properly configured DHCP server so it can boot machines using
PXE. MAAS can work with its own instance of the ISC DHCP server, if you
install the maas-dhcp package::

    $ sudo apt install maas-dhcp

Note that maas-dhcpd service definition referencese the maas-rackd
service, which won't be present if you run a development service. To
workaround edit /lib/systemd/system/maas-dhcp.service and comment out
this line:

    BindsTo=maas-rackd.service


Non-interactive configuration of RBAC service authentication
============================================================

For development and automating testing purposes, it's possible to configure
maas with the RBAC service in a non-interactive way, with the following::

    $ sudo MAAS_CANDID_CREDENTIALS=user1:password1 maas configauth --rbac-url http://<url-of-rbac>:5000 --rbac-sevice-name <maas-service-name-in-RBAC>

This will automatically handle logging in with Candid, without requiring the
user to fill in the authentication form via browser.


Development services
====================

The development environment uses *daemontools* to manage the various
services that are required. These are all defined in subdirectories in
``services/``.

There are familiar service-like commands::

  $ make start
  $ make status
  $ make restart
  $ make stop

The latter is a dependency of ``distclean`` so just running ``make
distclean`` when you've finished with your branch is enough to stop
everything.

Individual services can be manipulated too::

  $ make services/rackd/@start

The ``@<action>`` pattern works for any of the services.

There's an additional special action, ``run``::

  $ make run

This starts all services up and tails their log files. When you're
done, kill ``tail`` (e.g. Ctrl-c), and all the services will be
stopped.

However, when used with individual services::

  $ make services/regiond/@run

it does something even cooler. First it shuts down the service, then
it restarts it in the foreground so you can see the logs in the
console. More importantly, it allows you to use ``pdb``, for example.

A note of caution: some of the services have slightly different
behaviour when run in the foreground:

* regiond (the *webapp* service) will be run with its auto-reloading
  enabled.

There's a convenience target for hacking regiond that starts everything
up, but with regiond in the foreground::

  $ make run+regiond

Apparently Django needs a lot of debugging ;)


Adding new source files
=======================

When creating a new source file, a Python module or test for example,
always start with the appropriate template from the ``templates``
directory.


Database information
====================

MAAS uses Django_ to manage changes to the database schema.

.. _Django: https://www.djangoproject.com/

Be sure to have a look at `Django's migration documentation`_ before you make
any change.

.. _Django's migration documentation:
    https://docs.djangoproject.com/en/1.8/topics/migrations/


Changing the schema
^^^^^^^^^^^^^^^^^^^

Once you've made a model change (i.e. a change to a file in
``src/<application>/models/*.py``) you have to run Django's `makemigrations`_
command to create a migration file that will be stored in
``src/<application>/migrations/builtin/``.

Note that if you want to add a new model class you'll need to import it
in ``src/<application>/models/__init__.py``

.. _makemigrations: https://docs.djangoproject.com/en/1.8/ref/django-admin/#django-admin-makemigrations

Generate the migration script with::

    $ ./bin/maas-region makemigrations --name description_of_the_change maasserver

This will generate a migration module named
``src/maasserver/migrations/builtin/<auto_number>_description_of_the_change.py``.
Don't forget to add that file to the project with::

    $ git add src/maasserver/migrations/builtin/<auto_number>_description_of_the_change.py

To apply that migration, run::

    $ make syncdb


Performing data migration
^^^^^^^^^^^^^^^^^^^^^^^^^

If you need to perform data migration, very much in the same way, you will need
to run Django's `makemigrations`_ command. For instance, if you want to perform
changes to the ``maasserver`` application, run::

    $ ./bin/maas-region makemigrations --empty --name description_of_the_change maasserver

This will generate a migration module named
``src/maasserver/migrations/builtin/<auto_number>_description_of_the_change.py``.
You will need to edit that file and fill the ``operations`` list with the
options that need to be performed. Again, don't forget to add that file to the
project::

    $ git add src/maasserver/migrations/builtin/<auto_number>_description_of_the_change.py

Once the operations have been added, apply that migration with::

    $ make syncdb


Examining the database manually
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you need to get an interactive ``psql`` prompt, you can use `dbshell`_::

    $ bin/maas-region dbshell

.. _dbshell: https://docs.djangoproject.com/en/dev/ref/django-admin/#dbshell

If you need to do the same thing with a version of MAAS you have installed
from the package, you can use::

    $ sudo maas-region dbshell --installed

You can use the ``\dt`` command to list the tables in the MAAS database. You
can also execute arbitrary SQL. For example:::

    maasdb=# select system_id, hostname from maasserver_node;
                     system_id                 |      hostname
    -------------------------------------------+--------------------
     node-709703ec-c304-11e4-804c-00163e32e5b5 | gross-debt.local
     node-7069401a-c304-11e4-a64e-00163e32e5b5 | round-attack.local
    (2 rows)


Viewing SQL queries during tests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you need to view the SQL queries that are performed during a test, the
`LogSQL` fixture can be used to output all the queries during the test.::

    from maasserver.testing.fixtures import LogSQL
    self.useFixture(LogSQL())

Sometimes you need to see where in the code that query was performed.::

    from maasserver.testing.fixtures import LogSQL
    self.useFixture(LogSQL(include_stacktrace=True))
