# MaaS database control functions
#
# The control functions take as their first argument a database cluster's data
# directory.  This is where the database's socket, pidfile, log, and data will
# reside.  The data directory must start with a slash.
#
# Some design choices for this module:
#
#  * Everything is PostgreSQL on Ubuntu.
#  * POSIX shell.  Test your changes in dash, not just in bash.
#  * Each branch gets its own cluster(s).  Kill & delete when done.
#  * One database per cluster.  May change this later if it's a problem.
#  * Databases run under the system user that creates them.  No root required.
#  * No global configuration apart from a basic PostgreSQL install.
#  * Connections use Unix sockets.  No TCP port hogging.

POSTGRES_VERSION=9.1
PGCTL="/usr/lib/postgresql/${POSTGRES_VERSION}/bin/pg_ctl"


# Figure out the full data directory path for a given cluster, even if it's a
# relative path.
maasdb_locate() {
    DATADIR="$1"
    if test -z "$1"
    then
        echo "Specify a data directory for the MaaS database cluster." >&2
        return 1
    fi
    if ! echo "$DATADIR" | grep '^/'
    then
        echo "`pwd`/$DATADIR"
    fi
}


# Create a database cluster.
maasdb_create_cluster() {
    DATADIR="`maasdb_locate "$1"`"
    if ! test -d "$DATADIR/base"
    then
        mkdir -p -- "$DATADIR"
        $PGCTL init -D "$DATADIR" -o '-E utf8'
    fi
}


# Start a database cluster.
maasdb_start_cluster() {
    DATADIR="`maasdb_locate "$1"`"
    # Pass "disposable" as the second argument if the data in this database
    # is not important at all and you're willing to cut corners for speed.
    DISPOSABLE="$2"

    if test "$DISPOSABLE" = "disposable"
    then
        #  -F -- don't bother fsync'ing.
        EXTRA_POSTGRES_OPTS="-F"
    else
        EXTRA_POSTGRES_OPTS=""
    fi

    maasdb_create_cluster "$DATADIR"

    if ! test -f "$DATADIR/postmaster.pid"
    then
        # pg_ctl options:
        #  -D <dir> -- data directory.
        #  -l <file> -- log file.
        #  -w -- wait until startup is complete.
        # postgres options:
        #  -h <arg> -- host name; empty arg means Unix socket only.
        #  -k -- socket directory.
        $PGCTL start \
            -D "$DATADIR" -l "$DATADIR/backend.log" -w \
            -o "-h '' -k '$DATADIR' $EXTRA_POSTGRES_OPTS"
    fi
}


# Stop a database cluster.
maasdb_stop_cluster() {
    DATADIR="`maasdb_locate "$1"`"
    if test -f "$DATADIR/postmaster.pid"
    then
        $PGCTL stop -D "$DATADIR"
    fi
}


# Initialize a MaaS database.
maasdb_init_db() {
    DATADIR="`maasdb_locate "$1"`"
    # Pass "disposable" as the second argument if the data in this database
    # is not important at all and you're willing to cut corners for speed.
    DISPOSABLE="$2"
    MARKER="$DATADIR/maas-created"
    maasdb_start_cluster "$DATADIR" "$DISPOSABLE"
    if ! test -f "$MARKER"
    then
        createdb -h "$DATADIR" maas && touch "$MARKER"
    fi
}


# Open a psql shell on a MaaS database.
maasdb_shell() {
    DATADIR="`maasdb_locate "$1"`"
    maasdb_init_db "$DATADIR"
    psql -h "$DATADIR" maas
}


# Execute a query on a MaaS database.
maasdb_query() {
    DATADIR="`maasdb_locate "$1"`"
    QUERY="$2"
    maasdb_init_db "$DATADIR"
    psql -h "$DATADIR" maas -c "$QUERY"
}


# Delete an entire MaaS database and cluster.  Use only with extreme care!
maasdb_delete_cluster() {
    DATADIR="`maasdb_locate "$1"`"
    # Before deleting anything, does this at least look like a MaaS database
    # cluster?
    if test -d "$DATADIR/base"
    then
        maasdb_stop_cluster "$DATADIR"
        rm -rf -- "$DATADIR"
    fi
}
