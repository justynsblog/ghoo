# {{ epic.title }} (#{{ epic.id }})

**Status**: `{{ epic.state.value }}` | **Repository**: `{{ epic.repository }}`

---

## Description

{{ epic.pre_section_description }}

---

## Sections
{% for section in epic.sections %}
### {{ section.title }} ({{ section.completed_todos }}/{{ section.total_todos }} todos)
{{ section.body }}
{% else %}
*No sections defined.*
{% endfor %}

---

## Open Tasks ({{ epic.open_tasks | length }})
{% for task in epic.open_tasks %}
- `{{ task.repository }}`#{{ task.id }}: {{ task.title }}
{% else %}
*No open tasks.*
{% endfor %}

---

## Available Milestones
{% for milestone in available_milestones %}
- **{{ milestone.title }}** (ID: {{ milestone.id }}, Due: {{ milestone.due_date or 'N/A' }})
{% else %}
*No open milestones found.*
{% endfor %}