# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Extension of Django's JSON serializer to support MAAS custom data types.

We register this as a replacement for Django's own JSON serialization by
setting it in the SERIALIZATION_MODULES setting.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Serializer',
    'Deserializer',
    ]

import django.core.serializers.json
import simplejson


class Serializer(django.core.serializers.json.Serializer):
    """A copy of Django's serializer for JSON, but using our own encoder."""
    # TODO bug=1217239: This may break in Django 1.5.
    def end_serialization(self):
        # Import lazily to avoid forcing import orders on startup.
        from maasserver.fields import MACJSONEncoder
        if simplejson.__version__.split('.') >= ['2', '1', '3']:
            # Use JS strings to represent Python Decimal instances
            # (ticket #16850)
            self.options.update({'use_decimal': False})
        simplejson.dump(
            self.objects, self.stream, cls=MACJSONEncoder, **self.options)


# Keep using Django's deserializer.  Loading a MAC from JSON will produce a
# string.
Deserializer = django.core.serializers.json.Deserializer
