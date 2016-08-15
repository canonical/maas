.. -*- mode: rst -*-

.. _packagerepositories:

====================
Package Repositories
====================

.. note::

  This feature is available in MAAS versions 2.0 and above.

MAAS allows the configuring of multiple additional package repositories, which
will find their way into the /etc/apt/sources.list on MAAS deployed machines.

Creating a Package Repository
-----------------------------

Administrators can create Package Repositories over the API using the following command:::

  $ maas <profile> package-repositories create name=<Package Repository Name> url=<URL locating the package repository>

These are the minimally required parameters - see the online API help,
described below, for the complete list of parameters.

Package Repository Enablement
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Package Repositories can be turned off by using the enabled flag option as follows:::

  $ maas <profile> package-repositories create name=<Package Repository Name> url=<URL locating the package repository> enabled=false

The enabled flag can be modified on an existing repository by using the update
API, described below.

Listing Package Repositories
----------------------------

To list all Package Repositories use the following command:::

  $ maas <profile> package-repositories read

To list a particular Package Repository use the following command:::

  $ maas <profile> package-repository read <Package Repository id or name>

Updating a Package Repository
-----------------------------

Administrators can update the Package Repository attributes using the following
command:::

  $ maas <profile> package-repository update <Package Repository id or name> <options>

Deleting a Package Repository
-----------------------------

Administrators can delete a Package Repository using the following command:::

  $ maas <profile> package-repository delete <Package Repository id or name>

Getting Help
------------

Online help is available for all API's in MAAS. For example:::

  $ maas <profile> package-repository --help
  $ maas <profile> package-repository <command> --help

  $ maas <profile> package-repositories --help
  $ maas <profile> package-repositories <command> --help
