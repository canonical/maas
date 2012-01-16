MaaS .. Description TODO.

For more information about MaaS:
https://launchpad.net/maas

= Development MaaS server setup =

You need a database for the maas server.

You can choose to use the database of your choice (note that you will
need to update the default values in src/maas/development.py if you choose
to do so).

If you want to use the default for a local development server (postgresql
database engine, user: 'maas' with 'maas' as password, database name: 'maas'):

    $ echo "CREATE USER maas WITH CREATEDB PASSWORD 'maas';" | psql -U postgres
    $ createdb -E utf8 -O maas maas

Setup the project (fetch all the required dependencies):

    $ make

Initialize the database:

    $ make syncdb

Run the development webserver:

    $ make run

Point your browser to http://localhost:8000/
