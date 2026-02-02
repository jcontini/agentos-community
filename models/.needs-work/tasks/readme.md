# Tasks App

Displays tasks, to-dos, issues, and project management items.

## Capabilities

| Capability | Description |
|------------|-------------|
| `task_list` | List tasks with filters |
| `task_get` | Get task details with relationships |
| `task_create` | Create a new task |
| `task_complete` | Mark task as done |
| `task_add_blocker` | Add blocking relationship |
| `task_remove_blocker` | Remove blocking relationship |

---

## Entity Display Names

The capability uses `task` but plugins can specify display names:

| Plugin | Display Name |
|--------|-------------|
| Todoist | Task |
| Linear | Issue |
| GitHub Issues | Issue |
| Jira | Ticket |
| Asana | Task |
| Notion | Task / To-do |

---

## Schemas

### `task_list`

```typescript
// Input
{ 
  filter?: string,
  status?: 'open' | 'in_progress' | 'done' | 'all',
  project_id?: string,
  assignee_id?: string
}

// Output (based on Linear/Todoist schemas)
{
  tasks: {
    id: string                           // required
    source_id?: string                   // e.g. "AGE-123" in Linear
    title: string                        // required
    description?: string
    status: 'open' | 'in_progress' | 'done' | 'cancelled'  // required
    priority?: number                    // 1=urgent, 2=high, 3=medium, 4=low, 0=none
    due?: string                         // date or datetime
    assignee?: {
      id?: string
      name: string
    }
    project?: {
      id: string
      name: string
    }
    parent_id?: string                   // for sub-tasks
    labels?: string[]
    url?: string                         // link to source
  }[]
}
```

### `task_get`

```typescript
// Input
{ id: string }

// Output (full detail with relationships)
{
  id: string                             // required
  source_id?: string
  title: string                          // required
  description?: string
  status: 'open' | 'in_progress' | 'done' | 'cancelled'
  priority?: number                      // 1=urgent, 2=high, 3=medium, 4=low
  due?: string
  assignee?: {
    id?: string
    name: string
  }
  project?: {
    id: string
    name: string
  }
  team?: {                               // Linear-specific
    id: string
    name: string
  }
  parent_id?: string
  children?: string[]                    // sub-task IDs
  blocked_by?: string[]                  // IDs of tasks blocking this one
  blocks?: string[]                      // IDs of tasks this one blocks
  related?: string[]                     // IDs of related tasks
  labels?: string[]
  url?: string
  created_at?: string
  updated_at?: string
}
```

### `task_create`

```typescript
// Input
{ 
  title: string,                         // required
  description?: string,
  due?: string,
  priority?: number,                     // 1=urgent, 2=high, 3=medium, 4=low
  project_id?: string,
  parent_id?: string,                    // create as sub-task
  labels?: string[]
}

// Output
{
  id: string                             // required
  title: string                          // required
  status: 'open'                         // required
  url?: string
}
```

### `task_complete`

```typescript
// Input
{ id: string }

// Output
{
  id: string
  status: 'done'
}
```

### `task_add_blocker`

```typescript
// Input
{ id: string, blocker_id: string }       // blocker_id blocks id

// Output
{ success: boolean }
```

### `task_remove_blocker`

```typescript
// Input
{ id: string, blocker_id: string }

// Output
{ success: boolean }
```

---

## Cross-References

| Field | Links to |
|-------|----------|
| `blocked_by[]` | `task_get(id)` |
| `blocks[]` | `task_get(id)` |
| `assignee.id` | `contact_get(id)` |
| `url` | `web_read(url)` |
| `project` | `collection_get(item_type: 'task')` |

---

## Example Plugins

- **Linear** — Issue tracking for software teams
- **Todoist** — Personal task management
- **GitHub Issues** — Repository issue tracking
- **Jira** — Enterprise project management
- **Asana** — Team task management
