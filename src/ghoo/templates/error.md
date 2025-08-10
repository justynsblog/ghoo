# ❌ Error: {{ error.title }}

**Command:** `{{ error.command }}`

**Reason:** {{ error.reason }}

{% if error.details %}
---
## Details

{{ error.details }}
{% endif %}

{% if error.valid_options %}
---
## Did you mean one of these?

{% for option in error.valid_options %}
- `{{ option }}`
{% endfor %}
{% endif %}