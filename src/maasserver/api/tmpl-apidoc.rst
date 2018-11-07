.. raw:: html

  <details>
    <summary>``{{ http_method }} {{ uri }}{{if operation != ""}}?{{ operation }}{{endif}}``</summary>

######################################################################################################

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

* **{{ p['name'] }}** (*{{ p['type'] }}*): {{if p['options']['required'] == "true"}} Required. {{else}} Optional. {{endif}} {{ p['description_stripped'] }}
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
