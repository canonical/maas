MAAS standard images come from a SimpleStreams source. Canonical provides two SimpleStreams for MAAS images: candidate and stable. Both streams contain Ubuntu images, CentOS images, bootloaders extracted from the Ubuntu archive, and release notifications. Either stream can be used in any version of MAAS greater than 2.1 -- but not all images are supported in older versions.

## The candidate stream

The candidate stream contains images and bootloaders which have not been explicitly tested with MAAS. Canonical's automated build process dumps all images and bootloaders here before they are tested with MAAS. This stream is useful when testing a bug fix before an image or bootloader has been promoted to stable. Think of the candidate stream as a preview: it should never be used in a production environment; and users are encouraged to provide feedback on any issues they find with this stream.

This stream is available [here](http://images.maas.io/ephemeral-v3/candidate)**^**.

## The stable stream

The stable stream contains images and bootloaders which have been tested with the latest version of MAAS. This is the default stream which should be used in production environments.  This stream is available [here](http://images.maas.io/ephemeral-v3/stable)**^**.

## The retired daily stream

Previously there was only one MAAS stream available, daily. This stream has been replaced by the stable stream. Any client using this stream will be automatically redirected to the stable stream.