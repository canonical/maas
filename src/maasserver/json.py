# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Extension of Django's JSON serializer to support MAAS custom data types.

We register this as a replacement for Django's own JSON serialization by
setting it in the SERIALIZATION_MODULES setting.
"""


import json

import django.core.serializers.json

from maasserver.fields import MAC


class MAASJSONEncoder(django.core.serializers.json.DjangoJSONEncoder):
    """MAAS-specific JSON encoder.

    Compared to Django's encoder, it adds support for representing a
    `MAC` in JSON.
    """

    def default(self, value):
        if isinstance(value, MAC):
            return value.get_raw()
        else:
            return super().default(value)


class Serializer(django.core.serializers.json.Serializer):
    """A copy of Django's serializer for JSON, but using our own encoder."""

    def end_serialization(self):
        json.dump(
            self.objects, self.stream, cls=MAASJSONEncoder, **self.options
        )


# Keep using Django's deserializer.  Loading a MAC from JSON will produce a
# string.
Deserializer = django.core.serializers.json.Deserializer
