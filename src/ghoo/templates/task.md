# {{ task.title }} (#{{ task.id }})

**Status**: `{{ task.state.value }}` | **Repository**: `{{ task.repository }}` | **Milestone**: `{{ task.milestone.title if task.milestone else 'None' }}`

---

## Description

{{ task.pre_section_description }}

---

## Sections
{% for section in task.sections %}
### {{ section.title }} ({{ section.completed_todos }}/{{ section.total_todos }} todos)
{{ section.body }}
{% else %}
*No sections defined.*
{% endfor %}

---

## Open Sub-tasks ({{ task.open_subtasks | length }})
{% for subtask in task.open_subtasks %}
- `{{ subtask.repository }}`#{{ subtask.id }}: {{ subtask.title }}
{% else %}
*No open sub-tasks.*
{% endfor %}

---

## Comments ({{ task.comments | length }})
{% for comment in task.comments %}
**{{ comment.author }}** on {{ comment.created_at }}:
> {{ comment.body }}
{% endfor %}