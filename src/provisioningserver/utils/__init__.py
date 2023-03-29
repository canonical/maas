# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for the provisioning server."""

from collections.abc import Iterable
from functools import lru_cache, reduce
from itertools import chain
import os
from typing import Tuple

import tempita

from provisioningserver.utils import snap


def locate_config(*path: Tuple[str]):
    """Return the location of a given config file or directory.

    :param path: Path elements to resolve relative to `${MAAS_ROOT}/etc/maas`.
    """
    # The `os.curdir` avoids a crash when `path` is empty.
    path = os.path.join(os.curdir, *path)
    if os.path.isabs(path):
        return path
    else:
        # Avoid circular imports.
        from provisioningserver.path import get_tentative_data_path

        return get_tentative_data_path("etc", "maas", path)


def locate_template(*path: Tuple[str]):
    """Return the absolute path of a template.

    :param path: Path elemets to resolve relative to the location the
                 Python library provisioning server is located in.
    """
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "templates", *path)
    )


@lru_cache(maxsize=256)
def load_template(*path: Tuple[str]):
    """Load the template."""
    return tempita.Template.from_filename(
        locate_template(*path), encoding="UTF-8"
    )


def dict_depth(d, depth=0):
    """Returns the max depth of a dictionary."""
    if not isinstance(d, dict) or not d:
        return depth
    return max(dict_depth(v, depth + 1) for _, v in d.items())


def classify(func, subjects):
    """Classify `subjects` according to `func`.

    Splits `subjects` into two lists: one for those which `func`
    returns a truth-like value, and one for the others.

    :param subjects: An iterable of `(ident, subject)` tuples, where
        `subject` is an argument that can be passed to `func` for
        classification.
    :param func: A function that takes a single argument.

    :return: A ``(matched, other)`` tuple, where ``matched`` and
        ``other`` are `list`s of `ident` values; `subject` values are
        not returned.
    """
    matched, other = [], []
    for ident, subject in subjects:
        bucket = matched if func(subject) else other
        bucket.append(ident)
    return matched, other


def flatten(*things):
    """Recursively flatten iterable parts of `things`.

    For example::

      >>> sorted(flatten([1, 2, {3, 4, (5, 6)}]))
      [1, 2, 3, 4, 5, 6]

    :return: An iterator.
    """

    def _flatten(things):
        if isinstance(things, str):
            # String-like objects are treated as leaves; iterating through a
            # string yields more strings, each of which is also iterable, and
            # so on, until the heat-death of the universe.
            return iter((things,))
        elif isinstance(things, Iterable):
            # Recurse and merge in order to flatten nested structures.
            return chain.from_iterable(map(_flatten, things))
        else:
            # This is a leaf; return an single-item iterator so that it can be
            # chained with any others.
            return iter((things,))

    return _flatten(things)


def sudo(command_args):
    """Wrap the command arguments in a sudo command, if not in debug mode."""
    if snap.running_in_snap():
        return command_args
    else:
        return ["sudo", "-n", *command_args]


class CircularDependency(ValueError):
    """A circular dependency has been found."""


def sorttop(data):
    """Sort `data` topologically.

    `data` should be a `dict`, where each entry maps a "thing" to a `set` of
    other things they depend on, or should be sorted after. For example:

      >>> list(sorttop({1: {2}, 2: {3, 4}}))
      [{3, 4}, {2}, {1}]

    :raises CircularDependency: If two or more things depend on one another,
        making it impossible to resolve their relative ordering.
    """
    empty = frozenset()
    # Copy data and discard self-referential dependencies.
    data = {thing: set(deps) for thing, deps in data.items()}
    for thing, deps in data.items():
        deps.discard(thing)
    # Find ghost dependencies and add them as "things".
    ghosts = reduce(set.union, data.values(), set()).difference(data)
    for ghost in ghosts:
        data[ghost] = empty
    # Skim batches off the top until we're done.
    while len(data) != 0:
        batch = {thing for thing, deps in data.items() if deps == empty}
        if len(batch) == 0:
            raise CircularDependency(data)
        else:
            for thing in batch:
                del data[thing]
            for deps in data.values():
                deps.difference_update(batch)
            yield batch


def is_instance_or_subclass(test, *query):
    """Checks if a `test` object is an instance or type matching `query`.

    The `query` parameter will be flattened into a tuple before being used.
    """
    # isinstance() requires a tuple.
    query_tuple = tuple(flatten(query))
    if isinstance(test, query_tuple):
        return True
    try:
        return issubclass(test, query_tuple)
    except TypeError:
        return False


# Architectures as defined by:
# https://github.com/lxc/lxd/blob/master/shared/osarch/architectures.go
# https://www.debian.org/releases/oldstable/i386/ch02s01.html.en
DEBIAN_TO_KERNEL_ARCHITECTURES = {
    "i386/generic": "i686",
    "amd64/generic": "x86_64",
    "arm64/generic": "aarch64",
    "ppc64el/generic": "ppc64le",
    "s390x/generic": "s390x",
    "mips/generic": "mips",
    "mips64el/generic": "mips64",
}
KERNEL_TO_DEBIAN_ARCHITECTURES = {
    v: k for k, v in DEBIAN_TO_KERNEL_ARCHITECTURES.items()
}


def kernel_to_debian_architecture(kernel_arch):
    """Map a kernel architecture to Debian architecture."""
    return KERNEL_TO_DEBIAN_ARCHITECTURES[kernel_arch]


def debian_to_kernel_architecture(debian_arch):
    """Map a Debian architecture to kernel architecture."""
    return DEBIAN_TO_KERNEL_ARCHITECTURES[debian_arch]
