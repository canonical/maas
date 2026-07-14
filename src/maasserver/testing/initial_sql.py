#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Shared constants for the seeded test SQL dump (`initial.maas_test.sql`).

The dump is regenerated with `make update-initial-sql`, which runs the
migrations against a clean database. Every default row seeded by that run
(default domain, default zone, default resource pool, package repositories,
...) shares the single wall-clock timestamp of the `dbupgrade` run.

To keep that value stable across regenerations, `utilities/update-initial-sql`
normalizes the seeded timestamp to the sentinel defined here. Tests that assert
the seeded default rows compare against this constant instead of chasing
whatever time the dump happened to be regenerated at.
"""

from datetime import datetime, timezone

# The string rendered into the SQL dump (Postgres `timestamptz` literal).
# Kept as the single source of truth: `utilities/update-initial-sql` reads it
# to rewrite the seeded timestamp.
INITIAL_SQL_SEED_TIMESTAMP_SQL = "2020-01-01 00:00:00+00"

# The same instant as a Python datetime, for use in test assertions.
INITIAL_SQL_SEED_TIMESTAMP = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
