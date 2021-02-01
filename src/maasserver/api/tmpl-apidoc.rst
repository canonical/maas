.. raw:: html

  <details>
  <summary><code>{{ http_method }} {{ uri }}{{if operation != ""}}?{{ operation }}{{endif}}</code></summary>

{{py:
params_length = len(params)
successes_length = len(successes)
errors_length = len(errors)
}}

{{if warnings != ""}}
THERE ARE PROBLEMS WITH THE DOCSTRING:

{{ warnings }}

{{endif}}


{{if description == ""}}

{{ description_title }}

{{else}}

{{ description }}

{{endif}}

{{if params_length > 0}}

**Parameters**

--------------------------
{{endif}}

{{for p in params}}
{{py:
options_dict = p['options']

required = "Optional."
if 'required' in options_dict and options_dict['required'] == "true":
    required = "Required."

format = False
if 'formatting' in options_dict and options_dict['formatting'] == 'true':
    format = True

description = p['description'] if format else p['description_stripped']
}}

**{{ p['name'] }}** (*{{ p['type'] }}*): {{required}} {{ description }}

{{endfor}}

{{if successes_length > 0}}

**Success**

--------------------------
{{endif}}

{{for p in successes}}

{{if p['example'] == ""}}

*{{ p['type'] }}* : {{ p['description_stripped'] }}

{{else}}

*{{ p['type'] }}*

{{py:
from textwrap import indent
example = indent(p['example'], '    ')
}}

::

{{ example }}

{{endif}}

{{endfor}}

{{if errors_length > 0}}

**Error**

--------------------------
{{endif}}

{{for p in errors}}

{{if p['example'] == ""}}

*{{ p['type'] }}* : {{ p['description_stripped'] }}

{{else}}

*{{ p['type'] }}*

::

    {{ p['example'] }}

{{endif}}

{{endfor}}

.. raw:: html

  <p>&nbsp;</p>
  </details>
