# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generic helpers for working with constraint strings."""

import re


class LabeledConstraintMap:
    """Class to encapsulate a labeled constraint map, so that it only
    needs to be parsed once.
    """

    def __init__(self, value):
        self.value = value
        self.map = None
        self.error = None
        try:
            self.map = parse_labeled_constraint_map(value)
        except ValueError as error:
            self.error = error

    def __repr__(self):
        return f"{self.__class__.__name__}({repr(self.value)})"

    def __str__(self):
        return self.value

    def __len__(self):
        if self.map is None:
            return 0
        return len(self.map)

    def __iter__(self):
        if self.map is None:
            return iter([])
        return iter(self.map)

    def __getitem__(self, item):
        return self.map[item]

    def validate(self, exception_type=ValueError):
        if self.error:
            # XXX mpontillo 2015-10-28 Need to re-raise this properly once we
            # get to Python 3.
            raise exception_type(str(self.error))


def parse_labeled_constraint_map(value, exception_type=ValueError):
    """Returns a dictionary of constraints, given the specified constraint
    value. Validates that the following conditions hold true:

     - The constraint string is non-empty
     - The constraint string is in the format:
         <label>:<key>=<value>[,<key2>=<value2>[,...]]'
     - Constraint labels must only be defined once
     - The ';', and ',', characters are reserved, and are not allowed to occur
       in any keys or values.

    The returned dictionary will be in the format:

    {
        <label1>: { <key1>: [<value1>],
                    <key2>: [<value2>, <value3>] }
        <label2>:  { ... },
        ...
    }

    When multiple keys are contained within a constraint, the values will be
    returned (in the order specified) inside a list.

    When a duplicate label is specified, an exception is thrown.

    Single values will also be returned inside a list, for consistency.

    :return:dict
    """
    if value is None or not isinstance(value, (str, bytes)):
        return None
    if len(value) <= 1:
        return {}
    result = {}
    constraints = value.split(";")
    for constraint in constraints:
        tokens = constraint.split(":", 1)
        if len(tokens) != 2:
            raise exception_type(
                "Malformed constraint: '%s' (required format: "
                "'<label>:<key>=<value>[,<key2>=<value2>[,...]]')" % constraint
            )
        label = tokens[0]
        validate_constraint_label_name(label, exception_type=exception_type)
        if label in result:
            raise exception_type(
                "Constraint label defined more than once: '%s'" % label
            )
        key_value_pairs = tokens[1].split(",")
        labeled_constraint = _parse_key_value_pairs(
            key_value_pairs, exception_type=exception_type
        )
        result[label] = labeled_constraint
    return result


def _parse_key_value_pairs(kvps, exception_type=ValueError):
    """Given the specified list of key/value pairs, returns a dictionary
    that maps each key to its value.
    """
    key_value_pairs = {}
    for kvp in kvps:
        tokens = kvp.split("=", 1)
        if len(tokens) != 2:
            raise exception_type(
                "Malformed key/value pair in constraint: '%s'" % kvp
            )
        key, value = tokens
        value_list = key_value_pairs.get(key, [])
        value_list.append(value)
        key_value_pairs[key] = value_list
    return key_value_pairs


def validate_constraint_label_name(label_name, exception_type=ValueError):
    """Throws the specified exception_type (default is ValueError) if the
    label name is invalid.
    """
    if not re.match(r"[a-zA-Z0-9]+[a-zA-Z0-9_-]*$", label_name):
        raise exception_type(
            "Invalid label name: '%s' (Must begin with an alphanumeric "
            "character, and include only alphanumeric characters, dashes, and "
            "underscores.)" % label_name
        )
