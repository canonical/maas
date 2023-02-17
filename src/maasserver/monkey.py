# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Monkey patch for the MAAS region server, with code for region server patching.
"""


from collections import OrderedDict

from twisted.web import http
import yaml

from provisioningserver.monkey import add_patches_to_twisted


class DeferredValueAccessError(AttributeError):
    """Raised when a deferred value is accessed."""


def DeferredAttributePreventer__get__(self, instance, cls=None):
    """Prevent retrieving the field.

    This is to be a replacement of Django's DeferredAttribute.__get__
    """
    if instance is None:
        return self
    raise DeferredValueAccessError(
        "Accessing deferred field is not allowed: %s" % self.field_name
    )


def fix_django_deferred_attribute():
    """Dont' allow DeferredAttributes to be loaded.

    If creating objects using Model.objects.all().only('id'), only the
    id attribute will be loaded from the database, and the rest will be
    DeferredAttributes. Howver, by default, Django will load such
    attributes implicitly, which might cause performance issues, given
    that you explicitly didn't want those attributes loaded.
    """
    from django.db.models.query_utils import DeferredAttribute

    DeferredAttribute.__get__ = DeferredAttributePreventer__get__


def fix_ordereddict_yaml_representer():
    """Fix PyYAML so an OrderedDict can be dumped."""

    def dumper(dumper, data):
        return dumper.represent_mapping("tag:yaml.org,2002:map", data.items())

    yaml.add_representer(OrderedDict, dumper, Dumper=yaml.Dumper)
    yaml.add_representer(OrderedDict, dumper, Dumper=yaml.SafeDumper)


OriginalRequest = http.Request


class PatchedRequest(OriginalRequest):
    def write(self, data):
        if self.finished:
            raise RuntimeError(
                "Request.write called on a request after "
                "Request.finish was called."
            )

        if self._disconnected:
            # Don't attempt to write any data to a disconnected client.
            # The RuntimeError exception will be thrown as usual when
            # request.finish is called
            return

        return OriginalRequest.write(self, data)


def fix_twisted_disconnect_write():
    """
    Patch twisted.web.http.Request to include the upstream fix

    See https://github.com/twisted/twisted/commit/169fd1d93b7af06bf0f6893b193ce19970881868
    """

    http.Request = PatchedRequest


def add_patches():
    add_patches_to_twisted()
    fix_django_deferred_attribute()
    fix_ordereddict_yaml_representer()
    fix_twisted_disconnect_write()
