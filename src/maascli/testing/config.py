# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fake `ProfileConfig` for testing."""

from maastesting.factory import factory


class FakeConfig(dict):
    """Fake `ProfileConfig`.  A dict that's also a context manager."""

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        pass


def make_handler():
    """Create a fake handler entry."""
    return {
        "name": factory.make_name("handler"),
        "doc": "Short\n\nLong",
        "params": [],
        "actions": [
            {"name": factory.make_name("action"), "doc": "Doc\n\nstring"},
            {
                "name": factory.make_name("data-action"),
                "doc": "Doc\n\nstring\n\n:param: data",
            },
        ],
    }


def make_resource(anon=True, auth=True):
    """Create a fake resource entry."""
    auth = make_handler() if auth else None
    anon = make_handler() if anon else None
    name = factory.make_name("resource")
    return {"auth": auth, "anon": anon, "name": name}


def make_profile(name=None):
    """Create a fake profile dict."""
    if name is None:
        name = factory.make_name("profile")
    return {
        "name": name,
        "url": "http://%s.example.com/" % name,
        "credentials": factory.make_name("credentials"),
        "description": {"resources": [make_resource(), make_resource()]},
    }


def make_configs(number_of_configs=1):
    """Create a dict mapping config names to `FakeConfig`."""
    result = {}
    while len(result) < number_of_configs:
        profile = factory.make_name("profile")
        result[profile] = FakeConfig(make_profile(profile))
    return FakeConfig(result)
