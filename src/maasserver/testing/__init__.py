# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Tests for `maasserver`."""

__metaclass__ = type
__all__ = [
    "get_fake_provisioning_api_proxy",
    "reload_object",
    "reload_objects",
    ]

from uuid import uuid1

from provisioningserver.testing import fakeapi


def get_fake_provisioning_api_proxy():
    papi_fake = fakeapi.FakeSynchronousProvisioningAPI()
    distro = papi_fake.add_distro(
        "distro-%s" % uuid1().get_hex(),
        "initrd", "kernel")
    papi_fake.add_profile(
        "profile-%s" % uuid1().get_hex(),
        distro)
    return papi_fake


def reload_object(model_object):
    """Reload `obj` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If the object has been deleted, this will raise the `DoesNotExist`
    exception for its model class.

    :param model_object: Model object to reload.
    :type model_object: Concrete `Model` subtype.
    :return: Freshly-loaded instance of `model_object`.
    :rtype: Same as `model_object`.
    """
    model_class = model_object.__class__
    try:
        return model_class.objects.get(id=model_object.id)
    except model_class.DoesNotExist:
        return None


def reload_objects(model_class, model_objects):
    """Reload `model_objects` of type `model_class` from the database.

    Use this when a test needs to inspect changes to model objects made by
    the API.

    If any of the objects have been deleted, they will not be included in
    the result.

    :param model_class: `Model` class to reload from.
    :type model_class: Class.
    :param model_objects: Objects to reload from the database.
    :type model_objects: Sequence of `model_class` objects.
    :return: Reloaded objects, in no particular order.
    :rtype: Sequence of `model_class` objects.
    """
    assert all(isinstance(obj, model_class) for obj in model_objects)
    return model_class.objects.filter(
        id__in=[obj.id for obj in model_objects])
