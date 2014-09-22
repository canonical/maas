.. -*- mode: rst -*-

***************
Baseline schema
***************

This directory holds a generated dump of the database schema.  It is used as of
MAAS 1.7 to speed up creation of a test database at the beginning of each test
run.  If it proves robust over time, it may also be useful for fresh package
installations.

To speed up tests, the ``development`` settings patch Django's database backend
implementation for PostgreSQL/psycopg2, injecting code to load the baseline
schema right after creating the test database but before running the MAAS
database migrations.

The database dump includes the information that tells South which schema and
data migrations have already been applied.  Thus any migrations that are not
yet in the baseline schema will still run, but the ones that are covered by
the baseline schema can be skipped.  This accelerates test startup
considerably.

Everything should still work fine without the baseline schema, but tests will
be slower to start up.  You may want to try from time to time that this still
works, especially if you are editing older migrations or testing upgrades.

As the baseline falls out of date with application development, test startup
will start to slow down again.  Refresh the baseline when this happens, by
running::

    make baseline-schema

This updates the database dump in the ``schema`` directory.  Assuming the
update works without problems, submit it for landing on the official MAAS
branch.
