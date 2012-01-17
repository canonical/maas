MaaS .. Description TODO.

For more information about MaaS:
https://launchpad.net/maas


= Development MaaS server setup =

Access to the database is configured in src/maas/development.py.

The Makefile or the test suite sets up a development database cluster inside
your branch.  It lives in the "db" directory, which gets created on demand.
You'll want to shut it down before deleting a branch; see below.

First, set up the project.  This fetches all the required dependencies, and
creates a local database cluster and development database:

    $ make

Initialize the database:

    $ make syncdb

Run the development webserver:

    $ make run

Point your browser to http://localhost:8000/

To shut down the database cluster and clean up all other generated files in
your branch:

    $ make distclean
