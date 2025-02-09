# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Profile-related functionality."""

from itertools import islice


class InvalidProfile(Exception):
    """Unknown profile specified."""


def get_profile(profiles, profile_name):
    """Look up the named profile in `profiles`.

    :param profiles: The result of `ProfileConfig.open()`.
    :param profile_name: The profile requested by the user.
    :return: The `ProfileConfig` option for the requested profile.
    :raise InvalidProfile: Requested profile was not found.
    """
    if profile_name not in profiles:
        raise InvalidProfile("'%s' is not an active profile." % profile_name)
    return profiles[profile_name]


def name_default_profile(profiles):
    """Return name of the default profile, or raise `NoDefaultProfile`.

    :param profiles: The result of `ProfileConfig.open()`.
    :return: The name of the default profile, or None if there is no
        reasonable default.
    """
    profiles_sample = list(islice(profiles, 2))
    if len(profiles_sample) == 1:
        # There's exactly one profile.  That makes a sensible default.
        return profiles_sample[0]

    return None


def select_profile(profiles, profile_name=None):
    """Return name for the applicable profile: the given name, or the default.

    :param profiles: The result of `ProfileConfig.open()`.
    :param profile_name: The profile requested by the user, if any.  This may
        be `None`, in which case `select_profile` will look for a sensible
        default to use.
    :return: Name of the applicable profile, or `None` if no profile was
        explicitly requested and no sensible default presents itself.
    """
    if profile_name is None:
        return name_default_profile(profiles)
    else:
        return profile_name
