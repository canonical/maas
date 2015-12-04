# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check Python 3 type hints."""

__all__ = [
    "ArgumentTypeError",
    "ReturnTypeError",
    "typed",
]

from functools import wraps
import inspect
import typing


class AnnotationError(TypeError):
    """An annotation has not be understood."""


class ArgumentTypeError(TypeError):
    """An argument was of the wrong type."""

    def __init__(self, func, name, value, expected):
        super(ArgumentTypeError, self).__init__(
            "In %s, for argument '%s', %r is not of type %s; "
            "it is of type %s." % (
                name_of(func), name, value, name_of(expected),
                name_of(type(value))))


class ReturnTypeError(TypeError):
    """The return value was of the wrong type."""

    def __init__(self, func, value, expected):
        super(ReturnTypeError, self).__init__(
            "In %s, the returned value %r is not of type %s; "
            "it is of type %s." % (
                name_of(func), value, name_of(expected),
                name_of(type(value))))


def typed(func):
    signature = inspect.signature(func)
    type_hints = typing.get_type_hints(func)
    types_in = tuple(get_types_in(type_hints, func))
    type_out = get_type_out(type_hints, func)

    if type_out is None:
        @wraps(func)
        def checked(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()

            # Check incoming arguments.
            for name, type_in in types_in:
                # An empty *args, for example, will not appear in the bound
                # arguments list, so we much check for that.
                if name in bound.arguments:
                    value = bound.arguments[name]
                    if not issubclass(type(value), type_in):
                        raise ArgumentTypeError(func, name, value, type_in)

            # No annotation on return value.
            return func(*args, **kwargs)

    else:
        @wraps(func)
        def checked(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()

            # Check incoming arguments.
            for name, type_in in types_in:
                value = bound.arguments[name]
                if not issubclass(type(value), type_in):
                    raise ArgumentTypeError(func, name, value, type_in)

            # Call function and check return value.
            result = func(*args, **kwargs)
            if issubclass(type(result), type_out):
                return result
            else:
                raise ReturnTypeError(func, result, type_out)

    return checked


def get_types_in(hints, func):
    for name, hint in hints.items():
        if name == "return":
            pass  # Not handled here.
        elif hint is None:
            yield name, type(None)  # Special case for None.
        elif is_typesig(hint):
            yield name, hint
        else:
            raise AnnotationError(
                "In %s, annotation %r for argument '%s' is "
                "not understood." % (name_of(func), hint, name))


def get_type_out(hints, func):
    if "return" in hints:
        hint = hints["return"]
        if hint is None:
            return type(None)  # Special case for None.
        elif is_typesig(hint):
            return hint
        else:
            raise AnnotationError(
                "In %s, annotation %r for return value is "
                "not understood." % (name_of(func), hint))
    else:
        return None


def is_typesig(typesig):
    if isinstance(typesig, tuple):
        if len(typesig) == 0:
            return False
        else:
            return all(map(is_typesig, typesig))
    else:
        return isinstance(typesig, type)


def name_of(thing):
    try:
        return thing.__qualname__
    except AttributeError:
        return repr(thing)
