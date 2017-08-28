# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Parameters form."""

__all__ = [
    "ParametersForm",
    ]

from django.forms import Form
from maasserver.utils.forms import set_form_error


class ParametersForm(Form):
    """Parameters forms."""

    def __init__(self, data=None, script=None, node=None):
        super().__init__(data=data)

    def clean(self):
        for param, fields in self.data.items():
            # All parameter values should have a type defined.
            # Only currently supported parameter types are storage and runtime.
            param_type = fields.get('type')
            param_min = fields.get('min')
            param_max = fields.get('max')
            param_title = fields.get('title')
            param_description = fields.get('description')
            param_argument_format = fields.get('argument_format')
            param_default = fields.get('default')
            param_required = fields.get('required', True)

            # Check param data type.
            if not isinstance(param, str):
                set_form_error(
                    self, "parameters",
                    "%s: parameter must be a string" % param)
            # Check fields data types.
            if not isinstance(param_type, str):
                set_form_error(
                    self, "parameters",
                    "%s: type must be a string" % param_type)
            if param_min is not None and not isinstance(param_min, int):
                set_form_error(
                    self, "parameters",
                    "%s: min must be an integer" % param_min)
            if param_max is not None and not isinstance(param_max, int):
                set_form_error(
                    self, "parameters",
                    "%s: max must be an integer" % param_max)
            if param_title is not None and not isinstance(param_title, str):
                set_form_error(
                    self, "parameters",
                    "%s: title must be a string" % param_title)
            if param_description is not None and not isinstance(
                    param_description, str):
                set_form_error(
                    self, "parameters",
                    "%s: description must be a string" % param_description)
            if param_argument_format is not None and not isinstance(
                    param_argument_format, str):
                set_form_error(
                    self, "parameters",
                    "%s: argument_format must be a string"
                    % param_argument_format)
            if param_default is not None and not isinstance(
                    param_default, str):
                set_form_error(
                    self, "parameters",
                    "%s: default must be a string" % param_default)
            if param_required is not None and not isinstance(
                    param_required, bool):
                set_form_error(
                    self, "parameters",
                    "%s: required must be a boolean" % param_required)

            # Check parameter type is supported and required.
            if param_type not in ('storage', 'runtime') and param_required:
                set_form_error(
                    self, "parameters",
                    "%s: type must be either storage or runtime" % param_type)
            if param_type == 'storage' and (
                    param_min is not None or param_max is not None):
                set_form_error(
                    self, "parameters",
                    "storage type doesn't support min or max")
            if param_type == 'runtime' and isinstance(param_min, int):
                if param_min < 0:
                    set_form_error(
                        self, "parameters",
                        "runtime minimum must be greater than zero")
            if isinstance(param_min, int) and isinstance(param_max, int):
                if param_min > param_max:
                    set_form_error(
                        self, "parameters", "min must be less than max")
            if isinstance(param_argument_format, str):
                if param_type == 'storage':
                    if not any(
                            format in param_argument_format
                            for format in ('{input}', '{name}', '{path}',
                                           '{model}', '{serial}')):
                        set_form_error(
                            self, "parameters",
                            "%s: argument_format must contain one of {input}, "
                            "{name}, {path}, {model}, {serial}" % param_type)
                else:
                    if '{input}' not in param_argument_format:
                        set_form_error(
                            self, "parameters",
                            "%s: argument_format must contain {input}"
                            % param_type)
