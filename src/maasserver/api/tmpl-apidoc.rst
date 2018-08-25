``{{ http_method }} {{ uri }}{% if operation != "" %}?op={{ operation }}{% endif %}``
######################################################################################################

{% if warnings != "" %}
THERE ARE PROBLEMS WITH THE DOCSTRING:

{{ warnings }}

{% endif %}


{% if description == "" %}
{{ description_title }}
{% else %}
{{ description }}
{% endif %}

{% if http_method == "POST" or http_method == "PUT" %}

.. raw:: html
  
  <details>
  <summary><b>Using {{ http_method }} methods</b></summary>
  <p>

``{{ http_method }}`` methods require a list of URL-encoded parameters to be passed in the BODY
of the request (e.g. ``name=test-update&description=This+is+a+new+resource+pool+for+updating.``)
and must contain ``Content-Type:'application/x-www-form-urlencoded'`` in the HEADER
in addition to the OAuth authentication headers `as discussed here <https://docs.maas.io/2.4/en/api-authentication>`_.

.. raw:: html

  </p>
  </details>

{% endif %}

{% if params|length > 0 %}

.. raw:: html
  
  <details>
  <summary><b>Parameters</b></summary>

--------------------------
{% endif %}

{% for p in params %}
* **{{ p['name'] }}** (*{{ p['type'] }}*): {{ p['description_stripped'] }}
{% endfor %}

.. raw:: html

  </details>


{% if successes|length > 0 %}

.. raw:: html
  
  <details>
  <summary><b>Success</b></summary>


--------------------------
{% endif %}

{% for p in successes %}

*{{ p['type'] }}*

::

    {{ p['example'] }}

{% endfor %}

.. raw:: html

  </details>

{% if errors|length > 0 %}

.. raw:: html
  
  <details>
  <summary><b>Error</b></summary>

--------------------------
{% endif %}

{% for p in errors %}

*{{ p['type'] }}*

::

    {{ p['example'] }}
    

{% endfor %}

.. raw:: html

  </details>
