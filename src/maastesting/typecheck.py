# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check Python 3 type hints."""


from functools import wraps
import inspect
import typing

# Some releases of the `typing` module, even within the same major/minor/patch
# version of Python, have changed their issubclass behaviour, breaking this
# module. Changing a module's public API without bumping Python's version is
# not cool. See bug 1650202.
try:
    issubclass(str, typing.Optional[str])
except TypeError:
    typing_is_broken = True
else:
    typing_is_broken = False


class AnnotationError(TypeError):
    """An annotation has not be understood."""


class ArgumentTypeError(TypeError):
    """An argument was of the wrong type."""

    def __init__(self, func, name, value, expected):
        super().__init__(
            "In %s, for argument '%s', %r is not of type %s; "
            "it is of type %s."
            % (
                name_of(func),
                name,
                value,
                describe_typesig(expected),
                name_of(type(value)),
            )
        )


class ReturnTypeError(TypeError):
    """The return value was of the wrong type."""

    def __init__(self, func, value, expected):
        super().__init__(
            "In %s, the returned value %r is not of type %s; "
            "it is of type %s."
            % (
                name_of(func),
                value,
                describe_typesig(expected),
                name_of(type(value)),
            )
        )


def typed(func):
    """Decorate `func` and check types on arguments and return values.

    `func` is a callable with type annotations, like::

      @typed
      def do_something(foo: str, bar: int) -> str:
          return foo * bar

    It's also possible to use typing information from the built-in `typing`
    module::

      @typed
      def do_something(foo: AnyStr, bar: SupportsInt) -> AnyStr:
          return foo * int(bar)

    Checking type signatures can be slow, so it's better to import `typed`
    from `provisioningserver.utils`; that becomes a no-op in deployed
    environments.
    """
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


if typing_is_broken:

    def typed(func):  # noqa
        """Return `func` unchanged.

        This release of Python has a "broken" version of `typing` so no type
        checks are attempted.
        """
        return func


def get_types_in(hints, func):
    """Yield type annotations for function arguments."""
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
                "not understood." % (name_of(func), hint, name)
            )


def get_type_out(hints, func):
    """Return a type annotation for the return value."""
    if "return" in hints:
        hint = hints["return"]
        if hint is None:
            return type(None)  # Special case for None.
        elif is_typesig(hint):
            return hint
        else:
            raise AnnotationError(
                "In %s, annotation %r for return value is "
                "not understood." % (name_of(func), hint)
            )
    else:
        return None


def is_typesig(typesig):
    """Is `typesig` a type signature?

    A type signature is a subclass of `type`, or a tuple of type signatures
    (i.e. recursively).
    """
    if isinstance(typesig, tuple):
        if len(typesig) == 0:
            return False
        else:
            return all(map(is_typesig, typesig))
    else:
        return isinstance(typesig, type)


def describe_typesig(typesig):
    """Return a string describing `typesig`.

    See `is_typesig` for the definition of a `typesig`.
    """
    if issubclass(typesig, typing.Union):
        return describe_typesig(typesig.__union_params__)
    elif isinstance(typesig, tuple):
        return " or ".join(map(describe_typesig, typesig))
    else:
        return name_of(typesig)


def name_of(thing):
    """Return a friendly name for `thing`."""
    try:
        return thing.__qualname__
    except AttributeError:
        return repr(thing)
