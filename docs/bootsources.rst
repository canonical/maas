.. -*- mode: rst -*-

.. _bootsources:

Boot images import configuration
================================

The configuration for where a cluster downloads its images is defined by
a set of "sources".  Each "source" defines a Simplestreams repository
location (``url``) from which images can be downloaded and a
``keyring_filename`` (or ``keyring_data``) for validating index and image
signatures from that location.  For each source, you can define a series of
filters (``selections``) specifying which images should be downloaded from
that source.

The following example use the MAAS CLI to list the boot sources and the boot
source selections for a particular cluster.  Assuming that ``CLUSTER_UUID`` is
the UUID of the cluster being examined and the CLI ``PROFILE`` is the name of
the profile being used::

    $ sudo maas $PROFILE boot-sources read $CLUSTER_UUID
    [
        {
            "url": "http://maas.ubuntu.com/images/ephemeral-v2/releases/",
            "keyring_data": "",
            "resource_uri": "<url omitted for readability>",
            "keyring_filename": "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg",
            "id": 1
        }
    ]

    $ sudo maas $PROFILE boot-source-selections read $CLUSTER_UUID 1
    [
        {
            "release": "precise",
            "arches": ["*"],
            "resource_uri": "<url omitted for readability>",
            "id": 1,
            "subarches": ["*"]
        },
        {
            "release": "trusty",
            "arches": ["*"],
            "resource_uri": "<url omitted for readability>",
            "id": 2,
            "subarches": ["*"]
        }
    ]

Restricting the images being downloaded
---------------------------------------

Let's say you want to restrict the images being downloaded to only one
architecture and one release; starting from the configuration described above,
you would need to:

- Delete the "Precise" selection (the selection '1' of the source '1')::

    $ sudo maas $PROFILE boot-source-selection delete  $CLUSTER_UUID 1 1

- Update the architecture list of the "Trusty" selection so that only the
  image for amd64 will be downloaded (this is the selection '2' of the source
  '1')::

    $ sudo maas $PROFILE boot-source-selection update $CLUSTER_UUID 1 2 arches=amd64
    {
        "release": "trusty",
        "arches": ["amd64"],
        "resource_uri": "<url omitted for readability>",
        "id": 2,
        "subarches": ["*"]
    }

Downloading the images from a different source
----------------------------------------------

Let's say you want to import the images from a different location.  You would
need to to change the source's url and keyring::

    $ sudo maas $PROFILE boot-source update $CLUSTER_UUID 1 url="http://custom.url" keyring_filename="" keyring_data@=./custom_keyring_file
    {
        "url": "http://custom.url/",
        "keyring_data": "<base64 encoded content of `custom_keyring_file`>",
        "resource_uri": "<url omitted for readability>",
        "keyring_filename": "",
        "id": 1
    }

Adding a source
---------------

You can also add a new source::

    $ sudo maas maas boot-sources create $CLUSTER_UUID url=http://my.url keyring_filename="" keyring_data@=./ custom_keyring_file
    {
        "url": "http://my.url/",
        "keyring_data": "ZW1wdHkK",
        "keyring_filename": "",
        "id": 2,
        "resource_uri": "<url omitted for readability>"
    }

Inside that newly created source ('2') you can add selections::

    $ sudo maas $PROFILE boot-source-selections create $CLUSTER_UUID 2 arches=amd64 subarches='*' release='trusty' labels='*'
    {
        "labels": ["*"],
        "arches": ["amd64"],
        "subarches": ["*"],
        "release": "trusty",
        "id": 3,
        "resource_uri": "<url omitted for readability>"
    }
