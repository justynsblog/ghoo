# {{ subtask.title }} (#{{ subtask.id }})

**Status**: `{{ subtask.state.value }}` | **Repository**: `{{ subtask.repository }}` | **Parent Task**: #{{ subtask.parent_task_id }}

---

## Description

{{ subtask.pre_section_description }}

---

## Sections
{% for section in subtask.sections %}
### {{ section.title }} ({{ section.completed_todos }}/{{ section.total_todos }} todos)
{{ section.body }}
{% else %}
*No sections defined.*
{% endfor %}

---

## Comments ({{ subtask.comments | length }})
{% for comment in subtask.comments %}
**{{ comment.author }}** on {{ comment.created_at }}:
> {{ comment.body }}
{% endfor %}