# Milestone: {{ milestone.title }}

**ID**: {{ milestone.id }} | **Number**: {{ milestone.number }} | **State**: `{{ milestone.state }}`

{% if milestone.due_date %}
**Due Date**: {{ milestone.due_date.strftime('%Y-%m-%d') }}
{% endif %}

---

## Description

{{ milestone.description or '*No description provided.*' }}

---

## Issues in this Milestone

{% for issue in issues %}
- #{{ issue.id }}: {{ issue.title }} (`{{ issue.state.value }}`)
{% else %}
*No issues assigned to this milestone.*
{% endfor %}